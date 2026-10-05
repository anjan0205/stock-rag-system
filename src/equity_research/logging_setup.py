"""Logging configuration.

Every module logs through the standard `logging` library. In Phase 2 we will
also log full agent prompts/responses; centralizing setup here keeps that
consistent. Logs go to both console and a rotating-per-run file.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

_configured = False


def setup_logging(log_dir: Path, level: int = logging.INFO) -> Path:
    """Configure root logging once. Returns the path of the run log file."""
    global _configured
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"run_{stamp}.log"

    if _configured:
        return log_file

    fmt = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
    formatter = logging.Formatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # yfinance/urllib3 are chatty; keep them at WARNING.
    for noisy in ("urllib3", "yfinance", "peewee", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True
    return log_file


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
