"""
Tests for InferenceBackend implementations.

GPU tests are guarded with pytest markers so they only run
on machines with the appropriate hardware.
"""

from __future__ import annotations

import numpy as np
import pytest

from hipixel_core.backends.selector import list_available_backends, select_backend


class TestRemapInputs:
    """Unit tests for the _remap_inputs tensor-name normalisation helper."""

    def _fn(
        self,
        inputs: dict[str, np.ndarray],
        model_names: list[str],
    ) -> dict[str, np.ndarray]:
        from hipixel_core.backends.cpu import _remap_inputs

        return _remap_inputs(inputs, model_names)

    def test_passthrough_when_names_match(self) -> None:
        arr = np.zeros((1, 3, 64, 64), dtype=np.float32)
        inputs = {"input": arr}
        result = self._fn(inputs, ["input"])
        assert result is inputs  # same object, no copy

    def test_remap_single_input_different_name(self) -> None:
        arr = np.zeros((1, 3, 64, 64), dtype=np.float32)
        inputs = {"input": arr}  # caller says "input"
        result = self._fn(inputs, ["x"])  # model wants "x"
        assert set(result.keys()) == {"x"}
        assert result["x"] is arr

    def test_remap_preserves_tensor_values(self) -> None:
        a = np.ones((1, 3, 4, 4), dtype=np.float32) * 2
        b = np.ones((1, 3, 4, 4), dtype=np.float32) * 5
        inputs = {"in0": a, "in1": b}
        result = self._fn(inputs, ["lq", "ref"])
        assert np.array_equal(result["lq"], a)
        assert np.array_equal(result["ref"], b)

    def test_remap_onnx_default_name(self) -> None:
        """PyTorch ONNX export without input_names often generates 'input.1'."""
        arr = np.zeros((1,), dtype=np.float32)
        inputs = {"input": arr}
        result = self._fn(inputs, ["input.1"])
        assert "input.1" in result
        assert result["input.1"] is arr

    def test_passthrough_multiple_matching(self) -> None:
        a, b = np.zeros(1, dtype=np.float32), np.ones(1, dtype=np.float32)
        inputs = {"x": a, "y": b}
        result = self._fn(inputs, ["x", "y"])
        assert result is inputs


class TestBackendSelector:
    def test_select_cpu_explicit(self) -> None:
        backend = select_backend(force="cpu")
        assert backend.name == "cpu"

    def test_select_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown backend"):
            select_backend(force="nonexistent")

    def test_list_available_includes_cpu(self) -> None:
        available = list_available_backends()
        assert "cpu" in available

    def test_auto_select_returns_backend(self) -> None:
        backend = select_backend()
        assert backend.name in ("coreml", "cuda", "directml", "openvino", "cpu")


class TestCpuBackend:
    def _make_backend(self) -> object:
        from hipixel_core.backends.cpu import CpuBackend

        be = CpuBackend()
        be.initialize()
        return be

    def test_name(self) -> None:
        from hipixel_core.backends.cpu import CpuBackend

        assert CpuBackend.name == "cpu"

    def test_device_info_no_gpu(self) -> None:
        be = self._make_backend()
        di = be.device_info  # type: ignore[attr-defined]
        assert di.has_gpu is False
        assert di.total_vram_mb == 0

    def test_available_vram_returns_zero(self) -> None:
        be = self._make_backend()
        assert be.available_vram_mb() == 0  # type: ignore[attr-defined]

    def test_is_model_loaded_false_before_load(self) -> None:
        be = self._make_backend()
        assert be.is_model_loaded("nonexistent") is False  # type: ignore[attr-defined]

    def test_shutdown_idempotent(self) -> None:
        be = self._make_backend()
        be.shutdown()  # type: ignore[attr-defined]
        be.shutdown()  # Should not raise

    def test_run_without_init_raises(self) -> None:
        from hipixel_core.backends.cpu import CpuBackend

        be = CpuBackend()
        with pytest.raises(RuntimeError, match="not initialized"):
            be.load_model("some/path.onnx", "key")


@pytest.mark.coreml
class TestCoreMLBackend:
    """CoreML backend tests — only run on macOS Apple Silicon."""

    def test_initialize_without_onnxruntime(self) -> None:
        """Should raise ImportError if onnxruntime is not installed."""
        import sys
        import unittest.mock as mock

        with mock.patch.dict(sys.modules, {"onnxruntime": None}):
            # Force reimport of coreml module so it picks up the patched sys.modules
            import importlib

            import hipixel_core.backends.coreml as coreml_mod
            importlib.reload(coreml_mod)
            be = coreml_mod.CoreMLBackend()
            with pytest.raises(ImportError, match="onnxruntime"):
                be.initialize()

    def test_initialize_raises_when_coreml_ep_unavailable(self) -> None:
        """Should raise RuntimeError when CoreMLExecutionProvider is absent."""
        import unittest.mock as mock

        with mock.patch(
            "onnxruntime.get_available_providers",
            return_value=["CPUExecutionProvider"],
        ):
            from hipixel_core.backends.coreml import CoreMLBackend

            be = CoreMLBackend()
            with pytest.raises(RuntimeError, match="CoreMLExecutionProvider"):
                be.initialize()
