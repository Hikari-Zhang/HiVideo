"""
Filter pipeline — orchestrates multi-step AI enhancement.

The Pipeline ties together:
    1. Video decoding (VideoDecoder)
    2. Sequential filter application (Filter chain)
    3. Video encoding (VideoEncoder)

with a 3-thread producer-consumer architecture:
    Thread 1: decode frames → queue_in
    Thread 2: apply filters  queue_in → queue_out
    Thread 3: encode frames  queue_out →

Progress events are emitted via an optional callback.

Phase 2.5: The Python threading model will be replaced by
a Rust tokio async executor with zero-copy frame passing.
"""

from __future__ import annotations

import queue
import threading
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

from hipixel_core._log import get_logger
from hipixel_core.types import FilterParams, PipelineResult, ProgressEvent
from hipixel_core._fps_tracker import FpsTracker

_log = get_logger("pipeline")

if TYPE_CHECKING:
    from hipixel_core.backends.base import InferenceBackend
    from hipixel_core.filters.base import Filter
    from hipixel_core.types import OutputSpec, VideoFrame, VideoMeta


#: Sentinel value placed in queues to signal end of stream.
_EOS = object()

#: Queue depth for raw decoded frames (uint8, ~6 MB each at 1080p).
_QUEUE_DEPTH_IN = 4

#: Queue depth for processed frames (float32, up to 377 MB each at 4× 1080p).
#: Keep small to prevent the process worker from racing ahead of the encoder
#: and filling RAM with fully-upscaled frames.
_QUEUE_DEPTH_OUT = 2


