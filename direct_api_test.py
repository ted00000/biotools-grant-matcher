#!/usr/bin/env python3
"""
Direct API test to bypass scraper logic
"""

import requests

def direct_api_test():
    """Test API directly and show response"""
    print("🔬 Direct API Test")
    print("=" * 30)
    
    url = "https://api.www.sbir.gov/public/api/awards"
    params = {
        'agency': 'HHS',
        'year': 2024,
        'start': 0,
        'rows': 5,  # Just 5 for testing
        'format': 'json'
    }
    
    print(f"URL: {url}")
    print(f"Params: {params}")
    print()
    
    try:
        response = requests.get(url, params=params, timeout=30)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response Type: {type(data)}")
            print(f"Response Length: {len(data) if isinstance(data, list) else 'N/A'}")
            
            if isinstance(data, list) and len(data) > 0:
                print(f"\nFirst award:")
                first_award = data[0]
                print(f"Title: {first_award.get('award_title', 'No title')}")
                print(f"Company: {first_award.get('firm', 'No company')}")
                print(f"Year: {first_award.get('award_year', 'No year')}")
                print(f"Agency: {first_award.get('agency', 'No agency')}")
                
                # Test biotools filtering on this award
                title = first_award.get('award_title', '')
                abstract = first_award.get('abstract', '')
                
                biotools_keywords = ['diagnostic', 'biomarker', 'assay', 'test', 'detection', 'medical', 'clinical']
                combined_text = f"{title} {abstract}".lower()
                
                matches = [kw for kw in biotools_keywords if kw in combined_text]
                
                print(f"\nBiotools check:")
                print(f"Combined text length: {len(combined_text)}")
                print(f"Matched keywords: {matches}")
                print(f"Is biotools relevant: {len(matches) > 0}")
                
            else:
                print("No data in response")
                
        else:
            print(f"Error: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    direct_api_test()