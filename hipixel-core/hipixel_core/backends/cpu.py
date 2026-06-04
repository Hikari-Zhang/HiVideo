"""
CPU inference backend — universal fallback using ONNX Runtime (CPU EP).

This is the only backend guaranteed to be available on all platforms.
Performance is significantly lower than GPU backends; suitable for
development, testing, and low-end hardware.
"""

from __future__ import annotations

import platform
import sys
from typing import Any

import numpy as np
import onnxruntime as ort

from hipixel_core._log import get_logger
from hipixel_core.types import DeviceInfo

_log = get_logger("backends.cpu")


def _remap_inputs(
    inputs: dict[str, np.ndarray],
    model_input_names: list[str],
) -> dict[str, np.ndarray]:
    """Re-bind caller-supplied tensors to a model's actual input names.

    Community-exported ONNX files sometimes use arbitrary input names
    (``"x"``, ``"input.1"``, ``"lq"``, …) that differ from the
    ``"input"`` key the filters pass.  When all supplied keys are already
    valid model input names the dict is returned as-is.  Otherwise the
    tensors are re-bound by position (first tensor → first model input,
    etc.), which is unambiguous for single-input models and any model
    where the call-site provides values in the correct order.
    """
    if all(k in model_input_names for k in inputs):
        return inputs
    # Positional rebind
    return {name: v for name, v in zip(model_input_names, inputs.values())}


class CpuBackend:
    """ONNX Runtime CPU Execution Provider backend.

    Thread safety: Each ``CpuBackend`` instance holds its own session map.
    Do not share instances across threads without external locking.
    """

    name: str = "cpu"

    def __init__(self) -> None:
        self._sessions: dict[str, ort.InferenceSession] = {}
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            backend_name="cpu",
            device_name=platform.processor() or "CPU",
            total_vram_mb=0,
            available_vram_mb=0,
            platform=sys.platform,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Set up ONNX Runtime session options."""
        _log.debug("CpuBackend.initialize")
        self._session_options = ort.SessionOptions()
        self._session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self._initialized = True
        _log.debug("CpuBackend ready")

    def shutdown(self) -> None:
        """Release all loaded sessions."""
        _log.debug("CpuBackend.shutdown: releasing %d sessions", len(self._sessions))
        self._sessions.clear()
        self._initialized = False

    # ------------------------------------------------------------------
    # Model management
    # ------------------------------------------------------------------

    def load_model(self, model_path: str, model_key: str) -> None:
        """Load an ONNX model using the CPU Execution Provider.

        Args:
            model_path:  Absolute path to ``.onnx`` file.
            model_key:   Logical identifier for later ``run()`` calls.
        """
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")
        _log.debug("CpuBackend.load_model: key=%s path=%s", model_key, model_path)
        providers: list[Any] = ["CPUExecutionProvider"]
        session = ort.InferenceSession(
            model_path,
            sess_options=self._session_options,
            providers=providers,
        )
        self._sessions[model_key] = session
        _log.debug("CpuBackend.load_model: %s loaded", model_key)

    def unload_model(self, model_key: str) -> None:
        self._sessions.pop(model_key, None)

    def is_model_loaded(self, model_key: str) -> bool:
        return model_key in self._sessions

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def run(
        self,
        inputs: dict[str, np.ndarray],
        model_key: str,
    ) -> dict[str, np.ndarray]:
        """Execute a forward pass on the CPU.

        Args:
            inputs:     ``{input_name: np.ndarray}`` mapping.  The keys are
                        matched against the model's actual input names; if they
                        differ (e.g. a community ONNX uses ``"x"`` instead of
                        ``"input"``), the tensors are re-bound by position so
                        the call still succeeds.
            model_key:  Which loaded session to use.

        Returns:
            ``{output_name: np.ndarray}`` mapping.
        """
        session = self._sessions.get(model_key)
        if session is None:
            raise KeyError(f"Model '{model_key}' is not loaded.")
        feed = _remap_inputs(inputs, [inp.name for inp in session.get_inputs()])
        output_names = [o.name for o in session.get_outputs()]
        outputs: list[np.ndarray] = session.run(output_names, feed)
        return dict(zip(output_names, outputs, strict=True))

    # ------------------------------------------------------------------
    # VRAM
    # ------------------------------------------------------------------

    def available_vram_mb(self) -> int:
        """CPU backend has no VRAM; always returns 0."""
        return 0

    def warmup(self, model_key: str, input_shape: tuple[int, ...]) -> None:
        """Run a dummy forward pass to prime the ONNX graph cache."""
        session = self._sessions.get(model_key)
        if session is None:
            raise KeyError(f"Model '{model_key}' is not loaded.")
        input_info = session.get_inputs()
        dummy_inputs = {inp.name: np.zeros(input_shape, dtype=np.float32) for inp in input_info[:1]}
        self.run(dummy_inputs, model_key)

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        loaded = list(self._sessions.keys())
        return f"CpuBackend(initialized={self._initialized}, loaded={loaded})"
