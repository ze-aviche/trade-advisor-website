#!/usr/bin/env python3
"""
Simplified Logging Configuration for Gap-Trade-Bot
Provides clean logging with minimal file output and Unicode support
"""
import os
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path

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
    # Set log level
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Create formatters with explicit date format
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console Handler (INFO and above) - UTF-8 safe
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    
    # Set encoding for console handler to handle Unicode
    if hasattr(console_handler.stream, 'reconfigure'):
        try:
            console_handler.stream.reconfigure(encoding='utf-8')
        except:
            pass
    
    root_logger.addHandler(console_handler)
    
    # File Handler - All logs (DEBUG and above) with UTF-8 encoding
    try:
        all_logs_file = log_path / 'gap_trade_backend_all.log'
        file_handler = logging.handlers.RotatingFileHandler(
            all_logs_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'  # Explicit UTF-8 encoding
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
        print(f"File logging enabled - All logs: {all_logs_file}")
    except PermissionError:
        print("Warning: Could not create file log handler due to permission error. Using console logging only.")
    except Exception as e:
        print(f"Warning: Could not create file log handler: {e}. Using console logging only.")
    
    # File Handler - Errors only with UTF-8 encoding
    try:
        error_logs_file = log_path / 'gap_trade_backend_errors.log'
        error_handler = logging.handlers.RotatingFileHandler(
            error_logs_file,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=3,
            encoding='utf-8'  # Explicit UTF-8 encoding
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(error_handler)
        print(f"Error logging enabled - Errors: {error_logs_file}")
    except PermissionError:
        print("Warning: Could not create error log handler due to permission error.")
    except Exception as e:
        print(f"Warning: Could not create error log handler: {e}.")
    
    print("Backend logging configured with Unicode support")

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
    """Apply emoji filter to console logging to prevent Unicode errors"""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
            handler.addFilter(EmojiFilter())
            break 