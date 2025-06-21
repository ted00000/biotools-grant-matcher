#!/usr/bin/env python3
"""
Search Debug Script - Diagnose why search returns same results for different queries
"""

import sqlite3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import EnhancedGrantMatcher

def debug_database_content():
    """Check what's actually in the database"""
    print("🔍 DATABASE CONTENT ANALYSIS")
    print("=" * 50)
    
    conn = sqlite3.connect("data/grants.db")
    cursor = conn.cursor()
    
    # Check total records
    cursor.execute("SELECT COUNT(*) FROM grants")
    total = cursor.fetchone()[0]
    print(f"📊 Total grants: {total}")
    
    # Check data distribution
    cursor.execute("""
        SELECT 
            COUNT(CASE WHEN title IS NOT NULL AND title != '' THEN 1 END) as has_title,
            COUNT(CASE WHEN description IS NOT NULL AND description != '' THEN 1 END) as has_description,
            COUNT(CASE WHEN keywords IS NOT NULL AND keywords != '' THEN 1 END) as has_keywords
        FROM grants
    """)
    content_stats = cursor.fetchone()
    print(f"📝 Content availability:")
    print(f"   Titles: {content_stats[0]}")
    print(f"   Descriptions: {content_stats[1]}")
    print(f"   Keywords: {content_stats[2]}")
    
    # Check data sources
    cursor.execute("SELECT data_source, COUNT(*) FROM grants WHERE data_source IS NOT NULL GROUP BY data_source")
    sources = cursor.fetchall()
    print(f"📈 Data sources:")
    for source, count in sources:
        print(f"   {source}: {count}")
    
    # Check grant types
    cursor.execute("SELECT grant_type, COUNT(*) FROM grants WHERE grant_type IS NOT NULL GROUP BY grant_type")
    types = cursor.fetchall()
    print(f"🏷️  Grant types:")
    for gtype, count in types:
        print(f"   {gtype}: {count}")
    
    # Sample some records
    print(f"\n📋 SAMPLE RECORDS:")
    cursor.execute("SELECT id, title, agency, grant_type, data_source FROM grants LIMIT 10")
    samples = cursor.fetchall()
    for record in samples:
        print(f"   ID {record[0]}: {record[1][:50]}... | {record[2]} | {record[3]} | {record[4]}")
    
    conn.close()

def debug_data_type_inference():
    """Test the data type inference logic"""
    print(f"\n🔬 DATA TYPE INFERENCE TEST")
    print("=" * 50)
    
    matcher = EnhancedGrantMatcher()
    
    conn = sqlite3.connect("data/grants.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM grants LIMIT 20")
    samples = cursor.fetchall()
    
    type_counts = {'award': 0, 'solicitation': 0, 'company': 0, 'unknown': 0}
    
    print(f"Sample type inference:")
    for i, row in enumerate(samples):
        grant = dict(row)
        inferred_type = matcher._determine_data_type(grant)
        type_counts[inferred_type] = type_counts.get(inferred_type, 0) + 1
        
        if i < 5:  # Show first 5
            print(f"   ID {grant['id']}: {inferred_type}")
            print(f"      grant_type: {grant.get('grant_type')}")
            print(f"      company_name: {grant.get('company_name')}")
            print(f"      solicitation_number: {grant.get('solicitation_number')}")
            print(f"      award_year: {grant.get('award_year')}")
    
    print(f"\nType distribution in sample:")
    for dtype, count in type_counts.items():
        print(f"   {dtype}: {count}")
    
    conn.close()

