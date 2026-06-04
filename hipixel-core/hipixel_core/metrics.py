"""
Image quality metrics for filter validation.

Provides PSNR and SSIM implementations in pure NumPy (with optional
scipy acceleration for the SSIM gaussian filter).

Usage::

    from hipixel_core.metrics import psnr, ssim

    score_psnr = psnr(reference_frame, degraded_frame)   # dB, inf = identical
    score_ssim = ssim(reference_frame, degraded_frame)   # [0, 1], 1 = identical
"""

from __future__ import annotations

import math

import numpy as np


# ---------------------------------------------------------------------------
# PSNR
# ---------------------------------------------------------------------------


def psnr(
    reference: np.ndarray,
    degraded: np.ndarray,
    max_val: float = 1.0,
) -> float:
    """Peak Signal-to-Noise Ratio (dB).

    Args:
        reference:  Ground-truth image, any dtype.  Float arrays are assumed
                    to be in ``[0, max_val]``; uint8 arrays ignore ``max_val``
                    and use 255.
        degraded:   Distorted image with the same shape and dtype as
                    ``reference``.
        max_val:    Signal range upper-bound.  Ignored when ``reference`` is
                    uint8 (255 is used automatically).

    Returns:
        PSNR in decibels.  Returns ``float('inf')`` when the images are
        pixel-perfect identical (MSE = 0).

    Raises:
        ValueError: if ``reference`` and ``degraded`` have different shapes.
    """
    if reference.shape != degraded.shape:
        raise ValueError(
            f"Shape mismatch: reference={reference.shape}, degraded={degraded.shape}"
        )

    if reference.dtype == np.uint8:
        max_val = 255.0

    ref = reference.astype(np.float64)
    deg = degraded.astype(np.float64)
    mse = float(np.mean((ref - deg) ** 2))

    if mse == 0.0:
        return float("inf")

    return 10.0 * math.log10((float(max_val) ** 2) / mse)


# ---------------------------------------------------------------------------
# SSIM
# ---------------------------------------------------------------------------

#: Default gaussian kernel radius (matches Wang et al. 2004)
_SSIM_KERNEL_RADIUS = 5
#: Default gaussian sigma (matches scikit-image default)
_SSIM_SIGMA = 1.5
#: Stability constants K1, K2 (Wang et al. 2004)
_K1 = 0.01
_K2 = 0.03


def ssim(
    reference: np.ndarray,
    degraded: np.ndarray,
    max_val: float = 1.0,
    *,
    multichannel: bool = True,
) -> float:
    """Structural Similarity Index (SSIM), Wang et al. 2004.

    Args:
        reference:    Ground-truth image, shape ``(H, W)`` or ``(H, W, C)``,
                      float32/float64 in ``[0, max_val]``, or uint8.
        degraded:     Distorted image matching ``reference`` shape/dtype.
        max_val:      Signal range.  Auto-set to 255 for uint8 inputs.
        multichannel: When ``True`` (default), compute SSIM per channel and
                      return the mean.

    Returns:
        Mean SSIM in ``[0, 1]``.  1.0 means identical.

    Raises:
        ValueError: if shapes differ.
    """
    if reference.shape != degraded.shape:
        raise ValueError(
            f"Shape mismatch: reference={reference.shape}, degraded={degraded.shape}"
        )

    if reference.dtype == np.uint8:
        max_val = 255.0

    ref = reference.astype(np.float64)
    deg = degraded.astype(np.float64)

    c1 = (_K1 * max_val) ** 2
    c2 = (_K2 * max_val) ** 2

    if ref.ndim == 3 and multichannel:
        scores = [_ssim_single_channel(ref[..., c], deg[..., c], c1, c2) for c in range(ref.shape[2])]
        return float(np.mean(scores))

    if ref.ndim == 3:
        # Collapse channels by averaging
        ref = ref.mean(axis=2)
        deg = deg.mean(axis=2)

    return _ssim_single_channel(ref, deg, c1, c2)


def _gaussian_kernel_1d(radius: int, sigma: float) -> np.ndarray:
    """1-D normalised Gaussian kernel."""
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-(x ** 2) / (2 * sigma ** 2))
    return kernel / kernel.sum()


def _ssim_single_channel(
    ref: np.ndarray,
    deg: np.ndarray,
    c1: float,
    c2: float,
) -> float:
    """SSIM for a single 2-D plane (float64)."""
    kernel = _gaussian_kernel_1d(_SSIM_KERNEL_RADIUS, _SSIM_SIGMA)

    def _conv(img: np.ndarray) -> np.ndarray:
        """Separable 2-D convolution with the gaussian kernel."""
        try:
            from scipy.ndimage import convolve1d

            tmp = convolve1d(img, kernel, axis=1, mode="reflect")
            return convolve1d(tmp, kernel, axis=0, mode="reflect")
        except ImportError:
            # Fallback: uniform_filter approximation
            from scipy.ndimage import uniform_filter

            k = len(kernel)
            return uniform_filter(img, size=k, mode="reflect")

    mu1 = _conv(ref)
    mu2 = _conv(deg)

    mu1_sq = mu1 * mu1
    mu2_sq = mu2 * mu2
    mu1_mu2 = mu1 * mu2

    sigma1_sq = _conv(ref * ref) - mu1_sq
    sigma2_sq = _conv(deg * deg) - mu2_sq
    sigma12 = _conv(ref * deg) - mu1_mu2

    numerator = (2.0 * mu1_mu2 + c1) * (2.0 * sigma12 + c2)
    denominator = (mu1_sq + mu2_sq + c1) * (sigma1_sq + sigma2_sq + c2)

    ssim_map = numerator / np.maximum(denominator, 1e-15)
    return float(ssim_map.mean())
