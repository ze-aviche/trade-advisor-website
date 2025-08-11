#!/usr/bin/env python3
"""
Check DAS Trader Port Status
Helps identify which port DAS Trader is running on
"""

import socket
import subprocess
import psutil
import sys
from typing import List, Dict, Optional

def check_port_in_use(port: int) -> bool:
    """Check if a specific port is in use"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex(('localhost', port))
            return result == 0
    except Exception:
        return False

def get_process_using_port(port: int) -> Optional[Dict]:
    """Get process information for a specific port"""
    try:
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.status == 'LISTEN':
                try:
                    process = psutil.Process(conn.pid)
                    return {
                        'pid': conn.pid,
                        'name': process.name(),
                        'cmdline': ' '.join(process.cmdline()),
                        'port': port
                    }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
    except Exception as e:
        print(f"Error getting process info: {e}")
    return None

def find_das_processes() -> List[Dict]:
    """Find all DAS-related processes"""
    das_processes = []
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                proc_info = proc.info
                if proc_info['name'] and 'das' in proc_info['name'].lower():
                    das_processes.append({
                        'pid': proc_info['pid'],
                        'name': proc_info['name'],
                        'cmdline': ' '.join(proc_info['cmdline']) if proc_info['cmdline'] else ''
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        print(f"Error finding DAS processes: {e}")
    return das_processes

def check_common_das_ports() -> Dict[int, bool]:
    """Check common DAS Trader ports"""
    common_ports = [8080, 8081, 8082, 5001, 5002, 5003, 5004]
    port_status = {}
    
    for port in common_ports:
        port_status[port] = check_port_in_use(port)
    
    return port_status

def run_netstat_command() -> str:
    """Run netstat command to get listening ports"""
    try:
        result = subprocess.run(
            ['netstat', '-an'], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        return result.stdout
    except Exception as e:
        return f"Error running netstat: {e}"

def main():
    """Main function to check DAS Trader port status"""
    print("🔍 DAS Trader Port Status Check")
    print("=" * 50)
    
    # Check common DAS ports
    print("\n📋 Checking common DAS Trader ports:")
    print("-" * 40)
    port_status = check_common_das_ports()
    
    for port, in_use in port_status.items():
        status = "✅ IN USE" if in_use else "❌ NOT IN USE"
        print(f"Port {port}: {status}")
        
        if in_use:
            process_info = get_process_using_port(port)
            if process_info:
                print(f"  Process: {process_info['name']} (PID: {process_info['pid']})")
                if 'das' in process_info['name'].lower():
                    print(f"  🎯 LIKELY DAS TRADER!")
    
    # Find DAS processes
    print("\n🔍 Looking for DAS processes:")
    print("-" * 40)
    das_processes = find_das_processes()
    
    if das_processes:
        for proc in das_processes:
            print(f"✅ Found: {proc['name']} (PID: {proc['pid']})")
            if proc['cmdline']:
                print(f"   Command: {proc['cmdline'][:100]}...")
    else:
        print("❌ No DAS processes found")
    
    # Check listening ports
    print("\n🌐 All listening ports (8080-8089):")
    print("-" * 40)
    netstat_output = run_netstat_command()
    
    for line in netstat_output.split('\n'):
        if 'LISTENING' in line and any(f':{port}' in line for port in range(8080, 8090)):
            print(f"  {line.strip()}")
    
    # Summary
    print("\n📊 SUMMARY:")
    print("-" * 40)
    
    # Check if DAS is likely running
    das_ports = [port for port, in_use in port_status.items() if in_use]
    das_processes_found = len(das_processes) > 0
    
    if das_ports and das_processes_found:
        print("✅ DAS Trader appears to be running!")
        print(f"   Ports in use: {das_ports}")
        print(f"   Processes found: {len(das_processes)}")
    elif das_ports:
        print("⚠️  Ports are in use but no DAS processes found")
        print(f"   Ports: {das_ports}")
    elif das_processes_found:
        print("⚠️  DAS processes found but no common ports in use")
        print("   Check DAS Trader API settings")
    else:
        print("❌ DAS Trader does not appear to be running")
        print("   Please start DAS Trader and enable CMD API")
    
    # Recommendations
    print("\n💡 RECOMMENDATIONS:")
    print("-" * 40)
    
    if not das_processes_found:
        print("1. Start DAS Trader Pro")
        print("2. Enable CMD API in settings")
        print("3. Set port to 8080 (default)")
    
    if not das_ports:
        print("1. Check DAS Trader API configuration")
        print("2. Verify port 8080 is not blocked")
        print("3. Restart DAS Trader")
    
    if das_ports and das_processes_found:
        print("1. DAS Trader is ready for connection")
        print("2. You can now run your trading bot")
        print("3. Test with: python test_das_demo.py")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Check interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during port check: {e}")
        print("Try running the batch file instead: check_das_port.bat")
