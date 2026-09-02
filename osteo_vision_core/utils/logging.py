"""Logging utilities for the Osteo Vision medical imaging platform.

This module provides a unified logging interface with support for different log levels,
formatters, and handlers.
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_timestamp() -> str:
    """Get UTC timestamp in ISO format."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class Logger:
    """
    Unified logger for the Osteo Vision medical imaging platform.

    Provides standard logging methods plus specialized methods for
    performance, lifecycle, inference, and training events.
    """

    def __init__(
        self,
        name: str,
        level: int = logging.DEBUG,
        log_file: str | Path | None = None,
    ):
        """
        Initialize logger.

        Args:
            name: Logger name (usually module name)
            level: Logging level
            log_file: Optional log file path
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # Avoid adding handlers multiple times
        if not self.logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_format = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            console_handler.setFormatter(console_format)
            self.logger.addHandler(console_handler)

            # File handler (if specified)
            if log_file:
                log_path = Path(log_file)
                log_path.parent.mkdir(parents=True, exist_ok=True)
                file_handler = logging.FileHandler(log_path, encoding="utf-8")
                file_handler.setLevel(logging.DEBUG)
                file_format = logging.Formatter(
                    "%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
                file_handler.setFormatter(file_format)
                self.logger.addHandler(file_handler)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self.logger.debug(message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self.logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self.logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        self.logger.error(message, **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message."""
        self.logger.critical(message, **kwargs)

    def performance(self, operation: str, duration_ms: float, **kwargs: Any) -> None:
        """
        Log performance metric.

        Args:
            operation: Operation name
            duration_ms: Duration in milliseconds
            **kwargs: Additional context
        """
        extra = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        msg = f"Performance: {operation} took {duration_ms:.2f}ms"
        if extra:
            msg += f" | {extra}"
        self.logger.info(msg)

    def lifecycle(self, component: str, event: str, **kwargs: Any) -> None:
        """
        Log lifecycle event.

        Args:
            component: Component name
            event: Event name (e.g., "initialized", "started", "stopped")
            **kwargs: Additional context
        """
        extra = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        msg = f"Lifecycle: {component} - {event}"
        if extra:
            msg += f" | {extra}"
        self.logger.info(msg)

    def inference(
        self,
        case_id: str,
        model_id: str,
        task_type: str,
        duration_ms: float,
        **kwargs: Any,
    ) -> None:
        """
        Log inference event.

        Args:
            case_id: Case ID
            model_id: Model ID
            task_type: Task type
            duration_ms: Duration in milliseconds
            **kwargs: Additional context
        """
        extra = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        msg = f"Inference: case={case_id} model={model_id} task={task_type} duration={duration_ms:.2f}ms"
        if extra:
            msg += f" | {extra}"
        self.logger.info(msg)

    def training(
        self,
        epoch: int,
        loss: float,
        metric: float | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Log training event.

        Args:
            epoch: Current epoch
            loss: Current loss
            metric: Optional metric value
            **kwargs: Additional context
        """
        extra = " | ".join(f"{k}={v}" for k, v in kwargs.items())
        msg = f"Training: epoch={epoch} loss={loss:.4f}"
        if metric is not None:
            msg += f" metric={metric:.4f}"
        if extra:
            msg += f" | {extra}"
        self.logger.info(msg)


# Global logger registry
_loggers: dict[str, Logger] = {}


def get_logger(
    name: str,
    level: int = logging.DEBUG,
    log_file: str | Path | None = None,
) -> Logger:
    """
    Get or create a logger instance.

    Args:
        name: Logger name
        level: Logging level
        log_file: Optional log file path

    Returns:
        Logger instance
    """
    if name not in _loggers:
        _loggers[name] = Logger(name, level, log_file)
    return _loggers[name]
