"""Tests for utils.logger — logging setup behaviour."""

import logging

import utils.logger as logger_module
from utils.logger import get_logger, setup_logging


class TestSetupLogging:
    def test_idempotent(self):
        setup_logging()
        handler_count = len(logging.getLogger().handlers)

        setup_logging(level=logging.DEBUG, console=False)
        assert len(logging.getLogger().handlers) == handler_count

    def test_get_logger_returns_named_logger(self):
        logger = get_logger("explainv.test-logger")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "explainv.test-logger"

    def test_log_file_written(self):
        setup_logging()
        get_logger("explainv.file-check").info("file handler message")
        log_dir = logger_module._LOG_DIR
        assert log_dir.is_dir()
        assert any(log_dir.glob("explainv_*.log"))
