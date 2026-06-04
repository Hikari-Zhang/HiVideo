"""Converter protocol & base utilities.

Every ``.pth`` → ``.onnx`` converter must implement the
:class:`PthToOnnxConverter` protocol.
"""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import Protocol, runtime_checkable

from .utils import ONNX_OPSET, export_onnx, verify_onnx


@runtime_checkable
class PthToOnnxConverter(Protocol):
    """Protocol that all converters must satisfy.

    A *converter* knows how to build the correct model architecture,
    load PyTorch weights from a ``.pth`` file, and export the model to
    the ONNX format.
    """

    @classmethod
    @abstractmethod
    def supports(cls, arch_config: dict) -> bool:
        """Return ``True`` if this converter can handle *arch_config*."""
        ...

    @abstractmethod
    def convert(self, pth_path: Path, onnx_path: Path, arch_config: dict) -> None:
        """Convert *pth_path* → *onnx_path*.

        Parameters
        ----------
        pth_path:
            Local ``.pth`` checkpoint (already downloaded).
        onnx_path:
            Destination ``.onnx`` file path.
        arch_config:
            Architecture descriptor from :file:`registry.json`.
        """
        ...
