"""
Video decoder — wraps FFmpeg to produce VideoFrame sequences.

Uses ``ffmpeg-python`` (a Python binding to the FFmpeg CLI) to decode
any video file into a stream of raw RGB frames.

Phase 2.5: This will be replaced by a Rust decoder using
``ffmpeg-sys-next`` bindings for zero-copy frame delivery.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

import numpy as np

from hipixel_core.types import ColorSpace, VideoFrame, VideoMeta


def probe(path: str) -> VideoMeta:
    """Extract metadata from a video file using ffprobe.

    Args:
        path:  Absolute or relative path to the video file.

    Returns:
        :class:`VideoMeta` populated with stream information.

    Raises:
        ``FileNotFoundError`` if the path does not exist.
        ``ValueError`` if no video stream is found.
    """
    if not Path(path).exists():
        raise FileNotFoundError(f"Video file not found: {path}")

    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info: dict[str, Any] = json.loads(result.stdout)

    # Find the first video stream
    video_stream: dict[str, Any] | None = None
    audio_streams: list[dict[str, Any]] = []
    for stream in info.get("streams", []):
        if stream.get("codec_type") == "video" and video_stream is None:
            video_stream = stream
        elif stream.get("codec_type") == "audio":
            audio_streams.append(stream)

    if video_stream is None:
        raise ValueError(f"No video stream found in: {path}")

    fmt = info.get("format", {})
    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))

    # Parse FPS from r_frame_rate (e.g. "24/1" or "30000/1001")
    fps_str: str = video_stream.get("r_frame_rate", "25/1")
    fps = _parse_fps(fps_str)

    # Estimate frame count
    nb_frames_str: str = video_stream.get("nb_frames", "0")
    if nb_frames_str.isdigit() and int(nb_frames_str) > 0:
        frame_count = int(nb_frames_str)
    else:
        duration_s = float(fmt.get("duration", 0.0) or video_stream.get("duration", 0.0))
        frame_count = max(1, int(duration_s * fps))

    duration_s = float(fmt.get("duration", 0.0) or video_stream.get("duration", 0.0))

    return VideoMeta(
        path=path,
        width=width,
        height=height,
        fps=fps,
        frame_count=frame_count,
        duration_s=duration_s,
        codec=video_stream.get("codec_name", "unknown"),
        pixel_format=video_stream.get("pix_fmt", "yuv420p"),
        colorspace=_detect_colorspace(video_stream),
        is_hdr=_detect_hdr(video_stream),
        audio_streams=audio_streams,
        container=fmt.get("format_name", "mp4").split(",")[0],
        bit_rate=int(fmt.get("bit_rate", 0) or 0),
    )


def decode_frames(meta: VideoMeta) -> Iterator[VideoFrame]:
    """Decode all frames from a video file as an iterator of VideoFrames.

    Frames are delivered in presentation order as ``float32`` [0, 1] RGB.

    Args:
        meta:  VideoMeta from :func:`probe`.

    Yields:
        :class:`VideoFrame` instances.
    """
    import ffmpeg

    stream = (
        ffmpeg.input(meta.path)
        .output("pipe:", format="rawvideo", pix_fmt="rgb24")
        .global_args("-loglevel", "error")
    )
    process = stream.run_async(pipe_stdout=True)

    frame_size = meta.width * meta.height * 3  # RGB bytes
    frame_index = 0

    try:
        while True:
            raw = process.stdout.read(frame_size)
            if len(raw) < frame_size:
                break
            arr = np.frombuffer(raw, dtype=np.uint8).reshape((meta.height, meta.width, 3))
            pts = frame_index / meta.fps
            frame_data = arr.copy()
            del raw, arr  # free the bytes buffer before generator suspension
            yield VideoFrame(
                data=frame_data,
                pts=pts,
                width=meta.width,
                height=meta.height,
                colorspace=meta.colorspace,
                is_hdr=meta.is_hdr,
            )
            frame_index += 1
    finally:
        process.stdout.close()
        process.wait()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_fps(fps_str: str) -> float:
    """Parse FFprobe fraction string to float (e.g. '30000/1001' → 29.97)."""
    if "/" in fps_str:
        num, den = fps_str.split("/")
        den_i = int(den)
        return float(num) / den_i if den_i > 0 else 25.0
    return float(fps_str)


def _detect_colorspace(stream: dict[str, Any]) -> ColorSpace:
    cs = stream.get("color_space", "") or ""
    if "bt2020" in cs.lower():
        return ColorSpace.BT2020
    if "bt601" in cs.lower() or "smpte170m" in cs.lower():
        return ColorSpace.BT601
    return ColorSpace.BT709


def _detect_hdr(stream: dict[str, Any]) -> bool:
    transfer = stream.get("color_transfer", "") or ""
    return transfer.lower() in {"smpte2084", "arib-std-b67", "bt2020-10", "bt2020-12"}
