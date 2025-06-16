#!/usr/bin/env python3
"""
Test script for security features and rate limiting
"""

import requests
import time
import json

BASE_URL = "http://localhost:5000/api"

def test_rate_limiting():
    """Test rate limiting functionality"""
    print("🛡️  Testing Rate Limiting")
    print("-" * 30)
    
    search_url = f"{BASE_URL}/search"
    
    # Test normal requests
    for i in range(3):
        payload = {"query": f"test query {i}"}
        response = requests.post(search_url, json=payload)
        print(f"Request {i+1}: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Found {data.get('total_found', 0)} grants")
        elif response.status_code == 429:
            print("  Rate limited!")
            break
        
        time.sleep(1)  # Small delay between requests
    
    # Test rapid requests to trigger rate limiting
    print("\n🚨 Testing Rapid Requests (should trigger rate limit)")
    for i in range(10):
        payload = {"query": f"rapid test {i}"}
        response = requests.post(search_url, json=payload)
        
        if response.status_code == 429:
            print(f"  ✅ Rate limit triggered on request {i+1}")
            break
        elif i == 9:
            print("  ⚠️  Rate limit not triggered (this might be expected)")

def test_input_validation():
    """Test input validation and sanitization"""
    print("\n🔍 Testing Input Validation")
    print("-" * 30)
    
    search_url = f"{BASE_URL}/search"
    
    # Test cases: [payload, expected_status, description]
    test_cases = [
        # Valid input
        ({"query": "diagnostic device"}, 200, "Valid query"),
        
        # Missing required field
        ({}, 400, "Missing query field"),
        
        # Empty query
        ({"query": ""}, 400, "Empty query"),
        
        # Too short query
        ({"query": "a"}, 400, "Too short query"),
        
        # Very long query (should be truncated/rejected)
        ({"query": "a" * 250}, 400, "Too long query"),
        
        # Potential XSS attempt
        ({"query": "<script>alert('xss')</script>"}, 200, "XSS attempt (sanitized)"),
        
        # SQL injection attempt
        ({"query": "'; DROP TABLE grants; --"}, 400, "SQL injection attempt"),
        
        # Valid with filters
        ({
            "query": "biomarker",
            "filters": {
                "agency": "NSF",
                "amount_min": 100000
            }
        }, 200, "Valid query with filters"),
    ]
    
    for payload, expected_status, description in test_cases:
        try:
            response = requests.post(search_url, json=payload)
            actual_status = response.status_code
            
            if actual_status == expected_status:
                print(f"  ✅ {description}: {actual_status}")
            else:
                print(f"  ❌ {description}: expected {expected_status}, got {actual_status}")
                if response.content:
                    error_data = response.json()
                    print(f"     Error: {error_data.get('error', 'Unknown')}")
                    
        except Exception as e:
            print(f"  ❌ {description}: Request failed - {e}")

def test_security_headers():
    """Test security headers are present"""
    print("\n🛡️  Testing Security Headers")
    print("-" * 30)
    
    response = requests.get(f"{BASE_URL}/stats")
    headers = response.headers
    
    expected_headers = [
        'X-Content-Type-Options',
        'X-Frame-Options', 
        'X-XSS-Protection',
        'Referrer-Policy',
        'Content-Security-Policy'
    ]
    
    for header in expected_headers:
        if header in headers:
            print(f"  ✅ {header}: {headers[header]}")
        else:
            print(f"  ❌ {header}: Missing")
    
    # Check that server info is hidden
    if 'Server' not in headers:
        print(f"  ✅ Server header hidden")
    else:
        print(f"  ⚠️  Server header present: {headers['Server']}")

def test_feedback_validation():
    """Test feedback endpoint validation"""
    print("\n💬 Testing Feedback Validation")
    print("-" * 30)
    
    feedback_url = f"{BASE_URL}/feedback"
    
    test_cases = [
        # Valid feedback
        ({
            "grant_id": 1,
            "feedback_type": "helpful",
            "search_query": "test query"
        }, 200, "Valid feedback"),
        
        # Missing required fields
        ({"grant_id": 1}, 400, "Missing feedback_type"),
        
        # Invalid feedback type
        ({
            "grant_id": 1,
            "feedback_type": "invalid_type"
        }, 400, "Invalid feedback type"),
        
        # Invalid grant ID
        ({
            "grant_id": -1,
            "feedback_type": "helpful"
        }, 400, "Invalid grant ID"),
        
        # Very long notes (should be rejected)
        ({
            "grant_id": 1,
            "feedback_type": "helpful",
            "notes": "a" * 600
        }, 400, "Too long notes"),
    ]
    
    for payload, expected_status, description in test_cases:
        try:
            response = requests.post(feedback_url, json=payload)
            actual_status = response.status_code
            
            if actual_status == expected_status:
                print(f"  ✅ {description}: {actual_status}")
            else:
                print(f"  ❌ {description}: expected {expected_status}, got {actual_status}")
                if response.content:
                    try:
                        error_data = response.json()
                        print(f"     Response: {error_data}")
                    except:
                        print(f"     Response: {response.text}")
                        
        except Exception as e:
            print(f"  ❌ {description}: Request failed - {e}")

def test_grant_details_security():
    """Test grant details endpoint security"""
    print("\n📄 Testing Grant Details Security")
    print("-" * 30)
    
    # Test valid grant ID
    response = requests.get(f"{BASE_URL}/grant/1")
    if response.status_code in [200, 404]:
        print(f"  ✅ Valid grant ID: {response.status_code}")
    else:
        print(f"  ❌ Valid grant ID: unexpected {response.status_code}")
    
    # Test invalid grant IDs
    invalid_ids = [0, -1, "abc", 999999]
    for invalid_id in invalid_ids:
        response = requests.get(f"{BASE_URL}/grant/{invalid_id}")
        if response.status_code in [400, 404]:
            print(f"  ✅ Invalid grant ID ({invalid_id}): {response.status_code}")
        else:
            print(f"  ❌ Invalid grant ID ({invalid_id}): unexpected {response.status_code}")

def main():
    """Run all security tests"""
    print("🚀 Starting Security Tests")
    print("=" * 50)
    
    print("⚠️  Make sure your Flask app is running on localhost:5000")
    print("   Run: python3 main.py")
    print()
    
    # Test if server is running
    try:
        response = requests.get(f"{BASE_URL}/stats", timeout=5)
        print(f"✅ Server is running (status: {response.status_code})")
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running. Start it with: python3 main.py")
        return
    except Exception as e:
        print(f"❌ Server check failed: {e}")
        return
    
    # Run all tests
    test_input_validation()
    test_security_headers()
    test_feedback_validation() 
    test_grant_details_security()
    test_rate_limiting()  # Run this last as it may trigger limits
    
    print("\n🎉 Security Tests Completed!")
    print("\n📊 Check logs/app.log for detailed security events")

if __name__ == "__main__":
    main()