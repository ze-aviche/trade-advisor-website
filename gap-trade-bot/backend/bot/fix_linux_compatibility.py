#!/usr/bin/env python3
"""
Linux Compatibility Fix Script
Automatically fixes common issues when running macOS-built app on Linux
"""

import os
import sys
import platform
import shutil
import subprocess
from pathlib import Path

def print_header(title):
    print(f"\n{'='*60}")
    print(f"🔧 {title}")
    print(f"{'='*60}")

def print_step(step, description):
    print(f"\n📋 Step {step}: {description}")
    print("-" * 40)

def check_platform():
    """Check current platform"""
    system = platform.system()
    print(f"🖥️  Platform: {system}")
    print(f"📁 Current directory: {os.getcwd()}")
    return system

def fix_paths():
    """Fix platform-specific paths"""
    print_step(1, "Fixing platform-specific paths")
    
    # Common path issues
    path_fixes = {
        # macOS paths to Linux paths
        "/Users/": "/home/",
        "Documents/Projects": "Documents/Projects",
        "Library/Application Support": ".config",
    }
    
    # Find and fix path references in Python files
    python_files = list(Path('.').rglob('*.py'))
    
    for py_file in python_files:
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Fix common path issues
            for old_path, new_path in path_fixes.items():
                if old_path in content:
                    content = content.replace(old_path, new_path)
            
            # Write back if changed
            if content != original_content:
                with open(py_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"✅ Fixed paths in: {py_file}")
                
        except Exception as e:
            print(f"⚠️  Warning: Could not process {py_file}: {e}")

def fix_permissions():
    """Fix file permissions"""
    print_step(2, "Fixing file permissions")
    
    # Make Python files executable
    python_files = list(Path('.').rglob('*.py'))
    for py_file in python_files:
        try:
            os.chmod(py_file, 0o755)
            print(f"✅ Made executable: {py_file}")
        except Exception as e:
            print(f"⚠️  Warning: Could not set permissions for {py_file}: {e}")
    
    # Make shell scripts executable
    shell_files = list(Path('.').rglob('*.sh'))
    for sh_file in shell_files:
        try:
            os.chmod(sh_file, 0o755)
            print(f"✅ Made executable: {sh_file}")
        except Exception as e:
            print(f"⚠️  Warning: Could not set permissions for {sh_file}: {e}")
    
    # Set database files to read-write
    db_files = list(Path('.').rglob('*.db'))
    for db_file in db_files:
        try:
            os.chmod(db_file, 0o644)
            print(f"✅ Set permissions: {db_file}")
        except Exception as e:
            print(f"⚠️  Warning: Could not set permissions for {db_file}: {e}")

def create_linux_env():
    """Create Linux-specific environment file"""
    print_step(3, "Creating Linux environment configuration")
    
    env_content = """# Linux Configuration
BROKER_TYPE=alpaca
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
ALPACA_ENDPOINT=https://paper-api.alpaca.markets
POLYGON_API_KEY=your_polygon_key_here

# Linux paths
LOG_PATH=/app/logs
DATA_PATH=/app/data
LOG_LEVEL=INFO

# Remove DAS Trader settings for Linux
DAS_API_KEY=
DAS_SECRET_KEY=
DAS_BASE_URL=
DAS_FIX_HOST=
DAS_FIX_PORT=
DAS_USERNAME=
DAS_PASSWORD=
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("✅ Created .env file for Linux")
    print("⚠️  Please update with your actual API keys")

def check_dependencies():
    """Check and install dependencies"""
    print_step(4, "Checking dependencies")
    
    # Check if virtual environment exists
    if not os.path.exists('venv'):
        print("📦 Creating virtual environment...")
        try:
            subprocess.run([sys.executable, '-m', 'venv', 'venv'], check=True)
            print("✅ Virtual environment created")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error creating virtual environment: {e}")
            print("Please install python3-venv: sudo apt install python3-venv")
            return False
    
    # Check if requirements_linux.txt exists
    if not os.path.exists('requirements_linux.txt'):
        print("❌ requirements_linux.txt not found")
        print("Please create it with Linux-specific dependencies")
        return False
    
    print("✅ Dependencies check complete")
    return True

def create_directories():
    """Create necessary directories"""
    print_step(5, "Creating necessary directories")
    
    directories = ['logs', 'data', 'cache']
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"✅ Created directory: {directory}")
        except Exception as e:
            print(f"⚠️  Warning: Could not create {directory}: {e}")

def check_port_availability():
    """Check if port 5000 is available"""
    print_step(6, "Checking port availability")
    
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 5000))
        sock.close()
        
        if result == 0:
            print("⚠️  Warning: Port 5000 is already in use")
            print("You may need to kill the existing process:")
            print("sudo lsof -ti:5000 | xargs kill -9")
        else:
            print("✅ Port 5000 is available")
    except Exception as e:
        print(f"⚠️  Warning: Could not check port: {e}")

def create_linux_startup_script():
    """Create Linux startup script"""
    print_step(7, "Creating Linux startup script")
    
    script_content = """#!/bin/bash
# Linux Trading Bot Startup Script

echo "🚀 Starting Trading Bot on Linux..."

# Activate virtual environment
source venv/bin/activate

# Set environment variables
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export FLASK_ENV=development

# Start the bot
python run_agent.py
"""
    
    with open('start_bot_linux.sh', 'w') as f:
        f.write(script_content)
    
    os.chmod('start_bot_linux.sh', 0o755)
    print("✅ Created start_bot_linux.sh")

def main():
    """Main function"""
    print_header("Linux Compatibility Fix Script")
    
    # Check platform
    system = check_platform()
    if system != "Linux":
        print(f"⚠️  Warning: This script is designed for Linux, but you're on {system}")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return
    
    # Run fixes
    fix_paths()
    fix_permissions()
    create_linux_env()
    
    if check_dependencies():
        create_directories()
        check_port_availability()
        create_linux_startup_script()
    
    # Summary
    print_header("Fix Complete!")
    print("✅ Linux compatibility fixes applied")
    print("\n📋 Next steps:")
    print("1. Update .env with your API keys")
    print("2. Activate virtual environment: source venv/bin/activate")
    print("3. Install requirements: pip install -r requirements_linux.txt")
    print("4. Start the bot: ./start_bot_linux.sh")
    print("\n💡 For DAS Trader support, consider using a Windows VM")
    print("   See CROSS_PLATFORM_SOLUTIONS.md for details")

if __name__ == "__main__":
    main()

