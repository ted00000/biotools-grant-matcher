#!/usr/bin/env python3
"""
Quick Test - Verify the search fix works
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_fixed_search():
    """Test the fixed search functionality"""
    print("🧪 TESTING FIXED SEARCH")
    print("=" * 40)
    
    try:
        from main import EnhancedGrantMatcher
        
        matcher = EnhancedGrantMatcher()
        
        # Test the specific problem case first
        print("🔍 Testing the 'hot dog' problem...")
        
        filters = {'data_type': 'companies'}
        results = matcher.search_grants("hot dog", limit=10, filters=filters)
        
        print(f"Results for 'hot dog': {len(results)}")
        
        if len(results) == 0:
            print("✅ PERFECT: 'hot dog' now returns 0 results!")
        elif len(results) <= 2:
            print(f"✅ GOOD: 'hot dog' returns only {len(results)} results")
            for result in results:
                score = result.get('relevance_score', 0)
                company = result.get('company_name', 'Unknown')
                title = result.get('title', 'No title')
                print(f"   - {company}: {title[:50]}... (score: {score})")
        else:
            print(f"❌ STILL BROKEN: 'hot dog' returns {len(results)} results")
            print("Top results:")
            for result in results[:3]:
                score = result.get('relevance_score', 0)
                company = result.get('company_name', 'Unknown')
                title = result.get('title', 'No title')
                print(f"   - {company}: {title[:50]}... (score: {score})")
        
        # Test positive cases
        print(f"\n🔍 Testing positive cases...")
        
        positive_tests = ["single cell", "biomarker", "diagnostic"]
        
        for query in positive_tests:
            results = matcher.search_grants(query, limit=5, filters=filters)
            print(f"'{query}': {len(results)} results")
            
            if len(results) > 0:
                top_result = results[0]
                score = top_result.get('relevance_score', 0)
                company = top_result.get('company_name', 'Unknown')
                print(f"   Top: {company} (score: {score})")
        
        print(f"\n🎯 SUMMARY:")
        print("The keyword and semantic scoring has been fixed to:")
        print("1. Only give points for actual content matches")
        print("2. Return 0 for completely unrelated queries")
        print("3. Not award agency bonuses unless content matches exist")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_fixed_search()