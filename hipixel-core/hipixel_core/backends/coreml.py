"""
CoreML / MPS backend — Apple Silicon acceleration via ONNX Runtime CoreML EP.

Uses ``onnxruntime``'s built-in ``CoreMLExecutionProvider`` to run ONNX models
on Apple Silicon (Neural Engine + GPU).  No manual ONNX-to-CoreML conversion
is needed; the execution provider handles the delegation internally.

``coremltools`` is **not** required.  The ``CoreMLExecutionProvider`` is
bundled in the standard ``onnxruntime`` wheel on macOS arm64 since v1.14.

Requires:
    - macOS 12+ with Apple Silicon (M1 or later)
    - ``onnxruntime >= 1.18`` (already a base dependency)
"""

from __future__ import annotations

import platform
import sys
import time
from typing import Any

import numpy as np

from hipixel_core._log import get_logger
from hipixel_core.types import DeviceInfo

_log = get_logger("backends.coreml")


class CoreMLBackend:
    """Apple CoreML / Metal Performance Shaders inference backend.

    Delegates ONNX model execution to Apple's ANE, GPU, and CPU via
    ``onnxruntime``'s ``CoreMLExecutionProvider``.  Falls back to
    ``CPUExecutionProvider`` for any op the CoreML EP cannot handle.
    """

    name: str = "coreml"

    def __init__(self) -> None:
        self._sessions: dict[str, Any] = {}  # model_key -> ort.InferenceSession
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def device_info(self) -> DeviceInfo:
        vram = self._probe_unified_memory_mb()
        return DeviceInfo(
            backend_name="coreml",
            device_name=f"Apple {platform.machine()} (CoreML)",
            total_vram_mb=vram,
            available_vram_mb=vram,  # Unified memory; approximate
            platform=sys.platform,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Verify that onnxruntime's CoreML EP is available on this machine."""
        _log.debug("CoreMLBackend.initialize")
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise ImportError(
                "onnxruntime is required. Install it with: pip install onnxruntime"
            ) from exc

        available = ort.get_available_providers()
        if "CoreMLExecutionProvider" not in available:
            raise RuntimeError(
                "CoreMLExecutionProvider is not available on this machine. "
                "It requires macOS 12+ on Apple Silicon with onnxruntime >= 1.14. "
                f"Available providers: {available}"
            )

        self._initialized = True
        _log.debug("CoreMLBackend ready — CoreMLExecutionProvider available")

    def shutdown(self) -> None:
        _log.debug("CoreMLBackend.shutdown: releasing %d sessions", len(self._sessions))
        self._sessions.clear()
        self._initialized = False

    # ------------------------------------------------------------------
    # Model management
    # ------------------------------------------------------------------

    # Models that should NOT use CoreML EP via ONNX Runtime.
    # real_esrgan: The exported ONNX declares output as [1,3,H,W] (4D) but
    # CoreML EP infers a 5D output {1,1,3,H*scale,W*scale}, causing a rank
    # mismatch crash at warmup.  Use the native .mlpackage path instead
    # (ModelManager prefers .mlpackage when coremltools is available).
    _COREML_BLACKLIST: frozenset[str] = frozenset({
        "real_esrgan",
        "realesrgan",
    })

    # Models that have native .mlpackage support (bypass ONNX CoreML EP entirely)
    _NATIVE_COREML_MODELS: frozenset[str] = frozenset({
        "real_esrgan_x4plus",
        "realesrgan_x4plus",
    })

    def load_model(self, model_path: str, model_key: str) -> None:
        """Load a model and bind it to the CoreML execution provider.

        Supports two model formats:
        1. ONNX (.onnx) — Uses ONNX Runtime's CoreML EP
        2. CoreML (.mlpackage) — Uses coremltools directly (bypasses ONNX)

        Attempts two strategies for ONNX models:
        1. CoreML EP — NeuralNetwork format (broadest model compatibility).
        2. CPU-only — silent fallback when CoreML cannot compile the model
           (e.g. unsupported op shapes, complex depthwise convolutions).

        The first CoreML call triggers onnxruntime's internal compilation;
        the compiled artifact is cached automatically in ``~/Library/Caches``.

        Idempotent: if ``model_key`` is already loaded the existing session is
        reused and no new session/model is created.
        """
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")

        if model_key in self._sessions:
            _log.debug(
                "CoreMLBackend.load_model: %s already loaded — reusing existing session",
                model_key,
            )
            return

        import os
        model_ext = os.path.splitext(model_path)[1].lower()

        if model_ext == ".mlpackage":
            # Native CoreML model — use coremltools directly
            self._load_coreml_native(model_path, model_key)
        elif model_ext == ".onnx":
            # ONNX model — use ONNX Runtime with CoreML EP
            self._load_onnx_with_coreml_ep(model_path, model_key)
        else:
            raise ValueError(
                f"Unsupported model format: {model_ext}. "
                "Supported formats: .onnx, .mlpackage"
            )

    def _load_coreml_native(self, model_path: str, model_key: str) -> None:
        """Load native CoreML .mlpackage model using coremltools."""
        _log.debug("CoreMLBackend: loading native CoreML model %s", model_key)

        try:
            import coremltools as ct
        except ImportError as exc:
            raise ImportError(
                "coremltools is required for .mlpackage models. "
                "Install it with: pip install coremltools"
            ) from exc

        try:
            # Load with ANE + GPU + CPU compute units
            model = ct.models.MLModel(
                model_path,
                compute_units=ct.ComputeUnit.ALL,
            )
            self._sessions[model_key] = model
            _log.info(
                "CoreMLBackend: %s loaded as native CoreML (ANE/GPU/CPU)",
                model_key,
            )
        except Exception as exc:
            _log.error(
                "CoreMLBackend: Failed to load native CoreML model %s: %s",
                model_key, exc,
            )
            raise

    def _load_onnx_with_coreml_ep(self, model_path: str, model_key: str) -> None:
        """Load ONNX model with CoreML EP (original implementation)."""
        import onnxruntime as ort

        _log.debug("CoreMLBackend.load_model: key=%s path=%s", model_key, model_path)

        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        # Silence onnxruntime's C++ WARNING messages
        opts.log_severity_level = 3

        # Check if model is blacklisted from CoreML (e.g., dynamic axes issues)
        model_lower = model_key.lower()
        use_coreml = not any(blk in model_lower for blk in self._COREML_BLACKLIST)

        if use_coreml:
            coreml_providers: list[Any] = [
                "CoreMLExecutionProvider",
                "CPUExecutionProvider",
            ]

            try:
                session = ort.InferenceSession(
                    model_path, sess_options=opts, providers=coreml_providers
                )
                active = session.get_providers()
                if "CoreMLExecutionProvider" in active:
                    _log.warning("CoreMLBackend: %s running on CoreML EP (ANE/GPU)", model_key)
                else:
                    _log.warning(
                        "CoreMLBackend: CoreML EP was not selected for %s — running on CPU",
                        model_key,
                    )
            except Exception as exc:
                _log.warning(
                    "CoreMLBackend: CoreML EP failed for %s (%s); falling back to CPU only",
                    model_key, exc,
                )
                use_coreml = False
        else:
            _log.warning(
                "CoreMLBackend: %s is blacklisted from CoreML EP — using CPU only",
                model_key,
            )

        # CPU-only fallback
        if not use_coreml:
            session = ort.InferenceSession(
                model_path,
                sess_options=opts,
                providers=["CPUExecutionProvider"],
            )
            _log.debug("CoreMLBackend.load_model: %s loaded (CPU only)", model_key)

        self._sessions[model_key] = session

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
        """Run inference via CoreML (ONNX EP or native CoreML).

        Supports both:
        - ONNX Runtime session (for .onnx files with CoreML EP)
        - Native CoreML MLModel (for .mlpackage files)
        """
        model = self._sessions.get(model_key)
        if model is None:
            raise KeyError(f"Model '{model_key}' is not loaded.")

        # Check if this is a native CoreML model (has 'predict' method)
        if hasattr(model, 'predict'):
            return self._run_native_coreml(model, inputs, model_key)
        else:
            return self._run_onnx_coreml_ep(model, inputs)

    def _run_native_coreml(
        self,
        model: Any,
        inputs: dict[str, np.ndarray],
        model_key: str,
    ) -> dict[str, np.ndarray]:
        """Run inference using native CoreML model (coremltools)."""
        import time

        # Get input description from model spec
        input_description = model.get_spec().description.input
        coreml_inputs = {}

        for i, inp in enumerate(input_description):
            inp_name = inp.name
            if i < len(inputs):
                # Use the input tensor provided by caller
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

    def _run_onnx_coreml_ep(
        self,
        session: Any,
        inputs: dict[str, np.ndarray],
    ) -> dict[str, np.ndarray]:
        """Run inference using ONNX Runtime with CoreML EP."""
        input_names = [inp.name for inp in session.get_inputs()]
        if not all(k in input_names for k in inputs):
            inputs = {name: v for name, v in zip(input_names, inputs.values())}

        output_names = [out.name for out in session.get_outputs()]
        results = session.run(output_names, inputs)
        return dict(zip(output_names, results))

    # ------------------------------------------------------------------
    # VRAM / warmup
    # ------------------------------------------------------------------

    def available_vram_mb(self) -> int:
        """Apple Silicon uses unified memory; return a rough estimate."""
        return self._probe_unified_memory_mb()

    def warmup(self, model_key: str, input_shape: tuple[int, ...]) -> None:
        """Run three forward passes to ensure CoreML compilation completes.

        Uses reproducible random floats in ``[0.1, 0.5]`` rather than zeros.
        Zero tensors can be short-circuited by ANE graph optimisers, causing
        the actual first production inference to trigger a full ANE cold-start
        instead of benefiting from the warmup.

        **Why three rounds?**  CoreML's ``NeuralNetwork`` EP starts async ANE
        compilation on the *first* ``session.run()`` call and returns in ~1 s.
        The *second* call blocks until compilation finishes (4–8 minutes on
        first run).  The *third* call confirms steady-state ANE/GPU latency.
        Running all three here moves the blocking wait into the setup spinner
        (where the user already expects a long delay) rather than silently
        stalling the encoding progress bar at 0%.
        """
        model = self._sessions.get(model_key)
        if model is None:
            raise KeyError(f"Model '{model_key}' is not loaded.")

        # Get input description based on model type
        dummy_inputs = self._build_dummy_inputs(model, input_shape)

        # Run warmup passes
        for i in range(3):
            t0 = time.monotonic()
            self.run(dummy_inputs, model_key)
            elapsed_ms = (time.monotonic() - t0) * 1000
            if elapsed_ms > 5_000:
                _log.warning(
                    "warmup round %d/3: %.0f ms — CoreML compilation in progress",
                    i + 1, elapsed_ms,
                )
            else:
                _log.debug("warmup round %d/3: %.0f ms", i + 1, elapsed_ms)

    def _build_dummy_inputs(
        self,
        model: Any,
        input_shape: tuple[int, ...],
    ) -> dict[str, np.ndarray]:
        """Build dummy input dictionary for warmup.

        Handles both:
        - ONNX Runtime session (has get_inputs())
        - Native CoreML MLModel (has get_spec().description.input)
        """
        rng = np.random.default_rng(0)
        dummy: dict[str, np.ndarray] = {}

        if hasattr(model, 'get_inputs'):
            # ONNX Runtime session
            for inp in model.get_inputs():
                shape: tuple[int, ...] = tuple(
                    d if isinstance(d, int) and d > 0 else input_shape[i]
                    for i, d in enumerate(inp.shape)
                )
                dummy[inp.name] = rng.uniform(0.1, 0.5, shape).astype(np.float32)
        elif hasattr(model, 'get_spec'):
            # Native CoreML MLModel
            input_desc = model.get_spec().description.input
            for i, inp in enumerate(input_desc):
                # Get shape from model spec
                shape = []
                for dim in inp.type.multiArrayType.shape:
                    if dim == -1:  # Dynamic dimension
                        shape.append(input_shape[i] if i < len(input_shape) else 512)
                    else:
                        shape.append(dim)
                shape = tuple(shape)
                dummy[inp.name] = rng.uniform(0.1, 0.5, shape).astype(np.float32)
        else:
            _log.warning("Unknown model type in warmup: %s", type(model).__name__)

        return dummy

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
        loaded = list(self._sessions.keys())
        return f"CoreMLBackend(initialized={self._initialized}, loaded={loaded})"
