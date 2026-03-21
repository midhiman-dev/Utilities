from __future__ import annotations

import logging
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path


@dataclass(frozen=True)
class LoggerContext:
    logger: logging.Logger
    log_file: Path


def configure_app_logger(logs_root: Path) -> LoggerContext:
    logs_root.mkdir(parents=True, exist_ok=True)
    log_file = logs_root / "app.log"

    logger = logging.getLogger("pdf_gui")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not any(isinstance(handler, RotatingFileHandler) for handler in logger.handlers):
        handler = RotatingFileHandler(
            log_file,
            maxBytes=1_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return LoggerContext(logger=logger, log_file=log_file)
