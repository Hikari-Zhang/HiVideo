"""
Synthetic frame and video-meta generators for benchmark and testing.

These produce deterministic, reproducible inputs that require no real video
files — suitable for CI and headless benchmark runs.

Patterns
--------
``noise``       : uniform random noise (stresses all filter paths)
``gradient``    : horizontal luminance ramp (smooth, low noise)
``solid_gray``  : flat mid-gray (minimal work per pixel)
``checkerboard``: alternating black/white 8×8 squares
"""

from __future__ import annotations

import numpy as np

from hipixel_core.types import ColorSpace, VideoFrame, VideoMeta


def make_frame(
    width: int,
    height: int,
    pattern: str = "noise",
    pts: float = 0.0,
    colorspace: ColorSpace = ColorSpace.BT709,
    seed: int = 42,
) -> VideoFrame:
    """Return a synthetic uint8 ``VideoFrame`` of the requested resolution.

    Args:
        width:      Frame width in pixels.
        height:     Frame height in pixels.
        pattern:    One of ``"noise"``, ``"gradient"``, ``"solid_gray"``,
                    ``"checkerboard"``.
        pts:        Presentation timestamp assigned to the frame.
        colorspace: Color space tag; does not affect pixel data.
        seed:       RNG seed (only used for ``"noise"``).

    Returns:
        A new :class:`~hipixel_core.types.VideoFrame` with ``dtype=uint8``.

    Raises:
        ValueError: if *pattern* is not one of the known options.
    """
    rng = np.random.default_rng(seed)

    if pattern == "noise":
        data = rng.integers(0, 256, size=(height, width, 3), dtype=np.uint8)

    elif pattern == "gradient":
        # Horizontal luminance ramp 0→255, constant across columns
        row = np.linspace(0, 255, width, dtype=np.float32).astype(np.uint8)
        channel = np.tile(row, (height, 1))  # (H, W)
        data = np.stack([channel, channel, channel], axis=2)

    elif pattern == "solid_gray":
        data = np.full((height, width, 3), 128, dtype=np.uint8)

    elif pattern == "checkerboard":
        # 8×8 pixel alternating black/white squares
        tile_size = 8
        xs = np.arange(width) // tile_size
        ys = np.arange(height) // tile_size
        grid = (xs[np.newaxis, :] + ys[:, np.newaxis]) % 2  # (H, W), 0 or 1
        channel = (grid * 255).astype(np.uint8)
        data = np.stack([channel, channel, channel], axis=2)

    else:
        raise ValueError(
            f"Unknown pattern '{pattern}'. "
            "Choose from: noise, gradient, solid_gray, checkerboard."
        )

    return VideoFrame(
        data=data,
        pts=pts,
        width=width,
        height=height,
        colorspace=colorspace,
    )


def make_video_meta(
    width: int = 1280,
    height: int = 720,
    fps: float = 24.0,
    frame_count: int = 100,
    codec: str = "h264",
    colorspace: ColorSpace = ColorSpace.BT709,
    is_hdr: bool = False,
) -> VideoMeta:
    """Return a synthetic :class:`~hipixel_core.types.VideoMeta`.

    No real file is created; ``path`` is set to ``"<synthetic>"``.
    """
    return VideoMeta(
        path="<synthetic>",
        width=width,
        height=height,
        fps=fps,
        frame_count=frame_count,
        duration_s=frame_count / fps,
        codec=codec,
        pixel_format="yuv420p",
        colorspace=colorspace,
        is_hdr=is_hdr,
    )


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------

#: Common benchmark resolutions (name → (width, height))
STANDARD_RESOLUTIONS: dict[str, tuple[int, int]] = {
    "480p": (854, 480),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "4k": (3840, 2160),
}


def parse_resolution(spec: str) -> tuple[int, int]:
    """Parse a resolution string to ``(width, height)``.

    Accepts:
    - Shorthand: ``"720p"``, ``"1080p"``, ``"4k"``
    - Explicit: ``"1280x720"``, ``"1920x1080"``

    Raises:
        ValueError: if the string cannot be parsed.
    """
    if spec in STANDARD_RESOLUTIONS:
        return STANDARD_RESOLUTIONS[spec]
    if "x" in spec.lower():
        parts = spec.lower().split("x")
        if len(parts) == 2:
            try:
                return int(parts[0]), int(parts[1])
            except ValueError:
                pass
    raise ValueError(
        f"Cannot parse resolution '{spec}'. "
        "Use '1280x720' or shorthand '720p'/'1080p'/'4k'."
    )
