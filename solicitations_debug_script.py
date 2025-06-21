#!/usr/bin/env python3
"""
Debug Solicitations - Find why we show 0 solicitations
"""

import sqlite3
import os

def debug_solicitations():
    """Debug why solicitations count is 0"""
    print("🔍 DEBUGGING SOLICITATIONS COUNT")
    print("=" * 50)
    
    if not os.path.exists("data/grants.db"):
        print("❌ Database not found!")
        return
    
    conn = sqlite3.connect("data/grants.db")
    cursor = conn.cursor()
    
    # Check total records
    cursor.execute("SELECT COUNT(*) FROM grants")
    total = cursor.fetchone()[0]
    print(f"📊 Total records: {total}")
    
    # Check grant_type distribution
    cursor.execute("SELECT grant_type, COUNT(*) FROM grants GROUP BY grant_type")
    grant_types = cursor.fetchall()
    print(f"\n🏷️ Grant type distribution:")
    for gtype, count in grant_types:
        print(f"   {gtype or 'NULL'}: {count}")
    
    # Check for solicitation indicators
    print(f"\n🔍 Checking solicitation indicators:")
    
    # Check solicitation_number
    cursor.execute("SELECT COUNT(*) FROM grants WHERE solicitation_number IS NOT NULL AND solicitation_number != ''")
    sol_num_count = cursor.fetchone()[0]
    print(f"   Records with solicitation_number: {sol_num_count}")
    
    # Check current_status
    cursor.execute("SELECT current_status, COUNT(*) FROM grants WHERE current_status IS NOT NULL GROUP BY current_status")
    status_counts = cursor.fetchall()
    print(f"   Current status distribution:")
    for status, count in status_counts:
        print(f"     {status}: {count}")
    
    # Check close_date
    cursor.execute("SELECT COUNT(*) FROM grants WHERE close_date IS NOT NULL AND close_date != ''")
    close_date_count = cursor.fetchone()[0]
    print(f"   Records with close_date: {close_date_count}")
    
    # Check what the stats function is actually counting
    print(f"\n🧮 Testing stats function logic:")
    
    # This is what the stats function does
    cursor.execute("""
        SELECT COUNT(*) FROM grants 
        WHERE grant_type = 'solicitation'
        AND (close_date IS NULL OR close_date > date('now'))
    """)
    open_solicitations = cursor.fetchone()[0]
    print(f"   Open solicitations (stats logic): {open_solicitations}")
    
    # Check all solicitation records
    cursor.execute("SELECT COUNT(*) FROM grants WHERE grant_type = 'solicitation'")
    all_solicitations = cursor.fetchone()[0]
    print(f"   All grant_type='solicitation': {all_solicitations}")
    
    # Show sample solicitation records if any exist
    if all_solicitations > 0:
        cursor.execute("""
            SELECT title, solicitation_number, current_status, close_date 
            FROM grants 
            WHERE grant_type = 'solicitation' 
            LIMIT 5
        """)
        samples = cursor.fetchall()
        print(f"\n📋 Sample solicitation records:")
        for title, sol_num, status, close_date in samples:
            print(f"   - {title[:50]}...")
            print(f"     Solicitation: {sol_num}, Status: {status}, Close: {close_date}")
    
    # Check if we have records that SHOULD be solicitations but aren't marked
    cursor.execute("""
        SELECT COUNT(*) FROM grants 
        WHERE grant_type != 'solicitation'
        AND (solicitation_number IS NOT NULL OR current_status IN ('open', 'active'))
    """)
    potential_solicitations = cursor.fetchone()[0]
    print(f"\n🤔 Records that could be solicitations: {potential_solicitations}")
    
    if potential_solicitations > 0:
        cursor.execute("""
            SELECT title, grant_type, solicitation_number, current_status 
            FROM grants 
            WHERE grant_type != 'solicitation'
            AND (solicitation_number IS NOT NULL OR current_status IN ('open', 'active'))
            LIMIT 5
        """)
        samples = cursor.fetchall()
        print(f"   Sample potential solicitations:")
        for title, gtype, sol_num, status in samples:
            print(f"   - {title[:50]}... (type: {gtype})")
            print(f"     Solicitation: {sol_num}, Status: {status}")
    
    conn.close()

def fix_solicitation_classification():
    """Fix solicitation classification if needed"""
    print(f"\n🔧 FIXING SOLICITATION CLASSIFICATION")
    print("-" * 40)
    
    conn = sqlite3.connect("data/grants.db")
    cursor = conn.cursor()
    
    # Update records that should be solicitations
    cursor.execute("""
        UPDATE grants 
        SET grant_type = 'solicitation'
        WHERE grant_type != 'solicitation'
        AND (
            (solicitation_number IS NOT NULL AND solicitation_number != '') OR
            current_status IN ('open', 'active') OR
            (close_date IS NOT NULL AND close_date > date('now'))
        )
    """)
    
    updated_count = cursor.rowcount
    conn.commit()
    
    if updated_count > 0:
        print(f"✅ Updated {updated_count} records to grant_type='solicitation'")
        
        # Check new distribution
        cursor.execute("SELECT grant_type, COUNT(*) FROM grants GROUP BY grant_type")
        new_distribution = cursor.fetchall()
        print(f"New distribution:")
        for gtype, count in new_distribution:
            print(f"   {gtype}: {count}")
    else:
        print("ℹ️  No records needed solicitation classification update")
    
    conn.close()

def main():
    debug_solicitations()
    fix_solicitation_classification()

if __name__ == "__main__":
    main()