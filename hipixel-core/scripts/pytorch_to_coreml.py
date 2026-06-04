#!/usr/bin/env python3
"""
Convert RealESRGAN PyTorch model to CoreML (.mlpackage) natively.

Bypasses ONNX entirely — converts PyTorch → CoreML directly using coremltools.
This gives better ANE compatibility than ONNX → CoreML conversion.

Usage:
    # Convert RealESRGAN_x4plus with dynamic input
    python scripts/pytorch_to_coreml.py --model RealESRGAN_x4plus

    # Convert with static 512x512 input (optimal for ANE)
    python scripts/pytorch_to_coreml.py --model RealESRGAN_x4plus --input-size 512

    # Convert all models in registry
    python scripts/pytorch_to_coreml.py --all
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import coremltools as ct
import torch

# ---------------------------------------------------------------------------
# Patch basicsr import issue
# ---------------------------------------------------------------------------
import torchvision.transforms.functional as _ft


class _FunctionalTensorShim:
    def __getattr__(self, name: str):
        return getattr(_ft, name)


sys.modules["torchvision.transforms.functional_tensor"] = _FunctionalTensorShim()

# ---------------------------------------------------------------------------
# Model config
# ---------------------------------------------------------------------------
_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "hipixel_core" / "models" / "registry.json"

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
    """Get model config from registry.json or fallback.

    Merges registry entry (for filename, url, etc.) with fallback config
    (for arch_config, source_pth_url needed for PyTorch conversion).
    """
    # Start with fallback config (has arch_config, source_pth_url)
    if model_name in _FALLBACK_CONFIGS:
        config = dict(_FALLBACK_CONFIGS[model_name])
    else:
        config = {}

    # Overlay registry entry (has filename, url, size_bytes, etc.)
    if _REGISTRY_PATH.exists():
        with open(_REGISTRY_PATH) as f:
            registry = json.load(f)
        if model_name in registry.get("models", {}):
            reg_entry = registry["models"][model_name]
            config.update(reg_entry)  # Registry values override fallback

    if not config:
        raise ValueError(f"Unknown model: {model_name}")

    return config


def load_model(model_name: str, config: dict) -> torch.nn.Module:
    """Load PyTorch model with weights."""
    import basicsr.archs.rrdbnet_arch as _rrdb

    RRDBNet = _rrdb.RRDBNet

    arch_config = config["arch_config"]
    scale = arch_config["scale"]

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

    print(f"  Loading weights from {pth_path.name} ...")
    ckpt = torch.load(str(pth_path), map_location="cpu")

    if "params_ema" in ckpt:
        state_dict = ckpt["params_ema"]
    elif "params" in ckpt:
        state_dict = ckpt["params"]
    elif "model" in ckpt:
        state_dict = ckpt["model"]
    else:
        state_dict = ckpt

    # Remove common prefixes
    new_state_dict = {k.replace("module.", "").replace("model.", ""): v for k, v in state_dict.items()}

    model.load_state_dict(new_state_dict, strict=True)
    print("  Weights loaded OK.")

    return model


def pytorch_to_coreml(
    model: torch.nn.Module,
    mlpackage_path: Path,
    input_size: int | None = None,
    scale: int = 4,
) -> Path:
    """
    Convert PyTorch model to CoreML .mlpackage.

    Parameters
    ----------
    model : torch.nn.Module
        PyTorch model in eval mode.
    mlpackage_path : Path
        Output .mlpackage path.
    input_size : int | None
        If provided, use static input shape (1,3,input_size,input_size).
        If None, use dynamic input shape.
    scale : int
        Upscale factor (2 or 4).
    """
    mlpackage_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Define input type
    # ------------------------------------------------------------------
    if input_size is not None:
        # Static shape (optimal for ANE)
        input_shape = (1, 3, input_size, input_size)
        print(f"  Input shape: {input_shape} (static)")
        print(f"  Output shape: (1, 3, {input_size * scale}, {input_size * scale})")
        inputs = [ct.TensorType(shape=input_shape, name="input")]
    else:
        # Dynamic shape
        print("  Input shape: dynamic (64 to 4096)")
        inputs = [
            ct.TensorType(
                shape=(
                    1,  # batch
                    3,  # channels
                    ct.RangeDim(64, 4096),  # height
                    ct.RangeDim(64, 4096),  # width
                ),
                name="input",
            )
        ]

    # ------------------------------------------------------------------
    # Convert (PyTorch → TorchScript → CoreML)
    # ------------------------------------------------------------------
    print("  Tracing PyTorch model ...")
    t0 = time.time()

    # Step 1: Trace model to TorchScript
    if input_size is not None:
        example_input = torch.zeros(1, 3, input_size, input_size)
    else:
        example_input = torch.zeros(1, 3, 512, 512)  # Default trace shape

    try:
        traced_model = torch.jit.trace(model, example_input)
        traced_model = torch.jit.freeze(traced_model)
        print("    Traced OK")
    except Exception as e:
        print(f"    Trace failed ({e}), using original model ...")
        traced_model = model

    # Step 2: Convert to CoreML
    print("  Converting TorchScript → CoreML ...")
    # Note: compute_precision only works with mlprogram (not neuralnetwork)
    mlmodel = ct.convert(
        traced_model,
        inputs=inputs,
        compute_units=ct.ComputeUnit.ALL,  # ANE + GPU + CPU
        convert_to="neuralnetwork",  # Broader op support
    )

    elapsed = time.time() - t0
    print(f"  Conversion took {elapsed:.1f}s")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    mlmodel.save(str(mlpackage_path))

    size_mb = mlpackage_path.stat().st_size / 1_048_576
    print(f"  ✓ Saved: {mlpackage_path.name} ({size_mb:.1f} MB)")
    print(f"    Compute units: ANE + GPU + CPU")

    return mlpackage_path


def convert_model(model_name: str, input_size: int | None = None) -> Path:
    """Convert a specific model by name."""
    config = get_model_config(model_name)
    model = load_model(model_name, config)

    scale = config["arch_config"]["scale"]

    # Output path
    if input_size is not None:
        suffix = f"_static_{input_size}"
    else:
        suffix = "_dynamic"
    mlpackage_path = Path.home() / ".cache" / "hipixel-core" / "models" / f"{model_name}{suffix}.mlpackage"

    return pytorch_to_coreml(model, mlpackage_path, input_size=input_size, scale=scale)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="RealESRGAN_x4plus", help="Model name")
    parser.add_argument(
        "--input-size",
        type=int,
        default=None,
        help="Static input size (e.g., 512). If not provided, uses dynamic shape.",
    )
    parser.add_argument("--all", action="store_true", help="Convert all known models")
    args = parser.parse_args()

    if args.all:
        models = list(_FALLBACK_CONFIGS.keys())
    else:
        models = [args.model]

    for model_name in models:
        print(f"\n── {model_name} ", end="")
        if args.input_size:
            print(f"(static {args.input_size}x{args.input_size}) ", end="")
        else:
            print("(dynamic) ", end="")
        print("──")

        try:
            mlpackage_path = convert_model(model_name, input_size=args.input_size)
            print(f"  ✓ Saved to: {mlpackage_path}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            import traceback

            traceback.print_exc()

    print("\nDone! CoreML models are ready for Apple Silicon acceleration.")


if __name__ == "__main__":
    main()
