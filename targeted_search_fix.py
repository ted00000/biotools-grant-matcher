#!/usr/bin/env python3
"""
Targeted Search Fix - Address the specific issues found in debug
"""

import sqlite3
import os
import sys
import json

def fix_data_type_inference():
    """Fix the data type inference to work with actual schema"""
    print("🔧 FIXING DATA TYPE INFERENCE")
    print("-" * 40)
    
    conn = sqlite3.connect("data/grants.db")
    cursor = conn.cursor()
    
    # Check current distribution
    cursor.execute("SELECT grant_type, COUNT(*) FROM grants GROUP BY grant_type")
    current_dist = cursor.fetchall()
    print("Current distribution:")
    for gtype, count in current_dist:
        print(f"   {gtype}: {count}")
    
    # Create company records from SBIR award data
    # Companies are the recipients of awards - we can extract them
    print("\n🏢 Creating company records from award recipients...")
    
    # Get unique companies from awards
    cursor.execute("""
        SELECT DISTINCT 
            company_name,
            company_city,
            company_state,
            company_uei,
            COUNT(*) as award_count,
            SUM(award_amount) as total_funding,
            GROUP_CONCAT(DISTINCT agency) as agencies,
            GROUP_CONCAT(title, ' | ') as project_descriptions
        FROM grants 
        WHERE company_name IS NOT NULL AND company_name != ''
        GROUP BY company_name, company_city, company_state
        HAVING COUNT(*) >= 1
        ORDER BY award_count DESC
        LIMIT 100
    """)
    
    companies = cursor.fetchall()
    print(f"Found {len(companies)} unique companies in award data")
    
    if companies:
        # Insert company records
        company_records_added = 0
        for company_data in companies:
            company_name, city, state, uei, award_count, total_funding, agencies, descriptions = company_data
            
            # Create a company profile record
            funding_opp_number = f"COMPANY-{uei or company_name.replace(' ', '-')[:20]}"
            title = f"{company_name} - Biotools Company Profile"
            description = f"Company with {award_count} SBIR awards totaling ${total_funding:,} from {agencies}. Recent projects: {descriptions[:500]}..."
            keywords = "biotools company, SBIR recipient, medical device, biotechnology"
            
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO grants (
                        funding_opportunity_number, title, agency, description, keywords,
                        company_name, company_city, company_state, company_uei,
                        award_amount, grant_type, data_source, biotools_category,
                        number_employees, relevance_score, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'company', 'SBIR', 'biotools', ?, 5.0, datetime('now'))
                """, (
                    funding_opp_number, title, agencies.split(',')[0] if agencies else 'HHS', 
                    description, keywords, company_name, city, state, uei,
                    total_funding, award_count * 10  # Estimate employees based on award count
                ))
                
                if cursor.rowcount > 0:
                    company_records_added += 1
                    
            except sqlite3.Error as e:
                print(f"   Error adding {company_name}: {e}")
        
        conn.commit()
        print(f"✅ Added {company_records_added} company records")
    
    # Fix solicitation records - mark records with solicitation indicators
    print("\n📋 Identifying solicitation records...")
    cursor.execute("""
        UPDATE grants 
        SET grant_type = 'solicitation'
        WHERE (solicitation_number IS NOT NULL AND solicitation_number != '')
           OR (current_status IN ('open', 'active'))
           OR (close_date IS NOT NULL AND close_date > date('now'))
    """)
    
    solicitations_fixed = cursor.rowcount
    conn.commit()
    print(f"✅ Updated {solicitations_fixed} solicitation records")
    
    # Show new distribution
    cursor.execute("SELECT grant_type, COUNT(*) FROM grants GROUP BY grant_type")
    new_dist = cursor.fetchall()
    print("\nNew distribution:")
    for gtype, count in new_dist:
        print(f"   {gtype}: {count}")
    
    conn.close()
    return True

def create_fixed_data_type_function():
    """Create a fixed version of the data type inference that works with actual schema"""
    
    fixed_function = '''
def _determine_data_type(self, record: Dict[str, Any]) -> str:
    """Fixed data type inference that works with actual schema"""
    # Check for explicit grant_type field first
    if record.get('grant_type'):
        return record['grant_type']
    
    # Check for solicitation indicators
    if (record.get('solicitation_number') or 
        record.get('current_status') in ['open', 'active'] or
        record.get('close_date')):
        return 'solicitation'
    
    # Check for company indicators (using actual schema columns)
    if (record.get('company_name') and 
        record.get('funding_opportunity_number', '').startswith('COMPANY-')):
        return 'company'
    
    # Default to award
    return 'award'
'''
    
    print("🔧 FIXED DATA TYPE FUNCTION")
    print("-" * 40)
    print("The data type inference function should be updated in main.py:")
    print(fixed_function)
    return fixed_function

def test_search_with_actual_data():
    """Test search with the actual data we have"""
    print("🧪 TESTING SEARCH WITH ACTUAL DATA")
    print("-" * 40)
    
    conn = sqlite3.connect("data/grants.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    test_queries = [
        "diagnostic",
        "biomarker", 
        "cell",
        "microfluidic",
        "genomic",
        "hot dog"  # Should return nothing or very few results
    ]
    
    for query in test_queries:
        print(f"\n🔍 Testing: '{query}'")
        
        # Simple relevance-based search
        cursor.execute("""
            SELECT title, agency, company_name, grant_type,
                   CASE 
                       WHEN LOWER(title) LIKE ? THEN 10
                       WHEN LOWER(description) LIKE ? THEN 7
                       WHEN LOWER(keywords) LIKE ? THEN 5
                       ELSE 1
                   END as relevance_score
            FROM grants 
            WHERE LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR LOWER(keywords) LIKE ?
            ORDER BY relevance_score DESC, title
            LIMIT 5
        """, [f'%{query.lower()}%'] * 6)
        
        results = cursor.fetchall()
        print(f"   Results: {len(results)}")
        
        for result in results:
            print(f"   - {result['title'][:60]}... (score: {result['relevance_score']}, type: {result['grant_type']})")
    
    conn.close()

def update_main_py_fixes():
    """Show the exact changes needed in main.py"""
    print("\n🔧 REQUIRED CHANGES FOR main.py")
    print("=" * 50)
    
    print("""
