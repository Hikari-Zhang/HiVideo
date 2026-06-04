"""
CUDA backend — NVIDIA GPU acceleration via ONNX Runtime CUDA EP.

Requires:
    - CUDA 11.8+ or 12.x
    - cuDNN 8.9+ compatible with the installed CUDA toolkit
    - ``onnxruntime-gpu`` extra: ``pip install hipixel-core[cuda]``

Note:
    ``onnxruntime`` and ``onnxruntime-gpu`` cannot be installed simultaneously.
    The ``[cuda]`` extra replaces the base ``onnxruntime`` package.
"""

from __future__ import annotations

import sys
from typing import Any

import numpy as np

from hipixel_core._log import get_logger
from hipixel_core.backends.cpu import _remap_inputs
from hipixel_core.types import DeviceInfo

_log = get_logger("backends.cuda")


class CudaBackend:
    """ONNX Runtime CUDA Execution Provider backend."""

    name: str = "cuda"

    def __init__(self, device_id: int = 0) -> None:
        self._device_id = device_id
        self._sessions: dict[str, Any] = {}  # model_key -> ort.InferenceSession
        self._session_options: Any = None
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            backend_name="cuda",
            device_name=self._probe_gpu_name(),
            total_vram_mb=self._probe_total_vram_mb(),
            available_vram_mb=self.available_vram_mb(),
            platform=sys.platform,
            compute_capability=self._probe_compute_capability(),
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        _log.debug("CudaBackend.initialize: device_id=%d", self._device_id)
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise ImportError(
                "onnxruntime-gpu is required for the CUDA backend. "
                "Install it with: pip install hipixel-core[cuda]"
            ) from exc

        if "CUDAExecutionProvider" not in ort.get_available_providers():
            raise RuntimeError(
                "CUDAExecutionProvider is not available. "
                "Make sure CUDA and cuDNN are installed correctly."
            )

        opts = ort.SessionOptions()
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self._session_options = opts
        self._initialized = True
        _log.debug("CudaBackend ready: %s", self._probe_gpu_name())

    def shutdown(self) -> None:
        _log.debug("CudaBackend.shutdown: releasing %d sessions", len(self._sessions))
        self._sessions.clear()
        self._initialized = False

    # ------------------------------------------------------------------
    # Model management
    # ------------------------------------------------------------------

    def load_model(self, model_path: str, model_key: str) -> None:
        if not self._initialized:
            raise RuntimeError("Backend not initialized. Call initialize() first.")
        import onnxruntime as ort

        _log.debug("CudaBackend.load_model: key=%s path=%s", model_key, model_path)
        providers = [
            ("CUDAExecutionProvider", {"device_id": self._device_id}),
            "CPUExecutionProvider",  # fallback for ops not on CUDA EP
        ]
        session = ort.InferenceSession(
            model_path,
            sess_options=self._session_options,
            providers=providers,
        )
        self._sessions[model_key] = session
        _log.debug("CudaBackend.load_model: %s loaded", model_key)

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
        try:
            import pynvml  # optional

            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(self._device_id)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            return int(info.free / 1024 / 1024)
        except Exception:
            return 0

    def warmup(self, model_key: str, input_shape: tuple[int, ...]) -> None:
        session = self._sessions.get(model_key)
        if session is None:
            raise KeyError(f"Model '{model_key}' is not loaded.")
        input_info = session.get_inputs()
        dummy = {inp.name: np.zeros(input_shape, dtype=np.float32) for inp in input_info[:1]}
        self.run(dummy, model_key)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _probe_gpu_name(self) -> str:
        try:
            import pynvml

            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(self._device_id)
            return str(pynvml.nvmlDeviceGetName(handle).decode())
        except Exception:
            return f"CUDA Device {self._device_id}"

    def _probe_total_vram_mb(self) -> int:
        try:
            import pynvml

            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(self._device_id)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            return int(info.total / 1024 / 1024)
        except Exception:
            return 0

    def _probe_compute_capability(self) -> str | None:
        try:
            import pynvml

            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(self._device_id)
            major, minor = pynvml.nvmlDeviceGetCudaComputeCapability(handle)
            return f"{major}.{minor}"
        except Exception:
            return None

    def __repr__(self) -> str:
        loaded = list(self._sessions.keys())
        return (
            f"CudaBackend(device_id={self._device_id}, "
            f"initialized={self._initialized}, loaded={loaded})"
        )
