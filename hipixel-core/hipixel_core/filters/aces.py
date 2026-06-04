"""
ACES tone-mapping filter — HDR scene-linear → SDR display.

Converts high-dynamic-range, scene-linear input to an SDR signal suitable
for standard (BT.1886 / sRGB) displays using either the Narkowicz 2016
ACES fitted curve or a simple Reinhard operator.

References:
    Narkowicz 2016 — "ACES Filmic Tone Mapping Curve"
    https://knarkowicz.wordpress.com/2016/01/06/aces-filmic-tone-mapping-curve/

    Reinhard et al. 2002 — "Photographic Tone Reproduction for Digital Images"

    IEC 61966-2-1 — sRGB gamma transfer function
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from hipixel_core._log import get_logger
from hipixel_core.types import ColorSpace, VideoFrame

if TYPE_CHECKING:
    from hipixel_core.backends.base import InferenceBackend
    from hipixel_core.types import FilterParams

_log = get_logger("filters.aces")


class ACESToneMappingFilter:
    """HDR→SDR tone-mapping filter (no neural model, CPU/GPU agnostic).

    Applies one of two tonemapping curves to scene-linear input, then
    optionally applies the sRGB transfer function (gamma encode).

    The output frame is always tagged ``is_hdr=False`` with
    ``colorspace=ColorSpace.SRGB``.

    Preset parameters:
        exposure (float):  Linear multiplier applied before the curve.
                           Values > 1 brighten; < 1 darken.  Default: 1.0.
        method (str):      Curve to apply.
                           ``"aces_fitted"`` (default) — Narkowicz 2016.
                           ``"reinhard"`` — simple Reinhard operator.
        gamma (str):       Output transfer function.
                           ``"srgb"`` (default) — IEC 61966-2-1 piecewise.
                           ``"linear"`` — no gamma encoding (leave linear).
    """

    name: str = "aces"

    def __init__(self) -> None:
        self._exposure: float = 1.0
        self._method: str = "aces_fitted"
        self._gamma: str = "srgb"

    # ------------------------------------------------------------------
    # Filter Protocol
    # ------------------------------------------------------------------

    @property
    def required_models(self) -> list[str]:
        return []

    def setup(self, backend: InferenceBackend, params: FilterParams) -> None:
        """Store parameters; no model loading required."""
        self._exposure = float(params.get("exposure", 1.0))
        self._method = str(params.get("method", "aces_fitted"))
        self._gamma = str(params.get("gamma", "srgb"))
        _log.debug(
            "ACESToneMappingFilter.setup: exposure=%.2f method=%s gamma=%s",
            self._exposure, self._method, self._gamma,
        )

    def teardown(self, backend: InferenceBackend) -> None:  # noqa: ARG002
        _log.debug("ACESToneMappingFilter.teardown")

    def process_frame(
        self,
        frame: VideoFrame,
        backend: InferenceBackend,  # noqa: ARG002
        params: FilterParams,
    ) -> VideoFrame:
        """Apply tone-mapping to a single frame.

        Per-frame ``params`` override any values stored in ``setup`` so
        the caller can vary exposure dynamically without re-calling setup.
        """
        exposure = float(params.get("exposure", self._exposure))
        method = str(params.get("method", self._method))
        gamma = str(params.get("gamma", self._gamma))

        f32 = frame.to_float32()
        img = f32.data * exposure  # scene-linear, possibly > 1

        if method == "reinhard":
            img = self._reinhard(img)
        else:
            img = self._aces_fitted(img)

        if gamma == "srgb":
            img = self._srgb_gamma(img)

        return VideoFrame(
            data=np.clip(img, 0.0, 1.0).astype(np.float32),
            pts=frame.pts,
            width=frame.width,
            height=frame.height,
            colorspace=ColorSpace.SRGB,
            is_hdr=False,
            hdr_metadata=None,
        )

    def estimated_vram_mb(self, input_resolution: tuple[int, int]) -> int:  # noqa: ARG002
        return 0

    # ------------------------------------------------------------------
    # Tone-mapping curves (static — no state dependency)
    # ------------------------------------------------------------------

    @staticmethod
    def _aces_fitted(x: np.ndarray) -> np.ndarray:
        """Narkowicz 2016 ACES fitted curve.

        Maps scene-linear ``[0, ∞)`` → display-linear ``[0, 1]``.
        Approximates the full ACES RRT + ODT chain with a rational polynomial.

        Formula::

            out = x*(2.51*x + 0.03) / (x*(2.43*x + 0.59) + 0.14)
        """
        return np.clip(
            x * (2.51 * x + 0.03) / (x * (2.43 * x + 0.59) + 0.14),
            0.0,
            1.0,
        )

    @staticmethod
    def _reinhard(x: np.ndarray) -> np.ndarray:
        """Simple Reinhard global operator.

        Maps ``[0, ∞)`` → ``[0, 1)`` monotonically::

            out = x / (1 + x)
        """
        return x / (1.0 + x)

    @staticmethod
    def _srgb_gamma(x: np.ndarray) -> np.ndarray:
        """IEC 61966-2-1 sRGB transfer function (display-linear → sRGB).

        Piecewise::

            out = 12.92 * x                            if x ≤ 0.0031308
            out = 1.055 * x^(1/2.4) − 0.055           otherwise
        """
        return np.where(
            x <= 0.0031308,
            12.92 * x,
            1.055 * np.power(np.maximum(x, 1e-12), 1.0 / 2.4) - 0.055,
        )

    def __repr__(self) -> str:
        return (
            f"ACESToneMappingFilter(exposure={self._exposure}, "
            f"method={self._method!r}, gamma={self._gamma!r})"
        )
