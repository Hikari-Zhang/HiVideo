"""
Core data models shared across all hipixel-core layers.

These are the fundamental value types that flow between
Video I/O, Filter, Pipeline, and Backend layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import numpy as np

# ---------------------------------------------------------------------------
# Color space
# ---------------------------------------------------------------------------


class ColorSpace(Enum):
    """Frame color space.  All internal processing happens in BT.709."""

    BT601 = auto()  # SD - NTSC/PAL
    BT709 = auto()  # HD - standard for most content
    BT2020 = auto()  # UHD / HDR wide gamut
    SRGB = auto()  # Web / display-referred
    LINEAR = auto()  # Linear light (for HDR math)


# ---------------------------------------------------------------------------
# Video frame
# ---------------------------------------------------------------------------


@dataclass
class VideoFrame:
    """Single decoded video frame passed through the filter pipeline.

    ``data`` is always a NumPy array in shape ``(H, W, 3)``, dtype ``uint8``
    or ``float32`` (float32 is normalized to [0, 1]).

    Filters must not mutate ``data`` in-place; they return a *new*
    ``VideoFrame`` with a fresh array.
    """

    data: np.ndarray  # (H, W, 3), uint8 or float32
    pts: float  # Presentation timestamp in seconds
    width: int
    height: int
    colorspace: ColorSpace = ColorSpace.BT709
    is_hdr: bool = False
    hdr_metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.data.ndim != 3 or self.data.shape[2] != 3:
            raise ValueError(f"VideoFrame.data must be (H, W, 3), got {self.data.shape}")
        if self.data.shape[0] != self.height or self.data.shape[1] != self.width:
            raise ValueError(
                f"VideoFrame dimensions mismatch: data={self.data.shape}, "
                f"declared=({self.height}, {self.width})"
            )

    @property
    def resolution(self) -> tuple[int, int]:
        """Returns (width, height)."""
        return self.width, self.height

    def to_float32(self) -> VideoFrame:
        """Return a copy with data normalized to float32 [0, 1]."""
        if self.data.dtype == np.float32:
            return self
        return VideoFrame(
            data=self.data.astype(np.float32) / 255.0,
            pts=self.pts,
            width=self.width,
            height=self.height,
            colorspace=self.colorspace,
            is_hdr=self.is_hdr,
            hdr_metadata=self.hdr_metadata,
        )

    def to_uint8(self) -> VideoFrame:
        """Return a copy with data as uint8 [0, 255]."""
        if self.data.dtype == np.uint8:
            return self
        clipped = np.clip(self.data * 255.0, 0, 255)
        return VideoFrame(
            data=clipped.astype(np.uint8),
            pts=self.pts,
            width=self.width,
            height=self.height,
            colorspace=self.colorspace,
            is_hdr=self.is_hdr,
            hdr_metadata=self.hdr_metadata,
        )


# ---------------------------------------------------------------------------
# Video metadata
# ---------------------------------------------------------------------------


@dataclass
class VideoMeta:
    """Metadata extracted from an input video file."""

    path: str
    width: int
    height: int
    fps: float
    frame_count: int
    duration_s: float
    codec: str
    pixel_format: str
    colorspace: ColorSpace = ColorSpace.BT709
    is_hdr: bool = False
    audio_streams: list[dict[str, Any]] = field(default_factory=list)
    container: str = "mp4"
    bit_rate: int = 0  # bits per second; 0 = unknown

    @property
    def resolution(self) -> tuple[int, int]:
        return self.width, self.height


# ---------------------------------------------------------------------------
# Device / backend info
# ---------------------------------------------------------------------------


@dataclass
class DeviceInfo:
    """Hardware descriptor for the active inference backend."""

    backend_name: str  # e.g. "coreml", "cuda", "cpu"
    device_name: str  # human-readable GPU/CPU name
    total_vram_mb: int  # 0 for CPU
    available_vram_mb: int  # 0 for CPU
    platform: str  # "darwin", "linux", "windows"
    compute_capability: str | None = None  # CUDA: e.g. "8.6"; None otherwise
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def has_gpu(self) -> bool:
        return self.total_vram_mb > 0


# ---------------------------------------------------------------------------
# Output specification
# ---------------------------------------------------------------------------


@dataclass
class OutputSpec:
    """Describes the desired output video encoding."""

    path: str
    codec: str = "h265"  # h264 | h265 | av1 | prores
    crf: int = 18  # Constant Rate Factor (lower = better)
    container: str = "mp4"  # mp4 | mkv | mov
    fps: float | None = None  # None = preserve source FPS
    resolution: str = "source"  # "source" | "2x" | "4x" | "WxH"
    audio_copy: bool = True  # Passthrough source audio

    def resolved_fps(self, source_fps: float) -> float:
        return source_fps if self.fps is None else self.fps


# ---------------------------------------------------------------------------
# Progress events
# ---------------------------------------------------------------------------


@dataclass
class ProgressEvent:
    """Emitted by the pipeline at regular intervals during processing."""

    frame_index: int
    total_frames: int
    elapsed_s: float
    fps_current: float  # instantaneous frames/sec
    fps_avg: float  # average frames/sec since start
    stage: str = "process"  # "decode" | "process" | "encode"

    @property
    def progress_pct(self) -> float:
        if self.total_frames <= 0:
            return 0.0
        return min(100.0, self.frame_index / self.total_frames * 100.0)

    @property
    def eta_s(self) -> float:
        if self.fps_avg <= 0:
            return float("inf")
        remaining = self.total_frames - self.frame_index
        return remaining / self.fps_avg


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    """Returned by Pipeline.run() after processing completes."""

    success: bool
    output_path: str
    frames_processed: int
    elapsed_s: float
    avg_fps: float
    backend_used: str
    error: str | None = None  # set if success is False

    @property
    def speedup_over_realtime(self) -> float:
        """Ratio of source duration to processing time; >1 = faster than RT."""
        return float("inf") if self.elapsed_s <= 0 else self.frames_processed / self.elapsed_s


# ---------------------------------------------------------------------------
# Filter parameters (open-ended mapping)
# ---------------------------------------------------------------------------

#: Generic parameter dict passed to Filter.setup() and Filter.process_frame().
FilterParams = dict[str, Any]
