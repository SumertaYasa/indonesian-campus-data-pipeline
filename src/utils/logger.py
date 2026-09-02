import logging
import datetime
from pathlib import Path

def setup_logger(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_file = log_dir / f"scrape_{timestamp}.log"
    
    logger = logging.getLogger("quipper_scraper")
    logger.setLevel(logging.DEBUG)
    
    # Avoid duplicate handlers if setup is called multiple times
    if logger.handlers:
        return logger
        
    # File handler (DEBUG and up)
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh_formatter = logging.Formatter('%(asctime)s | %(levelname)-7s | %(message)s')
    fh.setFormatter(fh_formatter)
    
    # Console handler (INFO and up)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    # The console just gets the raw message without prefixes for cleaner progress formatting
    ch_formatter = logging.Formatter('%(message)s')
    ch.setFormatter(ch_formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger

def get_logger() -> logging.Logger:
    """Returns the configured logger. Call setup_logger first at the entrypoint."""
    return logging.getLogger("quipper_scraper")
