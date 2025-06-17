#!/usr/bin/env python3
"""
Database Fix Script - Add missing tables for search functionality
"""

import sqlite3
import os
from datetime import datetime

def fix_database_tables(db_path="data/grants.db"):
    """Add missing tables that are causing errors"""
    print("🔧 Fixing database tables...")
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Create search_history table
    print("  Adding search_history table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            results_count INTEGER DEFAULT 0,
            user_session TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT
        )
    ''')
    
    # 2. Create grant_feedback table
    print("  Adding grant_feedback table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grant_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            grant_id INTEGER NOT NULL,
            search_query TEXT,
            feedback_type TEXT CHECK (feedback_type IN ('helpful', 'not_helpful', 'applied', 'bookmarked')),
            user_session TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (grant_id) REFERENCES grants(id) ON DELETE CASCADE
        )
    ''')
    
    # 3. Add missing indexes for performance
    print("  Adding performance indexes...")
    indexes = [
        ("idx_grants_title_fts", "CREATE INDEX IF NOT EXISTS idx_grants_title_fts ON grants(title)"),
        ("idx_grants_description_fts", "CREATE INDEX IF NOT EXISTS idx_grants_description_fts ON grants(description)"),
        ("idx_grants_keywords", "CREATE INDEX IF NOT EXISTS idx_grants_keywords ON grants(keywords)"),
        ("idx_grants_agency", "CREATE INDEX IF NOT EXISTS idx_grants_agency ON grants(agency)"),
        ("idx_grants_relevance", "CREATE INDEX IF NOT EXISTS idx_grants_relevance ON grants(relevance_score)"),
        ("idx_search_timestamp", "CREATE INDEX IF NOT EXISTS idx_search_timestamp ON search_history(timestamp)"),
        ("idx_feedback_grant", "CREATE INDEX IF NOT EXISTS idx_feedback_grant ON grant_feedback(grant_id)")
    ]
    
    for index_name, sql in indexes:
        try:
            cursor.execute(sql)
            print(f"    ✅ {index_name}")
        except sqlite3.Error as e:
            print(f"    ⚠️  {index_name}: {e}")
    
    # 4. Check current table structure
    print("\n📊 Current database status:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"  Tables: {tables}")
    
    cursor.execute("SELECT COUNT(*) FROM grants")
    grants_count = cursor.fetchone()[0]
    print(f"  Total grants: {grants_count}")
    
    # 5. Test search functionality
    print("\n🔍 Testing search functionality...")
    test_queries = ['bio', 'genomics', 'single cell', 'diagnostic']
    
    for query in test_queries:
        # Simple LIKE search
        cursor.execute("""
            SELECT COUNT(*) FROM grants 
            WHERE title LIKE ? OR description LIKE ? OR keywords LIKE ?
        """, (f'%{query}%', f'%{query}%', f'%{query}%'))
        
        count = cursor.fetchone()[0]
        print(f"  '{query}': {count} matches")
    
    conn.commit()
    conn.close()
    
    print("\n✅ Database fix completed!")

def test_search_algorithm(db_path="data/grants.db"):
    """Test why searches are returning 0 results"""
    print("\n🧪 Testing Search Algorithm...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check what's actually in the database
    cursor.execute("SELECT title, keywords, description FROM grants LIMIT 5")
    samples = cursor.fetchall()
    
    print("📋 Sample grant data:")
    for i, (title, keywords, desc) in enumerate(samples, 1):
        print(f"  {i}. Title: {title[:50]}...")
        print(f"     Keywords: {keywords[:50] if keywords else 'None'}...")
        print(f"     Description: {desc[:50] if desc else 'None'}...")
        print()
    
    # Test simple searches
    test_terms = ['bio', 'genomics', 'cell', 'diagnostic', 'medical']
    
    print("🔍 Search test results:")
    for term in test_terms:
        # Test different search methods
        
        # Method 1: Simple LIKE
        cursor.execute("""
            SELECT COUNT(*) FROM grants 
            WHERE LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR LOWER(keywords) LIKE ?
        """, (f'%{term.lower()}%', f'%{term.lower()}%', f'%{term.lower()}%'))
        like_count = cursor.fetchone()[0]
        
        # Method 2: Full text search in title only
        cursor.execute("SELECT COUNT(*) FROM grants WHERE LOWER(title) LIKE ?", (f'%{term.lower()}%',))
        title_count = cursor.fetchone()[0]
        
        # Method 3: Keywords only
        cursor.execute("SELECT COUNT(*) FROM grants WHERE LOWER(keywords) LIKE ?", (f'%{term.lower()}%',))
        keyword_count = cursor.fetchone()[0]
        
        print(f"  '{term}': LIKE={like_count}, Title={title_count}, Keywords={keyword_count}")
    
    conn.close()

if __name__ == "__main__":
    fix_database_tables()
    test_search_algorithm()