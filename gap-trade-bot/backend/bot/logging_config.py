#!/usr/bin/env python3
"""
Simplified Logging Configuration for Trading Bot
Provides clean logging with minimal file output
"""
import os
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path

def setup_logging(log_level='INFO', log_dir='logs'):
    """
    Setup simplified logging configuration with file output
    
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
    
    # Console Handler (INFO and above)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)
    root_logger.addHandler(console_handler)
    
    # File Handler - All logs (DEBUG and above)
    all_logs_file = log_path / 'gap_trade_bot_all.log'
    file_handler = logging.handlers.RotatingFileHandler(
        all_logs_file,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)
    
    # File Handler - Errors only
    error_logs_file = log_path / 'gap_trade_bot_errors.log'
    error_handler = logging.handlers.RotatingFileHandler(
        error_logs_file,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)
    
    print(f"✅ Bot logging configured - All logs: {all_logs_file}, Errors: {error_logs_file}")

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
        details (dict, optional): Additional details
    """
    logger = logging.getLogger('performance')
    message = f"⏱️ {operation} took {duration:.3f}s"
    if details:
        message += f" | {details}"
    logger.info(message)

def log_api_request(method, endpoint, status_code, duration=None, user_agent=None):
    """
    Log API request details
    
    Args:
        method (str): HTTP method
        endpoint (str): API endpoint
        status_code (int): HTTP status code
        duration (float, optional): Request duration
        user_agent (str, optional): User agent
    """
    logger = logging.getLogger('api')
    message = f"🌐 {method} {endpoint} -> {status_code}"
    if duration:
        message += f" ({duration:.3f}s)"
    if user_agent:
        message += f" | {user_agent}"
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
    Log errors with context
    
    Args:
        error (Exception): Error to log
        context (dict, optional): Additional context
    """
    logger = logging.getLogger('error')
    message = f"❌ {error}"
    if context:
        message += f" | Context: {context}"
    logger.error(message) 