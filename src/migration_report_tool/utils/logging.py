"""Central logging configuration for runtime diagnostics."""
from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_dir: Path, level: int = logging.INFO) -> logging.Logger:
    log_dir = Path(log_dir); log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("migration_report_tool")
    logger.setLevel(level)
    if not logger.handlers:
        handler = RotatingFileHandler(log_dir / "migration-report-tool.log", maxBytes=4*1024*1024, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s"))
        logger.addHandler(handler)
    return logger
