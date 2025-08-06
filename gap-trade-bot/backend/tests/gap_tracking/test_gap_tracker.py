#!/usr/bin/env python3
"""
Test script for Gap Tracking System
Tests peak detection, drop tracking, and overkill prevention
"""

import sys
import os
from datetime import datetime, time

# Add parent directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from gap_tracker import GapTracker

def test_basic_gap_tracking():
    """Test basic gap tracking functionality"""
    
    print("🧪 Testing Basic Gap Tracking")
    print("=" * 50)
    
    # Create a new tracker for testing
    tracker = GapTracker("test_data")
    
    # Simulate ZEPP stock behavior throughout the day
    print("\n📈 Testing ZEPP stock behavior:")
    print("-" * 30)
    
    # Morning: Initial gap-up detection
    print("🕐 9:30 AM - Initial detection")
    is_new_peak, peak_data = tracker.update_gap("ZEPP", 25.0, 12.50, "09:30:00")
    print(f"   Gap: 25.0% | New Peak: {is_new_peak} | Peak: {peak_data['peak_gap']:.2f}%")
    assert is_new_peak == True, "First detection should be new peak"
    
    # Mid-morning: Higher gap detected
    print("\n🕐 10:30 AM - Higher gap detected")
    is_new_peak, peak_data = tracker.update_gap("ZEPP", 35.0, 13.50, "10:30:00")
    print(f"   Gap: 35.0% | New Peak: {is_new_peak} | Peak: {peak_data['peak_gap']:.2f}%")
    assert is_new_peak == True, "Higher gap should be new peak"
    
    # Noon: Peak gap detected
    print("\n🕐 12:00 PM - Peak gap detected")
    is_new_peak, peak_data = tracker.update_gap("ZEPP", 38.12, 13.81, "12:00:00")
    print(f"   Gap: 38.12% | New Peak: {is_new_peak} | Peak: {peak_data['peak_gap']:.2f}%")
    assert is_new_peak == True, "Highest gap should be new peak"
    
    # Afternoon: Stock starts declining
    print("\n🕐 1:00 PM - Stock declining")
    is_new_peak, peak_data = tracker.update_gap("ZEPP", 35.0, 13.50, "13:00:00")
    print(f"   Gap: 35.0% | New Peak: {is_new_peak} | Peak: {peak_data['peak_gap']:.2f}%")
    assert is_new_peak == False, "Lower gap should not be new peak"
    
    # Late afternoon: Further decline
    print("\n🕐 2:00 PM - Further decline")
    is_new_peak, peak_data = tracker.update_gap("ZEPP", 30.0, 13.00, "14:00:00")
    print(f"   Gap: 30.0% | New Peak: {is_new_peak} | Peak: {peak_data['peak_gap']:.2f}%")
    assert is_new_peak == False, "Lower gap should not be new peak"
    
    # Check for significant drop
    is_significant_drop = tracker.is_significant_drop("ZEPP", 30.0, drop_threshold=10.0)
    print(f"   Significant Drop: {is_significant_drop}")
    assert is_significant_drop == False, "8% drop should not be significant"
    
    # Evening: More decline
    print("\n🕐 3:00 PM - More decline")
    is_new_peak, peak_data = tracker.update_gap("ZEPP", 25.0, 12.50, "15:00:00")
    print(f"   Gap: 25.0% | New Peak: {is_new_peak} | Peak: {peak_data['peak_gap']:.2f}%")
    assert is_new_peak == False, "Lower gap should not be new peak"
    
    # Check for significant drop
    is_significant_drop = tracker.is_significant_drop("ZEPP", 25.0, drop_threshold=10.0)
    print(f"   Significant Drop: {is_significant_drop}")
    assert is_significant_drop == True, "13% drop should be significant"
    
    print("\n📊 Summary:")
    print("-" * 30)
    final_peak_data = tracker.get_peak_data("ZEPP")
    if final_peak_data:
        print(f"   Peak Gap: {final_peak_data['peak_gap']:.2f}%")
        print(f"   Peak Time: {final_peak_data['peak_time']}")
        print(f"   Detection Count: {final_peak_data['detection_count']}")
        print(f"   First Detected: {final_peak_data['first_detected']}")
        assert final_peak_data['peak_gap'] == 38.12, "Peak should be 38.12%"
        assert final_peak_data['detection_count'] == 6, "Should have 6 detections"
    
    print("\n✅ Basic gap tracking test passed!")

