"""
Anime4K v4 super-resolution filter — optimized for anime content.

Upscales video frames using the Anime4K v4 ONNX model with tile-based inference
for efficient handling of large frames.

Produces sharper edges and better color preservation than Real-ESRGAN
on cel-shaded / anime-style content.

Reference: https://github.com/bloc97/Anime4K
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, ClassVar

import numpy as np

from hipixel_core.types import VideoFrame

if TYPE_CHECKING:
    from hipixel_core.backends.base import InferenceBackend
    from hipixel_core.types import FilterParams


#: VRAM budget (MB) per megapixel of input (empirical, lighter than Real-ESRGAN)
_VRAM_MB_PER_MP: float = 256.0

#: Model key used when loading into the backend
_MODEL_KEY_PREFIX = "anime4k"


class Anime4KFilter:
    """Anime4K v4 upscaling filter with tile-based inference.

    Implements tile-based inference to handle frames larger than VRAM
    without memory pressure.

    Preset parameters:
        scale (int):         Upscale factor: 2 or 4. Default: 2.
        model (str):         Model variant. Default: "Anime4K_v4_Upscale_Denoise_x2".
        tile_size (int):     Tile edge length in pixels. Default: 512.
        tile_padding (int):  Overlap between tiles. Default: 16.
    """

    name: str = "anime4k"

    #: Models shipped with hipixel-core
    SUPPORTED_MODELS: ClassVar[list[str]] = [
        "Anime4K_v4_Upscale_Denoise_x2",
    ]

    def __init__(self) -> None:
        self._model_key: str = ""
        self._scale: int = 2
        self._tile_size: int = 512
        self._tile_padding: int = 16

    # ------------------------------------------------------------------
    # Filter Protocol
    # ------------------------------------------------------------------

    @property
    def required_models(self) -> list[str]:
        return [self._model_key] if self._model_key else ["Anime4K_v4_Upscale_Denoise_x2"]

    def setup(self, backend: InferenceBackend, params: FilterParams) -> None:
        """Load model and store parameters."""
        self._scale = int(params.get("scale", 2))
        model_name: str = str(params.get("model", "Anime4K_v4_Upscale_Denoise_x2"))
        self._tile_padding = int(params.get("tile_padding", 16))
        self._model_key = f"{_MODEL_KEY_PREFIX}_{model_name}"

        # Tile size: explicit param wins; otherwise auto-size from VRAM
        if "tile_size" in params:
            self._tile_size = int(params["tile_size"])
        else:
            self._tile_size = self._auto_tile_size(backend)

        from hipixel_core.models.manager import ModelManager

        model_path = ModelManager.get_model_path(model_name)
        backend.load_model(model_path, self._model_key)

    def teardown(self, backend: InferenceBackend) -> None:
        if self._model_key:
            backend.unload_model(self._model_key)

    def process_frame(
        self,
        frame: VideoFrame,
        backend: InferenceBackend,
        params: FilterParams,
    ) -> VideoFrame:
        """Upscale a single frame via tiled Anime4K inference."""
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

        # Round down to nearest 64, clamp to [64, 1024]
        size = max(64, min(1024, (size // 64) * 64))
        return size

    # ------------------------------------------------------------------
    # Tile inference
    # ------------------------------------------------------------------

    def _tile_infer(
        self,
        img: np.ndarray,
        backend: InferenceBackend,
    ) -> np.ndarray:
        """Split ``img`` into tiles, run inference, stitch results."""
        h, w = img.shape[:2]
        tile = self._tile_size
        pad = self._tile_padding
        scale = self._scale

        out_h, out_w = h * scale, w * scale
        output = np.zeros((out_h, out_w, 3), dtype=np.float32)
        weight = np.zeros((out_h, out_w, 1), dtype=np.float32)

        for y in range(0, h, tile):
            for x in range(0, w, tile):
                # Padded tile bounds (clamped to image)
                x1 = max(0, x - pad)
                y1 = max(0, y - pad)
                x2 = min(w, x + tile + pad)
                y2 = min(h, y + tile + pad)

                patch = img[y1:y2, x1:x2]  # (ph, pw, 3)
                patch_t = np.transpose(patch, (2, 0, 1))[np.newaxis]  # NCHW

                result = backend.run({"input": patch_t}, self._model_key)
                out_patch = result.get("output", next(iter(result.values())))
                # out_patch: (1, 3, ph*scale, pw*scale)
                out_patch = np.transpose(out_patch[0], (1, 2, 0))  # HWC

                # Target slice in output (exclude padding contribution)
                ox1 = x1 * scale
                oy1 = y1 * scale
                ox2 = x2 * scale
                oy2 = y2 * scale

                output[oy1:oy2, ox1:ox2] += out_patch
                weight[oy1:oy2, ox1:ox2] += 1.0

        # Normalize overlapping regions
        output = output / np.maximum(weight, 1.0)
        return np.clip(output, 0.0, 1.0).astype(np.float32)

    def __repr__(self) -> str:
        return (
            f"Anime4KFilter(scale={self._scale}, "
            f"tile_size={self._tile_size}, model_key={self._model_key!r})"
        )
