"""
Logging initializer — separate log files per event type, with rotation.
Mirrors polymarket-arbitrage utils/logging_utils.py.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Custom log levels
TRADE = 25      # Between INFO and WARNING
OPPORTUNITY = 26


def setup_logging(
    log_dir: str = "logs",
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    main_log_file: str = "scanner.log",
    trades_log_file: str = "trades.log",
    opportunities_log_file: str = "opportunities.log",
    max_size_mb: int = 50,
    backup_count: int = 5,
):
    """Configure logging with per-event-type log files."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Register custom levels
    logging.addLevelName(TRADE, "TRADE")
    logging.addLevelName(OPPORTUNITY, "OPPORTUNITY")

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(getattr(logging, console_level.upper()))
    console.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%H:%M:%S",
    ))
    root.addHandler(console)

    # Main log file
    main_handler = RotatingFileHandler(
        log_path / main_log_file,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
    )
    main_handler.setLevel(getattr(logging, file_level.upper()))
    main_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-25s | %(funcName)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(main_handler)

    # Trades log file (separate logger)
    trades_logger = logging.getLogger("trades")
    trades_handler = RotatingFileHandler(
        log_path / trades_log_file,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
    )
    trades_handler.setLevel(logging.DEBUG)
    trades_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S.%f",
    ))
    trades_logger.addHandler(trades_handler)
    trades_logger.propagate = False

    # Opportunities log file (separate logger)
    opps_logger = logging.getLogger("opportunities")
    opps_handler = RotatingFileHandler(
        log_path / opportunities_log_file,
        maxBytes=max_size_mb * 1024 * 1024,
        backupCount=backup_count,
    )
    opps_handler.setLevel(logging.DEBUG)
    opps_handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S.%f",
    ))
    opps_logger.addHandler(opps_handler)
    opps_logger.propagate = False

    # Reduce noise from libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)

    logging.info(f"Logging initialized | console={console_level} | file={file_level} | dir={log_dir}")
