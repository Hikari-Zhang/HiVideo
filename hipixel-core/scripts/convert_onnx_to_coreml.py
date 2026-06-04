#!/usr/bin/env python3
"""
Convert ONNX models to CoreML (.mlpackage) for native Apple Silicon acceleration.

CoreML native format supports dynamic input shapes and runs directly on
ANE (Apple Neural Engine) without ONNX Runtime's CoreML EP overhead.

Usage:
    # Convert RealESRGAN_x4plus (dynamic input)
    python scripts/convert_onnx_to_coreml.py --model RealESRGAN_x4plus

    # Convert with specific input shape (for optimal ANE compilation)
    python scripts/convert_onnx_to_coreml.py --model RealESRGAN_x4plus --input-size 512

    # Convert all ONNX models in cache
    python scripts/convert_onnx_to_coreml.py --all
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import coremltools as ct
import numpy as np


# ---------------------------------------------------------------------------
# Model cache directory
# ---------------------------------------------------------------------------
_CACHE_DIR = Path.home() / ".cache" / "hipixel-core" / "models"


def onnx_to_coreml(
    onnx_path: Path,
    mlpackage_path: Path | None = None,
    input_size: int | None = None,
) -> Path:
    """
    Convert ONNX model to CoreML .mlpackage format.

    Parameters
    ----------
    onnx_path : Path
        Path to input .onnx file.
    mlpackage_path : Path | None
        Output .mlpackage path. If None, uses same name with .mlpackage suffix.
    input_size : int | None
        If provided, use static input shape (1, 3, input_size, input_size).
        If None, use dynamic input shape (any H×W).

    Returns
    -------
    Path
        Path to the converted .mlpackage file.
    """
    if not onnx_path.exists():
        raise FileNotFoundError(f"ONNX file not found: {onnx_path}")

    if mlpackage_path is None:
        mlpackage_path = onnx_path.with_suffix(".mlpackage")

    print(f"Converting {onnx_path.name} → {mlpackage_path.name} ...")

    # ------------------------------------------------------------------
    # Define input type
    # ------------------------------------------------------------------
    if input_size is not None:
        # Static shape (optimal for ANE compilation)
        input_shape = (1, 3, input_size, input_size)
        print(f"  Input shape: {input_shape} (static)")
        inputs = [ct.TensorType(shape=input_shape, name="input")]
    else:
        # Dynamic shape (flexible but may be slower)
        print("  Input shape: dynamic (range [1,3,64,64] to [1,3,4096,4096])")
        inputs = [
            ct.TensorType(
                shape=(
                    1,  # batch
                    3,  # channels
                    ct.RangeDim(64, 4096),  # height (dynamic)
                    ct.RangeDim(64, 4096),  # width (dynamic)
                ),
                name="input",
            )
        ]

    # ------------------------------------------------------------------
    # Convert ONNX → CoreML
    # ------------------------------------------------------------------
    print("  Converting (this may take several minutes) ...")

    # coremltools 9.0: specify source="onnx" explicitly
    mlmodel = ct.convert(
        str(onnx_path),
        source="onnx",  # Explicitly specify ONNX format
        inputs=inputs,
        compute_units=ct.ComputeUnit.ALL,  # Use ANE + GPU + CPU
        convert_to="neuralnetwork",  # Broader op support than "mlprogram"
        compute_precision=ct.precision.FLOAT32,  # RealESRGAN needs FP32
        # Skip ANE validation (RealESRGAN may have unsupported ops)
        skip_model_load=True,  # Don't validate on ANE during conversion
    )

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    mlpackage_path.parent.mkdir(parents=True, exist_ok=True)
    mlmodel.save(str(mlpackage_path))

    size_mb = mlpackage_path.stat().st_size / 1_048_576
    print(f"  ✓ Saved: {mlpackage_path.name} ({size_mb:.1f} MB)")
    print(f"    Compute units: ANE + GPU + CPU")

    return mlpackage_path


def convert_model(model_name: str, input_size: int | None = None) -> Path:
    """
    Convert a specific model by name.

    Looks for {model_name}.onnx in cache directory, converts to .mlpackage.
    """
    # Try dynamic-axis version first, then static
    onnx_candidates = [
        _CACHE_DIR / f"{model_name}.onnx",
        _CACHE_DIR / f"{model_name}_static.onnx",
    ]

    onnx_path = None
    for candidate in onnx_candidates:
        if candidate.exists():
            onnx_path = candidate
            break

    if onnx_path is None:
        # Try to download/convert via ModelManager
        print(f"  {model_name}.onnx not found in cache, attempting auto-download ...")
        from hipixel_core.models.manager import ModelManager

        onnx_path_str = ModelManager.get_model_path(model_name)
        onnx_path = Path(onnx_path_str)

    mlpackage_path = onnx_path.with_suffix(".mlpackage")

    return onnx_to_coreml(onnx_path, mlpackage_path, input_size=input_size)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--model", default="RealESRGAN_x4plus", help="Model name (without .onnx)")
    parser.add_argument(
        "--input-size",
        type=int,
        default=None,
        help="Static input size (e.g., 512). If not provided, uses dynamic shape.",
    )
    parser.add_argument("--all", action="store_true", help="Convert all .onnx files in cache")
    args = parser.parse_args()

    if args.all:
        # Convert all ONNX files in cache
        onnx_files = list(_CACHE_DIR.glob("*.onnx"))
        if not onnx_files:
            print(f"No .onnx files found in {_CACHE_DIR}")
            return

        print(f"Found {len(onnx_files)} ONNX file(s) to convert ...\n")
        for onnx_path in onnx_files:
            print(f"── {onnx_path.name} ──")
            try:
                mlpackage_path = onnx_path.with_suffix(".mlpackage")
                onnx_to_coreml(onnx_path, mlpackage_path, input_size=args.input_size)
                print()
            except Exception as e:
                print(f"  ✗ Error: {e}\n")
    else:
        # Convert single model
        print(f"Converting {args.model} ...\n")
        try:
            mlpackage_path = convert_model(args.model, input_size=args.input_size)
            print(f"\n✓ Done! CoreML model saved to: {mlpackage_path}")
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    main()
