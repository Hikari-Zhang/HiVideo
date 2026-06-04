"""
Tests for the PresetManager.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from hipixel_core.presets.manager import PresetManager


class TestPresetManager:
    def test_list_builtin_non_empty(self) -> None:
        presets = PresetManager.list_builtin()
        assert len(presets) >= 10

    def test_list_builtin_contains_expected(self) -> None:
        presets = PresetManager.list_builtin()
        assert "old-film-revival" in presets
        assert "anime-enhance-2x" in presets
        assert "denoise-only" in presets
        assert "bw-restoration" in presets
        assert "hdr-compatible" in presets
        assert "smooth-60fps" in presets

    def test_load_old_film_revival(self) -> None:
        p = PresetManager.load("old-film-revival")
        assert p.id == "old-film-revival"
        assert len(p.filters) == 3
        assert p.filters[0].filter == "nafnet"
        assert p.filters[1].filter == "real_esrgan"
        assert p.filters[2].filter == "cas"

    def test_load_denoise_only_single_filter(self) -> None:
        p = PresetManager.load("denoise-only")
        assert len(p.filters) == 1
        assert p.filters[0].filter == "nafnet"

    def test_load_unknown_raises_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError, match="Preset not found"):
            PresetManager.load("this-does-not-exist")

    def test_load_custom_json_file(self) -> None:
        custom = {
            "id": "custom-test",
            "filters": [{"filter": "cas", "params": {"sharpness": 0.3}}],
            "output": {"resolution": "source", "fps": "preserve", "codec": "h264", "crf": 22},
        }
        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump(custom, f)
            tmp_path = f.name

        try:
            p = PresetManager.load(tmp_path)
            assert p.id == "custom-test"
            assert p.filters[0].filter == "cas"
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_as_pipeline_dict_structure(self) -> None:
        p = PresetManager.load("old-film-revival")
        d = PresetManager.as_pipeline_dict(p)
        assert "filters" in d
        assert "output" in d
        assert d["filters"][0]["filter"] == "nafnet"

    def test_crf_validation(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            from hipixel_core.presets.manager import OutputConfig

            OutputConfig(crf=100)  # invalid

    def test_requirements_defaults(self) -> None:
        p = PresetManager.load("sharpen-only")
        assert p.requirements.min_vram_mb == 0  # CPU-only preset


class TestNewPresets:
    def test_bw_restoration_loads(self) -> None:
        p = PresetManager.load("bw-restoration")
        assert p.id == "bw-restoration"
        assert len(p.filters) == 3
        assert p.filters[0].filter == "nafnet"
        assert p.filters[0].params["strength"] == 0.8
        assert p.filters[1].filter == "real_esrgan"
        assert p.filters[2].filter == "cas"

    def test_bw_restoration_vram(self) -> None:
        p = PresetManager.load("bw-restoration")
        assert p.requirements.min_vram_mb == 4096

    def test_hdr_compatible_loads(self) -> None:
        p = PresetManager.load("hdr-compatible")
        assert p.id == "hdr-compatible"
        assert len(p.filters) == 2
        assert p.filters[0].filter == "aces"
        assert p.filters[1].filter == "cas"

    def test_hdr_compatible_no_vram(self) -> None:
        p = PresetManager.load("hdr-compatible")
        assert p.requirements.min_vram_mb == 0
        assert p.requirements.recommended_vram_mb == 0

    def test_hdr_compatible_source_resolution(self) -> None:
        p = PresetManager.load("hdr-compatible")
        assert p.output.resolution == "source"

    def test_hdr_compatible_aces_params(self) -> None:
        p = PresetManager.load("hdr-compatible")
        aces_params = p.filters[0].params
        assert aces_params["method"] == "aces_fitted"
        assert aces_params["gamma"] == "srgb"
        assert aces_params["exposure"] == 1.0

    def test_smooth_60fps_loads(self) -> None:
        p = PresetManager.load("smooth-60fps")
        assert p.id == "smooth-60fps"
        assert len(p.filters) == 2
        assert p.filters[0].filter == "nafnet"
        assert p.filters[1].filter == "rife"

    def test_smooth_60fps_target(self) -> None:
        p = PresetManager.load("smooth-60fps")
        assert p.output.fps == "60"
        assert p.output.resolution == "source"

    def test_smooth_60fps_rife_params(self) -> None:
        p = PresetManager.load("smooth-60fps")
        rife_params = p.filters[1].params
        assert rife_params["target_fps"] == 60
        assert rife_params["model"] == "RIFE_v4.6"
