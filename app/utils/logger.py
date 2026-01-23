"""
Logger utility for application-wide logging.
"""

import logging
from typing import Optional, Dict, Any


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Args:
        name: Logger name, typically __name__ from calling module.

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger


def log_info(logger: logging.Logger, message: str,
             extra_data: Optional[Dict[str, Any]] = None) -> None:
    """
    Log an info level message with optional extra data.

    Args:
        logger: Logger instance.
        message: Log message.
        extra_data: Optional dictionary with additional information.
    """
    if extra_data:
        logger.info(f"{message} - {extra_data}")
    else:
        logger.info(message)


def log_error(logger: logging.Logger, message: str,
              extra_data: Optional[Dict[str, Any]] = None) -> None:
    """
    Log an error level message with optional extra data.

    Args:
        logger: Logger instance.
        message: Log message.
        extra_data: Optional dictionary with additional information.
    """
    if extra_data:
        logger.error(f"{message} - {extra_data}")
    else:
        logger.error(message)


def log_warning(logger: logging.Logger, message: str,
                extra_data: Optional[Dict[str, Any]] = None) -> None:
    """
    Log a warning level message with optional extra data.

    Args:
        logger: Logger instance.
        message: Log message.
        extra_data: Optional dictionary with additional information.
    """
    if extra_data:
        logger.warning(f"{message} - {extra_data}")
    else:
        logger.warning(message)
