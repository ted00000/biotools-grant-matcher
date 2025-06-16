#!/usr/bin/env python3
"""
SBIR API Diagnostic Tool - Quick test to identify API issues
"""

import requests
import json
import time

def test_endpoint(url, description, headers=None):
    """Test a single API endpoint"""
    print(f"\n🔍 Testing: {description}")
    print(f"URL: {url}")
    print("-" * 50)
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                if isinstance(data, list):
                    print(f"✅ Success: {len(data)} records returned")
                    if data:
                        print(f"Sample record keys: {list(data[0].keys())}")
                        if 'solicitation_title' in data[0]:
                            print(f"Sample title: {data[0]['solicitation_title'][:60]}...")
                        elif 'award_title' in data[0]:
                            print(f"Sample title: {data[0]['award_title'][:60]}...")
                elif isinstance(data, dict):
                    print(f"✅ Success: Dictionary returned with keys: {list(data.keys())}")
                else:
                    print(f"✅ Success: {type(data)} returned")
            except json.JSONDecodeError:
                print(f"⚠️ Success but not JSON: {response.text[:100]}...")
        elif response.status_code == 403:
            print("❌ 403 Forbidden - API access denied")
        elif response.status_code == 404:
            print("❌ 404 Not Found - Endpoint doesn't exist")
        elif response.status_code == 429:
            print("❌ 429 Rate Limited")
        else:
            print(f"❌ Error {response.status_code}: {response.text[:200]}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

def main():
    print("🚀 SBIR API Diagnostic Tool")
    print("=" * 60)
    
    # Headers to appear more like a browser
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; GrantMatcher/1.0)',
        'Accept': 'application/json, text/html',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    
    # Test cases to try
    test_cases = [
        # Current API endpoints
        ("https://api.www.sbir.gov/public/api/awards?rows=5", "Current API - Awards (5 records)", headers),
        ("https://api.www.sbir.gov/public/api/awards?agency=HHS&rows=5", "Current API - HHS Awards", headers),
        ("https://api.www.sbir.gov/public/api/firm?rows=5", "Current API - Companies", headers),
        ("https://api.www.sbir.gov/public/api/solicitations?rows=5", "Current API - Solicitations", headers),
        ("https://api.www.sbir.gov/public/api/solicitations?open=1&rows=5", "Current API - Open Solicitations", headers),
        
        # Try with format parameter
        ("https://api.www.sbir.gov/public/api/solicitations?format=json&rows=5", "Current API - Solicitations with format", headers),
        ("https://api.www.sbir.gov/public/api/solicitations?format=json&open=1&rows=5", "Current API - Open Solicitations with format", headers),
        
        # Legacy API endpoints (if they exist)
        ("https://legacy.www.sbir.gov/api/solicitations?rows=5", "Legacy API - Solicitations", headers),
        ("https://www.sbir.gov/api/solicitations.json?rows=5", "Alternative API - Solicitations", headers),
        
        # Test without any parameters
        ("https://api.www.sbir.gov/public/api/solicitations", "Current API - Solicitations (no params)", headers),
        
        # Test with different user agent
        ("https://api.www.sbir.gov/public/api/solicitations?rows=5", "Current API - Different User Agent", {
            'User-Agent': 'curl/7.68.0',
            'Accept': '*/*'
        }),
        
        # Test with no headers
        ("https://api.www.sbir.gov/public/api/solicitations?rows=5", "Current API - No Headers", None),
    ]
    
    working_endpoints = []
    
    for url, description, test_headers in test_cases:
        test_endpoint(url, description, test_headers)
        
        # Brief pause between requests
        time.sleep(0.5)
        
        # Check if this one worked
        try:
            response = requests.get(url, headers=test_headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and len(data) > 0:
                    working_endpoints.append((url, description))
        except:
            pass
    
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("-" * 60)
    
    if working_endpoints:
        print("✅ Working endpoints found:")
        for url, desc in working_endpoints:
            print(f"  • {desc}")
            print(f"    {url}")
    else:
        print("❌ No working endpoints found")
        print("\nPossible issues:")
        print("  • API requires authentication now")
        print("  • Solicitations endpoint temporarily disabled")
        print("  • Rate limiting or IP blocking")
        print("  • API has moved to different URLs")
        print("  • SBIR.gov API changes or maintenance")
    
    print("\n🔧 Recommended next steps:")
    if working_endpoints:
        print("  • Use working endpoints to collect available data")
        print("  • Focus on awards and companies data")
        print("  • Check SBIR.gov website manually for solicitations")
    else:
        print("  • Check SBIR.gov website status")
        print("  • Try from different IP/network")
        print("  • Contact SBIR.gov technical support")
        print("  • Use alternative data sources (grants.gov, etc.)")

if __name__ == "__main__":
    main()