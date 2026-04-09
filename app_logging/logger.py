"""
Simple logger setup for the initial MVP.
"""

import logging
from pathlib import Path


def setup_logger(name: str = "ecu_tool") -> logging.Logger:
    """Create and configure a console + file logger."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_dir / "ecu_tool.log", encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
