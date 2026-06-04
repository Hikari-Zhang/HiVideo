"""
Tests for hipixel_core.bench — synthetic generators, runner, and report types.

All tests are CPU-only: they use cas/aces (no ONNX models, no GPU) and are safe
to run on any CI platform.
"""

from __future__ import annotations

import datetime
import json
import re
from pathlib import Path

import numpy as np
import pytest

from hipixel_core.types import ColorSpace


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cpu_backend():
    """Return an initialised CpuBackend."""
    from hipixel_core.backends.cpu import CpuBackend

    be = CpuBackend()
    be.initialize()
    return be


# ---------------------------------------------------------------------------
# make_frame
# ---------------------------------------------------------------------------


class TestMakeFrame:
    """Tests for hipixel_core.bench.synthetic.make_frame."""

    def test_noise_shape_and_dtype(self) -> None:
        from hipixel_core.bench.synthetic import make_frame

        frame = make_frame(64, 48, pattern="noise")
        assert frame.data.shape == (48, 64, 3)
        assert frame.data.dtype == np.uint8
        assert frame.width == 64
        assert frame.height == 48

    def test_gradient_shape_and_dtype(self) -> None:
        from hipixel_core.bench.synthetic import make_frame

        frame = make_frame(80, 60, pattern="gradient")
        assert frame.data.shape == (60, 80, 3)
        assert frame.data.dtype == np.uint8

    def test_gradient_monotonic_per_row(self) -> None:
        from hipixel_core.bench.synthetic import make_frame

        frame = make_frame(64, 1, pattern="gradient")
        row = frame.data[0, :, 0].astype(int)
        diffs = np.diff(row)
        # Values must be non-decreasing (0 → 255 ramp)
        assert np.all(diffs >= 0)

    def test_solid_gray_value(self) -> None:
        from hipixel_core.bench.synthetic import make_frame

        frame = make_frame(32, 32, pattern="solid_gray")
        assert np.all(frame.data == 128)

    def test_checkerboard_corners(self) -> None:
        from hipixel_core.bench.synthetic import make_frame

        # With tile_size=8, top-left 8x8 block is black (0), next is white (255)
        frame = make_frame(32, 16, pattern="checkerboard")
        assert frame.data[0, 0, 0] == 0    # top-left tile: black
        assert frame.data[0, 8, 0] == 255  # next tile: white

    def test_checkerboard_all_channels_equal(self) -> None:
        from hipixel_core.bench.synthetic import make_frame

        frame = make_frame(32, 16, pattern="checkerboard")
        # R == G == B for every pixel
        assert np.array_equal(frame.data[:, :, 0], frame.data[:, :, 1])
        assert np.array_equal(frame.data[:, :, 0], frame.data[:, :, 2])

    def test_pts_preserved(self) -> None:
        from hipixel_core.bench.synthetic import make_frame

        frame = make_frame(64, 48, pts=3.14)
        assert frame.pts == pytest.approx(3.14)

    def test_colorspace_preserved(self) -> None:
        from hipixel_core.bench.synthetic import make_frame

        frame = make_frame(64, 48, colorspace=ColorSpace.BT2020)
        assert frame.colorspace == ColorSpace.BT2020

    def test_default_colorspace_is_bt709(self) -> None:
        from hipixel_core.bench.synthetic import make_frame

        frame = make_frame(64, 48)
        assert frame.colorspace == ColorSpace.BT709

    def test_noise_reproducible_with_seed(self) -> None:
        from hipixel_core.bench.synthetic import make_frame

        f1 = make_frame(64, 48, pattern="noise", seed=99)
        f2 = make_frame(64, 48, pattern="noise", seed=99)
        assert np.array_equal(f1.data, f2.data)

    def test_noise_different_seeds_differ(self) -> None:
        from hipixel_core.bench.synthetic import make_frame

        f1 = make_frame(64, 48, pattern="noise", seed=1)
        f2 = make_frame(64, 48, pattern="noise", seed=2)
        assert not np.array_equal(f1.data, f2.data)

    def test_bad_pattern_raises(self) -> None:
        from hipixel_core.bench.synthetic import make_frame

        with pytest.raises(ValueError, match="Unknown pattern"):
            make_frame(64, 48, pattern="rainbow")


# ---------------------------------------------------------------------------
# make_video_meta
# ---------------------------------------------------------------------------


