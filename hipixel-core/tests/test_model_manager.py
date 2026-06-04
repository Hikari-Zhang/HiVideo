"""
Tests for ModelManager — download, cache, and integrity verification.

All tests use temporary files / patched registries so no real network
traffic is required.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_registry(entries: dict[str, Any]) -> dict[str, Any]:
    return {"version": "1", "models": entries}


def _manager_with_registry(
    registry: dict[str, Any],
    cache_dir: Path,
) -> Any:
    """Return a fresh ModelManager pointed at a temp cache and custom registry."""
    from hipixel_core.models.manager import ModelManager

    mgr = ModelManager  # class, not instance
    mgr._registry = registry  # inject test registry
    with mock.patch("hipixel_core.models.manager._CACHE_DIR", cache_dir):
        yield mgr
    mgr._registry = None  # reset for other tests


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------


class TestRegistryLoading:
    def setup_method(self) -> None:
        from hipixel_core.models.manager import ModelManager

        ModelManager._registry = None  # force fresh load

    def test_list_registry_returns_list(self) -> None:
        from hipixel_core.models.manager import ModelManager

        entries = ModelManager.list_registry()
        assert isinstance(entries, list)
        assert len(entries) > 0

    def test_registry_has_realesrgan_x2plus(self) -> None:
        from hipixel_core.models.manager import ModelManager

        names = {
            name
            for name in ModelManager._load_registry().get("models", {})
        }
        assert "RealESRGAN_x2plus" in names

    def test_registry_has_nafnet_reds(self) -> None:
        from hipixel_core.models.manager import ModelManager

        names = {
            name
            for name in ModelManager._load_registry().get("models", {})
        }
        assert "NAFNet-REDS-width64" in names

    def test_realesrgan_x2plus_url_is_onnx(self) -> None:
        from hipixel_core.models.manager import ModelManager

        entry = ModelManager._load_registry()["models"]["RealESRGAN_x2plus"]
        assert entry["url"].endswith(".onnx") or "onnx" in entry["url"].lower(), (
            f"Expected .onnx URL, got: {entry['url']}"
        )

    def test_nafnet_reds_url_is_onnx(self) -> None:
        from hipixel_core.models.manager import ModelManager

        entry = ModelManager._load_registry()["models"]["NAFNet-REDS-width64"]
        assert entry["url"].endswith(".onnx") or "onnx" in entry["url"].lower(), (
            f"Expected .onnx URL, got: {entry['url']}"
        )

    def test_realesrgan_x2plus_has_nonzero_size(self) -> None:
        from hipixel_core.models.manager import ModelManager

        entry = ModelManager._load_registry()["models"]["RealESRGAN_x2plus"]
        assert entry["size_bytes"] > 0

    def test_nafnet_reds_has_nonzero_size(self) -> None:
        from hipixel_core.models.manager import ModelManager

        entry = ModelManager._load_registry()["models"]["NAFNet-REDS-width64"]
        assert entry["size_bytes"] > 0

    def teardown_method(self) -> None:
        from hipixel_core.models.manager import ModelManager

        ModelManager._registry = None


# ---------------------------------------------------------------------------
# get_model_path cache behaviour
# ---------------------------------------------------------------------------


class TestGetModelPathCache:
    """Verify the size_bytes=0 cache fix and normal cache hit logic."""

    def _patched_manager(self, tmp_path: Path) -> Any:
        from hipixel_core.models.manager import ModelManager

        ModelManager._registry = None
        return ModelManager

    def test_returns_cached_file_when_size_matches(self, tmp_path: Path) -> None:
        from hipixel_core.models.manager import ModelManager

        registry = _make_registry(
            {
                "dummy_model": {
                    "filename": "dummy.onnx",
                    "url": "https://example.com/dummy.onnx",
                    "mirrors": [],
                    "sha256": "",
                    "size_bytes": 42,
                    "scale": 1,
                    "type": "test",
                    "description": "test",
                    "version": "0",
                }
            }
        )
        # Plant a fake cached file of the right size
        fake_file = tmp_path / "dummy.onnx"
        fake_file.write_bytes(b"x" * 42)

        ModelManager._registry = registry
        with mock.patch("hipixel_core.models.manager._CACHE_DIR", tmp_path):
            path = ModelManager.get_model_path("dummy_model", auto_download=False)

        assert path == str(fake_file)
        ModelManager._registry = None

    def test_trusts_cached_file_when_size_bytes_zero(self, tmp_path: Path) -> None:
        """When size_bytes=0 (unknown), an existing cache file is accepted as-is."""
        from hipixel_core.models.manager import ModelManager

        registry = _make_registry(
            {
                "unknown_size_model": {
                    "filename": "unknown.onnx",
                    "url": "https://example.com/unknown.onnx",
                    "mirrors": [],
                    "sha256": "",
                    "size_bytes": 0,
                    "scale": 1,
                    "type": "test",
                    "description": "test",
                    "version": "0",
                }
            }
        )
        fake_file = tmp_path / "unknown.onnx"
        fake_file.write_bytes(b"y" * 1000)

        ModelManager._registry = registry
        with mock.patch("hipixel_core.models.manager._CACHE_DIR", tmp_path):
            path = ModelManager.get_model_path("unknown_size_model", auto_download=False)

        assert path == str(fake_file)
        ModelManager._registry = None

    def test_raises_file_not_found_when_not_cached_and_no_download(
        self, tmp_path: Path
    ) -> None:
        from hipixel_core.models.manager import ModelManager

        registry = _make_registry(
            {
                "missing_model": {
                    "filename": "missing.onnx",
                    "url": "https://example.com/missing.onnx",
                    "mirrors": [],
                    "sha256": "",
                    "size_bytes": 0,
                    "scale": 1,
                    "type": "test",
                    "description": "test",
                    "version": "0",
                }
            }
        )
        ModelManager._registry = registry
        with mock.patch("hipixel_core.models.manager._CACHE_DIR", tmp_path):
            with pytest.raises(FileNotFoundError):
                ModelManager.get_model_path("missing_model", auto_download=False)
        ModelManager._registry = None


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestModelManagerErrors:
    def setup_method(self) -> None:
        from hipixel_core.models.manager import ModelManager

        ModelManager._registry = None

    def test_unknown_model_raises(self) -> None:
        from hipixel_core.models.manager import ModelManager, ModelNotFoundError

        with pytest.raises(ModelNotFoundError, match="not found in registry"):
            ModelManager._get_entry("does_not_exist_xyz")

    def test_list_cached_returns_list(self, tmp_path: Path) -> None:
        from hipixel_core.models.manager import ModelManager

        with mock.patch("hipixel_core.models.manager._CACHE_DIR", tmp_path):
            result = ModelManager.list_cached()
        assert isinstance(result, list)

    def teardown_method(self) -> None:
        from hipixel_core.models.manager import ModelManager

        ModelManager._registry = None
