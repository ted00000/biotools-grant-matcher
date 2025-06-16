#!/usr/bin/env python3
"""
Test script for the enhanced search algorithm
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import from the renamed main file
from main import EnhancedGrantMatcher

def test_search():
    """Test the enhanced search functionality"""
    
    print("🧪 Testing Enhanced Grant Search Algorithm")
    print("=" * 50)
    
    # Initialize the matcher
    try:
        matcher = EnhancedGrantMatcher()
        print(f"📊 IDF Cache built with {len(matcher.idf_cache)} terms")
    except Exception as e:
        print(f"❌ Failed to initialize matcher: {e}")
        return
    
    # Test queries
    test_queries = [
        "diagnostic biomarker cancer",
        "microfluidics lab-on-chip",
        "AI medical imaging",
        "point-of-care testing",
        "lab automation robotics",
        "genomic sequencing tool"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n🔍 Test {i}: '{query}'")
        print("-" * 30)
        
        try:
            # Test without filters
            results = matcher.search_grants(query, limit=5)
            
            if results:
                print(f"Found {len(results)} grants:")
                for j, grant in enumerate(results[:3], 1):  # Show top 3
                    print(f"  {j}. {grant['title'][:60]}...")
                    print(f"     Agency: {grant['agency']} | Score: {grant['relevance_score']}")
                    if grant.get('keywords'):
                        keywords = grant['keywords'].split(',')[:3]  # First 3 keywords
                        print(f"     Keywords: {', '.join(k.strip() for k in keywords)}")
            else:
                print("  No grants found")
        except Exception as e:
            print(f"  ❌ Search failed: {e}")
    
    # Test with filters
    print(f"\n🎯 Testing Filters")
    print("-" * 30)
    
    filter_query = "diagnostic device"
    filters = {
        'agency': 'NSF',
        'amount_min': 100000,
        'category': 'diagnostics'
    }
    
    print(f"Query: '{filter_query}' with filters: {filters}")
    try:
        filtered_results = matcher.search_grants(filter_query, limit=5, filters=filters)
        
        if filtered_results:
            print(f"Found {len(filtered_results)} filtered grants:")
            for grant in filtered_results[:2]:  # Show top 2
                print(f"  - {grant['title'][:50]}...")
                print(f"    Score: {grant['relevance_score']} | Agency: {grant['agency']}")
        else:
            print("  No grants found with these filters")
    except Exception as e:
        print(f"  ❌ Filtered search failed: {e}")
    
    print(f"\n✅ Enhanced Search Test Complete!")

def test_scoring_components():
    """Test individual scoring components"""
    
    print(f"\n🔬 Testing Scoring Components")
    print("=" * 50)
    
    try:
        matcher = EnhancedGrantMatcher()
        
        # Create a sample grant for testing
        sample_grant = {
            'title': 'Development of AI-Powered Diagnostic Biosensor for Cancer Detection',
            'description': 'This project aims to develop a novel biosensor platform that combines artificial intelligence with microfluidics technology for early cancer biomarker detection in point-of-care settings.',
            'keywords': 'biosensor, artificial intelligence, cancer, diagnostic, microfluidics, biomarker',
            'agency': 'NIH',
            'updated_at': '2024-12-01T00:00:00'
        }
        
        test_query = "AI diagnostic biosensor cancer"
        
        # Test individual scoring methods
        query_terms = matcher._extract_terms(test_query.lower())
        combined_text = f"{sample_grant['title']} {sample_grant['description']} {sample_grant['keywords']}"
        
        tf_idf_score = matcher._calculate_tf_idf_score(query_terms, combined_text)
        semantic_score = matcher._calculate_semantic_score(test_query, sample_grant)
        keyword_score = matcher._calculate_keyword_score(test_query, sample_grant)
        freshness_score = matcher._calculate_freshness_score(sample_grant)
        
        print(f"Query: '{test_query}'")
        print(f"Grant: '{sample_grant['title'][:50]}...'")
        print()
        print(f"📈 Scoring Breakdown:")
        print(f"  TF-IDF Score:    {tf_idf_score:.2f}")
        print(f"  Semantic Score:  {semantic_score:.2f}")
        print(f"  Keyword Score:   {keyword_score:.2f}")
        print(f"  Freshness Score: {freshness_score:.2f}")
        
        # Calculate weighted final score
        final_score = (
            tf_idf_score * 0.25 +
            semantic_score * 0.35 +
            keyword_score * 0.30 +
            freshness_score * 0.10
        )
        print(f"  Final Score:     {final_score:.2f}")
        
        print(f"\n📝 Query Terms Extracted: {query_terms}")
        
    except Exception as e:
        print(f"❌ Scoring test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 Starting Enhanced Search Tests...")
    print(f"📁 Working directory: {os.getcwd()}")
    print(f"🗄️ Looking for database at: data/grants.db")
    
    # Check if database exists
    if not os.path.exists("data/grants.db"):
        print("⚠️  Warning: Database not found at data/grants.db")
        print("   Make sure you've run the scraper first!")
        print("   Run: python app/scraper.py")
        exit(1)
    
    try:
        test_search()
        test_scoring_components()
        print("\n🎉 All tests completed!")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()