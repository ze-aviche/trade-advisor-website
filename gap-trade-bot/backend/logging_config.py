#!/usr/bin/env python3
"""
Comprehensive Logging Configuration for Gap-Trade-Bot
Provides structured logging with file output for debugging
"""
import os
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path

def setup_logging(log_level='INFO', log_dir='logs'):
    """
    Setup comprehensive logging configuration with file output
    
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
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(filename)s:%(lineno)d | %(funcName)s() | %(message)s'
    )
    
    simple_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
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
    
    # File Handler - API requests
    api_logs_file = log_path / 'gap_trade_bot_api.log'
    api_handler = logging.handlers.RotatingFileHandler(
        api_logs_file,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3
    )
    api_handler.setLevel(logging.INFO)
    api_handler.setFormatter(detailed_formatter)
    
    # Create API logger
    api_logger = logging.getLogger('api')
    api_logger.addHandler(api_handler)
    api_logger.setLevel(logging.INFO)
    
    # File Handler - Performance metrics
    perf_logs_file = log_path / 'gap_trade_bot_performance.log'
    perf_handler = logging.handlers.RotatingFileHandler(
        perf_logs_file,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3
    )
    perf_handler.setLevel(logging.INFO)
    perf_handler.setFormatter(detailed_formatter)
    
    # Create performance logger
    perf_logger = logging.getLogger('performance')
    perf_logger.addHandler(perf_handler)
    perf_logger.setLevel(logging.INFO)
    
    # File Handler - Cache operations
    cache_logs_file = log_path / 'gap_trade_bot_cache.log'
    cache_handler = logging.handlers.RotatingFileHandler(
        cache_logs_file,
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3
    )
    cache_handler.setLevel(logging.INFO)
    cache_handler.setFormatter(detailed_formatter)
    
    # Create cache logger
    cache_logger = logging.getLogger('cache')
    cache_logger.addHandler(cache_handler)
    cache_logger.setLevel(logging.INFO)
    
    # Log startup message
    startup_logger = logging.getLogger('startup')
    startup_logger.info("🚀 Gap-Trade-Bot Logging System Initialized")
    startup_logger.info(f"📁 Log directory: {log_path.absolute()}")
    startup_logger.info(f"🔧 Log level: {log_level.upper()}")
    startup_logger.info(f"📊 Log files: all.log, errors.log, api.log, performance.log, cache.log")
    
    return {
        'all_logs': all_logs_file,
        'error_logs': error_logs_file,
        'api_logs': api_logs_file,
        'performance_logs': perf_logs_file,
        'cache_logs': cache_logs_file
    }

def get_logger(name):
    """
    Get a logger with the specified name
    
    Args:
        name (str): Logger name
        
    Returns:
        logging.Logger: Configured logger
    """
    return logging.getLogger(name)

def log_performance(operation, duration, details=None):
    """
    Log performance metrics
    
    Args:
        operation (str): Name of the operation
        duration (float): Duration in seconds
        details (dict): Additional details
    """
    perf_logger = logging.getLogger('performance')
    message = f"⏱️ {operation} | Duration: {duration:.3f}s"
    if details:
        message += f" | Details: {details}"
    perf_logger.info(message)

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
    api_logger = logging.getLogger('api')
    message = f"🌐 {method} {endpoint} | Status: {status_code}"
    if duration:
        message += f" | Duration: {duration:.3f}s"
    if user_agent:
        message += f" | User-Agent: {user_agent}"
    api_logger.info(message)

def log_cache_operation(operation, ticker=None, details=None):
    """
    Log cache operations
    
    Args:
        operation (str): Cache operation (hit, miss, store, clear)
        ticker (str): Stock ticker
        details (dict): Additional details
    """
    cache_logger = logging.getLogger('cache')
    message = f"💾 Cache {operation}"
    if ticker:
        message += f" | Ticker: {ticker}"
    if details:
        message += f" | Details: {details}"
    cache_logger.info(message)

def log_error(error, context=None):
    """
    Log errors with context
    
    Args:
        error (Exception): The error that occurred
        context (dict): Additional context information
    """
    error_logger = logging.getLogger('errors')
    message = f"❌ Error: {type(error).__name__}: {str(error)}"
    if context:
        message += f" | Context: {context}"
    error_logger.error(message, exc_info=True)

# Initialize logging when module is imported
if __name__ != "__main__":
    setup_logging() 