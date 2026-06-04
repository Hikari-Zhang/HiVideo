"""
NAFNet denoising filter.

NAFNet (Nonlinear Activation Free Network) is a state-of-the-art image
restoration network.  We use the REDS-trained variant for video denoising.

Reference: https://github.com/megvii-research/NAFNet
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from hipixel_core._log import get_logger
from hipixel_core.types import VideoFrame

if TYPE_CHECKING:
    from hipixel_core.backends.base import InferenceBackend
    from hipixel_core.types import FilterParams

_log = get_logger("filters.nafnet")


class NAFNetFilter:
    """NAFNet video denoising filter.

    Preset parameters:
        strength (float):  Blend factor between input and denoised output
                           [0.0, 1.0]. 1.0 = fully denoised. Default: 0.8.
        model (str):       Model variant. Default: "NAFNet-REDS-width64".
        tile_size (int):   Tile size for large frames. Default: 256.
    """

    name: str = "nafnet"

    def __init__(self) -> None:
        self._model_key: str = ""
        self._strength: float = 0.8
        self._tile_size: int = 256

    @property
    def required_models(self) -> list[str]:
        return [self._model_key] if self._model_key else ["NAFNet-REDS-width64"]

    def setup(self, backend: InferenceBackend, params: FilterParams) -> None:
        self._strength = float(params.get("strength", 0.8))
        model_name: str = str(params.get("model", "NAFNet-REDS-width64"))
        self._tile_size = int(params.get("tile_size", 256))
        self._model_key = f"nafnet_{model_name}"

        _log.debug(
            "NAFNetFilter.setup: strength=%.2f model=%s tile_size=%d",
            self._strength, model_name, self._tile_size,
        )

        from hipixel_core.models.manager import ModelManager

        model_path = ModelManager.get_model_path(model_name)
        _log.debug("NAFNetFilter: loading model %s from %s", self._model_key, model_path)
        backend.load_model(model_path, self._model_key)

        _log.warning(
            "Warming up %s for hardware acceleration "
            "(first-run CoreML compilation may take several minutes — cached after first use)",
            model_name,
        )
        backend.warmup(self._model_key, (1, 3, self._tile_size, self._tile_size))
        _log.debug("NAFNetFilter: warmup complete")

    def teardown(self, backend: InferenceBackend) -> None:
        if self._model_key:
            _log.debug("NAFNetFilter.teardown: unloading %s", self._model_key)
            backend.unload_model(self._model_key)

    def process_frame(
        self,
        frame: VideoFrame,
        backend: InferenceBackend,
        params: FilterParams,
    ) -> VideoFrame:
        f32 = frame.to_float32()
        denoised = self._tile_infer(f32.data, backend)

        # In-place blend: denoised = original + strength * (denoised - original)
        # Avoids creating a separate blended array.
        strength = float(params.get("strength", self._strength))
        denoised -= f32.data
        denoised *= strength
        denoised += f32.data
        np.clip(denoised, 0.0, 1.0, out=denoised)

        return VideoFrame(
            data=denoised,
            pts=frame.pts,
            width=frame.width,
            height=frame.height,
            colorspace=frame.colorspace,
            is_hdr=frame.is_hdr,
            hdr_metadata=frame.hdr_metadata,
        )

    def _tile_infer(
        self,
        img: np.ndarray,
        backend: InferenceBackend,
    ) -> np.ndarray:
        """Run NAFNet on ``img`` tile-by-tile to keep memory bounded.

        Edge tiles that are smaller than ``tile_size`` are padded with
        reflect-padding to the required size, then the valid region is
        cropped from the output.
        """
        h, w = img.shape[:2]
        tile = self._tile_size
        output = np.empty((h, w, 3), dtype=np.float32)

        for y in range(0, h, tile):
            for x in range(0, w, tile):
                y2 = min(h, y + tile)
                x2 = min(w, x + tile)
                patch = img[y:y2, x:x2]
                ph, pw = patch.shape[:2]

                # Pad edge tiles to exactly tile_size (NAFNet UNet stride
                # requires height and width divisible by 32 at minimum).
                if ph < tile or pw < tile:
                    patch = np.pad(
                        patch,
                        ((0, tile - ph), (0, tile - pw), (0, 0)),
                        mode="reflect",
                    )

                inp = np.ascontiguousarray(np.transpose(patch, (2, 0, 1))[np.newaxis])
                result = backend.run({"input": inp}, self._model_key)
                out = np.transpose(next(iter(result.values()))[0], (1, 2, 0))
                # Crop back to valid region for edge tiles
                output[y:y2, x:x2] = out[:ph, :pw]

        return output

    def estimated_vram_mb(self, input_resolution: tuple[int, int]) -> int:
        w, h = input_resolution
        mp = w * h / 1_000_000
        return int(mp * 192)

    def __repr__(self) -> str:
        return f"NAFNetFilter(strength={self._strength}, model_key={self._model_key!r})"
