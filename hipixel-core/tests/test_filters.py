"""
Tests for the filter implementations.
"""

from __future__ import annotations

import numpy as np
import pytest

from hipixel_core.types import ColorSpace, VideoFrame


def _frame(w: int = 64, h: int = 48) -> VideoFrame:
    data = (np.random.rand(h, w, 3) * 255).astype(np.uint8)
    return VideoFrame(data=data, pts=0.0, width=w, height=h, colorspace=ColorSpace.BT709)


class TestCASFilter:
    """CAS is CPU-only — always safe to test."""

    def _backend(self) -> object:
        from hipixel_core.backends.cpu import CpuBackend

        be = CpuBackend()
        be.initialize()
        return be

    def test_name(self) -> None:
        from hipixel_core.filters.cas import CASFilter

        assert CASFilter.name == "cas"  # type: ignore[attr-defined]

    def test_required_models_empty(self) -> None:
        from hipixel_core.filters.cas import CASFilter

        f = CASFilter()
        assert f.required_models == []

    def test_process_preserves_dimensions(self) -> None:
        from hipixel_core.filters.cas import CASFilter

        be = self._backend()
        f = CASFilter()
        params = {"sharpness": 0.5}
        f.setup(be, params)  # type: ignore[arg-type]
        frame = _frame(128, 96)
        result = f.process_frame(frame, be, params)  # type: ignore[arg-type]
        assert result.width == 128
        assert result.height == 96

    def test_process_output_in_range(self) -> None:
        from hipixel_core.filters.cas import CASFilter

        be = self._backend()
        f = CASFilter()
        params = {"sharpness": 0.5}
        f.setup(be, params)  # type: ignore[arg-type]
        result = f.process_frame(_frame(), be, params)  # type: ignore[arg-type]
        out = result.to_float32().data
        assert out.min() >= 0.0
        assert out.max() <= 1.0

    def test_teardown_no_error(self) -> None:
        from hipixel_core.filters.cas import CASFilter

        be = self._backend()
        f = CASFilter()
        f.setup(be, {})  # type: ignore[arg-type]
        f.teardown(be)  # type: ignore[arg-type]

    def test_pts_preserved(self) -> None:
        from hipixel_core.filters.cas import CASFilter

        be = self._backend()
        f = CASFilter()
        f.setup(be, {})  # type: ignore[arg-type]
        data = np.zeros((48, 64, 3), dtype=np.uint8)
        frame = VideoFrame(data=data, pts=3.14, width=64, height=48)
        result = f.process_frame(frame, be, {})  # type: ignore[arg-type]
        assert result.pts == pytest.approx(3.14)


class TestFilterRegistry:
    def test_get_known_filter(self) -> None:
        from hipixel_core.filters import get_filter

        f = get_filter("cas")
        assert hasattr(f, "name")

    def test_get_unknown_filter_raises(self) -> None:
        from hipixel_core.filters import get_filter

        with pytest.raises(KeyError, match="Unknown filter"):
            get_filter("not_a_real_filter")

    def test_all_filters_in_registry(self) -> None:
        from hipixel_core.filters import FILTER_REGISTRY

        expected = {"real_esrgan", "anime4k", "nafnet", "cas", "aces", "rife"}
        assert expected == set(FILTER_REGISTRY.keys())



