"""
Tests for hipixel_core.metrics — PSNR and SSIM.

All tests run in-process with synthetic NumPy arrays; no file I/O,
no model downloads, no FFmpeg required.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from hipixel_core.metrics import psnr, ssim


# ---------------------------------------------------------------------------
# PSNR tests
# ---------------------------------------------------------------------------


class TestPSNR:
    def _rand_f32(self, shape: tuple[int, ...]) -> np.ndarray:
        rng = np.random.default_rng(0)
        return rng.random(shape).astype(np.float32)

    def test_identical_arrays_return_inf(self) -> None:
        img = self._rand_f32((64, 64, 3))
        assert psnr(img, img) == float("inf")

    def test_identical_uint8_return_inf(self) -> None:
        img = np.zeros((32, 32, 3), dtype=np.uint8)
        assert psnr(img, img) == float("inf")

    def test_all_zero_vs_max_signal(self) -> None:
        ref = np.ones((8, 8, 3), dtype=np.float32)
        deg = np.zeros((8, 8, 3), dtype=np.float32)
        # MSE = 1.0, max_val = 1.0 → PSNR = 10 * log10(1/1) = 0 dB
        assert abs(psnr(ref, deg, max_val=1.0) - 0.0) < 1e-6

    def test_known_value_float32(self) -> None:
        """MSE = 0.01, max_val = 1 → PSNR = 20 dB."""
        ref = np.ones((100, 100, 3), dtype=np.float32)
        deg = ref - 0.1  # MSE = 0.01
        result = psnr(ref, deg)
        assert abs(result - 20.0) < 1e-4

    def test_known_value_uint8(self) -> None:
        """max_val=255, MSE=1.0 → PSNR = 10*log10(255²/1) ≈ 48.13 dB."""
        ref = np.ones((100, 100, 3), dtype=np.uint8) * 200
        deg = ref.copy()
        deg[:] -= 1  # MSE = 1.0 exactly
        expected = 10 * math.log10(255.0 ** 2 / 1.0)
        assert abs(psnr(ref, deg) - expected) < 1e-4

    def test_noisy_image_less_than_30db(self) -> None:
        rng = np.random.default_rng(42)
        ref = rng.random((64, 64, 3)).astype(np.float32)
        noise = rng.normal(0, 0.1, ref.shape).astype(np.float32)
        deg = np.clip(ref + noise, 0, 1).astype(np.float32)
        result = psnr(ref, deg)
        assert 0.0 < result < 40.0, f"Expected moderate PSNR, got {result:.2f}"

    def test_shape_mismatch_raises(self) -> None:
        ref = np.zeros((64, 64, 3), dtype=np.float32)
        deg = np.zeros((32, 32, 3), dtype=np.float32)
        with pytest.raises(ValueError, match="Shape mismatch"):
            psnr(ref, deg)

    def test_single_channel(self) -> None:
        ref = np.ones((16, 16), dtype=np.float32)
        deg = ref * 0.5  # MSE = 0.25 → PSNR = 10*log10(1/0.25) = 6.02 dB
        result = psnr(ref, deg)
        assert abs(result - 6.0206) < 0.01

    def test_identity_model_psnr_is_very_high(self, tmp_path: "pathlib.Path") -> None:  # type: ignore[name-defined]  # noqa: F821
        """An ONNX Identity model should return PSNR > 60 dB (near-lossless)."""
        import pathlib
        from unittest import mock

        import sys
        sys.path.insert(0, str(pathlib.Path(__file__).parent))
        from test_inference_e2e import _make_identity_onnx

        from hipixel_core.backends.cpu import CpuBackend
        from hipixel_core.filters.nafnet import NAFNetFilter
        from hipixel_core.types import VideoFrame

        model_path = tmp_path / "identity.onnx"
        model_path.write_bytes(_make_identity_onnx("input", "output"))

        backend = CpuBackend()
        backend.initialize()

        filt = NAFNetFilter()
        with mock.patch(
            "hipixel_core.models.manager.ModelManager.get_model_path",
            return_value=str(model_path),
        ):
            filt.setup(backend, {"model": "NAFNet-REDS-width64", "strength": 1.0})

        rng = np.random.default_rng(7)
        data = rng.random((64, 64, 3)).astype(np.float32)
        frame = VideoFrame(data=data.copy(), pts=0.0, width=64, height=64)

        out = filt.process_frame(frame, backend, {"strength": 1.0})
        filt.teardown(backend)

        score = psnr(data, out.data)
        assert score > 60.0, f"Identity model PSNR should be > 60 dB, got {score:.2f}"


# ---------------------------------------------------------------------------
# SSIM tests
# ---------------------------------------------------------------------------


class TestSSIM:
    def _rand_f32(self, shape: tuple[int, ...], seed: int = 0) -> np.ndarray:
        rng = np.random.default_rng(seed)
        return rng.random(shape).astype(np.float32)

    def test_identical_returns_one(self) -> None:
        img = self._rand_f32((64, 64, 3))
        score = ssim(img, img)
        assert abs(score - 1.0) < 1e-4

    def test_identical_uint8_returns_one(self) -> None:
        img = np.full((32, 32, 3), 128, dtype=np.uint8)
        score = ssim(img, img, max_val=255.0)
        assert abs(score - 1.0) < 1e-4

    def test_pure_noise_vs_constant_is_low(self) -> None:
        ref = np.full((64, 64, 3), 0.5, dtype=np.float32)
        rng = np.random.default_rng(0)
        deg = rng.random((64, 64, 3)).astype(np.float32)
        score = ssim(ref, deg)
        assert score < 0.5, f"Expected SSIM < 0.5 for noise, got {score:.4f}"

    def test_slight_noise_is_near_one(self) -> None:
        ref = self._rand_f32((64, 64, 3), seed=1)
        rng = np.random.default_rng(99)
        noise = rng.normal(0, 0.01, ref.shape).astype(np.float32)
        deg = np.clip(ref + noise, 0, 1).astype(np.float32)
        score = ssim(ref, deg)
        assert score > 0.90, f"Expected SSIM > 0.90 for slight noise, got {score:.4f}"

    def test_shape_mismatch_raises(self) -> None:
        ref = np.zeros((64, 64, 3), dtype=np.float32)
        deg = np.zeros((32, 32, 3), dtype=np.float32)
        with pytest.raises(ValueError, match="Shape mismatch"):
            ssim(ref, deg)

    def test_single_channel(self) -> None:
        img = self._rand_f32((64, 64))
        score = ssim(img, img)
        assert abs(score - 1.0) < 1e-4

    def test_multichannel_false_collapses(self) -> None:
        img = self._rand_f32((64, 64, 3))
        score = ssim(img, img, multichannel=False)
        assert abs(score - 1.0) < 1e-4

    def test_score_is_in_range(self) -> None:
        ref = self._rand_f32((48, 48, 3), seed=10)
        rng = np.random.default_rng(20)
        deg = np.clip(ref + rng.normal(0, 0.05, ref.shape), 0, 1).astype(np.float32)
        score = ssim(ref, deg)
        assert 0.0 <= score <= 1.0, f"SSIM out of range: {score}"