def debug_search_algorithm():
    """Test the search algorithm with different queries"""
    print(f"\n🧪 SEARCH ALGORITHM TEST")
    print("=" * 50)
    
    matcher = EnhancedGrantMatcher()
    
    test_queries = [
        "single cell",
        "hot dog",
        "biomarker",
        "xyz123nonsense"
    ]
    
    for query in test_queries:
        print(f"\n🔍 Testing query: '{query}'")
        print("-" * 30)
        
        # Test without filters
        results = matcher.search_grants(query, limit=5)
        print(f"   Results found: {len(results)}")
        
        if results:
            print(f"   Top result: {results[0].get('title', 'No title')[:50]}...")
            print(f"   Relevance score: {results[0].get('relevance_score', 'No score')}")
            print(f"   Inferred type: {results[0].get('inferred_type', 'No type')}")
        
        # Test with data type filters
        for data_type in ['awards', 'solicitations', 'companies']:
            filtered_results = matcher.search_grants(query, limit=5, filters={'data_type': data_type})
            print(f"   {data_type}: {len(filtered_results)} results")

def debug_idf_cache():
    """Check if IDF cache is working"""
    print(f"\n🧮 IDF CACHE TEST")
    print("=" * 50)
    
    matcher = EnhancedGrantMatcher()
    
    print(f"IDF cache size: {len(matcher.idf_cache)}")
    
    if len(matcher.idf_cache) == 0:
        print("❌ IDF cache is empty! This could be the problem.")
        return
    
    # Show some sample IDF values
    print(f"Sample IDF values:")
    sample_terms = list(matcher.idf_cache.items())[:10]
    for term, idf_value in sample_terms:
        print(f"   '{term}': {idf_value:.2f}")
    
    # Test term extraction
    test_queries = ["single cell", "hot dog", "biomarker"]
    for query in test_queries:
        terms = matcher._extract_terms(query.lower())
        print(f"   '{query}' -> terms: {terms}")

def debug_simple_search():
    """Test the simple fallback search directly"""
    print(f"\n🔧 SIMPLE SEARCH TEST")
    print("=" * 50)
    
    matcher = EnhancedGrantMatcher()
    
    test_queries = ["single cell", "hot dog", "biomarker"]
    
    for query in test_queries:
        print(f"\n🔍 Simple search for: '{query}'")
        results = matcher._simple_search(query, limit=5)
        print(f"   Results: {len(results)}")
        
        if results:
            print(f"   First result: {results[0].get('title', 'No title')[:50]}...")
            print(f"   Relevance score: {results[0].get('relevance_score', 'No score')}")

def debug_database_schema():
    """Check database schema for missing columns"""
    print(f"\n📊 DATABASE SCHEMA CHECK")
    print("=" * 50)
    
    conn = sqlite3.connect("data/grants.db")
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(grants);")
    columns = cursor.fetchall()
    
    print(f"Table columns ({len(columns)} total):")
    for col in columns:
        print(f"   {col[1]} ({col[2]})")
    
    # Check for company-related data
    cursor.execute("""
        SELECT 
            COUNT(CASE WHEN company_name IS NOT NULL AND company_name != '' THEN 1 END) as has_company_name,
            COUNT(CASE WHEN firm IS NOT NULL AND firm != '' THEN 1 END) as has_firm,
            COUNT(CASE WHEN uei IS NOT NULL AND uei != '' THEN 1 END) as has_uei
        FROM grants
    """)
    company_stats = cursor.fetchone()
    print(f"\nCompany data availability:")
    print(f"   company_name: {company_stats[0]}")
    print(f"   firm: {company_stats[1]}")
    print(f"   uei: {company_stats[2]}")
    
    conn.close()

def main():
    """Run all debug tests"""
    print("🚀 BIOTOOLS GRANT MATCHER - SEARCH DEBUG")
    print("=" * 60)
    
    if not os.path.exists("data/grants.db"):
        print("❌ Database not found!")
        return
    
    try:
        debug_database_content()
        debug_database_schema()
        debug_data_type_inference()
        debug_idf_cache()
        debug_simple_search()
        debug_search_algorithm()
        
        print(f"\n🎯 DIAGNOSIS COMPLETE")
        print("=" * 60)
        print("Check the output above to identify:")
        print("1. Whether IDF cache is empty (search not working)")
        print("2. Whether data type inference is failing")
        print("3. Whether company data exists in database")
        print("4. Whether simple search works differently than enhanced search")
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()