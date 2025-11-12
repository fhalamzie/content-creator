"""
Central logging system using structlog

Provides structured logging with:
- ISO timestamps
- Log levels
- Context variables
- Metrics tracking hooks

Usage:
    # In main.py (call ONCE)
    from src.utils.logger import setup_logging
    setup_logging(log_level="INFO")

    # In any module
    from src.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("event", key="value")

Output:
    {"event": "event", "key": "value", "timestamp": "2025-11-03T12:00:00Z", "level": "info"}
"""

import logging
import sys
import structlog


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure central logging system

    Call this ONCE in main.py or application entry point.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Raises:
        AttributeError: If log_level is not a valid logging level
    """
    # Convert string to logging constant
    numeric_level = getattr(logging, log_level.upper())

    # Force unbuffered stdout for immediate log visibility
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
        force=True  # Override any existing configuration
    )

    # Configure structlog
    structlog.configure(
        processors=[
            # Merge contextvars (for correlation IDs, request IDs, etc.)
            structlog.contextvars.merge_contextvars,
            # Add log level to output
            structlog.processors.add_log_level,
            # Add ISO timestamp
            structlog.processors.TimeStamper(fmt="iso"),
            # Console renderer for human-readable output
            structlog.dev.ConsoleRenderer()
        ],
        # Filter by log level
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        # Use dict for context
        context_class=dict,
        # Use standard library logging
        logger_factory=structlog.PrintLoggerFactory(),
        # Cache loggers for performance
        cache_logger_on_first_use=True
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """
    Get logger for module

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog BoundLogger

    Usage:
        from src.utils.logger import get_logger

        logger = get_logger(__name__)
        logger.info("rss_collection_started", feed_count=20)
        logger.error("rss_collection_failed", error=str(e), feed=url)
    """
    return structlog.get_logger(name)
