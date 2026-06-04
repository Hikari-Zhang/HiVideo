"""
Native CoreML backend — Apple Silicon acceleration using coremltools.

Loads and runs native .mlpackage models directly via coremltools,
bypassing ONNX Runtime entirely. This gives the best ANE compatibility
and performance for models that have been converted to CoreML format.

Requires:
    - macOS 12+ with Apple Silicon (M1 or later)
    - coremltools >= 7.0
    - Native .mlpackage model file
"""

from __future__ import annotations

import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

from hipixel_core._log import get_logger
from hipixel_core.types import DeviceInfo

_log = get_logger("backends.coreml_native")


class CoreMLNativeBackend:
    """Native Apple CoreML inference backend using coremltools.

    Loads .mlpackage models directly and runs inference on ANE/GPU/CPU.
    This is the preferred backend for Apple Silicon as it:
    - Avoids ONNX Runtime's CoreML EP shape compatibility issues
    - Uses coremltools' optimized ANE compilation
    - Supports static and dynamic input shapes
    """

    name: str = "coreml_native"

    def __init__(self) -> None:
        self._models: dict[str, Any] = {}  # model_key -> MLModel
        self._initialized: bool = False
        self._compute_units: Any = None

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def device_info(self) -> DeviceInfo:
        vram = self._probe_unified_memory_mb()
        return DeviceInfo(
            backend_name="coreml_native",
            device_name=f"Apple {platform.machine()} (CoreML Native)",
            total_vram_mb=vram,
            available_vram_mb=vram,
            platform=sys.platform,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Verify that coremltools is available and working."""
        _log.debug("CoreMLNativeBackend.initialize")
        try:
            import coremltools as ct
        except ImportError as exc:
            raise ImportError(
                "coremltools is required. Install it with: pip install coremltools"
            ) from exc

        # Test that we can at least import the MLModel class
        try:
            from coremltools.models import MLModel
        except Exception as exc:
            raise RuntimeError(
                f"coremltools installation is broken: {exc}"
            ) from exc

        self._initialized = True
        _log.debug("CoreMLNativeBackend ready — coremltools available")

    def shutdown(self) -> None:
        _log.debug("CoreMLNativeBackend.shutdown: releasing %d models", len(self._models))
        self._models.clear()
        self._initialized = False

    # ------------------------------------------------------------------
    # Model management
    # ------------------------------------------------------------------

    def load_model(self, model_path: str, model_key: str) -> None:
        """Load a native CoreML .mlpackage model.

        Args:
            model_path: Path to the .mlpackage file
            model_key: Unique key to identify this model
        """
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")

        if model_key in self._models:
            _log.debug(
                "CoreMLNativeBackend.load_model: %s already loaded — reusing",
                model_key,
            )
            return

        import coremltools as ct

        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        if not path.suffix == ".mlpackage":
            raise ValueError(
                f"Expected .mlpackage file, got: {path.suffix}"
            )

        _log.debug("CoreMLNativeBackend.load_model: key=%s path=%s", model_key, model_path)

        # Determine compute units (ANE + GPU + CPU by default)
        if self._compute_units is None:
            self._compute_units = ct.ComputeUnit.ALL

        try:
            # Load the model with specified compute units
            model = ct.models.MLModel(
                model_path,
                compute_units=self._compute_units,
            )
            self._models[model_key] = model
            _log.info(
                "CoreMLNativeBackend: %s loaded on %s",
                model_key,
                self._compute_units.name,
            )
        except Exception as exc:
            _log.error(
                "CoreMLNativeBackend: Failed to load %s: %s",
                model_key, exc,
            )
            raise

    def unload_model(self, model_key: str) -> None:
        self._models.pop(model_key, None)

    def is_model_loaded(self, model_key: str) -> bool:
        return model_key in self._models

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def run(
        self,
        inputs: dict[str, np.ndarray],
        model_key: str,
    ) -> dict[str, np.ndarray]:
        """Run inference using the native CoreML model.

        Args:
            inputs: Dictionary of input name -> numpy array
            model_key: Model to use for inference

        Returns:
            Dictionary of output name -> numpy array
        """
        model = self._models.get(model_key)
        if model is None:
            raise KeyError(f"Model '{model_key}' is not loaded.")

        # CoreML expects input as a dictionary with proper key names
        # The input names in the .mlpackage might be different from ONNX
        input_description = model.get_spec().description.input
        coreml_inputs = {}

        for i, inp in enumerate(input_description):
            inp_name = inp.name
            if i < len(inputs):
                # Match by position if names don't match
                input_tensor = list(inputs.values())[i]
                coreml_inputs[inp_name] = input_tensor
            else:
                _log.warning("No input provided for %s", inp_name)

        # Run inference
        try:
            t0 = time.monotonic()
            predictions = model.predict(coreml_inputs)
            elapsed_ms = (time.monotonic() - t0) * 1000
            _log.debug("CoreML Native inference: %.1f ms", elapsed_ms)
        except Exception as exc:
            _log.error("CoreML Native inference failed: %s", exc)
            raise

        # Convert outputs to numpy arrays
        results = {}
        for key, value in predictions.items():
            if hasattr(value, 'numpy'):
                results[key] = value.numpy()
            else:
                results[key] = np.array(value)

        return results

    # ------------------------------------------------------------------
    # VRAM / warmup
    # ------------------------------------------------------------------

    def available_vram_mb(self) -> int:
        """Apple Silicon uses unified memory; return a rough estimate."""
        return self._probe_unified_memory_mb()

    def warmup(self, model_key: str, input_shape: tuple[int, ...]) -> None:
        """Run three forward passes to ensure CoreML compilation completes.

        Similar to the ONNX CoreML EP warmup, this ensures the ANE
        compilation is complete before actual inference.
        """
        model = self._models.get(model_key)
        if model is None:
            raise KeyError(f"Model '{model_key}' is not loaded.")

        # Get input description
        input_description = model.get_spec().description.input

        # Create dummy input
        rng = np.random.default_rng(0)
        dummy_inputs = {}

        for i, inp in enumerate(input_description):
            # Use the input shape from the model spec
            shape = []
            for dim in inp.type.multiArrayType.shape:
                if dim == -1:  # Dynamic dimension
                    shape.append(input_shape[i] if i < len(input_shape) else 512)
                else:
                    shape.append(dim)

            dummy_inputs[inp.name] = rng.uniform(0.1, 0.5, shape).astype(np.float32)

        # Run warmup passes
        for i in range(3):
            t0 = time.monotonic()
            model.predict(dummy_inputs)
            elapsed_ms = (time.monotonic() - t0) * 1000
            if elapsed_ms > 5_000:
                _log.warning(
                    "warmup round %d/3: %.0f ms — CoreML compilation in progress",
                    i + 1, elapsed_ms,
                )
            else:
                _log.debug("warmup round %d/3: %.0f ms", i + 1, elapsed_ms)

    # ------------------------------------------------------------------
    # Compute unit management
    # ------------------------------------------------------------------

    def set_compute_units(self, units: str) -> None:
        """Set compute units for model loading.

        Args:
            units: One of "ALL", "ANE", "GPU", "CPU_ONLY", "CPU_ONLY"
        """
        import coremltools as ct

        unit_map = {
            "ALL": ct.ComputeUnit.ALL,
            "ANE": ct.ComputeUnit.ANE,
            "GPU": ct.ComputeUnit.GPU_ONLY,
            "CPU_ONLY": ct.ComputeUnit.CPU_ONLY,
            "CPU": ct.ComputeUnit.CPU_ONLY,
        }

        if units.upper() not in unit_map:
            raise ValueError(
                f"Invalid compute units: {units}. "
                f"Must be one of: {list(unit_map.keys())}"
            )

        self._compute_units = unit_map[units.upper()]
        _log.info("CoreMLNativeBackend: compute units set to %s", units)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _probe_unified_memory_mb() -> int:
        """Read total unified memory from sysctl; return 60% as usable estimate."""
        try:
            import subprocess

            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                check=True,
            )
            total_bytes = int(result.stdout.strip())
            return int(total_bytes / 1024 / 1024 * 0.6)
        except Exception:
            return 0

    def __repr__(self) -> str:
        loaded = list(self._models.keys())
        return f"CoreMLNativeBackend(initialized={self._initialized}, loaded={loaded})"
