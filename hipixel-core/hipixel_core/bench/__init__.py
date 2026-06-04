"""hipixel_core.bench — benchmark runner and synthetic frame generators."""

from hipixel_core.bench.runner import BenchmarkReport, BenchmarkResult, BenchmarkRunner
from hipixel_core.bench.synthetic import (
    STANDARD_RESOLUTIONS,
    make_frame,
    make_video_meta,
    parse_resolution,
)

__all__ = [
    "BenchmarkReport",
    "BenchmarkResult",
    "BenchmarkRunner",
    "STANDARD_RESOLUTIONS",
    "make_frame",
    "make_video_meta",
    "parse_resolution",
]