class Pipeline:
    """Sequential AI enhancement pipeline.

    Usage::

        pipeline = Pipeline(
            filters=[NAFNetFilter(), RealESRGANFilter(), CASFilter()],
            filter_params=[{"strength": 0.7}, {"scale": 2}, {"sharpness": 0.4}],
        )
        result = pipeline.run(
            source=meta,
            output_spec=spec,
            backend=backend,
            progress_cb=lambda e: print(f"{e.progress_pct:.1f}%"),
        )
    """

    def __init__(
        self,
        filters: list[Filter],
        filter_params: list[FilterParams] | None = None,
    ) -> None:
        self._filters = filters
        self._params = filter_params or [{} for _ in filters]
        if len(self._params) != len(self._filters):
            raise ValueError(
                f"filter_params length ({len(self._params)}) must match "
                f"filters length ({len(self._filters)})"
            )
        # True when setup() was called externally; run() skips lifecycle.
        self._is_setup: bool = False

    # ------------------------------------------------------------------
    # Class-level factory
    # ------------------------------------------------------------------

    @classmethod
    def from_preset(cls, preset: dict[str, Any]) -> Pipeline:
        """Construct a Pipeline from a parsed preset dictionary.

        Args:
            preset:  Parsed preset JSON (as returned by PresetManager).

        Returns:
            A new Pipeline instance ready for ``.run()``.
        """
        from hipixel_core.filters import get_filter

        filters: list[Any] = []
        params: list[FilterParams] = []
        for step in preset.get("filters", []):
            f = get_filter(step["filter"])
            filters.append(f)
            params.append(step.get("params", {}))
        return cls(filters=filters, filter_params=params)

    # ------------------------------------------------------------------
    # Lifecycle helpers (public)
    # ------------------------------------------------------------------

    def setup(
        self,
        backend: InferenceBackend,
        status_cb: Callable[[str], None] | None = None,
    ) -> None:
        """Load models and warm up all filters.

        Calling this before :meth:`run` allows the CLI to display a dedicated
        spinner during the (potentially long) CoreML first-run compilation
        phase, separate from the encoding progress bar.

        On partial failure the already-set-up filters are torn down before
        re-raising so the process is left in a clean state.

        Args:
            backend:   Initialized :class:`InferenceBackend`.
            status_cb: Optional callback invoked with each filter's name just
                       before its ``setup()`` is called — useful for updating
                       a CLI spinner with the current filter.
        """
        _log.debug("Pipeline.setup: filters=%s", [f.name for f in self._filters])
        try:
            for filt, params in zip(self._filters, self._params, strict=True):
                if status_cb:
                    status_cb(filt.name)
                filt.setup(backend, params)
        except Exception:
            # Partial setup — unload whatever was already loaded.
            self.teardown(backend)
            raise
        self._is_setup = True

    def teardown(self, backend: InferenceBackend) -> None:
        """Unload all filter models.

        Warns on individual failures instead of raising so that a single
        misbehaving filter does not prevent the others from being cleaned up.
        """
        for filt, _params in zip(self._filters, self._params, strict=True):
            try:
                filt.teardown(backend)
            except Exception as exc:
                _log.warning("Filter %s teardown failed: %s", filt.name, exc)
        self._is_setup = False

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(
        self,
        source: VideoMeta,
        output_spec: OutputSpec,
        backend: InferenceBackend,
        progress_cb: Callable[[ProgressEvent], None] | None = None,
    ) -> PipelineResult:
        """Process a video file end-to-end.

        If :meth:`setup` was already called externally this method skips the
        setup / teardown lifecycle and only runs the encode pipeline, leaving
        teardown responsibility with the caller.

        Args:
            source:      Metadata from ``video.probe()``.
            output_spec: Desired output encoding parameters.
            backend:     Initialized InferenceBackend.
            progress_cb: Optional callback invoked every ~1 second.

        Returns:
            :class:`PipelineResult` describing the completed run.
        """
        start = time.monotonic()
        error: str | None = None
        externally_managed = self._is_setup

        filter_names = [f.name for f in self._filters]
        _log.debug(
            "Pipeline.run: filters=%s source=%s", filter_names, source.path
        )

        try:
            if not externally_managed:
                # Set up all filters inline (convenience / backward-compat path)
                for filt, params in zip(self._filters, self._params, strict=True):
                    filt.setup(backend, params)

            # Run 3-thread pipeline
            self._run_threaded(source, output_spec, backend, progress_cb)

        except Exception as exc:
            error = str(exc)
            _log.error("Pipeline error: %s", exc)
        finally:
            if not externally_managed:
                # Tear down all filters — warn on individual teardown failures
                for filt, _params in zip(self._filters, self._params, strict=True):
                    try:
                        filt.teardown(backend)
                    except Exception as exc:
                        _log.warning("Filter %s teardown failed: %s", filt.name, exc)

        elapsed = time.monotonic() - start
        # Count total frames processed (from source meta as approximation)
        frames = source.frame_count if error is None else 0
        avg_fps = frames / elapsed if elapsed > 0 else 0.0

        if error is None:
            _log.info(
                "Pipeline complete: %d frames in %.1fs (%.1f fps)",
                frames, elapsed, avg_fps,
            )

        return PipelineResult(
            success=error is None,
            output_path=output_spec.path,
            frames_processed=frames,
            elapsed_s=elapsed,
            avg_fps=avg_fps,
            backend_used=backend.name,
            error=error,
        )

    # ------------------------------------------------------------------
    # Threading internals
    # ------------------------------------------------------------------

    def _run_threaded(
        self,
        source: VideoMeta,
        output_spec: OutputSpec,
        backend: InferenceBackend,
        progress_cb: Callable[[ProgressEvent], None] | None,
    ) -> None:
        """Spin up 3 threads: decode → process → encode."""
        from hipixel_core.video.decoder import decode_frames
        from hipixel_core.video.encoder import VideoEncoder

        q_in: queue.Queue[Any] = queue.Queue(maxsize=_QUEUE_DEPTH_IN)
        q_out: queue.Queue[Any] = queue.Queue(maxsize=_QUEUE_DEPTH_OUT)

        errors: list[Exception] = []

        def decode_worker() -> None:
            _log.debug("decode_worker starting")
            frame_count = 0
            try:
                for frame in decode_frames(source):
                    q_in.put(frame)
                    frame_count += 1
            except Exception as exc:
                errors.append(exc)
            finally:
                q_in.put(_EOS)
                _log.debug("decode_worker done, %d frames queued", frame_count)

        def process_worker() -> None:
            _log.debug("process_worker starting")
            frame_idx = 0
            try:
                while True:
                    item = q_in.get()
                    if item is _EOS:
                        _log.debug("process_worker: received EOS after %d frames", frame_idx)
                        break
                    frame: VideoFrame = item
                    _log.debug("process_worker: processing frame %d", frame_idx)
                    for filt, params in zip(self._filters, self._params, strict=True):
                        t0 = time.monotonic()
                        frame = filt.process_frame(frame, backend, params)
                        elapsed_ms = (time.monotonic() - t0) * 1000
                        _log.debug(
                            "process_worker: frame %d — %s: %.0f ms",
                            frame_idx, filt.name, elapsed_ms,
                        )
                    _log.debug("process_worker: frame %d done, putting to q_out", frame_idx)
                    q_out.put(frame)
                    _log.debug("process_worker: frame %d queued to q_out", frame_idx)
                    frame_idx += 1
            except Exception as exc:
                _log.error("process_worker error: %s", exc)
                errors.append(exc)
            finally:
                q_out.put(_EOS)
                _log.debug("process_worker done, total frames: %d", frame_idx)

        def encode_worker() -> None:
            _log.debug("encode_worker starting")
            frame_idx = 0
            t_start = time.monotonic()
            t_last_report = t_start
            tracker = FpsTracker(window=30)
            upstream_ok = False

            enc = VideoEncoder(source, output_spec)
            try:
                _log.debug("encode_worker: opening encoder")
                enc.open()
                _log.debug("encode_worker: encoder opened")
                while True:
                    _log.debug("encode_worker: waiting for frame from q_out")
                    item = q_out.get()
                    _log.debug("encode_worker: got item from q_out")
                    if item is _EOS:
                        _log.debug("encode_worker: received EOS")
                        upstream_ok = not bool(errors)
                        break
                    _log.debug("encode_worker: writing frame %d", frame_idx)
                    enc.write(item)
                    _log.debug("encode_worker: frame %d written", frame_idx)
                    frame_idx += 1

                    now = time.monotonic()
                    tracker.tick(now)
                    elapsed = now - t_start
                    fps_avg = frame_idx / elapsed if elapsed > 0 else 0.0

                    if progress_cb and (now - t_last_report) >= 1.0:
                        try:
                            event = ProgressEvent(
                                frame_index=frame_idx,
                                total_frames=source.frame_count,
                                elapsed_s=elapsed,
                                fps_current=tracker.fps_current,
                                fps_avg=fps_avg,
                            )
                            progress_cb(event)
                            t_last_report = now
                        except Exception as exc:
                            _log.debug("encode_worker: progress_cb error: %s", exc)
            except Exception as exc:
                _log.error("encode_worker error: %s", exc)
                errors.append(exc)
            finally:
                try:
                    _log.debug("encode_worker: closing encoder, upstream_ok=%s", upstream_ok)
                    enc.close(do_mux=upstream_ok)
                    _log.debug("encode_worker: encoder closed")
                except Exception as exc:
                    _log.error("encode_worker: close error: %s", exc)
                    errors.append(exc)
            _log.debug("encode_worker done: %d frames encoded", frame_idx)

        threads = [
            threading.Thread(target=decode_worker, name="hpc-decode", daemon=True),
            threading.Thread(target=process_worker, name="hpc-process", daemon=True),
            threading.Thread(target=encode_worker, name="hpc-encode", daemon=True),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        if errors:
            raise errors[0]

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        names = [f.name for f in self._filters]
        return f"Pipeline(filters={names})"