class TestMakeVideoMeta:
    """Tests for hipixel_core.bench.synthetic.make_video_meta."""

    def test_default_fields(self) -> None:
        from hipixel_core.bench.synthetic import make_video_meta

        m = make_video_meta()
        assert m.width == 1280
        assert m.height == 720
        assert m.fps == pytest.approx(24.0)
        assert m.frame_count == 100
        assert m.codec == "h264"

    def test_synthetic_path(self) -> None:
        from hipixel_core.bench.synthetic import make_video_meta

        m = make_video_meta()
        assert m.path == "<synthetic>"

    def test_duration_computed(self) -> None:
        from hipixel_core.bench.synthetic import make_video_meta

        m = make_video_meta(fps=25.0, frame_count=50)
        assert m.duration_s == pytest.approx(2.0)

    def test_hdr_flag_passthrough(self) -> None:
        from hipixel_core.bench.synthetic import make_video_meta

        m = make_video_meta(is_hdr=True)
        assert m.is_hdr is True

    def test_colorspace_passthrough(self) -> None:
        from hipixel_core.bench.synthetic import make_video_meta

        m = make_video_meta(colorspace=ColorSpace.BT2020)
        assert m.colorspace == ColorSpace.BT2020

    def test_custom_dimensions(self) -> None:
        from hipixel_core.bench.synthetic import make_video_meta

        m = make_video_meta(width=3840, height=2160)
        assert m.width == 3840
        assert m.height == 2160


# ---------------------------------------------------------------------------
# parse_resolution + STANDARD_RESOLUTIONS
# ---------------------------------------------------------------------------


class TestParseResolution:
    """Tests for hipixel_core.bench.synthetic.parse_resolution."""

    def test_720p(self) -> None:
        from hipixel_core.bench.synthetic import parse_resolution

        assert parse_resolution("720p") == (1280, 720)

    def test_1080p(self) -> None:
        from hipixel_core.bench.synthetic import parse_resolution

        assert parse_resolution("1080p") == (1920, 1080)

    def test_4k(self) -> None:
        from hipixel_core.bench.synthetic import parse_resolution

        assert parse_resolution("4k") == (3840, 2160)

    def test_480p(self) -> None:
        from hipixel_core.bench.synthetic import parse_resolution

        assert parse_resolution("480p") == (854, 480)

    def test_explicit_lowercase(self) -> None:
        from hipixel_core.bench.synthetic import parse_resolution

        assert parse_resolution("1280x720") == (1280, 720)

    def test_explicit_uppercase(self) -> None:
        from hipixel_core.bench.synthetic import parse_resolution

        # Should be case-insensitive after the lowercase split
        assert parse_resolution("1920X1080") == (1920, 1080)

    def test_explicit_custom(self) -> None:
        from hipixel_core.bench.synthetic import parse_resolution

        assert parse_resolution("640x360") == (640, 360)

    def test_bad_string_raises(self) -> None:
        from hipixel_core.bench.synthetic import parse_resolution

        with pytest.raises(ValueError, match="Cannot parse resolution"):
            parse_resolution("fullhd")

    def test_bad_explicit_raises(self) -> None:
        from hipixel_core.bench.synthetic import parse_resolution

        with pytest.raises(ValueError):
            parse_resolution("axb")


class TestStandardResolutions:
    def test_expected_entries(self) -> None:
        from hipixel_core.bench.synthetic import STANDARD_RESOLUTIONS

        assert "480p" in STANDARD_RESOLUTIONS
        assert "720p" in STANDARD_RESOLUTIONS
        assert "1080p" in STANDARD_RESOLUTIONS
        assert "4k" in STANDARD_RESOLUTIONS
        assert STANDARD_RESOLUTIONS["720p"] == (1280, 720)
        assert STANDARD_RESOLUTIONS["4k"] == (3840, 2160)


# ---------------------------------------------------------------------------
# BenchmarkResult
# ---------------------------------------------------------------------------


def _make_fake_result(**overrides) -> "BenchmarkResult":
    from hipixel_core.bench.runner import BenchmarkResult

    defaults = dict(
        filter_name="cas",
        resolution="1280x720",
        frame_count=10,
        avg_fps=500.0,
        min_fps=450.0,
        max_fps=550.0,
        p50_ms=2.0,
        p95_ms=2.2,
        backend_name="cpu",
        device_name="TestCPU",
        platform="linux",
        python_version="3.11.0",
        hipixel_version="0.1.0",
        timestamp="2025-01-01T00:00:00+00:00",
        _frame_times_ms=[2.0] * 10,
    )
    defaults.update(overrides)
    return BenchmarkResult(**defaults)


