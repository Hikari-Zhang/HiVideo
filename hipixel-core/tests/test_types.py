"""
Tests for hipixel_core.types — core data models.
"""

from __future__ import annotations

import numpy as np
import pytest

from hipixel_core.types import (
    DeviceInfo,
    OutputSpec,
    ProgressEvent,
    VideoFrame,
)


class TestVideoFrame:
    def _make_frame(
        self,
        w: int = 64,
        h: int = 48,
        dtype: type = np.uint8,
    ) -> VideoFrame:
        data = np.zeros((h, w, 3), dtype=dtype)
        return VideoFrame(data=data, pts=0.0, width=w, height=h)

    def test_resolution_property(self) -> None:
        f = self._make_frame(320, 240)
        assert f.resolution == (320, 240)

    def test_to_float32_normalizes(self) -> None:
        data = np.full((4, 4, 3), 255, dtype=np.uint8)
        f = VideoFrame(data=data, pts=0.0, width=4, height=4)
        ff = f.to_float32()
        assert ff.data.dtype == np.float32
        assert ff.data.max() == pytest.approx(1.0)

    def test_to_uint8_denormalizes(self) -> None:
        data = np.ones((4, 4, 3), dtype=np.float32)
        f = VideoFrame(data=data, pts=0.0, width=4, height=4)
        fu = f.to_uint8()
        assert fu.data.dtype == np.uint8
        assert fu.data.max() == 255

    def test_to_float32_idempotent_on_float(self) -> None:
        data = np.zeros((4, 4, 3), dtype=np.float32)
        f = VideoFrame(data=data, pts=0.0, width=4, height=4)
        assert f.to_float32() is f

    def test_to_uint8_idempotent_on_uint8(self) -> None:
        data = np.zeros((4, 4, 3), dtype=np.uint8)
        f = VideoFrame(data=data, pts=0.0, width=4, height=4)
        assert f.to_uint8() is f

    def test_invalid_shape_raises(self) -> None:
        with pytest.raises(ValueError, match="must be"):
            VideoFrame(
                data=np.zeros((48, 64, 4), dtype=np.uint8),
                pts=0.0,
                width=64,
                height=48,
            )

    def test_dimension_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="mismatch"):
            VideoFrame(
                data=np.zeros((48, 64, 3), dtype=np.uint8),
                pts=0.0,
                width=100,  # wrong
                height=48,
            )

    def test_pts_preserved_in_conversion(self) -> None:
        data = np.zeros((4, 4, 3), dtype=np.uint8)
        f = VideoFrame(data=data, pts=1.234, width=4, height=4)
        assert f.to_float32().pts == pytest.approx(1.234)


class TestProgressEvent:
    def test_progress_pct_normal(self) -> None:
        e = ProgressEvent(
            frame_index=50,
            total_frames=100,
            elapsed_s=5.0,
            fps_current=10.0,
            fps_avg=10.0,
        )
        assert e.progress_pct == pytest.approx(50.0)

    def test_progress_pct_zero_total(self) -> None:
        e = ProgressEvent(
            frame_index=0,
            total_frames=0,
            elapsed_s=0.0,
            fps_current=0.0,
            fps_avg=0.0,
        )
        assert e.progress_pct == 0.0

    def test_eta_s_finite(self) -> None:
        e = ProgressEvent(
            frame_index=10,
            total_frames=100,
            elapsed_s=1.0,
            fps_current=10.0,
            fps_avg=10.0,
        )
        assert e.eta_s == pytest.approx(9.0)

    def test_eta_s_infinite_when_fps_zero(self) -> None:
        e = ProgressEvent(
            frame_index=0,
            total_frames=100,
            elapsed_s=0.0,
            fps_current=0.0,
            fps_avg=0.0,
        )
        assert e.eta_s == float("inf")


class TestOutputSpec:
    def test_resolved_fps_preserves_source(self) -> None:
        spec = OutputSpec(path="/tmp/out.mp4", fps=None)
        assert spec.resolved_fps(29.97) == pytest.approx(29.97)

    def test_resolved_fps_override(self) -> None:
        spec = OutputSpec(path="/tmp/out.mp4", fps=60.0)
        assert spec.resolved_fps(29.97) == pytest.approx(60.0)


class TestDeviceInfo:
    def test_has_gpu_true(self) -> None:
        di = DeviceInfo(
            backend_name="cuda",
            device_name="RTX 4090",
            total_vram_mb=24576,
            available_vram_mb=20000,
            platform="linux",
        )
        assert di.has_gpu is True

    def test_has_gpu_false_for_cpu(self) -> None:
        di = DeviceInfo(
            backend_name="cpu",
            device_name="CPU",
            total_vram_mb=0,
            available_vram_mb=0,
            platform="darwin",
        )
        assert di.has_gpu is False
