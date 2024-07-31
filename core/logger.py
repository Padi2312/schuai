import logging
from logging.handlers import RotatingFileHandler
import os


class LogColors:
    RESET = "\033[0m"
    DEBUG = "\033[94m"  # Blue
    INFO = "\033[37m"  # White
    WARNING = "\033[93m"  # Yellow
    ERROR = "\033[91m"  # Red
    CRITICAL = "\033[41m\033[37m"  # White on Red


class ColoredFormatter(logging.Formatter):
    def format(self, record):
        # Get the log level and its corresponding color
        level_color = {
            logging.DEBUG: LogColors.DEBUG,
            logging.INFO: LogColors.INFO,
            logging.WARNING: LogColors.WARNING,
            logging.ERROR: LogColors.ERROR,
            logging.CRITICAL: LogColors.CRITICAL,
        }.get(record.levelno, LogColors.RESET)

        # Create a colored log level string
        level_name = f"{level_color}{record.levelname}{LogColors.RESET}"

        # Create a new log message with the colored level
        log_message = super().format(record)

        # Replace the level name in the log message with the colored version
        log_message = log_message.replace(record.levelname, level_name)

        return log_message


def create_logger(name):
    """Create and configure a custom logger."""
    logger = logging.getLogger(name)

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    logger.setLevel(LOG_LEVEL)

    # Create a console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)  # Set the level for the console handler

    # Create a colored formatter
    formatter = ColoredFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(formatter)

    # Add the console handler to the logger
    logger.addHandler(console_handler)

    os.makedirs("logs", exist_ok=True)
    log_handler = RotatingFileHandler(
        "logs/app.log", mode="a", maxBytes=1024*512, backupCount=1, encoding="utf-8"
    )
    log_handler.setLevel(logging.DEBUG)
    log_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )  # Use the same formatter
    # Add the file handler to the logger
    logger.addHandler(log_handler)

    return logger


log = create_logger("APP")
