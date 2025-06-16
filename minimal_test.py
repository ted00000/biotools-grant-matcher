#!/usr/bin/env python3
"""
Minimal test to isolate the processing issue
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.scraper import SBIRScraper
import requests

def minimal_test():
    """Minimal test of just the filtering logic"""
    print("🔬 Minimal Processing Test")
    print("=" * 30)
    
    # Get data directly like the scraper does
    url = "https://api.www.sbir.gov/public/api/awards"
    params = {
        'agency': 'HHS',
        'year': 2024,
        'start': 0,
        'rows': 5,  # Just 5 for testing
        'format': 'json'
    }
    
    print(f"1. Getting data from API...")
    response = requests.get(url, params=params, timeout=30)
    data = response.json()
    print(f"   Got {len(data)} awards")
    
    # Test the scraper's filtering methods
    scraper = SBIRScraper()
    
    print(f"\n2. Testing biotools filtering...")
    relevant_count = 0
    
    for i, award in enumerate(data):
        title = award.get('award_title', '')
        abstract = award.get('abstract', '')
        keywords = award.get('research_area_keywords', '') or ''
        
        print(f"\n   Award {i+1}: {title[:50]}...")
        
        # Test the filtering method directly
        combined_text = f"{title} {abstract} {keywords}"
        is_relevant = scraper.is_biotools_relevant(combined_text)
        
        print(f"   Combined text length: {len(combined_text)}")
        print(f"   Is biotools relevant: {is_relevant}")
        
        if is_relevant:
            relevant_count += 1
            score = scraper.calculate_biotools_relevance_score(title, abstract, keywords)
            print(f"   ✅ Relevance score: {score:.1f}")
        else:
            print(f"   ❌ Not relevant")
    
    print(f"\n📊 Results:")
    print(f"   Total awards: {len(data)}")
    print(f"   Biotools relevant: {relevant_count}")
    print(f"   Relevance rate: {relevant_count/len(data)*100:.1f}%")

if __name__ == "__main__":
    minimal_test()