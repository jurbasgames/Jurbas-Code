import pytest
import os
import logging
from jurbas_code.log_config import get_logger

def test_get_logger():
    # Remove any existing handlers to test fresh initialization
    test_logger = logging.getLogger("test_jurbas")
    test_logger.handlers.clear()

    logger = get_logger("test_jurbas")
    assert logger.name == "test_jurbas"
    assert len(logger.handlers) == 1

    handler = logger.handlers[0]
    from logging.handlers import RotatingFileHandler
    assert isinstance(handler, RotatingFileHandler)
    assert handler.baseFilename.endswith("jurbas.log")
    assert handler.maxBytes == 5 * 1024 * 1024
    assert handler.backupCount == 3

    # Calling again should not add another handler
    logger2 = get_logger("test_jurbas")
    assert len(logger2.handlers) == 1
