"""Central logging helpers for hipixel-core.

Library code calls ``get_logger(name)`` to obtain a child logger underneath
the ``hipixel_core`` root.  Application code (CLI, notebooks) calls
``setup_rich_logging(level)`` once to activate human-readable output via
Rich's ``RichHandler``.

The ``NullHandler`` attached to the root logger in ``__init__.py`` ensures
that library users who never call ``setup_rich_logging`` see no output —
the standard PEP 396 / PEP 3105 convention for library logging.
"""

from __future__ import annotations

import logging

_ROOT = "hipixel_core"


def get_logger(name: str) -> logging.Logger:
    """Return ``logging.getLogger("hipixel_core.<name>")``.

    Args:
        name: Dotted sub-name, e.g. ``"pipeline"`` or ``"backends.cpu"``.

    Returns:
        A :class:`logging.Logger` whose name is ``"hipixel_core.<name>"``.
    """
    return logging.getLogger(f"{_ROOT}.{name}")


def setup_rich_logging(level: int = logging.WARNING) -> None:
    """Attach a :class:`rich.logging.RichHandler` to the ``hipixel_core`` root logger.

    This function is **idempotent** — calling it multiple times does not add
    duplicate handlers.  The ``NullHandler`` added in ``__init__.py`` remains
    in place so that library users who never call this function see no output.

    Intended to be called once at application start-up (e.g. from the CLI
    callback) before any library functions are invoked.

    Args:
        level: Log level for both the root logger and the handler.
               Typical values: ``logging.DEBUG``, ``logging.INFO``,
               ``logging.WARNING`` (default), ``logging.ERROR``.
    """
    from rich.logging import RichHandler

    root = logging.getLogger(_ROOT)
    root.setLevel(level)

    # Guard against duplicate handlers if called more than once.
    if not any(isinstance(h, RichHandler) for h in root.handlers):
        handler = RichHandler(
            rich_tracebacks=True,
            show_path=False,
            markup=True,
        )
        handler.setLevel(level)
        root.addHandler(handler)
