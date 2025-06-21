#!/usr/bin/env python3
"""
Relevance Filtering Fix - Debug why "hot dog" returns 50 results
"""

import sqlite3
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_search_relevance():
    """Test search relevance for different queries"""
    print("🔍 TESTING SEARCH RELEVANCE")
    print("-" * 40)
    
    conn = sqlite3.connect("data/grants.db")
    cursor = conn.cursor()
    
    test_queries = ["hot dog", "single cell", "biomarker", "xyzfaketermthatdoesntexist"]
    
    for query in test_queries:
        print(f"\n🔍 Testing: '{query}'")
        
        # Test 1: Simple LIKE search with scoring
        cursor.execute("""
            SELECT 
                title, 
                company_name,
                CASE 
                    WHEN LOWER(title) LIKE ? THEN 10
                    WHEN LOWER(description) LIKE ? THEN 7
                    WHEN LOWER(keywords) LIKE ? THEN 5
                    ELSE 0
                END as simple_score
            FROM grants 
            WHERE company_name IS NOT NULL
            AND (LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR LOWER(keywords) LIKE ?)
            ORDER BY simple_score DESC
            LIMIT 5
        """, [f'%{query.lower()}%'] * 6)
        
        relevant_results = cursor.fetchall()
        print(f"   Relevant matches: {len(relevant_results)}")
        
        for result in relevant_results:
            print(f"     - {result[1]}: {result[0][:50]}... (score: {result[2]})")
        
        # Test 2: Count total with company names (what the broken search might be doing)
        cursor.execute("""
            SELECT COUNT(*) 
            FROM grants 
            WHERE company_name IS NOT NULL AND company_name != ''
        """)
        total_with_companies = cursor.fetchone()[0]
        
        print(f"   Total records with companies: {total_with_companies}")
        
        if len(relevant_results) == 0 and query == "hot dog":
            print(f"   ✅ GOOD: 'hot dog' should return 0 results")
        elif len(relevant_results) > 0 and query in ["single cell", "biomarker"]:
            print(f"   ✅ GOOD: '{query}' found relevant matches")
    
    conn.close()

def debug_actual_search_function():
    """Debug the actual search function by importing and testing it"""
    print(f"\n🧪 TESTING ACTUAL SEARCH FUNCTION")
    print("-" * 40)
    
    try:
        from main import EnhancedGrantMatcher
        
        matcher = EnhancedGrantMatcher()
        
        test_cases = [
            ("hot dog", "companies"),
            ("single cell", "companies"),
            ("biomarker", "companies")
        ]
        
        for query, data_type in test_cases:
            print(f"\n🔍 Enhanced search: '{query}' (type: {data_type})")
            
            filters = {'data_type': data_type}
            results = matcher.search_grants(query, limit=5, filters=filters)
            
            print(f"   Results: {len(results)}")
            
            if results:
                for i, result in enumerate(results[:3]):
                    score = result.get('relevance_score', 0)
                    company = result.get('company_name', 'Unknown')
                    title = result.get('title', 'No title')
                    print(f"     {i+1}. {company}: {title[:40]}... (score: {score})")
            
            # This should show the issue: if "hot dog" returns many results,
            # the relevance filtering is broken
            
    except ImportError as e:
        print(f"   ❌ Could not import search function: {e}")
    except Exception as e:
        print(f"   ❌ Search function error: {e}")

def identify_threshold_issue():
    """Check if the relevance threshold is too low"""
    print(f"\n🎯 CHECKING RELEVANCE THRESHOLD")
    print("-" * 40)
    
    conn = sqlite3.connect("data/grants.db")
    cursor = conn.cursor()
    
    # Manually test the scoring logic from main.py
    query = "hot dog"
    
    cursor.execute("""
        SELECT id, title, description, keywords, company_name
        FROM grants 
        WHERE company_name IS NOT NULL
        LIMIT 100
    """)
    
    sample_records = cursor.fetchall()
    
    print(f"Testing scoring on {len(sample_records)} sample records for '{query}'...")
    
    scores_above_threshold = []
    
    for record in sample_records:
        record_id, title, description, keywords, company_name = record
        
        # Simulate the keyword scoring from main.py
        score = 0.0
        query_lower = query.lower()
        
        if title:
            title_lower = title.lower()
            if query_lower in title_lower:
                score += 20.0
            query_words = query_lower.split()
            for word in query_words:
                if len(word) > 3 and word in title_lower:
                    score += 10.0
        
        if keywords:
            keywords_list = [k.strip().lower() for k in keywords.split(',')]
            for keyword in keywords_list:
                if keyword in query_lower or query_lower in keyword:
                    score += 8.0
                query_words = query_lower.split()
                for word in query_words:
                    if len(word) > 3 and word in keyword:
                        score += 4.0
        
        if description:
            desc_lower = description.lower()
            if query_lower in desc_lower:
                score += 6.0
            query_words = query_lower.split()
            for word in query_words:
                if len(word) > 3 and word in desc_lower:
                    score += 2.0
        
        # Check if this would pass the 0.5 threshold
        if score > 0.5:
            scores_above_threshold.append((company_name, title[:50], score))
    
    print(f"Records scoring above 0.5 threshold: {len(scores_above_threshold)}")
    
    if len(scores_above_threshold) > 10:
        print("❌ PROBLEM: Too many records pass the threshold!")
        print("Sample high-scoring records:")
        for company, title, score in scores_above_threshold[:5]:
            print(f"   {company}: {title}... (score: {score})")
    else:
        print("✅ Threshold seems appropriate")
    
    conn.close()

def main():
    """Run all relevance debugging"""
    print("🚀 RELEVANCE FILTERING DEBUG")
    print("=" * 60)
    
    if not os.path.exists("data/grants.db"):
        print("❌ Database not found!")
        return
    
    test_search_relevance()
    debug_actual_search_function()
    identify_threshold_issue()
    
    print(f"\n🎯 DIAGNOSIS:")
    print("If 'hot dog' returns many results, the issue is likely:")
    print("1. Relevance threshold too low (currently 0.5)")
    print("2. Search falling back to simple search incorrectly")
    print("3. TF-IDF cache not working, making all scores similar")

if __name__ == "__main__":
    main()