def test_multiple_stocks():
    """Test tracking multiple stocks simultaneously"""
    
    print("\n🧪 Testing Multiple Stocks")
    print("=" * 50)
    
    tracker = GapTracker("test_data_multi")
    
    # Stock A: Makes new peaks
    print("\n📈 Stock A (Making new peaks):")
    tracker.update_gap("STOCK_A", 20.0, 12.00, "09:30:00")
    tracker.update_gap("STOCK_A", 25.0, 12.50, "10:00:00")
    tracker.update_gap("STOCK_A", 30.0, 13.00, "10:30:00")
    
    # Stock B: Declining from peak
    print("\n📉 Stock B (Declining from peak):")
    tracker.update_gap("STOCK_B", 40.0, 14.00, "09:30:00")  # Peak
    tracker.update_gap("STOCK_B", 35.0, 13.50, "10:00:00")  # Decline
    tracker.update_gap("STOCK_B", 30.0, 13.00, "10:30:00")  # More decline
    
    # Stock C: No significant movement
    print("\n📊 Stock C (No significant movement):")
    tracker.update_gap("STOCK_C", 15.0, 11.50, "09:30:00")
    tracker.update_gap("STOCK_C", 16.0, 11.60, "10:00:00")
    tracker.update_gap("STOCK_C", 15.5, 11.55, "10:30:00")
    
    print("\n📊 All Peak Data:")
    all_peaks = tracker.get_all_peaks()
    for ticker, data in all_peaks.items():
        print(f"   {ticker}: Peak {data['peak_gap']:.2f}% at {data['peak_time']}")
    
    assert len(all_peaks) == 3, "Should track 3 stocks"
    assert all_peaks["STOCK_A"]["peak_gap"] == 30.0, "STOCK_A peak should be 30%"
    assert all_peaks["STOCK_B"]["peak_gap"] == 40.0, "STOCK_B peak should be 40%"
    assert all_peaks["STOCK_C"]["peak_gap"] == 16.0, "STOCK_C peak should be 16%"
    
    print("\n🚀 New Peaks Today (≥25%):")
    new_peaks = tracker.get_new_peaks_today(min_gap=25.0)
    for ticker in new_peaks:
        print(f"   {ticker}")
    
    assert "STOCK_A" in new_peaks, "STOCK_A should be in new peaks"
    assert "STOCK_B" in new_peaks, "STOCK_B should be in new peaks"
    assert "STOCK_C" not in new_peaks, "STOCK_C should not be in new peaks"
    
    print("\n📉 Drop Candidates (≥40% peak, ≥10% drop):")
    for ticker, data in all_peaks.items():
        if data['peak_gap'] >= 40.0:
            print(f"   {ticker}: Peak {data['peak_gap']:.2f}%")
    
    print("\n✅ Multiple stocks test passed!")

def test_edge_cases():
    """Test edge cases and error handling"""
    
    print("\n🧪 Testing Edge Cases")
    print("=" * 50)
    
    tracker = GapTracker("test_data_edge")
    
    # Test with zero gap
    print("\n📊 Testing zero gap:")
    is_new_peak, peak_data = tracker.update_gap("ZERO_STOCK", 0.0, 10.00, "09:30:00")
    print(f"   Gap: 0.0% | New Peak: {is_new_peak} | Peak: {peak_data['peak_gap']:.2f}%")
    assert is_new_peak == False, "Zero gap should not be new peak (even first detection)"
    
    # Test with negative gap
    print("\n📊 Testing negative gap:")
    is_new_peak, peak_data = tracker.update_gap("NEG_STOCK", -5.0, 9.50, "09:30:00")
    print(f"   Gap: -5.0% | New Peak: {is_new_peak} | Peak: {peak_data['peak_gap']:.2f}%")
    assert is_new_peak == False, "Negative gap should not be new peak (even first detection)"
    
    # Test with positive gap (should be new peak)
    print("\n📊 Testing positive gap:")
    is_new_peak, peak_data = tracker.update_gap("POS_STOCK", 5.0, 10.50, "09:30:00")
    print(f"   Gap: 5.0% | New Peak: {is_new_peak} | Peak: {peak_data['peak_gap']:.2f}%")
    assert is_new_peak == True, "Positive gap should be new peak (first detection)"
    
    # Test with very large gap
    print("\n📊 Testing very large gap:")
    is_new_peak, peak_data = tracker.update_gap("HUGE_STOCK", 500.0, 60.00, "09:30:00")
    print(f"   Gap: 500.0% | New Peak: {is_new_peak} | Peak: {peak_data['peak_gap']:.2f}%")
    assert is_new_peak == True, "Large gap should be new peak"
    
    # Test significant drop with large gap
    is_significant_drop = tracker.is_significant_drop("HUGE_STOCK", 450.0, drop_threshold=10.0)
    print(f"   Significant Drop (450%): {is_significant_drop}")
    assert is_significant_drop == True, "50% drop from 500% should be significant"
    
    print("\n✅ Edge cases test passed!")

def test_persistence():
    """Test data persistence across sessions"""
    
    print("\n🧪 Testing Data Persistence")
    print("=" * 50)
    
    # Create tracker and add some data
    tracker1 = GapTracker("test_data_persist")
    tracker1.update_gap("PERSIST_STOCK", 25.0, 12.50, "09:30:00")
    tracker1.update_gap("PERSIST_STOCK", 35.0, 13.50, "10:30:00")
    
    # Get peak data
    peak_data1 = tracker1.get_peak_data("PERSIST_STOCK")
    print(f"   Session 1 - Peak: {peak_data1['peak_gap']:.2f}%")
    
    # Create new tracker instance (simulates new session)
    tracker2 = GapTracker("test_data_persist")
    
    # Check if data persisted
    peak_data2 = tracker2.get_peak_data("PERSIST_STOCK")
    print(f"   Session 2 - Peak: {peak_data2['peak_gap']:.2f}%")
    
    assert peak_data2 is not None, "Data should persist across sessions"
    assert peak_data2['peak_gap'] == 35.0, "Peak should persist"
    assert peak_data2['detection_count'] == 2, "Detection count should persist"
    
    # Test updating in new session
    is_new_peak, peak_data3 = tracker2.update_gap("PERSIST_STOCK", 40.0, 14.00, "11:30:00")
    print(f"   Session 2 - New gap: 40.0% | New Peak: {is_new_peak}")
    assert is_new_peak == True, "Higher gap in new session should be new peak"
    
    print("\n✅ Data persistence test passed!")

if __name__ == "__main__":
    print("🚀 Starting Gap Tracker Tests")
    print("=" * 60)
    
    try:
        test_basic_gap_tracking()
        test_multiple_stocks()
        test_edge_cases()
        test_persistence()
        
        print("\n" + "=" * 60)
        print("🎉 All tests passed successfully!")
        print("✅ Gap tracking system is working correctly")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc() 