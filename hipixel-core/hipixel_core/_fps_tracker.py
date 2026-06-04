"""
Rolling-window frames-per-second tracker.

Tracks per-frame wall-clock timestamps to compute instantaneous
and window-average frame rates.  Designed to be embedded in the
pipeline encode_worker, but fully testable in isolation.

Usage::

    tracker = FpsTracker(window=30)
    for frame in ...:
        process(frame)
        tracker.tick()           # records time.monotonic() internally
        fps = tracker.fps_current  # rolling-window average
"""

from __future__ import annotations

import time
from collections import deque


class FpsTracker:
    """Rolling-window FPS tracker.

    Maintains a fixed-length deque of monotonic timestamps, one per
    frame.  ``fps_current`` returns the average rate over the last
    ``window`` frames (= (window - 1) inter-frame gaps divided by
    the total time span of those frames).

    Args:
        window: Maximum number of frame timestamps to retain.
                Must be >= 2 for a meaningful rate.
    """

    def __init__(self, window: int = 30) -> None:
        if window < 2:
            raise ValueError(f"window must be >= 2, got {window}")
        self._window = window
        self._times: deque[float] = deque(maxlen=window)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def tick(self, now: float | None = None) -> None:
        """Record a frame at time *now* (defaults to ``time.monotonic()``)."""
        self._times.append(now if now is not None else time.monotonic())

    @property
    def fps_current(self) -> float:
        """Rolling-window FPS estimate.

        Returns 0.0 until at least 2 frames have been ticked.
        """
        if len(self._times) < 2:
            return 0.0
        span = self._times[-1] - self._times[0]
        if span <= 0.0:
            return 0.0
        return (len(self._times) - 1) / span

    def reset(self) -> None:
        """Clear all recorded timestamps."""
        self._times.clear()

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"FpsTracker(window={self._window}, ticks={len(self._times)}, fps={self.fps_current:.1f})"
