import logging
import os
from logging.handlers import RotatingFileHandler

def get_logger(name: str = "jurbas") -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        log_level = logging.DEBUG if os.environ.get("JURBAS_DEBUG") else logging.INFO
        logger.setLevel(log_level)

        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # 5MB per file, 3 backups
        handler = RotatingFileHandler(
            "jurbas.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger

logger = get_logger()
