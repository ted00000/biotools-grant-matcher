#!/usr/bin/env python3
"""
Company Search Fix Script - Remove artificial company records and use award-based approach
"""

import sqlite3
import os

def fix_company_approach():
    """Remove artificial company records and rely on award-based company search"""
    print("🔧 FIXING COMPANY SEARCH APPROACH")
    print("-" * 40)
    
    if not os.path.exists("data/grants.db"):
        print("❌ Database not found!")
        return
    
    conn = sqlite3.connect("data/grants.db")
    cursor = conn.cursor()
    
    # Remove any artificial company records we might have created
    cursor.execute("DELETE FROM grants WHERE funding_opportunity_number LIKE 'COMPANY-%'")
    deleted_company_records = cursor.rowcount
    
    if deleted_company_records > 0:
        print(f"✅ Removed {deleted_company_records} artificial company records")
    
    # Ensure all SBIR awards are marked as awards (not companies)
    cursor.execute("UPDATE grants SET grant_type = 'award' WHERE data_source = 'SBIR'")
    updated_awards = cursor.rowcount
    
    if updated_awards > 0:
        print(f"✅ Updated {updated_awards} SBIR records to grant_type='award'")
    
    conn.commit()
    
    # Check how many awards have company data
    cursor.execute("SELECT COUNT(*) FROM grants WHERE company_name IS NOT NULL AND company_name != ''")
    awards_with_companies = cursor.fetchone()[0]
    
    print(f"📊 Awards with company data: {awards_with_companies}")
    
    # Show some sample companies
    cursor.execute("""
        SELECT DISTINCT company_name, company_city, company_state, COUNT(*) as award_count
        FROM grants 
        WHERE company_name IS NOT NULL AND company_name != ''
        GROUP BY company_name, company_city, company_state
        ORDER BY award_count DESC
        LIMIT 10
    """)
    
    sample_companies = cursor.fetchall()
    print(f"\nSample companies with awards:")
    for company_name, city, state, count in sample_companies:
        location = f" ({city}, {state})" if city and state else ""
        print(f"   {company_name}{location}: {count} awards")
    
    # Test the search approach
    print(f"\n🧪 Testing company search for 'single cell'...")
    
    cursor.execute("""
        SELECT company_name, title, award_amount
        FROM grants 
        WHERE company_name IS NOT NULL 
        AND (LOWER(title) LIKE '%single cell%' OR LOWER(description) LIKE '%single cell%')
        LIMIT 5
    """)
    
    test_results = cursor.fetchall()
    print(f"Found {len(test_results)} companies with 'single cell' projects:")
    for company, title, amount in test_results:
        print(f"   {company}: {title[:60]}... (${amount:,})")
    
    conn.close()
    
    print(f"\n✅ Company search approach fixed!")
    print("Now when users search 'single cell' with Companies filter,")
    print("they'll see companies that won awards for single cell research.")

def main():
    fix_company_approach()

if __name__ == "__main__":
    main()