#!/usr/bin/env python3
"""
Data Download Verification Script
Calculates expected data download based on speed and duration
"""

def calculate_expected_data(speed_mbps, duration_hours):
    """
    Calculate expected data download
    
    Args:
        speed_mbps: Average speed in megabits per second
        duration_hours: Duration in hours
    
    Returns:
        tuple: (expected_gb, breakdown_info)
    """
    # Convert units
    duration_seconds = duration_hours * 60 * 60
    duration_minutes = duration_hours * 60
    
    # Convert Mbps to MB/s (divide by 8 since 1 byte = 8 bits)
    speed_mbs = speed_mbps / 8  # megabytes per second
    
    # Calculate total data
    total_mb = speed_mbs * duration_seconds
    total_gb = total_mb / 1024  # Convert MB to GB (1024 MB = 1 GB)
    
    breakdown = {
        'speed_mbps': speed_mbps,
        'speed_mbs': speed_mbs,
        'duration_hours': duration_hours,
        'duration_minutes': duration_minutes,
        'duration_seconds': duration_seconds,
        'total_mb': total_mb,
        'total_gb': total_gb
    }
    
    return total_gb, breakdown

def compare_results(expected_gb, actual_gb):
    """Compare expected vs actual results"""
    difference_gb = actual_gb - expected_gb
    difference_percent = (difference_gb / expected_gb) * 100
    
    return {
        'difference_gb': difference_gb,
        'difference_percent': difference_percent
    }

def main():
    print("=" * 60)
    print("DATA DOWNLOAD VERIFICATION")
    print("=" * 60)
    
    # Your actual numbers
    actual_speed_mbps = 57
    actual_duration_hours = 8
    actual_data_gb = 207.17
    
    print(f"\n📊 INPUT DATA:")
    print(f"   Average Speed: {actual_speed_mbps} Mbps")
    print(f"   Duration: {actual_duration_hours} hours")
    print(f"   Actual Downloaded: {actual_data_gb} GB")
    
    # Calculate expected data
    expected_gb, breakdown = calculate_expected_data(actual_speed_mbps, actual_duration_hours)
    
    print(f"\n🔢 CALCULATION BREAKDOWN:")
    print(f"   Speed in Mbps: {breakdown['speed_mbps']}")
    print(f"   Speed in MB/s: {breakdown['speed_mbs']:.3f} MB/s")
    print(f"   Duration: {breakdown['duration_hours']} hours = {breakdown['duration_minutes']} minutes = {breakdown['duration_seconds']:,} seconds")
    print(f"   Total MB: {breakdown['total_mb']:,.1f} MB")
    print(f"   Total GB: {breakdown['total_gb']:.2f} GB")
    
    # Compare results
    comparison = compare_results(expected_gb, actual_data_gb)
    
    print(f"\n📈 RESULTS COMPARISON:")
    print(f"   Expected Data: {expected_gb:.2f} GB")
    print(f"   Actual Data:   {actual_data_gb:.2f} GB")
    print(f"   Difference:    {comparison['difference_gb']:+.2f} GB ({comparison['difference_percent']:+.1f}%)")
    
    # Analysis
    print(f"\n🔍 ANALYSIS:")
    abs_diff_percent = abs(comparison['difference_percent'])
    
    if abs_diff_percent <= 2:
        print(f"   ✅ EXCELLENT MATCH! The numbers are very close (within {abs_diff_percent:.1f}%)")
        print(f"   The small difference could be due to:")
        print(f"      • Natural speed variations during the test")
        print(f"      • Rounding in measurements")
        print(f"      • Brief periods of higher/lower speeds")
    elif abs_diff_percent <= 5:
        print(f"   ✅ GOOD MATCH! The numbers are reasonable (within {abs_diff_percent:.1f}%)")
        print(f"   This level of variation is normal for network testing")
    elif abs_diff_percent <= 10:
        print(f"   ⚠️  MODERATE DIFFERENCE ({abs_diff_percent:.1f}%)")
        print(f"   This could indicate some inconsistency in measurements")
    else:
        print(f"   ❌ SIGNIFICANT DIFFERENCE ({abs_diff_percent:.1f}%)")
        print(f"   The numbers may not match - check for calculation errors")
    
    # Additional calculations
    print(f"\n📋 ADDITIONAL METRICS:")
    
    # Data per hour
    data_per_hour = actual_data_gb / actual_duration_hours
    print(f"   Data per hour: {data_per_hour:.2f} GB/hour")
    
    # Data per minute
    data_per_minute = actual_data_gb / (actual_duration_hours * 60)
    print(f"   Data per minute: {data_per_minute:.3f} GB/minute = {data_per_minute * 1024:.1f} MB/minute")
    
    # Effective speed verification
    total_bits = actual_data_gb * 1024 * 1024 * 1024 * 8  # Convert GB to bits
    total_seconds = actual_duration_hours * 3600
    effective_speed_bps = total_bits / total_seconds
    effective_speed_mbps = effective_speed_bps / (1024 * 1024)  # Convert to Mbps
    
    print(f"   Effective speed based on actual data: {effective_speed_mbps:.1f} Mbps")
    print(f"   Speed difference: {effective_speed_mbps - actual_speed_mbps:+.1f} Mbps")
    
    # Theoretical maximums at different speeds
    print(f"\n🚀 THEORETICAL DATA AT DIFFERENT SPEEDS (8 hours):")
    speeds = [25, 50, 75, 100, 150, 200]
    for speed in speeds:
        theoretical_gb, _ = calculate_expected_data(speed, 8)
        print(f"   At {speed:3d} Mbps: {theoretical_gb:6.1f} GB")
    
    print(f"\n" + "=" * 60)

if __name__ == "__main__":
    main() 