class TestBenchmarkResult:
    def test_to_dict_has_all_public_keys(self) -> None:
        r = _make_fake_result()
        d = r.to_dict()
        expected_keys = {
            "filter_name", "resolution", "frame_count",
            "avg_fps", "min_fps", "max_fps",
            "p50_ms", "p95_ms",
            "backend_name", "device_name",
            "platform", "python_version", "hipixel_version", "timestamp",
        }
        assert expected_keys == set(d.keys())

    def test_to_dict_excludes_frame_times(self) -> None:
        r = _make_fake_result()
        d = r.to_dict()
        assert "_frame_times_ms" not in d
        assert "frame_times_ms" not in d

    def test_to_dict_rounds_fps(self) -> None:
        r = _make_fake_result(avg_fps=123.456789)
        d = r.to_dict()
        assert d["avg_fps"] == 123.46

    def test_to_dict_rounds_ms(self) -> None:
        r = _make_fake_result(p50_ms=1.23456)
        d = r.to_dict()
        assert d["p50_ms"] == 1.235

    def test_to_dict_values_correct(self) -> None:
        r = _make_fake_result()
        d = r.to_dict()
        assert d["filter_name"] == "cas"
        assert d["resolution"] == "1280x720"
        assert d["frame_count"] == 10


# ---------------------------------------------------------------------------
# BenchmarkReport
# ---------------------------------------------------------------------------


def _make_fake_report(n: int = 2) -> "BenchmarkReport":
    from hipixel_core.bench.runner import BenchmarkReport

    results = [
        _make_fake_result(filter_name=name)
        for name in ["cas", "aces"][:n]
    ]
    return BenchmarkReport(results=results, device_name="TestCPU", backend_name="cpu")


class TestBenchmarkReport:
    def test_to_json_is_valid_json(self) -> None:
        report = _make_fake_report()
        parsed = json.loads(report.to_json())
        assert isinstance(parsed, dict)

    def test_to_json_structure(self) -> None:
        report = _make_fake_report()
        parsed = json.loads(report.to_json())
        assert "results" in parsed
        assert "device_name" in parsed
        assert "backend_name" in parsed
        assert len(parsed["results"]) == 2

    def test_to_json_result_keys(self) -> None:
        report = _make_fake_report(n=1)
        parsed = json.loads(report.to_json())
        r = parsed["results"][0]
        assert "filter_name" in r
        assert "avg_fps" in r
        assert "p50_ms" in r

    def test_to_markdown_has_header(self) -> None:
        report = _make_fake_report()
        md = report.to_markdown()
        assert "| Filter |" in md
        assert "FPS avg" in md

    def test_to_markdown_contains_filter_names(self) -> None:
        report = _make_fake_report()
        md = report.to_markdown()
        assert "cas" in md
        assert "aces" in md

    def test_to_markdown_separator_row(self) -> None:
        report = _make_fake_report()
        md = report.to_markdown()
        # Must have at least one line of dashes for the table separator
        assert re.search(r"\|[-:]+\|", md)

    def test_to_markdown_empty(self) -> None:
        from hipixel_core.bench.runner import BenchmarkReport

        report = BenchmarkReport(results=[])
        md = report.to_markdown()
        assert "No benchmark results" in md or "_No" in md

    def test_to_markdown_device_metadata(self) -> None:
        report = _make_fake_report()
        md = report.to_markdown()
        assert "TestCPU" in md
        assert "cpu" in md

    def test_save_json(self, tmp_path: Path) -> None:
        report = _make_fake_report()
        out = tmp_path / "results.json"
        report.save(out)
        content = out.read_text()
        parsed = json.loads(content)
        assert "results" in parsed

    def test_save_md(self, tmp_path: Path) -> None:
        report = _make_fake_report()
        out = tmp_path / "results.md"
        report.save(out)
        content = out.read_text()
        assert "| Filter |" in content

    def test_save_fmt_override_json(self, tmp_path: Path) -> None:
        # File extension is .md but fmt="json" → should produce JSON
        report = _make_fake_report()
        out = tmp_path / "results.md"
        report.save(out, fmt="json")
        parsed = json.loads(out.read_text())
        assert "results" in parsed

    def test_save_fmt_override_md(self, tmp_path: Path) -> None:
        report = _make_fake_report()
        out = tmp_path / "results.json"
        report.save(out, fmt="md")
        assert "| Filter |" in out.read_text()

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        report = _make_fake_report()
        out = tmp_path / "deep" / "nested" / "results.json"
        report.save(out)
        assert out.exists()


# ---------------------------------------------------------------------------
# BenchmarkRunner (CPU, no model downloads)
# ---------------------------------------------------------------------------


