#!/usr/bin/env python3
"""
Fix Database Constraints - Remove UNIQUE constraint causing data loss
"""

import sqlite3
import os
from datetime import datetime

def fix_database_constraints(db_path="data/grants.db"):
    """Remove problematic UNIQUE constraint and rebuild table properly"""
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return False
    
    # Backup original database
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        print("🔧 Fixing database constraints...")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current data
        cursor.execute("SELECT COUNT(*) FROM grants")
        original_count = cursor.fetchone()[0]
        print(f"📊 Current database has {original_count} grants")
        
        # Create backup
        backup_conn = sqlite3.connect(backup_path)
        conn.backup(backup_conn)
        backup_conn.close()
        print(f"💾 Backup created: {backup_path}")
        
        # Create new table without UNIQUE constraint
        cursor.execute('''
            CREATE TABLE grants_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                abstract TEXT,
                agency TEXT,
                program TEXT,
                award_number TEXT,  -- REMOVED UNIQUE CONSTRAINT
                firm TEXT,
                principal_investigator TEXT,
                amount INTEGER,
                award_date TEXT,
                end_date TEXT,
                phase TEXT,
                keywords TEXT,
                source TEXT DEFAULT 'SBIR',
                grant_type TEXT DEFAULT 'award',
                relevance_score REAL DEFAULT 0.0,
                confidence_score REAL DEFAULT 0.0,
                biotools_category TEXT,
                compound_keyword_matches TEXT,
                agency_alignment_score REAL DEFAULT 0.0,
                url TEXT,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Copy existing data to new table
        cursor.execute('''
            INSERT INTO grants_new 
            SELECT * FROM grants
        ''')
        
        # Drop old table and rename new one
        cursor.execute('DROP TABLE grants')
        cursor.execute('ALTER TABLE grants_new RENAME TO grants')
        
        # Recreate useful indexes (without unique constraint)
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_grants_title ON grants(title)",
            "CREATE INDEX IF NOT EXISTS idx_grants_agency ON grants(agency)",
            "CREATE INDEX IF NOT EXISTS idx_grants_relevance ON grants(relevance_score)",
            "CREATE INDEX IF NOT EXISTS idx_grants_biotools_category ON grants(biotools_category)",
            "CREATE INDEX IF NOT EXISTS idx_grants_confidence ON grants(confidence_score)",
            "CREATE INDEX IF NOT EXISTS idx_grants_award_number ON grants(award_number)"  # Non-unique index
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        # Verify the fix
        cursor.execute("SELECT COUNT(*) FROM grants")
        final_count = cursor.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        print(f"✅ Database constraints fixed!")
        print(f"📊 Final count: {final_count} grants")
        print(f"🔄 Ready to re-run scraper without data loss")
        
        return True
        
    except Exception as e:
        print(f"❌ Error fixing database: {e}")
        return False

def verify_fix(db_path="data/grants.db"):
    """Verify the constraint fix worked"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check schema
        cursor.execute("PRAGMA table_info(grants)")
        columns = cursor.fetchall()
        
        print("\n📋 Updated Database Schema:")
        for col in columns:
            name, type_name, notnull, default, pk = col[1], col[2], col[3], col[4], col[5]
            unique_indicator = ""
            print(f"  {name} {type_name} {'NOT NULL' if notnull else ''} {unique_indicator}")
        
        # Check for duplicate award_numbers to confirm we can now handle them
        cursor.execute("""
            SELECT award_number, COUNT(*) as count 
            FROM grants 
            WHERE award_number IS NOT NULL AND award_number != ''
            GROUP BY award_number 
            HAVING COUNT(*) > 1
            LIMIT 5
        """)
        
        duplicates = cursor.fetchall()
        if duplicates:
            print(f"\n🔍 Found {len(duplicates)} duplicate award numbers (this is now OK):")
            for award_num, count in duplicates:
                print(f"  {award_num}: {count} occurrences")
        else:
            print("\n✅ No duplicate award numbers found")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error verifying fix: {e}")
        return False

if __name__ == "__main__":
    print("🔧 DATABASE CONSTRAINT FIX")
    print("=" * 40)
    
    # Fix the constraints
    if fix_database_constraints():
        print("\n" + "=" * 40)
        verify_fix()
        
        print("\n🎯 NEXT STEPS:")
        print("1. Run: python3 app/scraper.py recent 6")
        print("2. Check results: python3 -c \"import sqlite3; conn=sqlite3.connect('data/grants.db'); print(f'Total grants: {conn.execute(\"SELECT COUNT(*) FROM grants\").fetchone()[0]}'); conn.close()\"")
        print("3. Start the server: python3 main.py")
    else:
        print("\n❌ Fix failed. Check the error messages above.")
