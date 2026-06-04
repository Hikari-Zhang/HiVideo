#!/usr/bin/env python3
"""
Export Real-ESRGAN models  .pth → .onnx  using the unified converter pipeline.

Usage
-----
# Install conversion dependencies:
    pip install 'hipixel-core[convert]'

# Export RealESRGAN_x4plus  (downloads .pth if not cached):
    python scripts/export_realesrgan_onnx.py --model RealESRGAN_x4plus

# Export *all* models listed in registry.json that have source_pth_url:
    python scripts/export_realesrgan_onnx.py --all

Output
------
~/.cache/hipixel-core/models/<ModelName>.onnx
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Model catalogue  – kept for standalone CLI use.
# New models should be added to registry.json under ``source_pth_url``.
# ---------------------------------------------------------------------------

_MODELS: dict[str, dict] = {
    "RealESRGAN_x4plus": {
        "scale": 4,
        "arch_config": {
            "type": "RRDBNet",
            "num_in_ch": 3,
            "num_out_ch": 3,
            "num_feat": 64,
            "num_block": 23,
            "num_grow_ch": 32,
            "scale": 4,
        },
        "pth_url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
        "pth_name": "RealESRGAN_x4plus.pth",
    },
    "RealESRGAN_x2plus": {
        "scale": 2,
        "arch_config": {
            "type": "RRDBNet",
            "num_in_ch": 3,
            "num_out_ch": 3,
            "num_feat": 64,
            "num_block": 23,
            "num_grow_ch": 32,
            "scale": 2,
        },
        "pth_url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
        "pth_name": "RealESRGAN_x2plus.pth",
    },
    "RealESRNet_x4plus": {
        "scale": 4,
        "arch_config": {
            "type": "RRDBNet",
            "num_in_ch": 3,
            "num_out_ch": 3,
            "num_feat": 64,
            "num_block": 23,
            "num_grow_ch": 32,
            "scale": 4,
        },
        "pth_url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.1/RealESRNet_x4plus.pth",
        "pth_name": "RealESRNet_x4plus.pth",
    },
}

_CACHE_DIR = Path.home() / ".cache" / "hipixel-core" / "models"

# Try to load additional entries from registry.json
_REGISTRY_PATH = (
    Path(__file__).resolve().parent.parent / "hipixel_core" / "models" / "registry.json"
)
if _REGISTRY_PATH.exists():
    try:
        _REGISTRY = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
        for _name, _entry in _REGISTRY.get("models", {}).items():
            if "source_pth_url" in _entry and _name not in _MODELS:
                _MODELS[_name] = {
                    "scale": _entry.get("scale", 4),
                    "arch_config": _entry.get("arch_config", {}),
                    "pth_url": _entry["source_pth_url"],
                    "pth_name": _entry.get("pth_name", f"{_name}.pth"),
                }
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Export  – delegates to hipixel_core.models.converters
# ---------------------------------------------------------------------------

def export(model_name: str, opset: int = 11, tile_size: int = 64) -> Path:
    """
    Download .pth (if needed) and export to .onnx via the unified converter.
    """
    import torch  # lazy: only needed at export time

    cfg = _MODELS.get(model_name)
    if cfg is None:
        # Fallback: try registry-based conversion via ModelManager
        print(f"  '{model_name}' not in built-in catalogue — trying ModelManager …")
        from hipixel_core.models.manager import ModelManager

        onnx_path = Path.home() / ".cache" / "hipixel-core" / "models" / f"{model_name}.onnx"
        # Trigger the auto-conversion pipeline by force-downloading
        ModelManager.download(model_name, force=True)
        print(f"  ✓ Converted via ModelManager → {onnx_path}")
        return onnx_path

    pth_path = _CACHE_DIR / cfg["pth_name"]

    # ------------------------------------------------------------------
    # Fetch .pth weights (if not cached)
    # ------------------------------------------------------------------
    if not pth_path.exists():
        import httpx

        pth_url = cfg["pth_url"]
        print(f"  Downloading .pth weights: {pth_url} …")
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = pth_path.with_suffix(".tmp")
        with httpx.stream("GET", pth_url, follow_redirects=True, timeout=120.0) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=65536):
                    f.write(chunk)
        tmp.rename(pth_path)
        print(f"  Saved → {pth_path}")
    else:
        print(f"  Using cached .pth: {pth_path}")

    # ------------------------------------------------------------------
    # Convert via unified converter module
    # ------------------------------------------------------------------
    onnx_path = _CACHE_DIR / f"{model_name}.onnx"
    print(f"  Converting → {onnx_path.name} …")
    from hipixel_core.models.converters import convert as _convert

    _convert(pth_path, onnx_path, arch_config=cfg["arch_config"])

    size_mb = onnx_path.stat().st_size / 1_048_576
    print(f"  ✓ {onnx_path}  ({size_mb:.1f} MB)")
    return onnx_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="RealESRGAN_x4plus", help="Model to export (see --list for all)")
    parser.add_argument("--opset", type=int, default=11, help="ONNX opset version (default: 11)")
    parser.add_argument("--tile", type=int, default=64, help="Dummy tile size for export trace (default: 64)")
    parser.add_argument("--all", dest="all_models", action="store_true", help="Export all known models")
    parser.add_argument("--list", action="store_true", help="List all known models and exit")
    args = parser.parse_args()

    if args.list:
        for name in _MODELS:
            print(f"  {name}")
        return

    targets = list(_MODELS) if args.all_models else [args.model]
    for name in targets:
        print(f"\n── {name} ──")
        onnx_path = export(name, opset=args.opset, tile_size=args.tile)

    print("\nDone.  Models are ready in ~/.cache/hipixel-core/models/")
    print("You can now upload them to a public mirror and update registry.json.")


if __name__ == "__main__":
    main()
