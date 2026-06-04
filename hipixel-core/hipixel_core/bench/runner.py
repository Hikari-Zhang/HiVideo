"""
Benchmark runner — measures per-frame latency for individual filters.

Usage::

    from hipixel_core.backends.selector import select_backend
    from hipixel_core.bench.runner import BenchmarkRunner

    backend = select_backend()
    backend.initialize()

    runner = BenchmarkRunner(backend)
    result = runner.run_filter("cas", resolution="1280x720", frames=60)
    print(result.avg_fps)

    report = runner.run_cpu_filters(resolution="1280x720", frames=30)
    print(report.to_markdown())

    backend.shutdown()
"""

from __future__ import annotations

import json
import platform
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from hipixel_core._log import get_logger
from hipixel_core.bench.synthetic import make_frame, parse_resolution

_log = get_logger("bench")

if TYPE_CHECKING:
    from hipixel_core.backends.base import InferenceBackend


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class BenchmarkResult:
    """Timing statistics for one filter at one resolution.

    ``avg_fps``, ``min_fps``, ``max_fps`` are derived from per-frame
    wall-clock measurements (``process_frame`` only — no I/O).
    ``p50_ms`` and ``p95_ms`` are the median and 95th-percentile
    frame latencies in milliseconds.
    """

    filter_name: str
    resolution: str  # e.g. "1280x720"
    frame_count: int
    avg_fps: float
    min_fps: float
    max_fps: float
    p50_ms: float
    p95_ms: float
    backend_name: str
    device_name: str
    platform: str  # "darwin" | "linux" | "windows"
    python_version: str
    hipixel_version: str
    timestamp: str  # ISO-8601

    # Raw per-frame timings (excluded from JSON report but kept for analysis)
    _frame_times_ms: list[float] = field(default_factory=list, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict (excludes raw frame times)."""
        return {
            "filter_name": self.filter_name,
            "resolution": self.resolution,
            "frame_count": self.frame_count,
            "avg_fps": round(self.avg_fps, 2),
            "min_fps": round(self.min_fps, 2),
            "max_fps": round(self.max_fps, 2),
            "p50_ms": round(self.p50_ms, 3),
            "p95_ms": round(self.p95_ms, 3),
            "backend_name": self.backend_name,
            "device_name": self.device_name,
            "platform": self.platform,
            "python_version": self.python_version,
            "hipixel_version": self.hipixel_version,
            "timestamp": self.timestamp,
        }


@dataclass
class BenchmarkReport:
    """Collection of results from a multi-filter benchmark run.

    Supports export to JSON and Markdown (e.g. for pasting into
    GitHub issues or the performance-tuning docs).
    """

    results: list[BenchmarkResult]
    device_name: str = ""
    backend_name: str = ""

    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_name": self.device_name,
            "backend_name": self.backend_name,
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialise to a pretty-printed JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_markdown(self) -> str:
        """Render results as a Markdown table.

        Example output::

            | Filter    | Resolution | FPS avg | FPS min | FPS max | p50 ms | p95 ms |
            |-----------|------------|---------|---------|---------|--------|--------|
            | cas       | 1280x720   | 1523.4  | 1410.2  | 1680.9  |  0.66  |  0.72  |

        """
        if not self.results:
            return "_No benchmark results._\n"

        header = (
            "| Filter | Resolution | FPS avg | FPS min | FPS max | p50 ms | p95 ms |\n"
            "|--------|------------|--------:|--------:|--------:|-------:|-------:|\n"
        )
        rows = ""
        for r in self.results:
            rows += (
                f"| {r.filter_name} "
                f"| {r.resolution} "
                f"| {r.avg_fps:.1f} "
                f"| {r.min_fps:.1f} "
                f"| {r.max_fps:.1f} "
                f"| {r.p50_ms:.2f} "
                f"| {r.p95_ms:.2f} |\n"
            )

        meta = ""
        if self.device_name:
            meta += f"\n**Device**: {self.device_name}  \n"
        if self.backend_name:
            meta += f"**Backend**: {self.backend_name}\n"

        return header + rows + meta

    def save(self, path: Path | str, fmt: str | None = None) -> None:
        """Write the report to *path*.

        Args:
            path: Output file path.  Extension determines format if *fmt*
                  is not given (``".json"`` → JSON, ``".md"`` → Markdown,
                  anything else → JSON).
            fmt:  ``"json"`` or ``"md"`` — overrides the extension.
        """
        p = Path(path)
        if fmt is None:
            fmt = "md" if p.suffix.lower() == ".md" else "json"

        content = self.to_markdown() if fmt == "md" else self.to_json()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

#: Filters that run on CPU without an ONNX model.
CPU_ONLY_FILTERS: tuple[str, ...] = ("cas", "aces")


class BenchmarkRunner:
    """Measures ``process_frame`` latency for hipixel-core filters.

    The runner generates synthetic frames and passes them through a
    filter's ``setup → process_frame × N → teardown`` cycle, recording
    wall-clock time for each ``process_frame`` call.

    No video I/O is performed — results reflect pure filter throughput.

    Args:
        backend: An *initialised* :class:`~hipixel_core.backends.base.InferenceBackend`.
                 Defaults to auto-selected backend if ``None``.
    """

    def __init__(self, backend: InferenceBackend | None = None) -> None:
        self._owns_backend = False  # guard: set before any code that can raise
        if backend is None:
            from hipixel_core.backends.selector import select_backend

            backend = select_backend()
            backend.initialize()
            self._owns_backend = True
        self._backend = backend

    def __del__(self) -> None:
        if self._owns_backend:
            try:
                self._backend.shutdown()
            except Exception:
                pass

    # ------------------------------------------------------------------

    def run_filter(
        self,
        filter_name: str,
        resolution: str = "1280x720",
        frames: int = 30,
        params: dict[str, Any] | None = None,
        pattern: str = "noise",
    ) -> BenchmarkResult:
        """Benchmark a single filter.

        Args:
            filter_name: Registry name (e.g. ``"cas"``, ``"aces"``).
            resolution:  Resolution string (e.g. ``"1280x720"`` or ``"720p"``).
            frames:      Number of ``process_frame`` calls.
            params:      Filter params dict; defaults to empty (filter defaults).
            pattern:     Synthetic frame pattern (see :mod:`~hipixel_core.bench.synthetic`).

        Returns:
            A :class:`BenchmarkResult` with timing statistics.
        """
        from hipixel_core.filters import get_filter

        if params is None:
            params = {}

        w, h = parse_resolution(resolution)
        canonical = f"{w}x{h}"
        frame = make_frame(w, h, pattern=pattern)

        _log.debug(
            "BenchmarkRunner.run_filter: %s at %s, %d frames",
            filter_name, canonical, frames,
        )

        filt = get_filter(filter_name)
        filt.setup(self._backend, params)  # type: ignore[union-attr]

        # Warm-up: 3 frames to fill any JIT / lazy-init caches
        for _ in range(min(3, frames)):
            filt.process_frame(frame, self._backend, params)  # type: ignore[union-attr]

        # Timed run
        frame_times: list[float] = []
        for _ in range(frames):
            t0 = time.perf_counter()
            filt.process_frame(frame, self._backend, params)  # type: ignore[union-attr]
            frame_times.append((time.perf_counter() - t0) * 1000.0)  # → ms

        filt.teardown(self._backend)  # type: ignore[union-attr]

        result = self._make_result(filter_name, canonical, frame_times)
        _log.info(
            "%-12s  %.1f fps  p50=%.2fms  p95=%.2fms",
            result.filter_name, result.avg_fps, result.p50_ms, result.p95_ms,
        )
        return result

    def run_cpu_filters(
        self,
        resolution: str = "1280x720",
        frames: int = 30,
    ) -> BenchmarkReport:
        """Benchmark all CPU-only filters (``cas`` + ``aces``).

        This is the subset that runs on every CI platform without GPU
        hardware or ONNX model downloads.

        Returns:
            A :class:`BenchmarkReport` containing one result per filter.
        """
        results = [
            self.run_filter(name, resolution=resolution, frames=frames)
            for name in CPU_ONLY_FILTERS
        ]
        di = self._backend.device_info
        return BenchmarkReport(
            results=results,
            device_name=di.device_name,
            backend_name=di.backend_name,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_result(
        self,
        filter_name: str,
        resolution: str,
        frame_times: list[float],
    ) -> BenchmarkResult:
        """Compute statistics from a list of per-frame latencies (in ms)."""
        import datetime

        from hipixel_core import __version__

        arr = np.array(frame_times, dtype=np.float64)
        fps_per_frame = 1000.0 / arr  # fps implied by each frame's time

        p50 = float(np.percentile(arr, 50))
        p95 = float(np.percentile(arr, 95))

        di = self._backend.device_info

        return BenchmarkResult(
            filter_name=filter_name,
            resolution=resolution,
            frame_count=len(frame_times),
            avg_fps=float(np.mean(fps_per_frame)),
            min_fps=float(np.min(fps_per_frame)),
            max_fps=float(np.max(fps_per_frame)),
            p50_ms=p50,
            p95_ms=p95,
            backend_name=di.backend_name,
            device_name=di.device_name,
            platform=platform.system().lower(),
            python_version=sys.version.split()[0],
            hipixel_version=__version__,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            _frame_times_ms=frame_times,
        )
