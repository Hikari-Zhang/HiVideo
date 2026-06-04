"""
Filter Protocol — the core processing unit abstraction.

Every AI enhancement step (super-resolution, denoising, sharpening, etc.)
implements this Protocol.  Filters are stateless processors; all GPU state
(loaded model weights) lives in the ``InferenceBackend``.

Design principles:
    - Filters never own GPU memory — they borrow the backend.
    - ``process_frame`` must return a *new* VideoFrame (no in-place mutation).
    - Tile splitting for large frames is the filter's responsibility.
    - Filters must be thread-safe if called from the pipeline worker threads.

Phase 2.5: This Protocol will be mirrored as a Rust trait.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from hipixel_core.backends.base import InferenceBackend
    from hipixel_core.types import FilterParams, VideoFrame


@runtime_checkable
class Filter(Protocol):
    """Protocol for all hipixel-core video enhancement filters.

    Implementors:
        - :class:`~hipixel_core.filters.real_esrgan.RealESRGANFilter`
        - :class:`~hipixel_core.filters.anime4k.Anime4KFilter`
        - :class:`~hipixel_core.filters.nafnet.NAFNetFilter`
        - :class:`~hipixel_core.filters.cas.CASFilter`
        - :class:`~hipixel_core.filters.rife.RIFEFilter`
        - :class:`~hipixel_core.filters.deoldify.DeOldifyFilter`  (Phase 1)
    """

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Unique string identifier used in presets, e.g. ``"real_esrgan"``."""
        ...

    @property
    def required_models(self) -> list[str]:
        """List of model registry keys this filter needs.

        The Pipeline will ensure all models are downloaded and loaded
        into the backend before calling ``setup()``.

        Example: ``["RealESRGAN_x2plus"]``
        """
        ...

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def setup(self, backend: InferenceBackend, params: FilterParams) -> None:
        """Prepare the filter for processing.

        Called once before the first ``process_frame()``.  The filter should
        load its model(s) into the backend here.

        Args:
            backend:  Active inference backend with initialized GPU context.
            params:   User-supplied (or preset-supplied) parameters.
        """
        ...

    def teardown(self, backend: InferenceBackend) -> None:
        """Release resources after processing completes.

        The filter should unload its models from the backend here.
        Safe to call if ``setup()`` was never called (idempotent).
        """
        ...

    # ------------------------------------------------------------------
    # Frame processing
    # ------------------------------------------------------------------

    def process_frame(
        self,
        frame: VideoFrame,
        backend: InferenceBackend,
        params: FilterParams,
    ) -> VideoFrame:
        """Process a single frame and return the enhanced result.

        Args:
            frame:    Input frame (must not be mutated).
            backend:  Active inference backend (model already loaded).
            params:   Runtime parameters (same dict passed to ``setup()``).

        Returns:
            A new ``VideoFrame`` with enhanced pixel data.

        Raises:
            ``FilterProcessError`` on inference failure.
        """
        ...

    # ------------------------------------------------------------------
    # Resource estimation
    # ------------------------------------------------------------------

    def estimated_vram_mb(self, input_resolution: tuple[int, int]) -> int:
        """Estimate VRAM usage in MB for the given input resolution.

        Used by the Pipeline to decide tile size and scheduling.

        Args:
            input_resolution:  ``(width, height)`` of the input frame.

        Returns:
            Estimated peak VRAM in megabytes.
        """
        ...
