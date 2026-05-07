import logging
import sys
from logging.handlers import RotatingFileHandler
import os

def setup_logger(name="AEP_DataExplorer"):
    """Sets up application logger with console and file handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Create formatters
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler (Rotating) - Store in APPDATA
    app_data_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AEP_DataExplorer")
    log_dir = os.path.join(app_data_dir, "logs")
    
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
        
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, "app.log"),
        maxBytes=5*1024*1024,  # 5 MB
        backupCount=3
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# Global logger instance
logger = setup_logger()
