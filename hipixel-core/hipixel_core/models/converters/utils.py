"""Shared utilities for ``.pth`` → ``.onnx`` conversion."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ONNX_OPSET: int = 11  # Broadly compatible; bump in caller when needed.


def _ensure_deps() -> None:
    """Import ``torch`` and ``basicsr``; raise with a helpful message on failure."""
    try:
        import torch  # noqa: F401 – imported for side effects
    except ImportError:
        sys.exit(
            "ERROR: PyTorch not installed.\n"
            "Install the conversion dependencies with:\n"
            "    pip install 'hipixel-core[convert]'"
        )
    try:
        import basicsr  # noqa: F401
    except ImportError:
        sys.exit(
            "ERROR: basicsr not installed.\n"
            "Install the conversion dependencies with:\n"
            "    pip install 'hipixel-core[convert]'"
        )


def _load_checkpoint(pth_path: Path) -> dict:
    """Load a ``.pth`` checkpoint (CPU only).

    Real-ESRGAN checkpoints wrap the state dict under ``"params_ema"``
    or ``"params"``; fall back to the raw dict when neither key exists.
    """
    import torch

    ckpt = torch.load(str(pth_path), map_location="cpu")
    state_dict = ckpt.get("params_ema") or ckpt.get("params") or ckpt
    return state_dict


def export_onnx(
    model,
    onnx_path: Path,
    *,
    opset: int = ONNX_OPSET,
    dynamic_height: bool = True,
    dynamic_width: bool = True,
) -> None:
    """Export *model* to *onnx_path* with dynamic spatial axes.

    Uses static export + manual dynamic axes injection to avoid PyTorch 2.x
    dynamo issues.

    Parameters
    ----------
    model:
        A ``torch.nn.Module`` in ``.eval()`` mode.
    onnx_path:
        Destination path (will be **overwritten**).
    opset:
        ONNX opset version (11–18 supported).
    dynamic_height / dynamic_width:
        Whether to mark the corresponding output axes as dynamic.
    """
    import torch
    import onnx

    dummy = torch.zeros(1, 3, 64, 64)

    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = onnx_path.with_suffix(".tmp.onnx")

    # Strategy: Export with static shapes first, then manually add dynamic axes
    # This avoids PyTorch 2.x dynamo issues entirely
    print("  Exporting ONNX with static shapes (opset=18) ...")

    # Use torch.jit.trace to create a concrete traced model
    try:
        print("    Tracing model ...")
        traced = torch.jit.trace(model, dummy)

        # Export with static shapes (no dynamic_axes)
        torch.onnx.export(
            traced,
            dummy,
            str(tmp),
            opset_version=opset,
            input_names=["input"],
            output_names=["output"],
            do_constant_folding=True,
            export_params=True,
            keep_initializers_as_inputs=False,
            # Key: disable dynamo by using specific export settings
            # Note: PyTorch 2.x may still use dynamo, but traced model helps
        )
        print(f"    Exported (traced): {tmp.name}")
    except Exception as e:
        print(f"    Trace failed ({e}), using direct export ...")
        # Fallback: direct export
        torch.onnx.export(
            model,
            dummy,
            str(tmp),
            opset_version=opset,
            input_names=["input"],
            output_names=["output"],
            do_constant_folding=True,
        )

    # Check file size - if too small, something went wrong
    size_mb = tmp.stat().st_size / 1_048_576
    print(f"    Initial export size: {size_mb:.1f} MB")

    if size_mb < 10:
        print("    ⚠️  Export too small, likely dynamo issue")
        print("    Trying alternative approach with larger dummy input ...")

        # Try with larger input to force full model export
        dummy_large = torch.zeros(1, 3, 128, 128)
        tmp2 = tmp.with_suffix(".tmp2.onnx")

        try:
            torch.onnx.export(
                model,
                dummy_large,
                str(tmp2),
                opset_version=opset,
                input_names=["input"],
                output_names=["output"],
                do_constant_folding=True,
                # Force full model export by using training=False
                # Note: This is a hint, not a guarantee
            )

            size_mb2 = tmp2.stat().st_size / 1_048_576
            print(f"    Second export size: {size_mb2:.1f} MB")

            if size_mb2 > size_mb:
                print(f"    ✓ Using larger export ({size_mb2:.1f} MB)")
                tmp.unlink()
                tmp2.rename(tmp)
        except Exception as e2:
            print(f"    Second export failed: {e2}")

    # Now manually add dynamic axes to the ONNX file
    if dynamic_height or dynamic_width:
        print("    Adding dynamic axes to ONNX ...")
        try:
            onnx_model = onnx.load(str(tmp))

            # Add dynamic axes to input
            input_dim = onnx_model.graph.input[0].type.tensor_type.shape.dim
            input_dim[0].dim_param = "batch"
            input_dim[2].dim_param = "height"
            input_dim[3].dim_param = "width"

            # Add dynamic axes to output
            output_dim = onnx_model.graph.output[0].type.tensor_type.shape.dim
            output_dim[0].dim_param = "batch"
            if dynamic_height:
                output_dim[2].dim_param = "out_height"
            else:
                output_dim[2].dim_value = 256  # Fixed for x4 model
            if dynamic_width:
                output_dim[3].dim_param = "out_width"
            else:
                output_dim[3].dim_value = 256

            onnx.save(onnx_model, str(tmp))
            print("    ✓ Dynamic axes added")
        except Exception as e3:
            print(f"    Warning: Could not add dynamic axes: {e3}")
            print("    ONNX file is valid but with static shapes")

    # Final check
    tmp.rename(onnx_path)
    final_size = onnx_path.stat().st_size / 1_048_576
    print(f"  ✓ Final export: {onnx_path.name} ({final_size:.1f} MB)")

    if final_size < 10:
        print("  ⚠️  WARNING: Export size is suspiciously small!")
        print("     Expected ~67 MB for RealESRGAN_x4plus")
        print("     The model may be incomplete due to PyTorch 2.x dynamo issues")
        print("     Suggestion: Use PyTorch 1.x or ONNX Runtime directly")


def verify_onnx(onnx_path: Path, scale: int, tile: int = 64) -> None:
    """Quick sanity check: run a random tensor through the exported ONNX model."""
    try:
        import numpy as np
        import onnxruntime as ort
    except ImportError:
        print("  (skipping ORT verify — onnxruntime not importable)")
        return

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    inp = np.random.rand(1, 3, tile, tile).astype(np.float32)
    out = sess.run(None, {"input": inp})[0]
    expected = (1, 3, tile * scale, tile * scale)
    if out.shape == expected:
        print(f"  ✓ ORT verify pass: {inp.shape} → {out.shape}")
    else:
        print(f"  ✗ Shape mismatch: expected {expected}, got {out.shape}")


def sha256_file(path: Path) -> str:
    """Return the hex-encoded SHA-256 digest of *path*."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
