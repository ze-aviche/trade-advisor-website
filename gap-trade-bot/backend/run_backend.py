#!/usr/bin/env python3
"""
Simple wrapper to run the backend Flask app without logging setup
"""
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variable to disable file logging
os.environ['DISABLE_FILE_LOGGING'] = '1'

# Import and run the Flask app
try:
    from app import app
    print("Starting backend server on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)
except Exception as e:
    print(f"Error starting backend: {e}")
    sys.exit(1)
