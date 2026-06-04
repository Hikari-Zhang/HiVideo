"""
Backend auto-selector.

Probes the current platform and selects the highest-priority
InferenceBackend available.

Priority order (per design doc):
    1. CoreML/MPS  — Apple Silicon
    2. CUDA        — NVIDIA GPU
    3. DirectML    — Windows AMD/Intel  (Phase 4)
    4. OpenVINO    — Intel GPU          (Phase 4)
    5. CPU         — universal fallback
"""

from __future__ import annotations

import platform
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hipixel_core.backends.base import InferenceBackend


# ---------------------------------------------------------------------------
# Platform probes
# ---------------------------------------------------------------------------


def _is_apple_silicon() -> bool:
    """True when running on macOS with an Apple Silicon chip."""
    return sys.platform == "darwin" and platform.machine() == "arm64"


def _has_coreml() -> bool:
    """True when on Apple Silicon *and* onnxruntime's CoreML EP is available."""
    if not _is_apple_silicon():
        return False
    try:
        import onnxruntime as ort

        return "CoreMLExecutionProvider" in ort.get_available_providers()
    except ImportError:
        return False


def _has_cuda_gpu() -> bool:
    """True when onnxruntime-gpu is installed and a CUDA device is present."""
    try:
        import onnxruntime as ort

        return "CUDAExecutionProvider" in ort.get_available_providers()
    except ImportError:
        return False


def _is_windows_dml() -> bool:
    """True on Windows with DirectML support (Phase 4)."""
    return sys.platform == "win32"


def _has_intel_gpu() -> bool:
    """True if OpenVINO runtime is available (Phase 4)."""
    try:
        import openvino  # noqa: F401

        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Backend priority table
# ---------------------------------------------------------------------------

#: (probe_fn, backend_factory) pairs, evaluated in order.
_BACKEND_PRIORITY: list[tuple[str, object]] = [
    ("coreml", _has_coreml),
    ("cuda", _has_cuda_gpu),
    ("directml", _is_windows_dml),  # Phase 4
    ("openvino", _has_intel_gpu),  # Phase 4
    ("cpu", lambda: True),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def select_backend(force: str | None = None) -> InferenceBackend:
    """Instantiate and return the best available InferenceBackend.

    Args:
        force:  If given, bypass auto-detection and return the named backend.
                Valid values: ``"coreml"``, ``"cuda"``, ``"directml"``,
                ``"openvino"``, ``"cpu"``.

    Returns:
        An uninitialized ``InferenceBackend`` instance.
        Call ``.initialize()`` before use.

    Raises:
        ``ValueError`` if ``force`` names an unknown backend.
        ``RuntimeError`` if no backend could be selected (should never happen
        because CPU is always available).
    """
    from hipixel_core.backends.coreml import CoreMLBackend
    from hipixel_core.backends.cpu import CpuBackend
    from hipixel_core.backends.cuda import CudaBackend

    _factory_map: dict[str, type[InferenceBackend]] = {
        "coreml": CoreMLBackend,
        "cuda": CudaBackend,
        "cpu": CpuBackend,
        # "directml": DirectMLBackend,  # Phase 4
        # "openvino": OpenVINOBackend,  # Phase 4
    }

    if force is not None:
        if force not in _factory_map:
            raise ValueError(f"Unknown backend '{force}'. Available: {', '.join(_factory_map)}")
        return _factory_map[force]()

    for backend_name, probe in _BACKEND_PRIORITY:
        if callable(probe) and probe():
            factory = _factory_map.get(backend_name)
            if factory is not None:
                return factory()

    raise RuntimeError("No inference backend available (this should not happen).")


def list_available_backends() -> list[str]:
    """Return names of backends that pass their hardware probe."""
    available: list[str] = []
    for backend_name, probe in _BACKEND_PRIORITY:
        if callable(probe) and probe():
            available.append(backend_name)
    return available
