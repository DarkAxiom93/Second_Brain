"""Standard-library logging configuration."""

import logging
from typing import TextIO

_SUPPORTED_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class _ApplicationLogHandler(logging.StreamHandler[TextIO]):
    """Handler type used to make application logging setup idempotent."""


def configure_logging(level: str) -> None:
    """Configure concise root logging without adding duplicate handlers."""

    normalized_level = level.strip().upper()
    if normalized_level not in _SUPPORTED_LEVELS:
        raise ValueError(f"Unsupported logging level: {level!r}")

    numeric_level = getattr(logging, normalized_level)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    handler = next(
        (
            existing
            for existing in root_logger.handlers
            if isinstance(existing, _ApplicationLogHandler)
        ),
        None,
    )
    if handler is None:
        handler = _ApplicationLogHandler()
        root_logger.addHandler(handler)

    handler.setLevel(numeric_level)
    handler.setFormatter(logging.Formatter(_FORMAT))
    # Provider libraries must not emit request URLs or headers through root logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
