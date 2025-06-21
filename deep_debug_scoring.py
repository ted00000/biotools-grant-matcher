#!/usr/bin/env python3
"""
Deep Debug Scoring - Find exactly where the 2.65 score is coming from
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def debug_individual_scoring():
    """Debug the scoring for a specific record that's getting 2.65 for 'hot dog'"""
    print("🔬 DEEP DEBUG: Finding source of 2.65 score")
    print("=" * 50)
    
    try:
        from main import EnhancedGrantMatcher
        import sqlite3
        
        # Get the specific record that's scoring 2.65
        conn = sqlite3.connect("data/grants.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM grants 
            WHERE company_name = 'ASSURED INFORMATION SECURITY, INC.'
            LIMIT 1
        """)
        
        record = cursor.fetchone()
        if not record:
            print("❌ Could not find the problematic record")
            return
        
        grant = dict(record)
        query = "hot dog"
        data_type = "companies"
        
        print(f"📊 Analyzing record: {grant['company_name']}")
        print(f"Title: {grant['title']}")
        print(f"Description: {grant['description'][:100]}...")
        print(f"Keywords: {grant.get('keywords', 'None')}")
        
        # Initialize matcher and test each scoring component
        matcher = EnhancedGrantMatcher()
        
        query_terms = matcher._extract_terms(query.lower())
        print(f"\nQuery terms extracted: {query_terms}")
        
        # Test each scoring component individually
        combined_text = f"{grant.get('title', '')} {grant.get('description', '')} {grant.get('keywords', '')}"
        
        print(f"\n🧮 SCORING BREAKDOWN:")
        
        # 1. TF-IDF Score
        tf_idf_score = matcher._calculate_tf_idf_score(query_terms, combined_text)
        print(f"1. TF-IDF Score: {tf_idf_score:.3f}")
        
        # 2. Semantic Score
        semantic_score = matcher._calculate_semantic_score(query, grant, data_type)
        print(f"2. Semantic Score: {semantic_score:.3f}")
        
        # 3. Keyword Score
        keyword_score = matcher._calculate_keyword_score(query, grant)
        print(f"3. Keyword Score: {keyword_score:.3f}")
        
        # 4. Freshness Score
        freshness_score = matcher._calculate_freshness_score(grant)
        print(f"4. Freshness Score: {freshness_score:.3f}")
        
        # 5. Calculate final weighted score
        final_score = (
            tf_idf_score * 0.25 +
            semantic_score * 0.40 +
            keyword_score * 0.30 +
            freshness_score * 0.05
        )
        
        print(f"\n📊 WEIGHTED BREAKDOWN:")
        print(f"   TF-IDF:    {tf_idf_score:.3f} * 0.25 = {tf_idf_score * 0.25:.3f}")
        print(f"   Semantic:  {semantic_score:.3f} * 0.40 = {semantic_score * 0.40:.3f}")
        print(f"   Keyword:   {keyword_score:.3f} * 0.30 = {keyword_score * 0.30:.3f}")
        print(f"   Freshness: {freshness_score:.3f} * 0.05 = {freshness_score * 0.05:.3f}")
        print(f"   TOTAL:     {final_score:.3f}")
        
        # Check if this matches the actual search result
        filters = {'data_type': 'companies'}
        results = matcher.search_grants(query, limit=5, filters=filters)
        
        matching_result = None
        for result in results:
            if result.get('company_name') == grant['company_name']:
                matching_result = result
                break
        
        if matching_result:
            actual_score = matching_result.get('relevance_score', 0)
            print(f"\n🎯 VERIFICATION:")
            print(f"   Calculated score: {final_score:.3f}")
            print(f"   Actual score:     {actual_score:.3f}")
            print(f"   Match: {'✅' if abs(final_score - actual_score) < 0.01 else '❌'}")
        
        # Now test why keyword and semantic scores aren't 0
        print(f"\n🕵️ INVESTIGATING NON-ZERO SCORES:")
        
        if keyword_score > 0:
            print(f"❌ Keyword score should be 0! Investigating...")
            # Test keyword matching manually
            query_lower = query.lower()
            query_words = set(query_lower.split())
            print(f"   Query words: {query_words}")
            
            # Check each field manually
            score_breakdown = 0
            
            # Title matching
            if grant.get('title'):
                title_lower = grant['title'].lower()
                print(f"   Title: '{title_lower}'")
                
                if query_lower in title_lower:
                    print(f"   ❌ Full query '{query_lower}' found in title!")
                    score_breakdown += 20.0
                
                for word in query_words:
                    if len(word) > 3 and word in title_lower:
                        print(f"   ❌ Word '{word}' found in title!")
                        score_breakdown += 10.0
            
            # Keywords matching  
            if grant.get('keywords'):
                keywords = [k.strip().lower() for k in grant['keywords'].split(',')]
                print(f"   Keywords: {keywords}")
                
                for keyword in keywords:
                    if keyword in query_lower or query_lower in keyword:
                        print(f"   ❌ Keyword '{keyword}' matches query!")
                        score_breakdown += 8.0
                    
                    for word in query_words:
                        if len(word) > 3 and word in keyword:
                            print(f"   ❌ Word '{word}' found in keyword '{keyword}'!")
                            score_breakdown += 4.0
            
            # Description matching
            if grant.get('description'):
                desc_lower = grant['description'].lower()
                print(f"   Description: '{desc_lower[:100]}...'")
                
                if query_lower in desc_lower:
                    print(f"   ❌ Full query '{query_lower}' found in description!")
                    score_breakdown += 6.0
                
                for word in query_words:
                    if len(word) > 3 and word in desc_lower:
                        print(f"   ❌ Word '{word}' found in description!")
                        score_breakdown += 2.0
            
            # Company name matching
            if grant.get('company_name'):
                company_name = grant['company_name'].lower()
                print(f"   Company: '{company_name}'")
                
                if query_lower in company_name:
                    print(f"   ❌ Full query '{query_lower}' found in company name!")
                    score_breakdown += 12.0
                
                for word in query_words:
                    if len(word) > 3 and word in company_name:
                        print(f"   ❌ Word '{word}' found in company name!")
                        score_breakdown += 6.0
            
            print(f"   Manual score calculation: {score_breakdown}")
            print(f"   Function returned: {keyword_score}")
            
            # Check agency bonus
            biotools_agencies = ['nih', 'nsf', 'sbir', 'cdc', 'darpa', 'nist', 'hhs']
            if grant.get('agency'):
                agency_lower = grant['agency'].lower()
                print(f"   Agency: '{agency_lower}'")
                for bio_agency in biotools_agencies:
                    if bio_agency in agency_lower:
                        print(f"   ❌ Agency bonus for '{bio_agency}'!")
                        break
        
        if semantic_score > 0:
            print(f"❌ Semantic score should be 0! Investigating...")
            # The semantic score should be 0 for non-biotools queries
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_individual_scoring()