class TestBenchmarkRunner:
    """Integration tests using the real CpuBackend + CAS/ACES filters.

    These are intentionally lightweight (frames=5) to stay fast in CI.
    """

    def _runner(self):
        from hipixel_core.bench.runner import BenchmarkRunner

        return BenchmarkRunner(_cpu_backend())

    def test_run_filter_cas_returns_result(self) -> None:
        from hipixel_core.bench.runner import BenchmarkResult

        runner = self._runner()
        result = runner.run_filter("cas", resolution="320x240", frames=5)
        assert isinstance(result, BenchmarkResult)

    def test_run_filter_aces_returns_result(self) -> None:
        from hipixel_core.bench.runner import BenchmarkResult

        runner = self._runner()
        result = runner.run_filter("aces", resolution="320x240", frames=5)
        assert isinstance(result, BenchmarkResult)

    def test_result_filter_name(self) -> None:
        runner = self._runner()
        result = runner.run_filter("cas", resolution="320x240", frames=5)
        assert result.filter_name == "cas"

    def test_result_resolution_canonical(self) -> None:
        runner = self._runner()
        result = runner.run_filter("cas", resolution="720p", frames=5)
        assert result.resolution == "1280x720"

    def test_result_frame_count(self) -> None:
        runner = self._runner()
        result = runner.run_filter("cas", resolution="320x240", frames=7)
        assert result.frame_count == 7

    def test_result_fps_positive(self) -> None:
        runner = self._runner()
        result = runner.run_filter("cas", resolution="320x240", frames=5)
        assert result.avg_fps > 0
        assert result.min_fps > 0
        assert result.max_fps > 0

    def test_result_min_le_avg_le_max(self) -> None:
        runner = self._runner()
        result = runner.run_filter("cas", resolution="320x240", frames=10)
        assert result.min_fps <= result.avg_fps <= result.max_fps

    def test_result_p50_le_p95(self) -> None:
        runner = self._runner()
        result = runner.run_filter("cas", resolution="320x240", frames=10)
        assert result.p50_ms <= result.p95_ms

    def test_result_platform_string(self) -> None:
        import platform

        runner = self._runner()
        result = runner.run_filter("cas", resolution="320x240", frames=5)
        assert result.platform == platform.system().lower()

    def test_result_timestamp_is_iso(self) -> None:
        runner = self._runner()
        result = runner.run_filter("cas", resolution="320x240", frames=5)
        # Must be a valid ISO-8601 datetime
        dt = datetime.datetime.fromisoformat(result.timestamp)
        assert dt.tzinfo is not None  # must be timezone-aware

    def test_result_backend_name(self) -> None:
        runner = self._runner()
        result = runner.run_filter("cas", resolution="320x240", frames=5)
        assert result.backend_name == "cpu"

    def test_result_has_frame_times(self) -> None:
        runner = self._runner()
        result = runner.run_filter("cas", resolution="320x240", frames=5)
        assert len(result._frame_times_ms) == 5
        assert all(t > 0 for t in result._frame_times_ms)

    def test_run_filter_checkerboard_pattern(self) -> None:
        runner = self._runner()
        result = runner.run_filter(
            "cas", resolution="320x240", frames=5, pattern="checkerboard"
        )
        assert result.avg_fps > 0

    def test_run_cpu_filters_returns_report(self) -> None:
        from hipixel_core.bench.runner import BenchmarkReport

        runner = self._runner()
        report = runner.run_cpu_filters(resolution="320x240", frames=5)
        assert isinstance(report, BenchmarkReport)

    def test_run_cpu_filters_both_present(self) -> None:
        runner = self._runner()
        report = runner.run_cpu_filters(resolution="320x240", frames=5)
        names = {r.filter_name for r in report.results}
        assert names == {"cas", "aces"}

    def test_run_cpu_filters_device_name(self) -> None:
        runner = self._runner()
        report = runner.run_cpu_filters(resolution="320x240", frames=5)
        assert report.device_name  # non-empty
        assert report.backend_name == "cpu"

    def test_run_cpu_filters_to_json_roundtrip(self) -> None:
        runner = self._runner()
        report = runner.run_cpu_filters(resolution="320x240", frames=5)
        parsed = json.loads(report.to_json())
        assert len(parsed["results"]) == 2

    def test_auto_backend_init(self) -> None:
        """BenchmarkRunner with no backend arg auto-selects and runs.

        We force CPU here to avoid a coremltools/CUDA dependency at import time
        on machines where those extras are not installed.
        """
        import unittest.mock as mock

        from hipixel_core.backends.cpu import CpuBackend
        from hipixel_core.bench.runner import BenchmarkResult, BenchmarkRunner

        cpu = CpuBackend()
        cpu.initialize()
        with mock.patch(
            "hipixel_core.backends.selector.select_backend", return_value=cpu
        ):
            runner = BenchmarkRunner()  # owns backend
        result = runner.run_filter("cas", resolution="320x240", frames=3)
        assert isinstance(result, BenchmarkResult)
        assert result.avg_fps > 0
