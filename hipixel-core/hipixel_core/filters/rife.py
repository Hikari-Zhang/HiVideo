"""
RIFE frame interpolation filter (stub — Phase 1).

RIFE (Real-Time Intermediate Flow Estimation) doubles the frame rate
by generating intermediate frames between existing ones.

This is a Phase 1 filter.  The current implementation raises
``NotImplementedError`` to signal it is not yet ready for use.

Reference: https://github.com/hzwer/ECCV2022-RIFE
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hipixel_core.backends.base import InferenceBackend
    from hipixel_core.types import FilterParams, VideoFrame


class RIFEFilter:
    """RIFE temporal frame interpolation (Phase 1 stub).

    Preset parameters:
        multiplier (int):  FPS multiplier: 2 or 4. Default: 2.
        model (str):       RIFE model variant. Default: "RIFE_v4.6".
    """

    name: str = "rife"

    def __init__(self) -> None:
        self._model_key: str = ""

    @property
    def required_models(self) -> list[str]:
        return ["RIFE_v4.6"]

    def setup(self, backend: InferenceBackend, params: FilterParams) -> None:
        raise NotImplementedError(
            "RIFE frame interpolation is scheduled for Phase 1. "
            "It is not yet implemented in this release."
        )

    def teardown(self, backend: InferenceBackend) -> None:
        pass

    def process_frame(
        self,
        frame: VideoFrame,
        backend: InferenceBackend,
        params: FilterParams,
    ) -> VideoFrame:
        raise NotImplementedError("RIFE is not yet implemented (Phase 1).")

    def estimated_vram_mb(self, input_resolution: tuple[int, int]) -> int:
        w, h = input_resolution
        return int(w * h / 1_000_000 * 768)  # estimate

    def __repr__(self) -> str:
        return "RIFEFilter(status='Phase 1 stub')"
