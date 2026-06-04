"""
Backend manager — automatically selects the best inference backend.

Chooses between:
- ONNX Runtime (CPU/CoreML EP) for .onnx files
- Native CoreML (coremltools) for .mlpackage files

This allows seamless switching between backends based on model format.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from hipixel_core._log import get_logger
from hipixel_core.backends.base import InferenceBackend
from hipixel_core.types import DeviceInfo

_log = get_logger("backends.manager")


class BackendManager:
    """Manages multiple inference backends and routes models to the best one.

    Automatically selects:
    - Native CoreML backend for .mlpackage files (best for Apple Silicon)
    - ONNX Runtime backends for .onnx files (CPU, CoreML EP, etc.)
    """

    def __init__(self) -> None:
        self._backends: dict[str, InferenceBackend] = {}
        self._model_backend_map: dict[str, str] = {}  # model_key -> backend_name
        self._initialized: bool = False

    def initialize(self) -> None:
        """Initialize all available backends."""
        if self._initialized:
            return

        _log.info("BackendManager: initializing backends...")

        # Try to initialize ONNX Runtime backends
        self._init_onnx_backends()

        # Try to initialize native CoreML backend
        self._init_coreml_native_backend()

        self._initialized = True
        _log.info(
            "BackendManager: initialized %d backend(s): %s",
            len(self._backends),
            list(self._backends.keys()),
        )

    def _init_onnx_backends(self) -> None:
        """Initialize ONNX Runtime-based backends."""
        # CPU backend (always available if onnxruntime is installed)
        try:
            from hipixel_core.backends.onnx_cpu import ONNXCPUBackend

            backend = ONNXCPUBackend()
            backend.initialize()
            self._backends["onnx_cpu"] = backend
            _log.debug("BackendManager: registered onnx_cpu backend")
        except Exception as exc:
            _log.warning("BackendManager: failed to initialize onnx_cpu: %s", exc)

        # CoreML EP backend (macOS only)
        try:
            from hipixel_core.backends.coreml import CoreMLBackend

            backend = CoreMLBackend()
            backend.initialize()
            self._backends["coreml"] = backend
            _log.debug("BackendManager: registered coreml backend (ONNX CoreML EP)")
        except Exception as exc:
            _log.debug("BackendManager: coreml (ONNX) not available: %s", exc)

    def _init_coreml_native_backend(self) -> None:
        """Initialize native CoreML backend (for .mlpackage files)."""
        try:
            from hipixel_core.backends.coreml_native import CoreMLNativeBackend

            backend = CoreMLNativeBackend()
            backend.initialize()
            self._backends["coreml_native"] = backend
            _log.debug("BackendManager: registered coreml_native backend")
        except Exception as exc:
            _log.debug("BackendManager: coreml_native not available: %s", exc)

    def get_backend_for_model(self, model_path: str) -> InferenceBackend:
        """Automatically select the best backend for a model file.

        Args:
            model_path: Path to the model file

        Returns:
            The best available backend for this model format

        Raises:
            RuntimeError: If no suitable backend is available
        """
        if not self._initialized:
            self.initialize()

        path = Path(model_path)
        suffix = path.suffix.lower()

        if suffix == ".mlpackage":
            # Native CoreML model — use coreml_native backend
            if "coreml_native" in self._backends:
                _log.info(
                    "BackendManager: routing %s to coreml_native backend",
                    path.name,
                )
                return self._backends["coreml_native"]
            else:
                raise RuntimeError(
                    f"Native CoreML backend not available for {path.name}. "
                    "Install coremltools: pip install coremltools"
                )
        elif suffix == ".onnx":
            # ONNX model — prefer CoreML EP on Apple Silicon, fall back to CPU
            if "coreml" in self._backends:
                _log.info(
                    "BackendManager: routing %s to coreml backend (ONNX CoreML EP)",
                    path.name,
                )
                return self._backends["coreml"]
            elif "onnx_cpu" in self._backends:
                _log.info(
                    "BackendManager: routing %s to onnx_cpu backend",
                    path.name,
                )
                return self._backends["onnx_cpu"]
            else:
                raise RuntimeError(
                    f"No ONNX backend available for {path.name}. "
                    "Install onnxruntime: pip install onnxruntime"
                )
        else:
            raise ValueError(
                f"Unsupported model format: {suffix}. "
                "Supported formats: .onnx, .mlpackage"
            )

    def load_model(self, model_path: str, model_key: str) -> None:
        """Load a model using the appropriate backend.

        Args:
            model_path: Path to the model file
            model_key: Unique key to identify this model
        """
        backend = self.get_backend_for_model(model_path)
        backend.load_model(model_path, model_key)
        self._model_backend_map[model_key] = backend.name

        _log.info(
            "BackendManager: loaded %s with backend %s",
            model_key,
            backend.name,
        )

    def unload_model(self, model_key: str) -> None:
        """Unload a model from its backend."""
        backend_name = self._model_backend_map.get(model_key)
        if backend_name:
            backend = self._backends.get(backend_name)
            if backend:
                backend.unload_model(model_key)
            del self._model_backend_map[model_key]

    def run_inference(
        self,
        inputs: dict[str, Any],
        model_key: str,
    ) -> dict[str, Any]:
        """Run inference using the correct backend for this model.

        Args:
            inputs: Dictionary of input name -> input data
            model_key: Model to use for inference

        Returns:
            Dictionary of output name -> output data
        """
        backend_name = self._model_backend_map.get(model_key)
        if not backend_name:
            raise KeyError(f"Model '{model_key}' is not loaded.")

        backend = self._backends.get(backend_name)
        if not backend:
            raise RuntimeError(f"Backend '{backend_name}' not found.")

        return backend.run(inputs, model_key)

    def get_loaded_models(self) -> list[str]:
        """Return list of all loaded model keys."""
        return list(self._model_backend_map.keys())

    def get_backend_info(self) -> dict[str, DeviceInfo]:
        """Return device info for all initialized backends."""
        return {
            name: backend.device_info
            for name, backend in self._backends.items()
        }

    def shutdown(self) -> None:
        """Shutdown all backends."""
        _log.info("BackendManager: shutting down all backends...")
        for backend in self._backends.values():
            try:
                backend.shutdown()
            except Exception as exc:
                _log.warning("BackendManager: error shutting down backend: %s", exc)
        self._backends.clear()
        self._model_backend_map.clear()
        self._initialized = False

    def __repr__(self) -> str:
        return (
            f"BackendManager("
            f"initialized={self._initialized}, "
            f"backends={list(self._backends.keys())}, "
            f"loaded_models={len(self._model_backend_map)})"
        )


# Global backend manager instance
_manager: BackendManager | None = None


def get_backend_manager() -> BackendManager:
    """Get the global backend manager instance."""
    global _manager
    if _manager is None:
        _manager = BackendManager()
    return _manager
