"""Structured logging with rotating file support."""

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

from config.constants import (
    LOG_BACKUP_COUNT,
    LOG_FILE,
    LOG_MAX_BYTES,
)


class Logger:
    """Centralized logger factory for the migration tool."""

    _initialized = False
    _loggers: dict[str, logging.Logger] = {}

    @classmethod
    def setup_logger(
        cls,
        name: str = "migration_tool",
        level: int = logging.INFO,
    ) -> logging.Logger:
        """Create or return a configured logger with rotating file output."""
        if name in cls._loggers:
            return cls._loggers[name]

        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = False

        if not logger.handlers:
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )

            file_handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        cls._loggers[name] = logger
        cls._initialized = True
        return logger

    @classmethod
    def get_logger(cls, category: Optional[str] = None) -> logging.Logger:
        """Return a category-specific child logger."""
        base = cls.setup_logger()
        if not category:
            return base
        return base.getChild(category)
