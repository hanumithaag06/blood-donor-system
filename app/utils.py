"""
Cross-cutting concerns: centralized logging setup and custom exceptions.
Using custom exceptions (instead of raw ValueError everywhere) lets routes
catch specific error types and return appropriate HTTP status codes.
"""
import logging
import sys

from app.settings import settings


def get_logger(name: str) -> logging.Logger:
    """Returns a configured logger instance for the given module name."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))
    return logger


# ---------- Custom Exceptions ----------

class AppError(Exception):
    """Base exception for all application-specific errors."""
    status_code = 500

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NotFoundError(AppError):
    """Raised when a requested entity does not exist."""
    status_code = 404


class ValidationError(AppError):
    """Raised when input fails a business-rule validation check."""
    status_code = 400


class DuplicateError(AppError):
    """Raised when attempting to create a record that violates uniqueness."""
    status_code = 409