class TestACESToneMappingFilter:
    """ACES is CPU-only — always safe to test."""

    def _backend(self) -> object:
        from hipixel_core.backends.cpu import CpuBackend

        be = CpuBackend()
        be.initialize()
        return be

    def _frame(self, w: int = 64, h: int = 48, *, is_hdr: bool = True) -> VideoFrame:
        data = np.random.rand(h, w, 3).astype(np.float32)
        return VideoFrame(
            data=data,
            pts=0.0,
            width=w,
            height=h,
            colorspace=ColorSpace.BT2020,
            is_hdr=is_hdr,
        )

    def test_name(self) -> None:
        from hipixel_core.filters.aces import ACESToneMappingFilter

        assert ACESToneMappingFilter.name == "aces"

    def test_required_models_empty(self) -> None:
        from hipixel_core.filters.aces import ACESToneMappingFilter

        f = ACESToneMappingFilter()
        assert f.required_models == []

    def test_output_in_range(self) -> None:
        from hipixel_core.filters.aces import ACESToneMappingFilter

        be = self._backend()
        f = ACESToneMappingFilter()
        f.setup(be, {})  # type: ignore[arg-type]
        result = f.process_frame(self._frame(), be, {})  # type: ignore[arg-type]
        out = result.data
        assert out.min() >= 0.0
        assert out.max() <= 1.0

    def test_hdr_flag_cleared(self) -> None:
        from hipixel_core.filters.aces import ACESToneMappingFilter

        be = self._backend()
        f = ACESToneMappingFilter()
        f.setup(be, {})  # type: ignore[arg-type]
        frame = self._frame(is_hdr=True)
        result = f.process_frame(frame, be, {})  # type: ignore[arg-type]
        assert result.is_hdr is False

    def test_colorspace_set_to_srgb(self) -> None:
        from hipixel_core.filters.aces import ACESToneMappingFilter

        be = self._backend()
        f = ACESToneMappingFilter()
        f.setup(be, {})  # type: ignore[arg-type]
        result = f.process_frame(self._frame(), be, {})  # type: ignore[arg-type]
        assert result.colorspace == ColorSpace.SRGB

    def test_pts_preserved(self) -> None:
        from hipixel_core.filters.aces import ACESToneMappingFilter

        be = self._backend()
        f = ACESToneMappingFilter()
        f.setup(be, {})  # type: ignore[arg-type]
        data = np.zeros((48, 64, 3), dtype=np.float32)
        frame = VideoFrame(data=data, pts=2.718, width=64, height=48)
        result = f.process_frame(frame, be, {})  # type: ignore[arg-type]
        assert result.pts == pytest.approx(2.718)

    def test_exposure_gt1_brightens(self) -> None:
        from hipixel_core.filters.aces import ACESToneMappingFilter

        be = self._backend()
        np.random.seed(42)
        frame = self._frame()

        f_default = ACESToneMappingFilter()
        f_default.setup(be, {"exposure": 1.0})  # type: ignore[arg-type]
        out_default = f_default.process_frame(frame, be, {"exposure": 1.0})  # type: ignore[arg-type]

        f_bright = ACESToneMappingFilter()
        f_bright.setup(be, {"exposure": 4.0})  # type: ignore[arg-type]
        out_bright = f_bright.process_frame(frame, be, {"exposure": 4.0})  # type: ignore[arg-type]

        assert out_bright.to_float32().data.mean() > out_default.to_float32().data.mean()

    def test_exposure_lt1_darkens(self) -> None:
        from hipixel_core.filters.aces import ACESToneMappingFilter

        be = self._backend()
        np.random.seed(7)
        frame = self._frame()

        f_default = ACESToneMappingFilter()
        f_default.setup(be, {"exposure": 1.0})  # type: ignore[arg-type]
        out_default = f_default.process_frame(frame, be, {"exposure": 1.0})  # type: ignore[arg-type]

        f_dark = ACESToneMappingFilter()
        f_dark.setup(be, {"exposure": 0.1})  # type: ignore[arg-type]
        out_dark = f_dark.process_frame(frame, be, {"exposure": 0.1})  # type: ignore[arg-type]

        assert out_dark.to_float32().data.mean() < out_default.to_float32().data.mean()

    def test_reinhard_method(self) -> None:
        from hipixel_core.filters.aces import ACESToneMappingFilter

        be = self._backend()
        f = ACESToneMappingFilter()
        f.setup(be, {"method": "reinhard"})  # type: ignore[arg-type]
        result = f.process_frame(self._frame(), be, {"method": "reinhard"})  # type: ignore[arg-type]
        out = result.data
        assert out.min() >= 0.0
        assert out.max() <= 1.0

    def test_midgray_known_value(self) -> None:
        """Mid-gray 0.18 through ACES fitted (no gamma) → approx 0.399."""
        from hipixel_core.filters.aces import ACESToneMappingFilter

        be = self._backend()
        f = ACESToneMappingFilter()
        f.setup(be, {"exposure": 1.0, "gamma": "linear"})  # type: ignore[arg-type]

        data = np.full((1, 1, 3), 0.18, dtype=np.float32)
        frame = VideoFrame(data=data, pts=0.0, width=1, height=1)
        result = f.process_frame(frame, be, {"exposure": 1.0, "gamma": "linear"})  # type: ignore[arg-type]
        # ACES(0.18) = 0.18*(2.51*0.18+0.03)/(0.18*(2.43*0.18+0.59)+0.14)
        x = 0.18
        expected = x * (2.51 * x + 0.03) / (x * (2.43 * x + 0.59) + 0.14)
        assert result.data[0, 0, 0] == pytest.approx(expected, abs=1e-5)

    def test_teardown_no_error(self) -> None:
        from hipixel_core.filters.aces import ACESToneMappingFilter

        be = self._backend()
        f = ACESToneMappingFilter()
        f.setup(be, {})  # type: ignore[arg-type]
        f.teardown(be)  # type: ignore[arg-type]


class TestRIFEStub:
    def test_setup_raises_not_implemented(self) -> None:
        from hipixel_core.backends.cpu import CpuBackend
        from hipixel_core.filters.rife import RIFEFilter

        be = CpuBackend()
        be.initialize()
        f = RIFEFilter()
        with pytest.raises(NotImplementedError, match="Phase 1"):
            f.setup(be, {})
