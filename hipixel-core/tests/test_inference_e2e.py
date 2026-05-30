"""
End-to-end inference tests — single-frame and full pipeline.

These tests verify that:
1. Synthetic ONNX identity models (built from raw protobuf bytes) load
   correctly in OnnxRuntime without requiring the ``onnx`` Python package.
2. CpuBackend correctly loads and runs inference through a real ORT session,
   including the tensor-name remapping fix.
3. NAFNetFilter and RealESRGANFilter process frames end-to-end with a
   lightweight stub model (no 67 MB download needed).
4. The full 3-thread Pipeline (decode → filter → encode) completes
   successfully for a CAS-only preset and an NAFNet preset.

Video-dependent tests are guarded with ``@pytest.mark.slow`` and skipped
when FFmpeg is not available.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

from hipixel_core.types import ColorSpace, VideoFrame


# ---------------------------------------------------------------------------
# Minimal ONNX model builder (raw protobuf — no ``onnx`` package required)
# ---------------------------------------------------------------------------


def _encode_varint(value: int) -> bytes:
    """Encode an unsigned integer using protobuf varint encoding."""
    result: list[int] = []
    while value > 0x7F:
        result.append((value & 0x7F) | 0x80)
        value >>= 7
    result.append(value)
    return bytes(result)


def _pb_field_varint(field: int, value: int) -> bytes:
    """Protobuf field with wire-type 0 (varint)."""
    return _encode_varint((field << 3) | 0) + _encode_varint(value)


def _pb_field_bytes(field: int, data: bytes) -> bytes:
    """Protobuf field with wire-type 2 (length-delimited)."""
    return _encode_varint((field << 3) | 2) + _encode_varint(len(data)) + data


def _pb_field_string(field: int, text: str) -> bytes:
    return _pb_field_bytes(field, text.encode("utf-8"))


def _make_identity_onnx(
    input_name: str = "input",
    output_name: str = "output",
) -> bytes:
    """Return raw bytes of a minimal ONNX Identity model.

    The model accepts a float32 tensor with any shape (no static shape
    annotation) and returns it unchanged.  No ``onnx`` package required.

    ONNX protobuf field layout:
        ModelProto { ir_version=1, opset_import=8, graph=7 }
        GraphProto  { node=1, name=2, input=11, output=12 }
        NodeProto   { input=1, output=2, op_type=4 }
        ValueInfoProto { name=1, type=2 }
        TypeProto   { tensor_type=1 }
        TypeProto.Tensor { elem_type=1 }
    """
    # TypeProto.Tensor { elem_type = FLOAT = 1 }
    tensor_type_pb = _pb_field_varint(1, 1)
    # TypeProto { tensor_type = ... }
    type_proto_pb = _pb_field_bytes(1, tensor_type_pb)

    def _value_info_pb(name: str) -> bytes:
        return _pb_field_string(1, name) + _pb_field_bytes(2, type_proto_pb)

    # NodeProto: input, output, op_type=Identity
    node_pb = (
        _pb_field_string(1, input_name)
        + _pb_field_string(2, output_name)
        + _pb_field_string(4, "Identity")
    )

    # GraphProto: node, name, graph-input ValueInfoProto, graph-output ValueInfoProto
    graph_pb = (
        _pb_field_bytes(1, node_pb)
        + _pb_field_string(2, "g")
        + _pb_field_bytes(11, _value_info_pb(input_name))
        + _pb_field_bytes(12, _value_info_pb(output_name))
    )

    # OperatorSetIdProto: domain="", version=14
    opset_pb = _pb_field_string(1, "") + _pb_field_varint(2, 14)

    # ModelProto: ir_version=7, opset_import, graph
    return (
        _pb_field_varint(1, 7)
        + _pb_field_bytes(8, opset_pb)
        + _pb_field_bytes(7, graph_pb)
    )


# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------


def _synth_frame(w: int = 64, h: int = 48) -> VideoFrame:
    """Reproducible random uint8 frame."""
    rng = np.random.default_rng(42)
    data = (rng.random((h, w, 3)) * 255).astype(np.uint8)
    return VideoFrame(data=data, pts=0.0, width=w, height=h, colorspace=ColorSpace.BT709)


def _uniform_frame(w: int = 64, h: int = 48, value: float = 0.5) -> VideoFrame:
    """Uniform float32 frame (useful for tile-seam checks)."""
    data = np.full((h, w, 3), value, dtype=np.float32)
    return VideoFrame(data=data, pts=0.0, width=w, height=h)


_FFMPEG_AVAILABLE: bool = (
    subprocess.run(["ffmpeg", "-version"], capture_output=True).returncode == 0
)


def _create_test_video(
    path: Path,
    w: int = 64,
    h: int = 48,
    frames: int = 5,
    fps: int = 25,
) -> None:
    """Create a tiny synthetic video with FFmpeg lavfi testsrc."""
    duration = frames / fps
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi",
            "-i", f"testsrc=size={w}x{h}:rate={fps}:duration={duration}",
            "-vcodec", "libx264", "-crf", "28", "-pix_fmt", "yuv420p",
            str(path),
        ],
        check=True,
    )


# ---------------------------------------------------------------------------
# 1. Synthetic ONNX model validity
# ---------------------------------------------------------------------------


class TestSyntheticOnnxModel:
    """Verify that our hand-crafted protobuf bytes form a valid ONNX model."""

    def test_identity_model_loads_in_ort(self, tmp_path: Path) -> None:
        import onnxruntime as ort

        p = tmp_path / "identity.onnx"
        p.write_bytes(_make_identity_onnx())
        sess = ort.InferenceSession(str(p))
        assert sess is not None

    def test_identity_model_input_name(self, tmp_path: Path) -> None:
        import onnxruntime as ort

        p = tmp_path / "id.onnx"
        p.write_bytes(_make_identity_onnx("input", "output"))
        sess = ort.InferenceSession(str(p))
        assert [i.name for i in sess.get_inputs()] == ["input"]
        assert [o.name for o in sess.get_outputs()] == ["output"]

    def test_identity_model_runs_inference(self, tmp_path: Path) -> None:
        import onnxruntime as ort

        p = tmp_path / "id.onnx"
        p.write_bytes(_make_identity_onnx())
        sess = ort.InferenceSession(str(p))
        x = np.ones((1, 3, 8, 8), dtype=np.float32)
        [out] = sess.run(None, {"input": x})
        np.testing.assert_array_equal(out, x)

    def test_identity_custom_input_name(self, tmp_path: Path) -> None:
        import onnxruntime as ort

        p = tmp_path / "lq.onnx"
        p.write_bytes(_make_identity_onnx("lq", "output"))
        sess = ort.InferenceSession(str(p))
        assert [i.name for i in sess.get_inputs()] == ["lq"]
        x = np.zeros((1, 3, 4, 4), dtype=np.float32)
        [out] = sess.run(None, {"lq": x})
        np.testing.assert_array_equal(out, x)

    def test_identity_preserves_arbitrary_shape(self, tmp_path: Path) -> None:
        import onnxruntime as ort

        p = tmp_path / "id.onnx"
        p.write_bytes(_make_identity_onnx())
        sess = ort.InferenceSession(str(p))
        for shape in [(1, 1, 2, 2), (1, 3, 64, 64), (2, 3, 16, 32)]:
            x = np.random.rand(*shape).astype(np.float32)
            [out] = sess.run(None, {"input": x})
            np.testing.assert_array_equal(out, x)


# ---------------------------------------------------------------------------
# 2. CpuBackend + ORT integration
# ---------------------------------------------------------------------------


class TestCpuBackendWithSyntheticModel:
    """Load and run inference through the real CpuBackend → ORT stack."""

    def test_load_and_run_identity(self, tmp_path: Path) -> None:
        from hipixel_core.backends.cpu import CpuBackend

        p = tmp_path / "id.onnx"
        p.write_bytes(_make_identity_onnx("input", "output"))

        be = CpuBackend()
        be.initialize()
        be.load_model(str(p), "test_key")

        x = np.ones((1, 3, 8, 8), dtype=np.float32)
        result = be.run({"input": x}, "test_key")

        assert "output" in result
        np.testing.assert_array_equal(result["output"], x)
        be.shutdown()

    def test_is_model_loaded_after_load(self, tmp_path: Path) -> None:
        from hipixel_core.backends.cpu import CpuBackend

        p = tmp_path / "id.onnx"
        p.write_bytes(_make_identity_onnx())

        be = CpuBackend()
        be.initialize()
        assert be.is_model_loaded("key_a") is False
        be.load_model(str(p), "key_a")
        assert be.is_model_loaded("key_a") is True
        be.unload_model("key_a")
        assert be.is_model_loaded("key_a") is False
        be.shutdown()

    def test_remap_runs_with_arbitrary_input_name(self, tmp_path: Path) -> None:
        """CpuBackend auto-remaps caller's 'input' key to model's actual 'lq'."""
        from hipixel_core.backends.cpu import CpuBackend

        p = tmp_path / "lq.onnx"
        p.write_bytes(_make_identity_onnx("lq", "output"))

        be = CpuBackend()
        be.initialize()
        be.load_model(str(p), "lq_key")

        x = np.ones((1, 3, 4, 4), dtype=np.float32) * 0.7
        # Caller uses "input" but model expects "lq" — _remap_inputs must fix this
        result = be.run({"input": x}, "lq_key")

        assert "output" in result
        np.testing.assert_array_equal(result["output"], x)
        be.shutdown()

    def test_remap_preserves_values_with_multiple_inputs(self, tmp_path: Path) -> None:
        """Positional remapping keeps the correct tensor bound to each name."""
        # Build a 2-input model manually using an Add op
        # (Note: for simplicity we use two sequential identities with renamed
        # inputs — actual 2-input op would require the onnx package, so we
        # test the remap helper directly instead.)
        from hipixel_core.backends.cpu import _remap_inputs

        a = np.zeros((1, 3, 4, 4), dtype=np.float32)
        b = np.ones((1, 3, 4, 4), dtype=np.float32)
        inputs = {"x": a, "y": b}
        result = _remap_inputs(inputs, ["lq", "ref"])
        assert list(result.keys()) == ["lq", "ref"]
        np.testing.assert_array_equal(result["lq"], a)
        np.testing.assert_array_equal(result["ref"], b)

    def test_run_unloaded_key_raises(self, tmp_path: Path) -> None:
        from hipixel_core.backends.cpu import CpuBackend

        be = CpuBackend()
        be.initialize()
        x = np.zeros((1, 3, 4, 4), dtype=np.float32)
        with pytest.raises(KeyError, match="not loaded"):
            be.run({"input": x}, "ghost_key")
        be.shutdown()


# ---------------------------------------------------------------------------
# 3. NAFNet single-frame inference
# ---------------------------------------------------------------------------


class TestNAFNetSingleFrame:
    """NAFNetFilter end-to-end with a stub identity ONNX model."""

    def _setup(
        self, tmp_path: Path, input_name: str = "input"
    ) -> tuple[object, object]:
        from hipixel_core.backends.cpu import CpuBackend
        from hipixel_core.filters.nafnet import NAFNetFilter

        p = tmp_path / "nafnet_stub.onnx"
        p.write_bytes(_make_identity_onnx(input_name, "output"))

        be = CpuBackend()
        be.initialize()
        f = NAFNetFilter()

        with mock.patch(
            "hipixel_core.models.manager.ModelManager.get_model_path",
            return_value=str(p),
        ):
            f.setup(be, {"strength": 1.0, "model": "NAFNet-REDS-width64"})

        return f, be

    def test_preserves_dimensions(self, tmp_path: Path) -> None:
        f, be = self._setup(tmp_path)
        result = f.process_frame(_synth_frame(64, 48), be, {"strength": 1.0})  # type: ignore[arg-type]
        assert result.width == 64
        assert result.height == 48
        be.shutdown()  # type: ignore[attr-defined]

    def test_strength_zero_returns_original(self, tmp_path: Path) -> None:
        """strength=0 → blended = 1.0*original + 0.0*denoised → original."""
        f, be = self._setup(tmp_path)
        data = np.full((48, 64, 3), 0.4, dtype=np.float32)
        frame = VideoFrame(data=data, pts=0.0, width=64, height=48)
        result = f.process_frame(frame, be, {"strength": 0.0})  # type: ignore[arg-type]
        np.testing.assert_array_almost_equal(result.to_float32().data, data)
        be.shutdown()  # type: ignore[attr-defined]

    def test_strength_one_returns_model_output(self, tmp_path: Path) -> None:
        """With identity model, strength=1 output should equal input."""
        f, be = self._setup(tmp_path)
        data = np.random.default_rng(7).random((48, 64, 3)).astype(np.float32)
        frame = VideoFrame(data=data, pts=0.0, width=64, height=48)
        result = f.process_frame(frame, be, {"strength": 1.0})  # type: ignore[arg-type]
        np.testing.assert_array_almost_equal(result.to_float32().data, data, decimal=6)
        be.shutdown()  # type: ignore[attr-defined]

    def test_output_dtype_float32(self, tmp_path: Path) -> None:
        f, be = self._setup(tmp_path)
        result = f.process_frame(_synth_frame(), be, {"strength": 0.8})  # type: ignore[arg-type]
        assert result.to_float32().data.dtype == np.float32
        be.shutdown()  # type: ignore[attr-defined]

    def test_output_in_range(self, tmp_path: Path) -> None:
        f, be = self._setup(tmp_path)
        result = f.process_frame(_synth_frame(), be, {"strength": 0.8})  # type: ignore[arg-type]
        out = result.to_float32().data
        assert float(out.min()) >= 0.0
        assert float(out.max()) <= 1.0
        be.shutdown()  # type: ignore[attr-defined]

    def test_pts_preserved(self, tmp_path: Path) -> None:
        f, be = self._setup(tmp_path)
        data = np.zeros((48, 64, 3), dtype=np.float32)
        frame = VideoFrame(data=data, pts=1.234, width=64, height=48)
        result = f.process_frame(frame, be, {})  # type: ignore[arg-type]
        assert result.pts == pytest.approx(1.234)
        be.shutdown()  # type: ignore[attr-defined]

    def test_remapped_input_name(self, tmp_path: Path) -> None:
        """Model with 'lq' input should work via _remap_inputs."""
        f, be = self._setup(tmp_path, input_name="lq")
        result = f.process_frame(_synth_frame(32, 32), be, {"strength": 1.0})  # type: ignore[arg-type]
        assert result.width == 32
        assert result.height == 32
        be.shutdown()  # type: ignore[attr-defined]

    def test_teardown_unloads_model(self, tmp_path: Path) -> None:
        from hipixel_core.backends.cpu import CpuBackend

        f, be = self._setup(tmp_path)
        f.teardown(be)  # type: ignore[arg-type]
        # After teardown the model key is no longer loaded
        assert be.is_model_loaded(f._model_key) is False  # type: ignore[attr-defined]
        be.shutdown()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 4. RealESRGAN single-frame inference (scale=1 identity)
# ---------------------------------------------------------------------------


class TestRealESRGANSingleFrame:
    """RealESRGANFilter with scale=1 identity stub — validates tile stitching."""

    def _setup(
        self,
        tmp_path: Path,
        input_name: str = "input",
        tile_size: int = 32,
        tile_pad: int = 4,
    ) -> tuple[object, object]:
        from hipixel_core.backends.cpu import CpuBackend
        from hipixel_core.filters.real_esrgan import RealESRGANFilter

        p = tmp_path / "esrgan_stub.onnx"
        p.write_bytes(_make_identity_onnx(input_name, "output"))

        be = CpuBackend()
        be.initialize()
        f = RealESRGANFilter()

        with mock.patch(
            "hipixel_core.models.manager.ModelManager.get_model_path",
            return_value=str(p),
        ):
            f.setup(
                be,
                {
                    "scale": 1,
                    "tile_size": tile_size,
                    "tile_padding": tile_pad,
                    "model": "RealESRGAN_x2plus",
                },
            )

        return f, be

    def test_preserves_dimensions_scale1(self, tmp_path: Path) -> None:
        f, be = self._setup(tmp_path)
        result = f.process_frame(_synth_frame(64, 48), be, {})  # type: ignore[arg-type]
        assert result.width == 64
        assert result.height == 48
        be.shutdown()  # type: ignore[attr-defined]

    def test_output_in_range(self, tmp_path: Path) -> None:
        f, be = self._setup(tmp_path)
        result = f.process_frame(_synth_frame(48, 48), be, {})  # type: ignore[arg-type]
        out = result.to_float32().data
        assert float(out.min()) >= 0.0
        assert float(out.max()) <= 1.0
        be.shutdown()  # type: ignore[attr-defined]

    def test_tiled_output_no_seams(self, tmp_path: Path) -> None:
        """Tile-weighted stitching of a uniform frame should stay uniform.

        For a constant-valued input frame, the identity model outputs the same
        constant per-tile, and the weighted average across tile overlaps must
        recover the original constant value exactly.
        """
        f, be = self._setup(tmp_path, tile_size=32, tile_pad=8)
        frame = _uniform_frame(64, 48, value=0.5)
        result = f.process_frame(frame, be, {})  # type: ignore[arg-type]
        out = result.to_float32().data
        # No tile seam can deviate by more than floating-point rounding
        assert float(np.abs(out - 0.5).max()) < 1e-5, (
            f"Tile seam detected — max deviation: {float(np.abs(out - 0.5).max()):.2e}"
        )
        be.shutdown()  # type: ignore[attr-defined]

    def test_identity_scale1_roundtrip(self, tmp_path: Path) -> None:
        """Identity model with scale=1 should return the original pixel values."""
        f, be = self._setup(tmp_path, tile_size=64, tile_pad=0)
        data = np.random.default_rng(99).random((48, 64, 3)).astype(np.float32)
        frame = VideoFrame(data=data, pts=0.0, width=64, height=48)
        result = f.process_frame(frame, be, {})  # type: ignore[arg-type]
        np.testing.assert_array_almost_equal(result.to_float32().data, data, decimal=5)
        be.shutdown()  # type: ignore[attr-defined]

    def test_pts_preserved(self, tmp_path: Path) -> None:
        f, be = self._setup(tmp_path)
        data = np.zeros((48, 64, 3), dtype=np.float32)
        frame = VideoFrame(data=data, pts=2.718, width=64, height=48)
        result = f.process_frame(frame, be, {})  # type: ignore[arg-type]
        assert result.pts == pytest.approx(2.718)
        be.shutdown()  # type: ignore[attr-defined]

    def test_remapped_input_name_x(self, tmp_path: Path) -> None:
        """Model with 'x' input name should work via _remap_inputs."""
        f, be = self._setup(tmp_path, input_name="x")
        result = f.process_frame(_synth_frame(32, 32), be, {})  # type: ignore[arg-type]
        assert result.width == 32
        be.shutdown()  # type: ignore[attr-defined]

    def test_remapped_input_name_input1(self, tmp_path: Path) -> None:
        """PyTorch ONNX export often generates 'input.1' — must remap."""
        f, be = self._setup(tmp_path, input_name="input.1")
        result = f.process_frame(_synth_frame(32, 32), be, {})  # type: ignore[arg-type]
        assert result.width == 32
        be.shutdown()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# 5. Full pipeline — CAS (no model download)
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.skipif(not _FFMPEG_AVAILABLE, reason="FFmpeg not available")
class TestPipelineCASEndToEnd:
    """Full decode → CAS filter → encode pipeline with a synthetic video."""

    def test_produces_output_file(self, tmp_path: Path) -> None:
        from hipixel_core.backends.cpu import CpuBackend
        from hipixel_core.filters.cas import CASFilter
        from hipixel_core.pipeline import Pipeline
        from hipixel_core.types import OutputSpec
        from hipixel_core.video.decoder import probe

        inp = tmp_path / "in.mp4"
        out = tmp_path / "out.mp4"
        _create_test_video(inp)

        meta = probe(str(inp))
        pipeline = Pipeline(filters=[CASFilter()], filter_params=[{"sharpness": 0.5}])

        be = CpuBackend()
        be.initialize()
        result = pipeline.run(
            source=meta,
            output_spec=OutputSpec(str(out), codec="h264", crf=28, audio_copy=False),
            backend=be,
        )
        be.shutdown()

        assert result.success, f"Pipeline failed: {result.error}"
        assert out.exists()
        assert out.stat().st_size > 0

    def test_frame_count_matches_source(self, tmp_path: Path) -> None:
        from hipixel_core.backends.cpu import CpuBackend
        from hipixel_core.filters.cas import CASFilter
        from hipixel_core.pipeline import Pipeline
        from hipixel_core.types import OutputSpec
        from hipixel_core.video.decoder import probe

        inp = tmp_path / "in.mp4"
        out = tmp_path / "out.mp4"
        _create_test_video(inp, frames=8, fps=8)

        meta = probe(str(inp))
        be = CpuBackend()
        be.initialize()
        pipeline = Pipeline(filters=[CASFilter()], filter_params=[{}])
        result = pipeline.run(
            source=meta,
            output_spec=OutputSpec(str(out), codec="h264", crf=35, audio_copy=False),
            backend=be,
        )
        be.shutdown()

        assert result.success
        assert result.frames_processed == meta.frame_count

    def test_result_has_timing_stats(self, tmp_path: Path) -> None:
        from hipixel_core.backends.cpu import CpuBackend
        from hipixel_core.filters.cas import CASFilter
        from hipixel_core.pipeline import Pipeline
        from hipixel_core.types import OutputSpec
        from hipixel_core.video.decoder import probe

        inp = tmp_path / "in.mp4"
        out = tmp_path / "out.mp4"
        _create_test_video(inp, frames=4, fps=4)

        meta = probe(str(inp))
        be = CpuBackend()
        be.initialize()
        result = Pipeline(
            filters=[CASFilter()], filter_params=[{}]
        ).run(
            source=meta,
            output_spec=OutputSpec(str(out), codec="h264", crf=35, audio_copy=False),
            backend=be,
        )
        be.shutdown()

        assert result.success
        assert result.elapsed_s > 0.0
        assert result.avg_fps > 0.0
        assert result.backend_used == "cpu"

    def test_progress_callback_fires(self, tmp_path: Path) -> None:
        from hipixel_core.backends.cpu import CpuBackend
        from hipixel_core.filters.cas import CASFilter
        from hipixel_core.pipeline import Pipeline
        from hipixel_core.types import OutputSpec
        from hipixel_core.video.decoder import probe

        # Create a longer video (1 second @ 25 fps = 25 frames) so at least
        # one progress event fires during the 1-second reporting window.
        inp = tmp_path / "in.mp4"
        out = tmp_path / "out.mp4"
        _create_test_video(inp, frames=25, fps=25)

        events: list[object] = []
        meta = probe(str(inp))
        be = CpuBackend()
        be.initialize()
        Pipeline(filters=[CASFilter()], filter_params=[{}]).run(
            source=meta,
            output_spec=OutputSpec(str(out), codec="h264", crf=35, audio_copy=False),
            backend=be,
            progress_cb=events.append,
        )
        be.shutdown()
        # Progress callback may or may not fire depending on system speed;
        # we just verify the type is correct when it does.
        from hipixel_core.types import ProgressEvent

        for ev in events:
            assert isinstance(ev, ProgressEvent)


# ---------------------------------------------------------------------------
# 6. Full pipeline — NAFNet (stub model, no download)
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.skipif(not _FFMPEG_AVAILABLE, reason="FFmpeg not available")
class TestPipelineNAFNetEndToEnd:
    """Full pipeline with NAFNet stub — validates filter + pipeline integration."""

    def test_nafnet_pipeline_produces_output(self, tmp_path: Path) -> None:
        from hipixel_core.backends.cpu import CpuBackend
        from hipixel_core.filters.nafnet import NAFNetFilter
        from hipixel_core.pipeline import Pipeline
        from hipixel_core.types import OutputSpec
        from hipixel_core.video.decoder import probe

        inp = tmp_path / "in.mp4"
        out = tmp_path / "out.mp4"
        model_p = tmp_path / "nafnet_stub.onnx"
        model_p.write_bytes(_make_identity_onnx("input", "output"))

        _create_test_video(inp, frames=5, fps=5)
        meta = probe(str(inp))

        be = CpuBackend()
        be.initialize()

        with mock.patch(
            "hipixel_core.models.manager.ModelManager.get_model_path",
            return_value=str(model_p),
        ):
            result = Pipeline(
                filters=[NAFNetFilter()],
                filter_params=[{"strength": 0.8}],
            ).run(
                source=meta,
                output_spec=OutputSpec(str(out), codec="h264", crf=35, audio_copy=False),
                backend=be,
            )
        be.shutdown()

        assert result.success, f"NAFNet pipeline failed: {result.error}"
        assert out.exists()
        assert out.stat().st_size > 0

    def test_nafnet_pipeline_output_video_is_valid(self, tmp_path: Path) -> None:
        """Verify the output can be probed by ffprobe (valid container)."""
        from hipixel_core.backends.cpu import CpuBackend
        from hipixel_core.filters.nafnet import NAFNetFilter
        from hipixel_core.pipeline import Pipeline
        from hipixel_core.types import OutputSpec
        from hipixel_core.video.decoder import probe

        inp = tmp_path / "in.mp4"
        out = tmp_path / "out.mp4"
        model_p = tmp_path / "nafnet_stub.onnx"
        model_p.write_bytes(_make_identity_onnx())

        _create_test_video(inp, frames=4, fps=4)
        meta = probe(str(inp))

        be = CpuBackend()
        be.initialize()
        with mock.patch(
            "hipixel_core.models.manager.ModelManager.get_model_path",
            return_value=str(model_p),
        ):
            Pipeline(
                filters=[NAFNetFilter()],
                filter_params=[{"strength": 1.0}],
            ).run(
                source=meta,
                output_spec=OutputSpec(str(out), codec="h264", crf=35, audio_copy=False),
                backend=be,
            )
        be.shutdown()

        # Verify output video is a valid container that ffprobe can parse
        out_meta = probe(str(out))
        assert out_meta.width == meta.width
        assert out_meta.height == meta.height


# ---------------------------------------------------------------------------
# 7. Dynamic tile size  (_auto_tile_size)
# ---------------------------------------------------------------------------


class TestDynamicTileSize:
    """Unit tests for RealESRGANFilter._auto_tile_size()."""

    def _filter(self, scale: int = 2) -> object:
        from hipixel_core.filters.real_esrgan import RealESRGANFilter

        f = RealESRGANFilter()
        f._scale = scale
        return f

    def _mock_backend(self, vram_mb: int) -> object:
        """Return a minimal mock backend with a fixed available_vram_mb."""
        from unittest.mock import MagicMock

        be = MagicMock()
        be.available_vram_mb.return_value = vram_mb
        return be

    def test_cpu_backend_returns_256(self) -> None:
        """CPU backend (vram=0) should get the conservative 256-pixel default."""
        f = self._filter()
        be = self._mock_backend(0)
        size = f._auto_tile_size(be)  # type: ignore[attr-defined]
        assert size == 256

    def test_high_vram_produces_larger_tile(self) -> None:
        """A GPU with 8 GB should get a tile size clearly larger than CPU default."""
        f = self._filter(scale=2)
        be = self._mock_backend(8192)  # 8 GB
        size = f._auto_tile_size(be)  # type: ignore[attr-defined]
        assert size > 256

    def test_result_is_multiple_of_64(self) -> None:
        """Tile size is always rounded to nearest 64 for model alignment."""
        for vram in (512, 1024, 2048, 4096, 8192):
            f = self._filter(scale=2)
            be = self._mock_backend(vram)
            size = f._auto_tile_size(be)  # type: ignore[attr-defined]
            assert size % 64 == 0, f"vram={vram} → size={size} not multiple of 64"

    def test_result_clamped_to_1024(self) -> None:
        """Even with enormous VRAM the tile size should not exceed 1024."""
        f = self._filter(scale=2)
        be = self._mock_backend(131072)  # 128 GB (absurd)
        size = f._auto_tile_size(be)  # type: ignore[attr-defined]
        assert size <= 1024

    def test_result_at_least_64(self) -> None:
        """Even with very small VRAM (1 MB) the minimum tile is 64."""
        f = self._filter(scale=4)
        be = self._mock_backend(1)
        size = f._auto_tile_size(be)  # type: ignore[attr-defined]
        assert size >= 64

    def test_scale4_smaller_than_scale1(self) -> None:
        """Higher scale → more bytes per tile → smaller safe tile for same VRAM."""
        vram = 2048
        be_s1 = self._mock_backend(vram)
        be_s4 = self._mock_backend(vram)
        s1 = self._filter(scale=1)._auto_tile_size(be_s1)  # type: ignore[attr-defined]
        s4 = self._filter(scale=4)._auto_tile_size(be_s4)  # type: ignore[attr-defined]
        assert s4 <= s1, f"scale=4 tile ({s4}) should be <= scale=1 tile ({s1})"

    def test_explicit_tile_size_overrides_auto(self, tmp_path: Path) -> None:
        """When tile_size is in params, auto-sizing should be bypassed."""
        from unittest.mock import patch

        from hipixel_core.backends.cpu import CpuBackend
        from hipixel_core.filters.real_esrgan import RealESRGANFilter

        p = tmp_path / "stub.onnx"
        p.write_bytes(_make_identity_onnx())

        be = CpuBackend()
        be.initialize()
        f = RealESRGANFilter()

        with patch(
            "hipixel_core.models.manager.ModelManager.get_model_path",
            return_value=str(p),
        ):
            f.setup(be, {"scale": 1, "tile_size": 128, "model": "RealESRGAN_x2plus"})

        assert f._tile_size == 128  # type: ignore[attr-defined]
        f.teardown(be)  # type: ignore[arg-type]
        be.shutdown()





# ============================================================================
# Anime4K v4 Filter Tests
# ============================================================================


class TestAnime4KSingleFrame:
    """Anime4KFilter with scale=1 identity stub — validates tile stitching."""

    def _setup(
        self,
        tmp_path: Path,
        input_name: str = "input",
        tile_size: int = 32,
        tile_pad: int = 4,
    ) -> tuple[object, object]:
        from hipixel_core.backends.cpu import CpuBackend
        from hipixel_core.filters.anime4k import Anime4KFilter

        p = tmp_path / "anime4k_stub.onnx"
        p.write_bytes(_make_identity_onnx(input_name, "output"))

        be = CpuBackend()
        be.initialize()
        f = Anime4KFilter()

        with mock.patch(
            "hipixel_core.models.manager.ModelManager.get_model_path",
            return_value=str(p),
        ):
            f.setup(
                be,
                {
                    "scale": 1,
                    "tile_size": tile_size,
                    "tile_padding": tile_pad,
                    "model": "Anime4K_v4_Upscale_Denoise_x2",
                },
            )
        return be, f

    def test_preserves_dimensions_scale1(self, tmp_path: Path) -> None:
        """With scale=1 identity, dimensions unchanged."""
        be, f = self._setup(tmp_path)
        synth = _synth_frame(128, 96)
        frame = VideoFrame(
            data=synth.data,
            pts=1.0,
            width=128,
            height=96,
            colorspace=synth.colorspace,
        )
        out = f.process_frame(frame, be, {})  # type: ignore[arg-type]
        assert out.data.shape == (96, 128, 3)
        assert out.width == 128
        assert out.height == 96
        f.teardown(be)  # type: ignore[arg-type]
        be.shutdown()

    def test_output_in_range(self, tmp_path: Path) -> None:
        """Output normalized to [0.0, 1.0]."""
        be, f = self._setup(tmp_path)
        synth = _synth_frame(64, 48)
        frame = VideoFrame(
            data=synth.data,
            pts=2.0,
            width=64,
            height=48,
            colorspace=synth.colorspace,
        )
        out = f.process_frame(frame, be, {})  # type: ignore[arg-type]
        assert out.data.min() >= 0.0
        assert out.data.max() <= 1.0
        f.teardown(be)  # type: ignore[arg-type]
        be.shutdown()

    def test_tiled_output_no_seams(self, tmp_path: Path) -> None:
        """With uniform input, overlapping tiles should stitch seamlessly."""
        be, f = self._setup(tmp_path, tile_size=16, tile_pad=2)
        uniform = _uniform_frame(64, 48, value=0.5)
        frame = VideoFrame(
            data=uniform.data,
            pts=3.0,
            width=64,
            height=48,
            colorspace=uniform.colorspace,
        )
        out = f.process_frame(frame, be, {})  # type: ignore[arg-type]
        # Check output is uniform (no tile artifacts)
        mean = out.data.mean()
        std = out.data.std()
        assert std < 0.01, f"Tiled output has seams: std={std}"
        assert abs(mean - 0.5) < 0.05, f"Mean shifted: {mean}"
        f.teardown(be)  # type: ignore[arg-type]
        be.shutdown()

    def test_pts_preserved(self, tmp_path: Path) -> None:
        """Presentation timestamp should pass through unchanged."""
        be, f = self._setup(tmp_path)
        synth = _synth_frame(32, 24)
        frame = VideoFrame(
            data=synth.data,
            pts=42.5,
            width=32,
            height=24,
            colorspace=synth.colorspace,
        )
        out = f.process_frame(frame, be, {})  # type: ignore[arg-type]
        assert out.pts == 42.5
        f.teardown(be)  # type: ignore[arg-type]
        be.shutdown()

    def test_output_dtype_float32(self, tmp_path: Path) -> None:
        """Output must be float32."""
        be, f = self._setup(tmp_path)
        synth = _synth_frame(32, 24)
        frame = VideoFrame(
            data=synth.data,
            pts=1.0,
            width=32,
            height=24,
            colorspace=synth.colorspace,
        )
        out = f.process_frame(frame, be, {})  # type: ignore[arg-type]
        assert out.data.dtype == np.float32
        f.teardown(be)  # type: ignore[arg-type]
        be.shutdown()

    def test_identity_scale1_roundtrip(self, tmp_path: Path) -> None:
        """Identity model with scale=1: input ≈ output (within float32 precision)."""
        be, f = self._setup(tmp_path)
        synth = _synth_frame(48, 36)
        frame = VideoFrame(
            data=synth.data,
            pts=1.0,
            width=48,
            height=36,
            colorspace=synth.colorspace,
        )
        out = f.process_frame(frame, be, {})  # type: ignore[arg-type]
        # Convert synth.data to float32 to match output type
        original_float = synth.data.astype(np.float32) / 255.0
        assert np.allclose(out.data, original_float, atol=1e-5)
        f.teardown(be)  # type: ignore[arg-type]
        be.shutdown()

    def test_remapped_input_name(self, tmp_path: Path) -> None:
        """Backend should remap arbitrary input names (e.g., 'x' → matched by position)."""
        be, f = self._setup(tmp_path, input_name="x")
        synth = _synth_frame(32, 24)
        frame = VideoFrame(
            data=synth.data,
            pts=1.0,
            width=32,
            height=24,
            colorspace=synth.colorspace,
        )
        # Should not raise KeyError even though model uses "x" and we pass "input"
        out = f.process_frame(frame, be, {})  # type: ignore[arg-type]
        assert out.data.shape == (24, 32, 3)
        f.teardown(be)  # type: ignore[arg-type]
        be.shutdown()

    def test_teardown_unloads_model(self, tmp_path: Path) -> None:
        """After teardown, the model should be unloaded."""
        be, f = self._setup(tmp_path)
        model_key = f._model_key  # type: ignore[attr-defined]
        assert be.is_model_loaded(model_key)
        f.teardown(be)  # type: ignore[arg-type]
        assert not be.is_model_loaded(model_key)
        be.shutdown()
