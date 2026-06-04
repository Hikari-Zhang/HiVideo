"""
InferenceBackend Protocol — the core GPU abstraction.

Every hardware backend (CoreML, CUDA, DirectML, OpenVINO, CPU) implements
this Protocol.  The Pipeline interacts with backends *only* through this
interface, ensuring full pluggability.

Phase 2.5: This Protocol will be mirrored 1:1 as a Rust trait, and the
Python classes here will become thin PyO3 wrappers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import numpy as np

    from hipixel_core.types import DeviceInfo


@runtime_checkable
class InferenceBackend(Protocol):
    """Protocol defining the interface for all hardware inference backends.

    Implementors:
        - :class:`~hipixel_core.backends.cpu.CpuBackend`
        - :class:`~hipixel_core.backends.coreml.CoreMLBackend`
        - :class:`~hipixel_core.backends.cuda.CudaBackend`
        - :class:`~hipixel_core.backends.directml.DirectMLBackend`  (Phase 4)
        - :class:`~hipixel_core.backends.openvino.OpenVINOBackend`  (Phase 4)
    """

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Short identifier string, e.g. ``"coreml"``, ``"cuda"``, ``"cpu"``."""
        ...

    @property
    def device_info(self) -> DeviceInfo:
        """Hardware descriptor for this backend instance."""
        ...

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """One-time initialization (driver setup, memory allocation).

        Called by the pipeline before any models are loaded.
        Raises ``BackendInitError`` on failure.
        """
        ...

    def shutdown(self) -> None:
        """Release all allocated resources.

        Safe to call multiple times (idempotent).
        """
        ...

    # ------------------------------------------------------------------
    # Model management
    # ------------------------------------------------------------------

    def load_model(self, model_path: str, model_key: str) -> None:
        """Load an ONNX (or platform-native) model into GPU memory.

        Args:
            model_path:  Absolute path to the model file.
            model_key:   Logical name used to reference this model later,
                         e.g. ``"real_esrgan_x2"``.

        Raises:
            ``ModelLoadError`` if the file is missing, corrupt, or incompatible.
        """
        ...

    def unload_model(self, model_key: str) -> None:
        """Remove a model from GPU memory.

        No-op if ``model_key`` is not currently loaded.
        """
        ...

    def is_model_loaded(self, model_key: str) -> bool:
        """Return True if the model is currently resident in GPU memory."""
        ...

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def run(
        self,
        inputs: dict[str, np.ndarray],
        model_key: str,
    ) -> dict[str, np.ndarray]:
        """Execute a single forward pass through the specified model.

        Args:
            inputs:     Named input tensors. Array dtype and shape must
                        match the model's expected input spec.
            model_key:  Which loaded model to run.

        Returns:
            Named output tensors as NumPy arrays.

        Raises:
            ``InferenceError`` on execution failure.
        """
        ...

    # ------------------------------------------------------------------
    # VRAM management
    # ------------------------------------------------------------------

    def available_vram_mb(self) -> int:
        """Return currently available VRAM in megabytes.

        Returns 0 for CPU-only backends.
        """
        ...

    def warmup(self, model_key: str, input_shape: tuple[int, ...]) -> None:
        """Run a single dummy forward pass to warm up JIT / driver caches.

        Args:
            model_key:    Model to warm up (must already be loaded).
            input_shape:  Expected input tensor shape (N, C, H, W).
        """
        ...
