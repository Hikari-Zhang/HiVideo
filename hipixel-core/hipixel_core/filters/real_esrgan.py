"""
Real-ESRGAN super-resolution filter.

Upscales video frames using the Real-ESRGAN model family.
Supported models:
    - RealESRGAN_x2plus  -- 2x upscale, general content
    - RealESRGAN_x4plus  -- 4x upscale, general content
    - RealESRNet_x4plus  -- 4x upscale, faster (lighter discriminator)

Reference: https://github.com/xinntao/Real-ESRGAN
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, ClassVar

import numpy as np

from hipixel_core._log import get_logger
from hipixel_core.types import VideoFrame

if TYPE_CHECKING:
    from hipixel_core.backends.base import InferenceBackend
    from hipixel_core.types import FilterParams

_log = get_logger("filters.real_esrgan")


#: VRAM budget (MB) per megapixel of input (empirical, x2 model)
_VRAM_MB_PER_MP: float = 512.0

#: Model key used when loading into the backend
_MODEL_KEY_PREFIX = "real_esrgan"


class RealESRGANFilter:
    """Real-ESRGAN super-resolution filter.

    Implements tile-based inference to handle frames larger than VRAM.

    Preset parameters:
        scale (int):         Upscale factor: 2 or 4. Default: 2.
        model (str):         Model name. Default: "RealESRGAN_x2plus".
        tile_size (int):     Tile edge length in pixels. Default: 512.
        tile_padding (int):  Overlap between tiles. Default: 32.
        half_precision (bool): Use FP16 for CUDA. Default: False (Phase 2).
    """

    name: str = "real_esrgan"

    #: Models shipped with hipixel-core
    SUPPORTED_MODELS: ClassVar[list[str]] = [
        "RealESRGAN_x2plus",
        "RealESRGAN_x4plus",
        "RealESRNet_x4plus",
    ]

    def __init__(self) -> None:
        self._model_key: str = ""
        self._scale: int = 2
        self._tile_size: int = 512
        self._tile_padding: int = 32

    # ------------------------------------------------------------------
    # Filter Protocol
    # ------------------------------------------------------------------

    @property
    def required_models(self) -> list[str]:
        return [self._model_key] if self._model_key else ["RealESRGAN_x2plus"]

    def setup(self, backend: InferenceBackend, params: FilterParams) -> None:
        """Load model and store parameters."""
        # Default to x4plus (has working CoreML .mlpackage)
        model_name: str = str(params.get("model", "RealESRGAN_x4plus"))
        
        # Auto-detect scale from model name if not explicitly set
        if "scale" in params:
            self._scale = int(params["scale"])
        else:
            # Infer scale from model name: x2plus → 2, x4plus → 4
            if "x2" in model_name.lower():
                self._scale = 2
            elif "x4" in model_name.lower():
                self._scale = 4
            else:
                self._scale = 4  # safe default
        
        self._tile_padding = int(params.get("tile_padding", 32))
        self._model_key = f"{_MODEL_KEY_PREFIX}_{model_name}"

        # Tile size: explicit param wins; otherwise auto-size from VRAM
        if "tile_size" in params:
            self._tile_size = int(params["tile_size"])
        else:
            self._tile_size = self._auto_tile_size(backend)

        _log.debug(
            "RealESRGANFilter.setup: scale=%d model=%s tile_size=%d tile_padding=%d",
            self._scale, model_name, self._tile_size, self._tile_padding,
        )

        from hipixel_core.models.manager import ModelManager

        model_path = ModelManager.get_model_path(model_name)
        _log.debug("RealESRGANFilter: loading model %s from %s", self._model_key, model_path)
        backend.load_model(model_path, self._model_key)

        _log.warning(
            "Warming up %s for hardware acceleration "
            "(first-run CoreML compilation may take several minutes — cached after first use)",
            model_name,
        )
        # Warmup with the ACTUAL inference shape: every patch is padded to
        # (tile + 2*pad) × (tile + 2*pad) so CoreML only ever sees one shape.
        warmup_size = self._tile_size + 2 * self._tile_padding
        backend.warmup(self._model_key, (1, 3, warmup_size, warmup_size))
        _log.debug("RealESRGANFilter: warmup complete")

    def teardown(self, backend: InferenceBackend) -> None:
        if self._model_key:
            _log.debug("RealESRGANFilter.teardown: unloading %s", self._model_key)
            backend.unload_model(self._model_key)

    def process_frame(
        self,
        frame: VideoFrame,
        backend: InferenceBackend,
        params: FilterParams,
    ) -> VideoFrame:
        """Upscale a single frame via tiled Real-ESRGAN inference."""
        f32 = frame.to_float32()
        output_data = self._tile_infer(f32.data, backend)
        return VideoFrame(
            data=output_data,
            pts=frame.pts,
            width=output_data.shape[1],
            height=output_data.shape[0],
            colorspace=frame.colorspace,
            is_hdr=frame.is_hdr,
            hdr_metadata=frame.hdr_metadata,
        )

    def estimated_vram_mb(self, input_resolution: tuple[int, int]) -> int:
        w, h = input_resolution
        mp = (w * h) / 1_000_000
        return math.ceil(mp * _VRAM_MB_PER_MP)

    def _auto_tile_size(self, backend: InferenceBackend) -> int:
        """Compute a safe tile size from the backend's available VRAM.

        When VRAM is unknown (CPU backend, ``available_vram_mb() == 0``),
        returns a conservative CPU-safe default (256 pixels).

        The budget formula accounts for:
        - Input tile  : tile² × 3 × 4 bytes (float32 NCHW)
        - Output tile : (tile × scale)² × 3 × 4 bytes
        - Activations : ~4× working overhead inside the model
        - Safety margin: 50% of available VRAM

        The resulting tile size is clamped to [64, 1024] and rounded
        down to the nearest 64-pixel boundary.
        """
        vram_mb = backend.available_vram_mb()
        if vram_mb <= 0:
            return 256  # CPU-safe default

        # bytes available for one tile pass (50% safety margin)
        available_bytes = vram_mb * 1024 * 1024 * 0.5

        # bytes per input pixel (input + scaled output + 4× activation overhead)
        scale = self._scale
        bytes_per_input_px = (
            3 * 4  # input: float32 NCHW
            + scale * scale * 3 * 4  # output
        ) * 4.0  # activation overhead factor

        max_pixels = int(available_bytes / bytes_per_input_px)
        size = int(math.isqrt(max_pixels))

        # Round down to nearest 64, clamp to [64, 512]
        # 512 → 576 px with default padding=32, which stays within the range
        # that CoreML's NeuralNetwork EP can reliably dispatch to ANE/GPU.
        # Tiles larger than ~600 px risk silent CPU fallback.
        size = max(64, min(512, (size // 64) * 64))
        return size

    # ------------------------------------------------------------------
    # Tile inference
    # ------------------------------------------------------------------

    def _tile_infer(
        self,
        img: np.ndarray,
        backend: InferenceBackend,
    ) -> np.ndarray:
        """Split ``img`` into tiles, run inference, stitch results.

        Every patch is zero-padded to exactly ``(tile + 2*pad) × (tile + 2*pad)``
        before inference so CoreML always sees the same input shape (matching the
        warmup shape).  The corresponding output region is cropped back to the
        actual tile size before accumulation.
        """
        import time as _time

        h, w = img.shape[:2]
        tile = self._tile_size
        pad = self._tile_padding
        scale = self._scale
        target = tile + 2 * pad  # fixed inference shape on each side

        out_h, out_w = h * scale, w * scale
        output = np.zeros((out_h, out_w, 3), dtype=np.float32)
        weight = np.zeros((out_h, out_w, 1), dtype=np.float32)

        tile_idx = 0
        for y in range(0, h, tile):
            for x in range(0, w, tile):
                # Padded tile bounds (clamped to image)
                x1 = max(0, x - pad)
                y1 = max(0, y - pad)
                x2 = min(w, x + tile + pad)
                y2 = min(h, y + tile + pad)

                patch = img[y1:y2, x1:x2]  # (actual_ph, actual_pw, 3)
                actual_ph, actual_pw = patch.shape[:2]

                # Pad to fixed target shape so CoreML never sees a new input shape
                if actual_ph < target or actual_pw < target:
                    patch = np.pad(
                        patch,
                        ((0, target - actual_ph), (0, target - actual_pw), (0, 0)),
                        mode="reflect",
                    )

                patch_t = np.ascontiguousarray(np.transpose(patch, (2, 0, 1))[np.newaxis])  # NCHW

                t0 = _time.monotonic()
                result = backend.run({"input": patch_t}, self._model_key)
                elapsed_ms = (_time.monotonic() - t0) * 1000
                # Log the first 3 tiles at WARNING so they appear without --verbose.
                # After 3 tiles the pattern is established; subsequent tiles use DEBUG.
                if tile_idx < 3:
                    _log.warning(
                        "_tile_infer: tile %d (%dx%d patch → %dx%d target) — %.0f ms",
                        tile_idx, actual_ph, actual_pw, target, target, elapsed_ms,
                    )
                else:
                    _log.debug(
                        "_tile_infer: tile %d — %.0f ms", tile_idx, elapsed_ms,
                    )
                tile_idx += 1

                out_patch = result.get("output", next(iter(result.values())))
                # out_patch: (1, 3, target*scale, target*scale)
                out_patch = np.transpose(out_patch[0], (1, 2, 0))  # HWC

                # Crop to the valid (non-padded) output region
                valid_out_ph = actual_ph * scale
                valid_out_pw = actual_pw * scale
                out_patch = out_patch[:valid_out_ph, :valid_out_pw]

                # Target slice in output (exclude padding contribution)
                ox1 = x1 * scale
                oy1 = y1 * scale
                ox2 = x2 * scale
                oy2 = y2 * scale

                output[oy1:oy2, ox1:ox2] += out_patch
                weight[oy1:oy2, ox1:ox2] += 1.0

        # Normalize overlapping regions — all in-place to avoid extra copies
        np.maximum(weight, 1.0, out=weight)
        output /= weight
        np.clip(output, 0.0, 1.0, out=output)
        return output

    def __repr__(self) -> str:
        return (
            f"RealESRGANFilter(scale={self._scale}, "
            f"tile_size={self._tile_size}, model_key={self._model_key!r})"
        )
