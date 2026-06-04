"""
Benchmark: CAS filter throughput across resolutions.

Run with:
    pytest benchmarks/bench_cas.py --benchmark-only -v
"""

from __future__ import annotations

import numpy as np
import pytest

from hipixel_core.backends.cpu import CpuBackend
from hipixel_core.filters.cas import CASFilter
from hipixel_core.types import ColorSpace, VideoFrame


def _make_frame(w: int, h: int) -> VideoFrame:
    data = (np.random.rand(h, w, 3) * 255).astype(np.uint8)
    return VideoFrame(data=data, pts=0.0, width=w, height=h, colorspace=ColorSpace.BT709)


@pytest.fixture(scope="module")
def cpu_backend() -> CpuBackend:
    be = CpuBackend()
    be.initialize()
    yield be
    be.shutdown()


@pytest.fixture(scope="module")
def cas_filter(cpu_backend: CpuBackend) -> CASFilter:
    f = CASFilter()
    f.setup(cpu_backend, {"sharpness": 0.5})
    return f


@pytest.mark.benchmark(group="cas-resolution")
@pytest.mark.parametrize(
    "resolution",
    [
        (640, 360),
        (1280, 720),
        (1920, 1080),
        (3840, 2160),
    ],
)
def test_cas_throughput(
    benchmark: object,
    cas_filter: CASFilter,
    cpu_backend: CpuBackend,
    resolution: tuple[int, int],
) -> None:
    w, h = resolution
    frame = _make_frame(w, h)
    benchmark(cas_filter.process_frame, frame, cpu_backend, {"sharpness": 0.5})  # type: ignore[call-arg]
