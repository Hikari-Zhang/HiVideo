"""
CAS (Contrast Adaptive Sharpening) filter.

A fast, GPU-shader-style sharpening filter based on AMD FidelityFX CAS.
Implemented here as a pure NumPy/SciPy operation (no neural network).
Acts as a lightweight post-sharpening step after super-resolution.

Reference: https://gpuopen.com/fidelityfx-cas/
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from hipixel_core._log import get_logger
from hipixel_core.types import VideoFrame

if TYPE_CHECKING:
    from hipixel_core.backends.base import InferenceBackend
    from hipixel_core.types import FilterParams

_log = get_logger("filters.cas")


class CASFilter:
    """Contrast Adaptive Sharpening filter.

    This filter does NOT use a neural network.  It is a CPU-side
    image processing operation.  ``required_models`` is empty.

    Preset parameters:
        sharpness (float):  Sharpening strength [0.0, 1.0]. Default: 0.5.
                            0.0 = no sharpening, 1.0 = maximum sharpening.
    """

    name: str = "cas"

    def __init__(self) -> None:
        self._sharpness: float = 0.5

    @property
    def required_models(self) -> list[str]:
        return []  # CPU-only, no model needed

    def setup(self, backend: InferenceBackend, params: FilterParams) -> None:
        self._sharpness = float(params.get("sharpness", 0.5))
        _log.debug("CASFilter.setup: sharpness=%.2f", self._sharpness)

    def teardown(self, backend: InferenceBackend) -> None:
        _log.debug("CASFilter.teardown")

    def process_frame(
        self,
        frame: VideoFrame,
        backend: InferenceBackend,
        params: FilterParams,
    ) -> VideoFrame:
        """Apply CAS sharpening using an unsharp-mask approximation."""
        sharpness = float(params.get("sharpness", self._sharpness))
        f32 = frame.to_float32()
        sharpened = self._cas_sharpen(f32.data, sharpness)
        return VideoFrame(
            data=sharpened,
            pts=frame.pts,
            width=frame.width,
            height=frame.height,
            colorspace=frame.colorspace,
            is_hdr=frame.is_hdr,
            hdr_metadata=frame.hdr_metadata,
        )

    def estimated_vram_mb(self, input_resolution: tuple[int, int]) -> int:
        return 0  # CPU-only

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _cas_sharpen(img: np.ndarray, sharpness: float) -> np.ndarray:
        """Simplified CAS: unsharp masking with contrast-adaptive gain.

        Full GPU CAS uses per-pixel min/max neighborhood analysis.
        This NumPy version uses a Laplacian kernel for sharpness details.
        """
        from scipy.ndimage import uniform_filter

        # Low-frequency component
        blurred: np.ndarray = np.asarray(uniform_filter(img, size=3, mode="reflect"))
        # High-frequency (detail) component
        detail = img - blurred
        # Adaptive gain: stronger sharpening where contrast is low
        gain = sharpness * (1.0 + (1.0 - np.std(img, axis=(0, 1), keepdims=True)))
        sharpened = img + gain * detail
        clipped: np.ndarray = np.asarray(np.clip(sharpened, 0.0, 1.0))
        return clipped.astype(np.float32)

    def __repr__(self) -> str:
        return f"CASFilter(sharpness={self._sharpness})"
