"""
Tests for hipixel_core logging infrastructure.

Verifies:
- Logger namespace convention (get_logger)
- NullHandler attached to root logger by default (PEP 396)
- setup_rich_logging sets level and adds RichHandler
- Idempotency of setup_rich_logging
- Library components emit log records at the correct levels
"""

from __future__ import annotations

import logging

import pytest


# ---------------------------------------------------------------------------
# _log module — get_logger / setup_rich_logging
# ---------------------------------------------------------------------------


def test_get_logger_namespace() -> None:
    """get_logger('pipeline') returns a logger named 'hipixel_core.pipeline'."""
    from hipixel_core._log import get_logger

    assert get_logger("pipeline").name == "hipixel_core.pipeline"


def test_get_logger_nested_namespace() -> None:
    """get_logger('backends.cpu') returns 'hipixel_core.backends.cpu'."""
    from hipixel_core._log import get_logger

    assert get_logger("backends.cpu").name == "hipixel_core.backends.cpu"


def test_null_handler_attached() -> None:
    """hipixel_core root logger carries a NullHandler after import."""
    import hipixel_core  # noqa: F401

    root = logging.getLogger("hipixel_core")
    assert any(isinstance(h, logging.NullHandler) for h in root.handlers)


def test_setup_rich_logging_sets_level() -> None:
    """setup_rich_logging(DEBUG) sets the root logger level to DEBUG."""
    from hipixel_core._log import setup_rich_logging

    setup_rich_logging(logging.DEBUG)
    root = logging.getLogger("hipixel_core")
    assert root.level == logging.DEBUG


def test_setup_rich_logging_adds_handler() -> None:
    """setup_rich_logging adds exactly a RichHandler to the root logger."""
    from rich.logging import RichHandler

    from hipixel_core._log import setup_rich_logging

    setup_rich_logging(logging.WARNING)
    root = logging.getLogger("hipixel_core")
    assert any(isinstance(h, RichHandler) for h in root.handlers)


def test_setup_rich_logging_idempotent() -> None:
    """Calling setup_rich_logging twice does not add a second RichHandler."""
    from rich.logging import RichHandler

    from hipixel_core._log import setup_rich_logging

    setup_rich_logging(logging.DEBUG)
    setup_rich_logging(logging.DEBUG)
    root = logging.getLogger("hipixel_core")
    rich_handlers = [h for h in root.handlers if isinstance(h, RichHandler)]
    assert len(rich_handlers) == 1


def test_setup_rich_logging_quiet() -> None:
    """setup_rich_logging(ERROR) sets the root logger level to ERROR."""
    from hipixel_core._log import setup_rich_logging

    setup_rich_logging(logging.ERROR)
    root = logging.getLogger("hipixel_core")
    assert root.level == logging.ERROR


# ---------------------------------------------------------------------------
# Filter log emission
# ---------------------------------------------------------------------------


def test_cas_setup_emits_debug(caplog: pytest.LogCaptureFixture) -> None:
    """CASFilter.setup emits a DEBUG record containing sharpness value."""
    from hipixel_core.backends.cpu import CpuBackend
    from hipixel_core.filters.cas import CASFilter

    be = CpuBackend()
    be.initialize()
    filt = CASFilter()

    with caplog.at_level(logging.DEBUG, logger="hipixel_core.filters.cas"):
        filt.setup(be, {"sharpness": 0.7})

    messages = [r.message for r in caplog.records]
    assert any("CASFilter.setup" in m for m in messages)
    assert any("0.70" in m for m in messages)

    be.shutdown()


def test_cas_teardown_emits_debug(caplog: pytest.LogCaptureFixture) -> None:
    """CASFilter.teardown emits a DEBUG record."""
    from hipixel_core.backends.cpu import CpuBackend
    from hipixel_core.filters.cas import CASFilter

    be = CpuBackend()
    be.initialize()
    filt = CASFilter()
    filt.setup(be, {})

    with caplog.at_level(logging.DEBUG, logger="hipixel_core.filters.cas"):
        filt.teardown(be)

    assert any("CASFilter.teardown" in r.message for r in caplog.records)

    be.shutdown()


# ---------------------------------------------------------------------------
# Backend log emission
# ---------------------------------------------------------------------------


def test_cpu_backend_initialize_emits_debug(caplog: pytest.LogCaptureFixture) -> None:
    """CpuBackend.initialize emits DEBUG records at start and on ready."""
    from hipixel_core.backends.cpu import CpuBackend

    be = CpuBackend()
    with caplog.at_level(logging.DEBUG, logger="hipixel_core.backends.cpu"):
        be.initialize()

    messages = [r.message for r in caplog.records]
    assert any("CpuBackend.initialize" in m for m in messages)
    be.shutdown()


def test_cpu_backend_shutdown_emits_debug(caplog: pytest.LogCaptureFixture) -> None:
    """CpuBackend.shutdown emits a DEBUG record with session count."""
    from hipixel_core.backends.cpu import CpuBackend

    be = CpuBackend()
    be.initialize()
    with caplog.at_level(logging.DEBUG, logger="hipixel_core.backends.cpu"):
        be.shutdown()

    assert any("CpuBackend.shutdown" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Bench runner log emission
# ---------------------------------------------------------------------------


def test_bench_runner_emits_info_on_complete(caplog: pytest.LogCaptureFixture) -> None:
    """BenchmarkRunner.run_filter emits an INFO record with fps stats."""
    from hipixel_core.backends.cpu import CpuBackend
    from hipixel_core.bench.runner import BenchmarkRunner

    be = CpuBackend()
    be.initialize()
    runner = BenchmarkRunner(be)

    with caplog.at_level(logging.INFO, logger="hipixel_core.bench"):
        result = runner.run_filter("cas", resolution="320x240", frames=5)

    info_messages = [r.message for r in caplog.records if r.levelno == logging.INFO]
    # Should have at least one INFO record mentioning the filter name
    assert any(result.filter_name in m for m in info_messages)
    # And fps data
    assert any("fps" in m for m in info_messages)

    be.shutdown()
