#!/usr/bin/env python3
"""
Logging configuration for Gap-Trade-Bot.
Provides structured JSON logging with per-request user context and per-user debug mode.
"""
import os
import json
import logging
import logging.handlers
import sys
import threading
import traceback as _traceback
from pathlib import Path

# ── Per-user debug mode ────────────────────────────────────────────────────────
# Admin can add/remove user IDs at runtime via POST /api/admin/debug-user.
# When a user ID is in this set, their requests emit DEBUG-level logs even when
# the global log level is INFO.

_debug_user_ids: set = set()
_debug_lock = threading.Lock()


def set_debug_user(user_id: int, enable: bool) -> None:
    """Enable or disable verbose debug logging for a specific user."""
    with _debug_lock:
        if enable:
            _debug_user_ids.add(int(user_id))
        else:
            _debug_user_ids.discard(int(user_id))


def is_debug_user(user_id: int) -> bool:
    return int(user_id) in _debug_user_ids


def get_debug_users() -> list:
    with _debug_lock:
        return sorted(_debug_user_ids)

# ── Filters & Formatters ───────────────────────────────────────────────────────

class UserContextFilter(logging.Filter):
    """Inject user_id, ip, and endpoint into every log record.

    Reads from Flask's g object when inside a request context.
    Falls back to '-' in background threads and at startup.
    """
    def filter(self, record):
        try:
            from flask import g, request as _req
            record.user_id  = getattr(g, 'current_user_id', '-')
            record.ip       = _req.remote_addr or '-'
            record.endpoint = _req.endpoint or _req.path or '-'
        except RuntimeError:
            record.user_id  = '-'
            record.ip       = '-'
            record.endpoint = '-'
        return True


class JsonFormatter(logging.Formatter):
    """Single-line JSON log records for structured log aggregation (Render, Datadog, Logtail)."""
    def format(self, record):
        doc = {
            'time':     self.formatTime(record, '%Y-%m-%dT%H:%M:%S'),
            'level':    record.levelname,
            'logger':   record.name,
            'user_id':  getattr(record, 'user_id', '-'),
            'ip':       getattr(record, 'ip', '-'),
            'endpoint': getattr(record, 'endpoint', '-'),
            'msg':      record.getMessage(),
        }
        if record.exc_info:
            doc['exc'] = _traceback.format_exception(*record.exc_info)[-1].strip()
        return json.dumps(doc, ensure_ascii=True)


def setup_logging(log_level='INFO', log_dir='logs'):
    """
    Setup simplified logging configuration with file output and Unicode support
    
    Args:
        log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir (str): Directory to store log files
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    root_logger.handlers.clear()

    ctx_filter = UserContextFilter()

    # Console handler — JSON lines so Render stdout is grep/filter-friendly
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(JsonFormatter())
    console_handler.addFilter(ctx_filter)
    if hasattr(console_handler.stream, 'reconfigure'):
        try:
            console_handler.stream.reconfigure(encoding='utf-8')
        except Exception:
            pass
    root_logger.addHandler(console_handler)

    # Human-readable formatter for local log files
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | user=%(user_id)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File Handler — all logs (DEBUG+), human-readable for local dev
    try:
        all_logs_file = log_path / 'gap_trade_backend_all.log'
        file_handler = logging.handlers.RotatingFileHandler(
            all_logs_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        file_handler.addFilter(ctx_filter)
        root_logger.addHandler(file_handler)
        print(f"File logging enabled: {all_logs_file}")
    except (PermissionError, Exception) as e:
        print(f"Warning: Could not create file log handler: {e}. Console only.")

    # File Handler — errors only
    try:
        error_logs_file = log_path / 'gap_trade_backend_errors.log'
        error_handler = logging.handlers.RotatingFileHandler(
            error_logs_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        error_handler.addFilter(ctx_filter)
        root_logger.addHandler(error_handler)
        print(f"Error logging enabled: {error_logs_file}")
    except (PermissionError, Exception) as e:
        print(f"Warning: Could not create error log handler: {e}.")
    
    print("Backend logging configured with Unicode support")

    # Suppress noisy loggers not relevant to BrownBot/Alpaca debugging.
    # Remove individual entries to re-enable a logger.
    for _suppressed_logger in [
        # DAS Trader — DAS_ENABLED=False, none of these should fire anyway
        'das_integration', 'das_utils', 'das_startup',
        'scheduled_das_sync', 'bot.broker.das', 'panic_exit', 'bot.trading_bot',
        # Historical data fetch — verbose cache/delta logic, not needed during live trading
        'historical_data', 'historical_cache',
    ]:
        logging.getLogger(_suppressed_logger).setLevel(logging.CRITICAL)

def get_logger(name):
    """
    Get a logger instance with the specified name
    
    Args:
        name (str): Logger name
        
    Returns:
        logging.Logger: Configured logger instance
    """
    return logging.getLogger(name)

def log_performance(operation, duration, details=None):
    """
    Log performance metrics
    
    Args:
        operation (str): Operation name
        duration (float): Duration in seconds
        details (dict): Additional details
    """
    logger = logging.getLogger('performance')
    message = f"Performance: {operation} took {duration:.3f}s"
    if details:
        message += f" | Details: {details}"
    logger.info(message)

def log_api_request(method, endpoint, status_code, duration=None, user_agent=None):
    """
    Log API request details
    
    Args:
        method (str): HTTP method
        endpoint (str): API endpoint
        status_code (int): HTTP status code
        duration (float): Request duration in seconds
        user_agent (str): User agent string
    """
    logger = logging.getLogger('api')
    message = f"API Request: {method} {endpoint} -> {status_code}"
    if duration:
        message += f" ({duration:.3f}s)"
    if user_agent:
        message += f" | UA: {user_agent[:50]}..."
    logger.info(message)

def log_cache_operation(operation, ticker=None, details=None):
    """
    Log cache operations
    
    Args:
        operation (str): Cache operation
        ticker (str, optional): Stock ticker
        details (dict, optional): Additional details
    """
    logger = logging.getLogger('cache')
    message = f"💾 {operation}"
    if ticker:
        message += f" | {ticker}"
    if details:
        message += f" | {details}"
    logger.info(message)

def log_error(error, context=None):
    """
    Log error with context
    
    Args:
        error (Exception): The error that occurred
        context (dict): Additional context information
    """
    logger = logging.getLogger('error')
    message = f"Error: {type(error).__name__}: {str(error)}"
    if context:
        message += f" | Context: {context}"
    logger.error(message, exc_info=True)

# Custom filter to remove emoji characters from console output
class EmojiFilter(logging.Filter):
    """Filter to remove emoji characters from log messages for console output"""
    
    def filter(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            # Remove common emoji characters
            import re
            # Remove emoji characters (Unicode ranges for emojis)
            record.msg = re.sub(r'[^\x00-\x7F]+', '', record.msg)
        return True

# Apply emoji filter to console handler
def apply_emoji_filter():
    """Apply emoji filter to file handlers to prevent Unicode errors.
    The console handler uses JsonFormatter (ensure_ascii=True) and is already safe."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        # Only add to file handlers — JsonFormatter already outputs ASCII-only
        if isinstance(handler, logging.handlers.RotatingFileHandler):
            handler.addFilter(EmojiFilter()) 