1. UPDATE _determine_data_type method (around line 130):

def _determine_data_type(self, record: Dict[str, Any]) -> str:
    \"\"\"Determine the data type of a record - FIXED VERSION\"\"\"
    # Check for explicit grant_type field first
    if record.get('grant_type'):
        return record['grant_type']
    
    # Check for solicitation indicators
    if (record.get('solicitation_number') or 
        record.get('current_status') in ['open', 'active'] or
        record.get('close_date')):
        return 'solicitation'
    
    # Check for company indicators (using actual schema columns)
    if (record.get('company_name') and 
        record.get('funding_opportunity_number', '').startswith('COMPANY-')):
        return 'company'
    
    # Default to award
    return 'award'

2. UPDATE _apply_data_type_filter method to handle 0 results:

def _apply_data_type_filter(self, grants: List[Dict[str, Any]], data_type: str) -> List[Dict[str, Any]]:
    \"\"\"Filter grants by data type\"\"\"
    if data_type == 'all':
        return grants
    
    filtered_grants = []
    for grant in grants:
        record_type = self._determine_data_type(grant)
        
        # Map plural forms to singular
        target_type = data_type.rstrip('s')  # Remove 's' from plurals
        
        if record_type == target_type:
            filtered_grants.append(grant)
    
    return filtered_grants

3. ADD better error handling in search_grants method:

# Add this after the scoring loop:
if not scored_grants:
    logger.info(f"Enhanced search found no results for '{query}' in {data_type}, trying simple search")
    simple_results = self._simple_search(query, limit, filters)
    if simple_results:
        return simple_results
    else:
        logger.warning(f"No results found for '{query}' in any search method")
        return []
""")

def main():
    """Run targeted fixes"""
    print("🚀 BIOTOOLS GRANT MATCHER - TARGETED SEARCH FIX")
    print("=" * 60)
    
    if not os.path.exists("data/grants.db"):
        print("❌ Database not found!")
        return
    
    try:
        # Fix the database first
        fix_data_type_inference()
        
        # Test search functionality
        test_search_with_actual_data()
        
        # Show required code changes
        update_main_py_fixes()
        
        print(f"\n🎯 NEXT STEPS")
        print("=" * 60)
        print("1. Database has been updated with company records")
        print("2. Update main.py with the code changes shown above")
        print("3. Restart the web server: python main.py")
        print("4. Test searches for 'diagnostic' vs 'hot dog' - should be different now")
        
    except Exception as e:
        print(f"❌ Fix failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()