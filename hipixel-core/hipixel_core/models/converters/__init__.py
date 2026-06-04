"""``pth`` → ``onnx`` converter package.

This module provides a pluggable conversion pipeline so that models shipped
as PyTorch ``.pth`` weights can be exported to the ONNX format that
``hipixel-core`` uses for inference.

Usage
-----
Converters are selected automatically based on the ``arch_config["type"]``
field in :file:`registry.json`.  End-users normally don't interact with
this package directly — :class:`~hipixel_core.models.manager.ModelManager`
calls it when a download fails and ``source_pth_url`` is present.

See :mod:`hipixel_core.models.converters.base` for the converter protocol
and :mod:`hipixel_core.models.converters.rrdbsr` for the RRDBNet
implementation used by Real-ESRGAN models.
"""

from __future__ import annotations

from pathlib import Path

from .base import PthToOnnxConverter
from .rrdbsr import RRDBNetConverter

#: All built-in converters, tried in registration order.
_CONVERTERS: list[type[PthToOnnxConverter]] = [
    RRDBNetConverter,
]


def get_converter(arch_config: dict) -> PthToOnnxConverter:
    """Return the first converter that supports *arch_config*.

    Raises ``ValueError`` when no converter matches.
    """
    for cls in _CONVERTERS:
        if cls.supports(arch_config):
            return cls()
    raise ValueError(
        f"No converter for arch_config type={arch_config.get('type')!r}."
        f" Registered converters: {[c.__name__ for c in _CONVERTERS]}"
    )


def convert(pth_path: str | Path, onnx_path: str | Path, *, arch_config: dict) -> None:
    """Convert a ``.pth`` checkpoint to ``.onnx``.

    Parameters
    ----------
    pth_path:
        Local path to the PyTorch checkpoint.
    onnx_path:
        Destination path for the exported ``.onnx`` file.
    arch_config:
        Architecture descriptor from :file:`registry.json`
        (the ``arch_config`` field).
    """
    converter = get_converter(arch_config)
    converter.convert(Path(pth_path), Path(onnx_path), arch_config)


__all__ = [
    "PthToOnnxConverter",
    "RRDBNetConverter",
    "convert",
    "get_converter",
]
