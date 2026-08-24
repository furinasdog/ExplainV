"""
ExplainV logging configuration.

Provides a unified logger with console + file output.

Usage::

    from utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Pipeline started")
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_LOG_DIR = Path(__file__).resolve().parent.parent / "data" / "logs"
_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_INITIALIZED = False


def _ensure_log_dir() -> Path:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    return _LOG_DIR


def setup_logging(
    level: int = logging.INFO,
    log_file: str | None = None,
    console: bool = True,
) -> None:
    """Initialize the root logger (idempotent — safe to call multiple times).

    Args:
        level:    Logging level (e.g. ``logging.DEBUG``).
        log_file: Optional path to a log file. If *None*, a timestamped
                  file is created under ``data/logs/``.
        console:  Whether to also log to stderr.
    """
    global _INITIALIZED
    if _INITIALIZED:
        return
    _INITIALIZED = True

    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATE_FORMAT)

    # -- Console handler --
    if console:
        ch = logging.StreamHandler(sys.stderr)
        ch.setLevel(level)
        ch.setFormatter(formatter)
        root.addHandler(ch)

    # -- File handler --
    if log_file is None:
        log_dir = _ensure_log_dir()
        log_file = str(log_dir / f"explainv_{datetime.now():%Y%m%d_%H%M%S}.log")

    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(level)
    fh.setFormatter(formatter)
    root.addHandler(fh)

    root.info("Logging initialized — file: %s", log_file)


def get_logger(name: str) -> logging.Logger:
    """Get a named logger, ensuring logging is set up.

    Args:
        name: Logger name (typically ``__name__``).

    Returns:
        A :class:`logging.Logger` instance.
    """
    if not _INITIALIZED:
        setup_logging()
    return logging.getLogger(name)
