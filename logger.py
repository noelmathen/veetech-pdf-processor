# veetech_app/logger.py

import logging
from .config import AppConfig

class AppLogger:
    """Application logging manager."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.setup_logging()

    def setup_logging(self):
        """Configure application logging."""
        log_format = "%(asctime)s [%(levelname)s] %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"

        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            datefmt=date_format,
            handlers=[]
        )
        logger = logging.getLogger()

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format, date_format))
        logger.addHandler(console_handler)

        # File handler (if enabled)
        if self.config.save_logs:
            file_handler = logging.FileHandler(self.config.log_file)
            file_handler.setFormatter(logging.Formatter(log_format, date_format))
            logger.addHandler(file_handler)

    @staticmethod
    def get_logger(name: str = __name__) -> logging.Logger:
        """Get a logger instance."""
        return logging.getLogger(name)
