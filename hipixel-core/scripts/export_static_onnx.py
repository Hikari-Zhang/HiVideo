#!/usr/bin/env python3
"""
Export Real-ESRGAN models to static-shape ONNX (for CoreML compatibility).

CoreML EP does not support dynamic axes. This script exports ONNX files
with fixed input/output shapes so CoreML can compile them correctly.

Usage:
    # Export RealESRGAN_x4plus with 512x512 input (→ 2048x2048 output)
    python scripts/export_static_onnx.py --model RealESRGAN_x4plus --input-size 512

    # Export all models
    python scripts/export_static_onnx.py --all --input-size 512
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import torch

# ---------------------------------------------------------------------------
# Patch basicsr import issue (torchvision.transforms.functional_tensor removed)
# ---------------------------------------------------------------------------
import importlib
import torchvision.transforms.functional as _ft


class _FunctionalTensorShim:
    def __getattr__(self, name: str):
        return getattr(_ft, name)


sys.modules["torchvision.transforms.functional_tensor"] = _FunctionalTensorShim()


# ---------------------------------------------------------------------------
# Model configs from registry.json
# ---------------------------------------------------------------------------
_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "hipixel_core" / "models" / "registry.json"

# Fallback configs if registry not found
_FALLBACK_CONFIGS = {
    "RealESRGAN_x4plus": {
        "arch_config": {
            "type": "RRDBNet",
            "num_in_ch": 3,
            "num_out_ch": 3,
            "num_feat": 64,
            "num_block": 23,
            "num_grow_ch": 32,
            "scale": 4,
        },
        "source_pth_url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
    },
    "RealESRGAN_x2plus": {
        "arch_config": {
            "type": "RRDBNet",
            "num_in_ch": 3,
            "num_out_ch": 3,
            "num_feat": 64,
            "num_block": 23,
            "num_grow_ch": 32,
            "scale": 2,
        },
        "source_pth_url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
    },
}


def get_model_config(model_name: str) -> dict:
    """Get model config from registry.json or fallback."""
    if _REGISTRY_PATH.exists():
        with open(_REGISTRY_PATH) as f:
            registry = json.load(f)
        if model_name in registry.get("models", {}):
            return registry["models"][model_name]

    if model_name in _FALLBACK_CONFIGS:
        return _FALLBACK_CONFIGS[model_name]

    raise ValueError(f"Unknown model: {model_name}")


def load_pth_weights(model: torch.nn.Module, pth_path: Path) -> None:
    """Load .pth weights into model (handles various checkpoint formats)."""
    print(f"  Loading weights from {pth_path.name} ...")
    ckpt = torch.load(str(pth_path), map_location="cpu")

    # Handle different checkpoint formats
    if "params_ema" in ckpt:
        state_dict = ckpt["params_ema"]
    elif "params" in ckpt:
        state_dict = ckpt["params"]
    elif "model" in ckpt:
        state_dict = ckpt["model"]
    else:
        state_dict = ckpt

    # Remove common prefixes
    new_state_dict = {}
    for k, v in state_dict.items():
        new_k = k.replace("module.", "").replace("model.", "")
        new_state_dict[new_k] = v

    model.load_state_dict(new_state_dict, strict=True)
    print("  Weights loaded OK.")


def export_static(
    model_name: str,
    input_size: int = 512,
    output_path: Path | None = None,
) -> Path:
    """
    Export model to static-shape ONNX (no dynamic axes).

    Parameters
    ----------
    model_name : str
        Model name (e.g., 'RealESRGAN_x4plus')
    input_size : int
        Input image size (will be squared, e.g., 512 → 512x512)
    output_path : Path | None
        Output ONNX path. If None, uses ~/.cache/hipixel-core/models/
    """
    import basicsr.archs.rrdbnet_arch as _rrdb

    RRDBNet = _rrdb.RRDBNet

    config = get_model_config(model_name)
    arch_config = config["arch_config"]
    scale = arch_config["scale"]

    # Build model
    print(f"  Building RRDBNet(scale={scale}, num_block={arch_config['num_block']}) ...")
    model = RRDBNet(
        num_in_ch=arch_config["num_in_ch"],
        num_out_ch=arch_config["num_out_ch"],
        num_feat=arch_config["num_feat"],
        num_block=arch_config["num_block"],
        num_grow_ch=arch_config["num_grow_ch"],
        scale=scale,
    )
    model.eval()

    # Load weights
    cache_dir = Path.home() / ".cache" / "hipixel-core" / "models"
    cache_dir.mkdir(parents=True, exist_ok=True)

    pth_name = f"{model_name}.pth"
    pth_path = cache_dir / pth_name

    if not pth_path.exists():
        # Download
        import httpx

        url = config["source_pth_url"]
        print(f"  Downloading .pth from {url} ...")
        tmp = pth_path.with_suffix(".tmp")
        with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=65536):
                    f.write(chunk)
        tmp.rename(pth_path)
        print(f"  Downloaded → {pth_path}")

    load_pth_weights(model, pth_path)

    # Export with static shapes
    if output_path is None:
        suffix = f"_static_{input_size}" if input_size != 512 else "_static"
        output_path = cache_dir / f"{model_name}{suffix}.onnx"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(".tmp.onnx")

    dummy = torch.zeros(1, 3, input_size, input_size)
    output_size = input_size * scale

    print(f"  Exporting static ONNX (input={input_size}x{input_size}, output={output_size}x{output_size}) ...")

    # Strategy: Use torch.jit.trace to avoid dynamo issues
    try:
        print("    Tracing model ...")
        traced = torch.jit.trace(model, dummy)

        # Export traced model (should be complete)
        torch.onnx.export(
            traced,
            dummy,
            str(tmp_path),
            opset_version=18,
            input_names=["input"],
            output_names=["output"],
            do_constant_folding=True,
            export_params=True,
            keep_initializers_as_inputs=False,
        )
        print(f"    Exported (traced): {tmp_path.name}")
    except Exception as e:
        print(f"    Trace failed ({e}), using direct export ...")
        torch.onnx.export(
            model,
            dummy,
            str(tmp_path),
            opset_version=18,
            input_names=["input"],
            output_names=["output"],
            do_constant_folding=True,
        )

    # Check file size
    size_mb = tmp_path.stat().st_size / 1_048_576
    print(f"    Initial export size: {size_mb:.1f} MB")

    if size_mb < 10:
        print("    ⚠️  Export too small, trying larger input ...")
        # Try with larger input
        dummy_large = torch.zeros(1, 3, input_size * 2, input_size * 2)
        tmp_large = tmp_path.with_suffix(".large.onnx")
        try:
            traced_large = torch.jit.trace(model, dummy_large)
            torch.onnx.export(
                traced_large,
                dummy_large,
                str(tmp_large),
                opset_version=18,
                input_names=["input"],
                output_names=["output"],
                do_constant_folding=True,
                export_params=True,
                keep_initializers_as_inputs=False,
            )
            size_mb_large = tmp_large.stat().st_size / 1_048_576
            print(f"    Larger export size: {size_mb_large:.1f} MB")
            if size_mb_large > size_mb:
                tmp_path.unlink()
                tmp_large.rename(tmp_path)
                size_mb = size_mb_large
        except Exception as e2:
            print(f"    Larger export failed: {e2}")

    # Rename to final path
    tmp_path.rename(output_path)

    final_size = output_path.stat().st_size / 1_048_576
    print(f"  ✓ Exported: {output_path.name} ({final_size:.1f} MB)")
    print(f"    Input shape:  [1, 3, {input_size}, {input_size}]")
    print(f"    Output shape: [1, 3, {output_size}, {output_size}]")

    if final_size < 10:
        print("  ⚠️  WARNING: Export size is suspiciously small!")
        print("     Expected ~67 MB for RealESRGAN_x4plus")
        print("     The model may be incomplete due to PyTorch 2.x dynamo issues")
        print("     Suggestion: Use the dynamic-axis version and disable CoreML EP")

    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="RealESRGAN_x4plus", help="Model to export")
    parser.add_argument("--input-size", type=int, default=512, help="Input image size (default: 512)")
    parser.add_argument("--all", action="store_true", help="Export all known models")
    args = parser.parse_args()

    # Get model list
    if args.all:
        if _REGISTRY_PATH.exists():
            with open(_REGISTRY_PATH) as f:
                registry = json.load(f)
            models = list(registry.get("models", {}).keys())
        else:
            models = list(_FALLBACK_CONFIGS.keys())
    else:
        models = [args.model]

    # Export each model
    for model_name in models:
        print(f"\n── {model_name} (static, {args.input_size}x{args.input_size}) ──")
        try:
            onnx_path = export_static(model_name, input_size=args.input_size)
            print(f"  ✓ Saved to: {onnx_path}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback

            traceback.print_exc()

    print("\nDone. Static ONNX files are ready for CoreML.")


if __name__ == "__main__":
    main()
