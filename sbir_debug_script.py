#!/usr/bin/env python3
"""
SBIR API Debug Script - Test API responses and data structure
"""

import requests
import json
from datetime import datetime

def test_api_endpoint(url, description):
    """Test a single API endpoint and show response structure"""
    print(f"\n🔍 Testing: {description}")
    print(f"URL: {url}")
    print("-" * 60)
    
    try:
        response = requests.get(url, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Response Type: {type(data)}")
                
                if isinstance(data, dict):
                    print(f"Keys: {list(data.keys())}")
                    
                    # Look for results
                    if 'results' in data:
                        results = data['results']
                        print(f"Results count: {len(results)}")
                        
                        if results and len(results) > 0:
                            print("\nFirst result structure:")
                            first_result = results[0]
                            for key, value in first_result.items():
                                print(f"  {key}: {type(value)} = {str(value)[:100]}...")
                        else:
                            print("No results found")
                    
                    # Check if it's a direct array
                    elif isinstance(data, list):
                        print(f"Direct array with {len(data)} items")
                        if data:
                            print("First item structure:")
                            for key, value in data[0].items():
                                print(f"  {key}: {type(value)} = {str(value)[:100]}...")
                    
                    # Show all top-level keys and their types
                    else:
                        print("Top-level structure:")
                        for key, value in data.items():
                            print(f"  {key}: {type(value)}")
                            if isinstance(value, list) and value:
                                print(f"    (array with {len(value)} items)")
                
                elif isinstance(data, list):
                    print(f"Direct list with {len(data)} items")
                    if data:
                        print("First item structure:")
                        first_item = data[0]
                        if isinstance(first_item, dict):
                            for key, value in first_item.items():
                                print(f"  {key}: {type(value)} = {str(value)[:100]}...")
                
            except json.JSONDecodeError as e:
                print(f"JSON parsing error: {e}")
                print(f"Raw response (first 500 chars): {response.text[:500]}")
        
        else:
            print(f"Error response: {response.text[:200]}")
    
    except Exception as e:
        print(f"Request failed: {e}")

def main():
    print("🧪 SBIR API Debug Testing")
    print("=" * 60)
    
    # Test different API endpoints
    test_cases = [
        # Awards API tests
        ("https://api.www.sbir.gov/public/api/awards?agency=HHS&year=2024&rows=5", 
         "HHS Awards 2024 (5 records)"),
        
        ("https://api.www.sbir.gov/public/api/awards?agency=NSF&year=2024&rows=5", 
         "NSF Awards 2024 (5 records)"),
        
        ("https://api.www.sbir.gov/public/api/awards?rows=5", 
         "Any Awards (5 records)"),
        
        # Test without year filter
        ("https://api.www.sbir.gov/public/api/awards?agency=HHS&rows=5", 
         "HHS Awards (any year, 5 records)"),
        
        # Solicitations API tests  
        ("https://api.www.sbir.gov/public/api/solicitations?rows=5", 
         "Any Solicitations (5 records)"),
        
        ("https://api.www.sbir.gov/public/api/solicitations?open=1&rows=5", 
         "Open Solicitations (5 records)"),
        
        # Companies API tests
        ("https://api.www.sbir.gov/public/api/firm?rows=5", 
         "Companies (5 records)"),
        
        ("https://api.www.sbir.gov/public/api/firm?keyword=biotechnology&rows=5", 
         "Biotechnology Companies (5 records)"),
    ]
    
    for url, description in test_cases:
        test_api_endpoint(url, description)
    
    print("\n" + "=" * 60)
    print("🎯 Debug Summary:")
    print("- Check which endpoints return data")
    print("- Verify the JSON structure matches our parsing code")
    print("- Look for any API changes or different field names")
    print("- Test if biotools keywords are found in the actual data")

if __name__ == "__main__":
    main()