"""RRDBNet-series converter (RealESRGAN / RealESRNet)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import torch
import torchvision.transforms as _t

from .base import PthToOnnxConverter
from .utils import ONNX_OPSET, _ensure_deps, _load_checkpoint, export_onnx, verify_onnx, sha256_file


# ---------------------------------------------------------------------------
# Robust RRDBNet import
# ---------------------------------------------------------------------------
# basicsr >= 1.4.2 tries to import torchvision.transforms.functional_tensor
# (removed in recent torchvision) when loading basicsr.data.  We work around
# this by patching a shim module *before* the first basicsr import.

def _patch_functional_tensor() -> None:
    """Add a ``torchvision.transforms.functional_tensor`` shim.

    The shim redirects all attribute access to
    ``torchvision.transforms.functional`` (which still exists).
    """
    if "torchvision.transforms.functional_tensor" in sys.modules:
        return

    import torchvision.transforms.functional as _ft

    class _Shim:
        def __getattr__(self, name: str):
            return getattr(_ft, name)

    _shim_module = _Shim()  # type: ignore[assignment]
    sys.modules["torchvision.transforms.functional_tensor"] = _shim_module  # type: ignore[index]


_patch_functional_tensor()


def _get_RRDBNet():
    """Return the RRDBNet class (patches basicsr first)."""
    import basicsr.archs.rrdbnet_arch as _mod

    return _mod.RRDBNet


try:
    RRDBNet = _get_RRDBNet()
except Exception as _exc:
    # If patching failed, try again after a short cool-off.
    _patch_functional_tensor()
    RRDBNet = _get_RRDBNet()


class RRDBNetConverter:
    """Converter for RRDBNet-based models (RealESRGAN, RealESRNet, …).

    Expected ``arch_config`` keys
    -----------------------------
    ==============  =====  ======================================
    Key             Type   Description
    ==============  =====  ======================================
    ``type``        str    Must equal ``"RRDBNet"``.
    ``num_in_ch``   int    Input channels (usually 3).
    ``num_out_ch``  int    Output channels (usually 3).
    ``num_feat``    int    Base feature count (usually 64).
    ``num_block``   int    Number of residual blocks (e.g. 23).
    ``num_grow_ch`` int    Growth channels in residual blocks.
    ``scale``       int    Upsampling factor (2 or 4).
    ==============  =====  ======================================
    """

    @classmethod
    def supports(cls, arch_config: dict[str, Any]) -> bool:
        return arch_config.get("type") == "RRDBNet"

    def convert(self, pth_path: Path, onnx_path: Path, arch_config: dict[str, Any]) -> None:
        """Convert a RRDBNet ``.pth`` checkpoint to ``.onnx``."""
        _ensure_deps()
        import torch

        # ------------------------------------------------------------------
        # Build architecture
        # ------------------------------------------------------------------
        print(f"  Building RRDBNet(scale={arch_config['scale']}, "
              f"num_block={arch_config['num_block']}) …")
        model = RRDBNet(
            num_in_ch=arch_config["num_in_ch"],
            num_out_ch=arch_config["num_out_ch"],
            num_feat=arch_config["num_feat"],
            num_block=arch_config["num_block"],
            num_grow_ch=arch_config["num_grow_ch"],
            scale=arch_config["scale"],
        )

        # ------------------------------------------------------------------
        # Load weights
        # ------------------------------------------------------------------
        print(f"  Loading weights from {pth_path} …")
        state_dict = _load_checkpoint(pth_path)
        model.load_state_dict(state_dict, strict=True)
        model.eval()
        print("  Weights loaded OK.")

        # ------------------------------------------------------------------
        # Export ONNX
        # ------------------------------------------------------------------
        opset = arch_config.get("opset", ONNX_OPSET)
        print(f"  Exporting ONNX (opset={opset}, dynamic H×W) …")
        export_onnx(model, onnx_path, opset=opset)

        size_mb = onnx_path.stat().st_size / 1_048_576
        sha = sha256_file(onnx_path)
        print(f"  ✓ {onnx_path}  ({size_mb:.1f} MB, sha256={sha[:16]}…)")

        # ------------------------------------------------------------------
        # Verify
        # ------------------------------------------------------------------
        verify_onnx(onnx_path, scale=arch_config["scale"])

        # ------------------------------------------------------------------
        # Stamp registry-friendly metadata into a sidecar file
        # ------------------------------------------------------------------
        sidecar = onnx_path.with_suffix(".meta.json")
        import json

        sidecar.write_text(
            json.dumps(
                {"size_bytes": onnx_path.stat().st_size, "sha256": sha},
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"  Metadata written to {sidecar.name}")
