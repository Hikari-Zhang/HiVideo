"""
Video encoder — writes VideoFrame sequences to disk via FFmpeg.

Uses ``ffmpeg-python`` to encode a stream of RGB frames to a compressed
video file, optionally copying the source audio track.

Supported output codecs: h264, h265 (HEVC), av1, prores.

Phase 2.5: This will be replaced by a Rust encoder for zero-copy
GPU→disk pipeline.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hipixel_core.types import OutputSpec, VideoFrame, VideoMeta


class VideoEncoder:
    """Stream-based video encoder.

    Usage::

        encoder = VideoEncoder(meta, spec)
        with encoder:
            for frame in processed_frames:
                encoder.write(frame)

    The encoder automatically copies the source audio on close.
    """

    def __init__(self, source_meta: VideoMeta, output_spec: OutputSpec) -> None:
        self._meta = source_meta
        self._spec = output_spec
        self._process: subprocess.Popen[bytes] | None = None
        self._frame_count = 0

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> VideoEncoder:
        self.open()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()  # do_mux=True: standalone callers always mux on exit

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Start the FFmpeg encoding process."""
        from pathlib import Path

        fps = self._spec.resolved_fps(self._meta.fps)
        w, h = self._resolve_output_resolution()
        codec = self._codec_to_ffmpeg(self._spec.codec)

        cmd = [
            "ffmpeg",
            "-y",  # overwrite
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{w}x{h}",
            "-r",
            str(fps),
            "-i",
            "pipe:0",  # stdin
            "-vcodec",
            codec,
            "-crf",
            str(self._spec.crf),
            "-pix_fmt",
            "yuv420p",
        ]

        # -movflags +faststart is an MP4/MOV-specific optimisation that places
        # the moov atom at the start of the file for progressive playback.
        # It is not valid for MKV (EBML-based) or other containers and will
        # cause FFmpeg to exit with an error when the output path is .mkv.
        if Path(self._spec.path).suffix.lower() in {".mp4", ".mov", ".m4v"}:
            cmd += ["-movflags", "+faststart"]

        cmd.append(self._spec.path)

        self._process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    def write(self, frame: VideoFrame) -> None:
        """Write a single frame to the encoder.

        Args:
            frame:  Frame to encode (will be converted to uint8 RGB).
        """
        if self._process is None or self._process.stdin is None:
            raise RuntimeError("Encoder is not open. Call open() first.")
        uint8_frame = frame.to_uint8()
        self._process.stdin.write(uint8_frame.data.tobytes())
        self._frame_count += 1

    def close(self, *, do_mux: bool = True) -> None:
        """Flush and finalize the output file.

        Args:
            do_mux:  When *True* (the default), audio is re-muxed from the
                     source after encoding if ``output_spec.audio_copy`` is set.
                     Pass *False* when the pipeline had upstream errors so we
                     skip muxing a potentially incomplete/truncated output.
        """
        if self._process is not None:
            if self._process.stdin:
                self._process.stdin.close()
            ret_code = self._process.wait()
            stderr_output = (
                self._process.stderr.read().decode(errors="replace").strip()
                if self._process.stderr
                else ""
            )
            self._process = None

            if ret_code != 0:
                detail = f": {stderr_output}" if stderr_output else ""
                raise RuntimeError(
                    f"FFmpeg encoding failed (exit {ret_code}){detail}. "
                    f"Output path: {self._spec.path!r}"
                )

            # Mux audio from source if requested *and* encode was clean
            if do_mux and self._spec.audio_copy and self._meta.audio_streams:
                self._mux_audio()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_output_resolution(self) -> tuple[int, int]:
        """Return (width, height) for the output."""
        spec = self._spec.resolution
        if spec == "source":
            return self._meta.width, self._meta.height
        if spec == "2x":
            return self._meta.width * 2, self._meta.height * 2
        if spec == "4x":
            return self._meta.width * 4, self._meta.height * 4
        # Explicit WxH
        if "x" in spec.lower():
            w_s, h_s = spec.lower().split("x")
            return int(w_s), int(h_s)
        return self._meta.width, self._meta.height

    @staticmethod
    def _codec_to_ffmpeg(codec: str) -> str:
        mapping = {
            "h264": "libx264",
            "h265": "libx265",
            "hevc": "libx265",
            "av1": "libsvtav1",
            "prores": "prores_ks",
        }
        return mapping.get(codec.lower(), "libx265")

    def _mux_audio(self) -> None:
        """Re-mux encoded video with source audio using FFmpeg."""
        from pathlib import Path

        out_path = Path(self._spec.path)
        # Preserve the original container extension so FFmpeg can auto-detect
        # the format correctly.  e.g. anime_ep01_4k.mkv → anime_ep01_4k.nomux.tmp.mkv
        tmp_path = out_path.with_name(
            out_path.stem + ".nomux.tmp" + out_path.suffix
        )

        # Rename the video-only file to the temp path
        out_path.rename(tmp_path)

        # Sanity-check: refuse to mux an empty file (corrupt / truncated encode)
        if tmp_path.stat().st_size == 0:
            tmp_path.rename(out_path)
            raise RuntimeError(
                f"Audio mux aborted: encoded output is empty: {tmp_path!r}"
            )

        cmd = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(tmp_path),  # video-only (correct extension for format detection)
            "-i",
            self._meta.path,  # original (for audio)
            "-map",
            "0:v:0",
            "-map",
            "1:a?",  # copy all audio streams if present
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            str(out_path),
        ]
        try:
            result = subprocess.run(cmd, check=True, capture_output=True)
            tmp_path.unlink(missing_ok=True)
        except subprocess.CalledProcessError as exc:
            # Restore the video-only file so the user retains the encoded video
            # even when audio muxing fails.
            if tmp_path.exists() and not out_path.exists():
                tmp_path.rename(out_path)
            stderr = exc.stderr.decode(errors="replace").strip() if exc.stderr else ""
            detail = f": {stderr}" if stderr else ""
            raise RuntimeError(
                f"Audio mux failed (exit {exc.returncode}){detail}"
            ) from exc
        except Exception:
            if tmp_path.exists() and not out_path.exists():
                tmp_path.rename(out_path)
            raise

    @property
    def frames_written(self) -> int:
        return self._frame_count

    def __repr__(self) -> str:
        return (
            f"VideoEncoder(output={self._spec.path!r}, "
            f"codec={self._spec.codec}, frames={self._frame_count})"
        )
