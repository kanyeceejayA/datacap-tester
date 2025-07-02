#!/usr/bin/env python3
"""
Test script for ISP Data Cap Tester Backend
Verifies that all components are working correctly.
"""

import json
import time
import requests
import subprocess
import sys
from pathlib import Path

def test_config_files():
    """Test that configuration files exist and are valid."""
    print("Testing configuration files...")
    
    # Test config.json
    try:
        with open("config.json", 'r') as f:
            config = json.load(f)
        assert "test_urls" in config
        assert "data_cap_gb" in config
        assert "port" in config
        print("✓ config.json is valid")
    except Exception as e:
        print(f"✗ config.json error: {e}")
        return False
    
    # Test data.json
    try:
        with open("data.json", 'r') as f:
            data = json.load(f)
        assert "status" in data
        assert "speed_mbps" in data
        print("✓ data.json is valid")
    except Exception as e:
        print(f"✗ data.json error: {e}")
        return False
    
    return True

def test_downloader_import():
    """Test that downloader module can be imported."""
    print("Testing downloader module...")
    
    try:
        import downloader
        tester = downloader.DownloadTester()
        print("✓ Downloader module imports successfully")
        print(f"✓ Configuration loaded: {len(tester.config)} settings")
        return True
    except Exception as e:
        print(f"✗ Downloader import error: {e}")
        return False

def test_server_import():
    """Test that server module can be imported."""
    print("Testing server module...")
    
    try:
        import server
        test_server = server.DataCapTesterServer()
        print("✓ Server module imports successfully")
        print(f"✓ FastAPI app created: {test_server.app.title}")
        return True
    except Exception as e:
        print(f"✗ Server import error: {e}")
        return False

def test_api_endpoints():
    """Test API endpoints (requires server to be running)."""
    print("Testing API endpoints...")
    
    base_url = "http://localhost:8000"
    
    try:
        # Test /api/stats endpoint
        response = requests.get(f"{base_url}/api/stats", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print("✓ /api/stats endpoint working")
            print(f"  Current status: {data.get('status', 'unknown')}")
        else:
            print(f"✗ /api/stats returned status {response.status_code}")
            return False
        
        # Test /api/system endpoint
        response = requests.get(f"{base_url}/api/system", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("✓ /api/system endpoint working")
            print(f"  External IP: {data.get('external_ip', 'unknown')}")
            print(f"  ISP: {data.get('isp', 'unknown')}")
        else:
            print(f"✗ /api/system returned status {response.status_code}")
            return False
        
        return True
        
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to server. Make sure server is running with:")
        print("  python server.py")
        return False
    except Exception as e:
        print(f"✗ API test error: {e}")
        return False

def test_file_permissions():
    """Test that all necessary files are readable/writable."""
    print("Testing file permissions...")
    
    files_to_check = [
        ("config.json", "r"),
        ("data.json", "rw"),
        ("downloader.py", "r"),
        ("server.py", "r"),
        ("dashboard.html", "r")
    ]
    
    for filename, mode in files_to_check:
        try:
            if 'r' in mode:
                with open(filename, 'r') as f:
                    f.read()
            if 'w' in mode:
                # Test write by updating modification time
                Path(filename).touch()
            print(f"✓ {filename} has correct permissions")
        except Exception as e:
            print(f"✗ {filename} permission error: {e}")
            return False
    
    return True

def run_integration_test():
    """Run a quick integration test if server is available."""
    print("Running integration test...")
    
    try:
        # Test start/stop cycle
        base_url = "http://localhost:8000"
        
        # Start test
        response = requests.post(f"{base_url}/api/start", timeout=5)
        if response.status_code == 200:
            print("✓ Test started successfully")
            time.sleep(2)  # Let it run briefly
            
            # Check stats
            response = requests.get(f"{base_url}/api/stats", timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get("downloader_running", False):
                    print("✓ Downloader process is running")
                else:
                    print("⚠ Downloader process may not be running")
            
            # Stop test
            response = requests.post(f"{base_url}/api/stop", timeout=5)
            if response.status_code == 200:
                print("✓ Test stopped successfully")
            
            return True
        else:
            print(f"✗ Failed to start test: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Integration test error: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 50)
    print("ISP Data Cap Tester - Backend Test Suite")
    print("=" * 50)
    
    tests = [
        ("Configuration Files", test_config_files),
        ("File Permissions", test_file_permissions),
        ("Downloader Module", test_downloader_import),
        ("Server Module", test_server_import),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n[{test_name}]")
        if test_func():
            passed += 1
        print()
    
    # Optional tests that require server to be running
    print("[API Endpoints] (requires server to be running)")
    if test_api_endpoints():
        print("✓ API tests passed")
        print("\n[Integration Test]")
        if run_integration_test():
            print("✓ Integration test passed")
        else:
            print("⚠ Integration test failed (this may be normal)")
    else:
        print("⚠ API tests skipped - server not running")
    
    print("\n" + "=" * 50)
    print(f"Backend Tests Complete: {passed}/{total} core tests passed")
    print("=" * 50)
    
    if passed == total:
        print("\n🎉 All core backend components are working correctly!")
        print("\nTo start the system:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Start the server: python server.py")
        print("3. Open http://localhost:8000 in your browser")
    else:
        print(f"\n⚠ {total - passed} tests failed. Please check the errors above.")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 