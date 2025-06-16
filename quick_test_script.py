#!/usr/bin/env python3
"""
Quick test - just HHS 2024 awards to debug the scraper
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.scraper import SBIRScraper

def quick_test():
    """Test just HHS 2024 awards"""
    print("🔬 Quick Test: HHS 2024 Awards Only")
    print("=" * 40)
    
    scraper = SBIRScraper()
    
    # Test just HHS 2024
    try:
        awards = scraper.fetch_awards_by_agency('HHS', 2024)
        print(f"\n📊 Final Results:")
        print(f"Total biotools awards collected: {len(awards)}")
        
        if awards:
            print(f"\nFirst few awards:")
            for i, award in enumerate(awards[:3]):
                print(f"{i+1}. {award.get('award_title', '')[:60]}...")
                print(f"   Score: {award.get('relevance_score', 0):.1f}")
                print(f"   Company: {award.get('firm', 'Unknown')}")
        
        # Try to save them
        saved = scraper.save_awards(awards)
        print(f"\n💾 Saved {saved} awards to database")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    quick_test()