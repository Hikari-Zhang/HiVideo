"""
hipixel-core — AI video enhancement engine.

Phase 0 Python-first implementation.
Phase 2.5: Rust kernel + PyO3 bindings (planned).
"""

from __future__ import annotations

import logging

# PEP 396 / PEP 3105 convention: attach a NullHandler so that library users
# who do not configure logging see no output.  The CLI (and other application
# code) may call ``hipixel_core._log.setup_rich_logging()`` to activate output.
logging.getLogger("hipixel_core").addHandler(logging.NullHandler())

__version__ = "0.1.0-alpha"
__author__ = "HiVideo Contributors"
__license__ = "Apache-2.0"

from hipixel_core.types import (
    ColorSpace,
    DeviceInfo,
    OutputSpec,
    PipelineResult,
    ProgressEvent,
    VideoFrame,
    VideoMeta,
)

__all__ = [
    "ColorSpace",
    "DeviceInfo",
    "OutputSpec",
    "PipelineResult",
    "ProgressEvent",
    "VideoFrame",
    "VideoMeta",
    "__version__",
]
