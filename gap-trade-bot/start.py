#!/usr/bin/env python3
"""
Startup script for Trading Advisor Web Application
"""
import os
import sys
import subprocess
import time
import webbrowser
from pathlib import Path

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        import flask
        import flask_cors
        import flask_socketio
        print("✅ All Python dependencies are available")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Please install dependencies with: pip install -r backend/requirements.txt")
        return False

def start_backend():
    """Start the Flask backend server"""
    print("🚀 Starting backend server...")
    backend_dir = Path("backend")
    os.chdir(backend_dir)
    
    try:
        # Start the Flask app
        subprocess.run([sys.executable, "app.py"], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Backend server stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ Backend server failed to start: {e}")
    finally:
        os.chdir("..")

def start_frontend():
    """Start a simple HTTP server for the frontend"""
    print("🌐 Starting frontend server...")
    frontend_dir = Path("frontend")
    os.chdir(frontend_dir)
    
    try:
        # Start a simple HTTP server
        subprocess.run([sys.executable, "-m", "http.server", "3000"], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Frontend server stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ Frontend server failed to start: {e}")
    finally:
        os.chdir("..")

def main():
    """Main startup function"""
    print("🎯 Trading Advisor Web Application")
    print("=" * 40)
    
    # Check dependencies
    if not check_dependencies():
        return
    
    print("\n📋 Available options:")
    print("1. Start backend server only")
    print("2. Start frontend server only")
    print("3. Start both servers (recommended)")
    print("4. Exit")
    
    while True:
        try:
            choice = input("\nEnter your choice (1-4): ").strip()
            
            if choice == "1":
                start_backend()
                break
            elif choice == "2":
                start_frontend()
                break
            elif choice == "3":
                print("\n🔄 Starting both servers...")
                print("Backend will be available at: http://localhost:5000")
                print("Frontend will be available at: http://localhost:3000")
                print("Press Ctrl+C to stop both servers")
                
                # Start backend in a separate process
                backend_process = subprocess.Popen([sys.executable, "backend/app.py"])
                
                # Wait a moment for backend to start
                time.sleep(2)
                
                # Start frontend
                frontend_process = subprocess.Popen([sys.executable, "-m", "http.server", "3000"], cwd="frontend")
                
                try:
                    # Open browser after a short delay
                    time.sleep(3)
                    webbrowser.open("http://localhost:3000")
                    
                    # Wait for user to stop
                    input("\nPress Enter to stop both servers...")
                finally:
                    backend_process.terminate()
                    frontend_process.terminate()
                    print("\n🛑 Both servers stopped")
                break
            elif choice == "4":
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please enter 1-4.")
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break

if __name__ == "__main__":
    main() 