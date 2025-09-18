#!/usr/bin/env python3
"""
Test the get_toplist function directly
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from nasgain_scanner import get_toplist

def test_get_toplist():
    print("🧪 Testing get_toplist() function...")
    
    lines = get_toplist()
    print(f"📊 get_toplist() returned {len(lines)} lines")
    
    if lines:
        print("📋 Lines returned:")
        for i, line in enumerate(lines, 1):
            print(f"  {i}. {line}")
    else:
        print("❌ No lines returned")
    
    # Check if any lines contain $TopLst
    toplst_lines = [line for line in lines if '$TopLst' in line]
    print(f"\n📈 Found {len(toplst_lines)} lines with $TopLst:")
    for line in toplst_lines:
        print(f"  {line}")

if __name__ == "__main__":
    test_get_toplist()
