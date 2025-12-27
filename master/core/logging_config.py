"""
Centralized Logging Configuration

Production-ready logging with:
- File rotation (prevents disk exhaustion)
- JSON output (for API parsing and log aggregation)
- Sensitive data sanitization
- Multiple log levels and destinations
"""
import logging
import logging.handlers
import os
import json
import re
from datetime import datetime
from typing import Optional
from pathlib import Path


# Patterns for sensitive data that should be masked
SENSITIVE_PATTERNS = [
    (re.compile(r'password["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)', re.IGNORECASE), 'password=***'),
    (re.compile(r'secret["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)', re.IGNORECASE), 'secret=***'),
    (re.compile(r'token["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)', re.IGNORECASE), 'token=***'),
    (re.compile(r'api[_-]?key["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)', re.IGNORECASE), 'api_key=***'),
    (re.compile(r'Authorization:\s*Bearer\s+\S+', re.IGNORECASE), 'Authorization: Bearer ***'),
    (re.compile(r'-p["\']?([^"\'}\s]+)', re.IGNORECASE), '-p***'),  # MySQL passwords
]


def sanitize_message(message: str) -> str:
    """Remove sensitive information from log messages."""
    for pattern, replacement in SENSITIVE_PATTERNS:
        message = pattern.sub(replacement, message)
    return message


class SanitizingFormatter(logging.Formatter):
    """Formatter that sanitizes sensitive data from log messages."""
    
    def format(self, record: logging.LogRecord) -> str:
        # Sanitize the message
        record.msg = sanitize_message(str(record.msg))
        if record.args:
            record.args = tuple(
                sanitize_message(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for easy parsing."""
    
    def format(self, record: logging.LogRecord) -> str:
        # Build log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_message(record.getMessage()),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_entry["extra"] = record.extra_data
        
        return json.dumps(log_entry)


class ResilientRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """RotatingFileHandler that won't crash the app if logging fails."""
    
    def emit(self, record):
        try:
            super().emit(record)
        except Exception:
            # Silently fail - don't crash the app due to logging issues
            pass


def get_log_dir() -> Path:
    """Get the logging directory, creating it if necessary."""
    # Check for environment override
    log_dir = os.getenv("LOG_DIR", "")
    
    if not log_dir:
        # Production: /var/log/wordpress-backup
        # Development: ./logs
        if os.path.exists("/var/log") and os.access("/var/log", os.W_OK):
            log_dir = "/var/log/wordpress-backup"
        else:
            # Fallback to local logs directory
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    
    log_path = Path(log_dir)
    try:
        log_path.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # Fallback to temp directory if we can't create log dir
        log_path = Path("/tmp/wordpress-backup-logs")
        log_path.mkdir(parents=True, exist_ok=True)
    
    return log_path


def setup_logging(
    log_level: str = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    enable_json: bool = True,
    enable_console: bool = True,
) -> None:
    """
    Configure application-wide logging.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_bytes: Maximum size of each log file before rotation
        backup_count: Number of backup files to keep
        enable_json: Whether to create JSON-formatted log file
        enable_console: Whether to also log to console/stdout
    """
    # Determine log level
    level_str = log_level or os.getenv("LOG_LEVEL", "INFO")
    level = getattr(logging, level_str.upper(), logging.INFO)
    
    # Get log directory
    log_dir = get_log_dir()
    
    # Create root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all, handlers filter
    
    # Clear any existing handlers
    root_logger.handlers = []
    
    # === Console Handler ===
    if enable_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_formatter = SanitizingFormatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # === Main Application Log ===
    app_handler = ResilientRotatingFileHandler(
        log_dir / "app.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8',
    )
    app_handler.setLevel(level)
    app_formatter = SanitizingFormatter(
        '%(asctime)s [%(levelname)s] %(name)s (%(module)s:%(lineno)d): %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    app_handler.setFormatter(app_formatter)
    root_logger.addHandler(app_handler)
    
    # === JSON Log (for API parsing) ===
    if enable_json:
        json_handler = ResilientRotatingFileHandler(
            log_dir / "app.json.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8',
        )
        json_handler.setLevel(level)
        json_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(json_handler)
    
    # === Error-Only Log ===
    error_handler = ResilientRotatingFileHandler(
        log_dir / "error.log",
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8',
    )
    error_handler.setLevel(logging.ERROR)
    error_formatter = SanitizingFormatter(
        '%(asctime)s [%(levelname)s] %(name)s (%(module)s:%(lineno)d): %(message)s\n%(exc_info)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    error_handler.setFormatter(error_formatter)
    root_logger.addHandler(error_handler)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized: level={level_str}, dir={log_dir}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.
    
    Usage:
        from master.core.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")
    """
    return logging.getLogger(name)


# Convenience function to read recent log entries
def read_log_entries(
    log_file: str = "app.json.log",
    limit: int = 100,
    level: Optional[str] = None,
    search: Optional[str] = None,
) -> list:
    """
    Read recent log entries from JSON log file.
    
    Args:
        log_file: Name of log file to read
        limit: Maximum number of entries to return
        level: Filter by log level
        search: Filter by message content
    
    Returns:
        List of log entry dictionaries
    """
    log_path = get_log_dir() / log_file
    
    if not log_path.exists():
        return []
    
    entries = []
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            # Read file in reverse (newest first)
            lines = f.readlines()
            for line in reversed(lines):
                if len(entries) >= limit:
                    break
                
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    entry = json.loads(line)
                    
                    # Apply level filter
                    if level and entry.get("level") != level.upper():
                        continue
                    
                    # Apply search filter
                    if search and search.lower() not in entry.get("message", "").lower():
                        continue
                    
                    entries.append(entry)
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass
    
    return entries


def list_log_files() -> list:
    """List all available log files."""
    log_dir = get_log_dir()
    files = []
    
    try:
        for f in log_dir.iterdir():
            if f.is_file() and f.suffix in ('.log', ):
                stat = f.stat()
                files.append({
                    "name": f.name,
                    "size_bytes": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
    except Exception:
        pass
    
    return sorted(files, key=lambda x: x["name"])
