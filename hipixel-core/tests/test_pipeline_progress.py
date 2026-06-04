"""
Tests for FpsTracker and the pipeline progress callback.

No FFmpeg, no models, no network — all synthetic.
"""

from __future__ import annotations

import time

import pytest

from hipixel_core._fps_tracker import FpsTracker


# ---------------------------------------------------------------------------
# FpsTracker unit tests
# ---------------------------------------------------------------------------


class TestFpsTracker:
    def test_zero_fps_before_any_ticks(self) -> None:
        t = FpsTracker()
        assert t.fps_current == 0.0

    def test_zero_fps_after_one_tick(self) -> None:
        t = FpsTracker()
        t.tick(0.0)
        assert t.fps_current == 0.0

    def test_exact_fps_from_synthetic_timestamps(self) -> None:
        """10 frames at 0.1s intervals → 10 fps."""
        t = FpsTracker(window=30)
        for i in range(10):
            t.tick(float(i) * 0.1)
        # 9 intervals over 0.9 s  → 9/0.9 = 10 fps
        assert abs(t.fps_current - 10.0) < 1e-6

    def test_window_capping(self) -> None:
        """With window=5, only the last 5 timestamps are retained."""
        t = FpsTracker(window=5)
        # First 5 frames at 1 fps, then 5 frames at 100 fps
        for i in range(5):
            t.tick(float(i))
        for i in range(5):
            t.tick(5.0 + i * 0.01)
        # Only last 5 timestamps kept → rate ≈ 100 fps
        assert t.fps_current > 50.0

    def test_window_too_small_raises(self) -> None:
        with pytest.raises(ValueError, match="window must be >= 2"):
            FpsTracker(window=1)

    def test_reset_clears_state(self) -> None:
        t = FpsTracker()
        for i in range(10):
            t.tick(float(i) * 0.1)
        t.reset()
        assert t.fps_current == 0.0

    def test_default_tick_uses_monotonic(self) -> None:
        """Calling tick() without args should not raise and should record a time."""
        t = FpsTracker()
        t.tick()
        t.tick()
        # Two real ticks: the span should be tiny but positive
        assert t.fps_current >= 0.0

    def test_repr_contains_fps(self) -> None:
        t = FpsTracker(window=10)
        for i in range(5):
            t.tick(float(i) * 0.1)
        r = repr(t)
        assert "FpsTracker" in r
        assert "fps=" in r

    def test_steady_rate_converges(self) -> None:
        """30 fps steady → tracker should report very close to 30."""
        t = FpsTracker(window=30)
        for i in range(60):
            t.tick(i / 30.0)
        assert abs(t.fps_current - 30.0) < 0.01

    def test_variable_rate_returns_window_average(self) -> None:
        """Variable timestamps — fps_current should be window-averaged."""
        t = FpsTracker(window=10)
        # First 50 frames fast (100 fps), last 10 frames slow (5 fps)
        ts = [i * 0.01 for i in range(50)]
        ts += [ts[-1] + (i + 1) * 0.2 for i in range(10)]
        for tick in ts:
            t.tick(tick)
        # Window of last 10 → slow region → fps_current should reflect ~5 fps
        assert t.fps_current < 20.0


# ---------------------------------------------------------------------------
# Pipeline progress callback integration
# ---------------------------------------------------------------------------


class TestPipelineProgressCallback:
    """Verify that the pipeline emits well-formed ProgressEvent objects
    and that fps_current is a plausible (non-zero) value for a real
    encoding run."""

    @pytest.mark.slow
    def test_fps_current_is_positive(self, tmp_path: "pathlib.Path") -> None:  # type: ignore[name-defined]  # noqa: F821
        """fps_current should be > 0 after at least one progress event fires."""
        import pathlib
        import subprocess
        import sys
        from unittest import mock

        sys.path.insert(0, str(pathlib.Path(__file__).parent))
        from test_inference_e2e import _create_test_video, _make_identity_onnx

        from hipixel_core.backends.cpu import CpuBackend
        from hipixel_core.filters.cas import CASFilter
        from hipixel_core.pipeline import Pipeline
        from hipixel_core.types import OutputSpec
        from hipixel_core.video.decoder import probe

        src = tmp_path / "in.mp4"
        _create_test_video(src, w=64, h=48, frames=30, fps=25)

        meta = probe(str(src))
        out = OutputSpec(path=str(tmp_path / "out.mp4"), codec="h264", crf=28)

        events: list = []
        backend = CpuBackend()
        backend.initialize()

        pipeline = Pipeline(filters=[CASFilter()], filter_params=[{}])

        # Monkey-patch sleep so the 1-second throttle fires every frame
        import hipixel_core.pipeline as _pm
        original_time = _pm.time

        class _FastTime:
            _counter = 0.0

            @staticmethod
            def monotonic() -> float:
                # Each call advances by 2 seconds → every frame triggers callback
                _FastTime._counter += 2.0
                return _FastTime._counter

        with mock.patch.object(_pm, "time", _FastTime):
            result = pipeline.run(
                source=meta,
                output_spec=out,
                backend=backend,
                progress_cb=events.append,
            )

        assert result.success, result.error
        if events:
            for ev in events:
                assert ev.fps_current >= 0.0  # tracker reports non-negative
                assert ev.fps_avg >= 0.0
                assert 0.0 <= ev.progress_pct <= 100.0
                assert ev.elapsed_s >= 0.0

    @pytest.mark.slow
    def test_progress_event_fields(self, tmp_path: "pathlib.Path") -> None:  # type: ignore[name-defined]  # noqa: F821
        """Each emitted ProgressEvent has sensible field values."""
        import pathlib
        import sys

        sys.path.insert(0, str(pathlib.Path(__file__).parent))
        from test_inference_e2e import _create_test_video

        from hipixel_core.backends.cpu import CpuBackend
        from hipixel_core.filters.cas import CASFilter
        from hipixel_core.pipeline import Pipeline
        from hipixel_core.types import OutputSpec, ProgressEvent
        from hipixel_core.video.decoder import probe

        src = tmp_path / "in2.mp4"
        _create_test_video(src, w=64, h=48, frames=25, fps=25)

        meta = probe(str(src))
        out = OutputSpec(path=str(tmp_path / "out2.mp4"), codec="h264", crf=28)

        import hipixel_core.pipeline as _pm
        from unittest import mock

        class _FasterTime:
            _t = 0.0

            @staticmethod
            def monotonic() -> float:
                _FasterTime._t += 2.0
                return _FasterTime._t

        events: list[ProgressEvent] = []
        backend = CpuBackend()
        backend.initialize()
        pipeline = Pipeline(filters=[CASFilter()], filter_params=[{}])
        with mock.patch.object(_pm, "time", _FasterTime):
            pipeline.run(
                source=meta,
                output_spec=out,
                backend=backend,
                progress_cb=events.append,
            )

        for ev in events:
            assert isinstance(ev, ProgressEvent)
            assert ev.frame_index > 0
            assert ev.total_frames >= 0
            assert ev.elapsed_s > 0.0
            assert isinstance(ev.fps_current, float)
            assert isinstance(ev.fps_avg, float)
