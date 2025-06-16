#!/usr/bin/env python3
"""
Database Migration Script - Upgrade to Enhanced Schema
This script safely migrates your existing grants database to the enhanced schema
"""

import sqlite3
import os
from datetime import datetime

DATABASE_PATH = "data/grants.db"
BACKUP_PATH = f"data/grants_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

def backup_database():
    """Create a backup of the existing database"""
    if os.path.exists(DATABASE_PATH):
        print(f"📦 Creating backup: {BACKUP_PATH}")
        import shutil
        shutil.copy2(DATABASE_PATH, BACKUP_PATH)
        print(f"✅ Backup created successfully")
        return True
    else:
        print(f"⚠️  No existing database found at {DATABASE_PATH}")
        return False

def check_existing_structure():
    """Check what tables already exist"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    existing_tables = [row[0] for row in cursor.fetchall()]
    
    print(f"📊 Existing tables: {existing_tables}")
    
    if 'grants' in existing_tables:
        cursor.execute("PRAGMA table_info(grants);")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"📋 Existing grants columns: {columns}")
    
    conn.close()
    return existing_tables

def migrate_grants_table():
    """Migrate the grants table to enhanced schema"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print("🔄 Migrating grants table...")
    
    # Check if grants table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='grants';")
    grants_exists = cursor.fetchone()
    
    if grants_exists:
        # Get existing columns
        cursor.execute("PRAGMA table_info(grants);")
        existing_columns = {row[1]: row[2] for row in cursor.fetchall()}
        print(f"   Existing columns: {list(existing_columns.keys())}")
        
        # Add new columns if they don't exist
        new_columns = {
            'status': 'TEXT DEFAULT "active" CHECK (status IN ("active", "closed", "upcoming"))',
            'location_restrictions': 'TEXT',
            'application_deadline': 'DATE',
            'award_start_date': 'DATE',
            'award_duration_months': 'INTEGER',
            'last_scraped_at': 'TEXT DEFAULT CURRENT_TIMESTAMP'
        }
        
        for column_name, column_def in new_columns.items():
            if column_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE grants ADD COLUMN {column_name} {column_def}")
                    print(f"   ✅ Added column: {column_name}")
                except sqlite3.Error as e:
                    print(f"   ⚠️  Could not add {column_name}: {e}")
    else:
        # Create new grants table with full schema
        print("   Creating new grants table...")
        cursor.execute('''
            CREATE TABLE grants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                funding_opportunity_number TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                agency TEXT NOT NULL,
                deadline DATE,
                amount_min INTEGER DEFAULT 0,
                amount_max INTEGER DEFAULT 0,
                description TEXT,
                keywords TEXT,
                eligibility TEXT,
                url TEXT,
                status TEXT DEFAULT 'active' CHECK (status IN ('active', 'closed', 'upcoming')),
                location_restrictions TEXT,
                application_deadline DATE,
                award_start_date DATE,
                award_duration_months INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_scraped_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("   ✅ Created new grants table")
    
    conn.commit()
    conn.close()

def create_fts_table():
    """Create full-text search virtual table"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print("🔍 Setting up full-text search...")
    
    try:
        # Create FTS virtual table
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS grants_fts USING fts5(
                title,
                description,
                keywords,
                content='grants',
                content_rowid='id'
            )
        ''')
        print("   ✅ Created FTS virtual table")
        
        # Populate FTS table with existing data
        cursor.execute('''
            INSERT INTO grants_fts(rowid, title, description, keywords)
            SELECT id, title, description, keywords FROM grants
        ''')
        print("   ✅ Populated FTS table with existing data")
        
        # Create triggers to keep FTS in sync
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS grants_fts_insert AFTER INSERT ON grants BEGIN
                INSERT INTO grants_fts(rowid, title, description, keywords) 
                VALUES (new.id, new.title, new.description, new.keywords);
            END
        ''')
        
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS grants_fts_delete AFTER DELETE ON grants BEGIN
                DELETE FROM grants_fts WHERE rowid = old.id;
            END
        ''')
        
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS grants_fts_update AFTER UPDATE ON grants BEGIN
                DELETE FROM grants_fts WHERE rowid = old.id;
                INSERT INTO grants_fts(rowid, title, description, keywords) 
                VALUES (new.id, new.title, new.description, new.keywords);
            END
        ''')
        print("   ✅ Created FTS sync triggers")
        
    except sqlite3.Error as e:
        print(f"   ⚠️  FTS setup failed: {e}")
    
    conn.commit()
    conn.close()

def create_additional_tables():
    """Create the new additional tables"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print("📚 Creating additional tables...")
    
    # Grant categories table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grant_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            parent_id INTEGER,
            description TEXT,
            FOREIGN KEY (parent_id) REFERENCES grant_categories(id)
        )
    ''')
    print("   ✅ Created grant_categories table")
    
    # Grant category mapping table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS grant_category_mapping (
            grant_id INTEGER,
            category_id INTEGER,
            PRIMARY KEY (grant_id, category_id),
            FOREIGN KEY (grant_id) REFERENCES grants(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES grant_categories(id) ON DELETE CASCADE
        )
    ''')
    print("   ✅ Created grant_category_mapping table")
    
    # Search history table
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
    print("   ✅ Created search_history table")
    
    # Grant feedback table
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
    print("   ✅ Created grant_feedback table")
    
    # Scraping sources table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scraping_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT UNIQUE NOT NULL,
            base_url TEXT,
            last_scraped_at TEXT,
            grants_found INTEGER DEFAULT 0,
            scraping_enabled BOOLEAN DEFAULT 1,
            api_key_required BOOLEAN DEFAULT 0,
            rate_limit_per_hour INTEGER DEFAULT 100
        )
    ''')
    print("   ✅ Created scraping_sources table")
    
    conn.commit()
    conn.close()

def create_indexes():
    """Create performance indexes"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print("⚡ Creating performance indexes...")
    
    indexes = [
        ("idx_grants_agency", "CREATE INDEX IF NOT EXISTS idx_grants_agency ON grants(agency)"),
        ("idx_grants_deadline", "CREATE INDEX IF NOT EXISTS idx_grants_deadline ON grants(deadline)"),
        ("idx_grants_amount", "CREATE INDEX IF NOT EXISTS idx_grants_amount ON grants(amount_max)"),
        ("idx_grants_updated", "CREATE INDEX IF NOT EXISTS idx_grants_updated ON grants(updated_at)"),
        ("idx_grants_status", "CREATE INDEX IF NOT EXISTS idx_grants_status ON grants(status)"),
        ("idx_feedback_grant", "CREATE INDEX IF NOT EXISTS idx_feedback_grant ON grant_feedback(grant_id)"),
        ("idx_search_timestamp", "CREATE INDEX IF NOT EXISTS idx_search_timestamp ON search_history(timestamp)")
    ]
    
    for index_name, sql in indexes:
        try:
            cursor.execute(sql)
            print(f"   ✅ Created index: {index_name}")
        except sqlite3.Error as e:
            print(f"   ⚠️  Could not create {index_name}: {e}")
    
    conn.commit()
    conn.close()

def insert_default_data():
    """Insert default categories and scraping sources"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print("📝 Inserting default data...")
    
    # Default categories
    categories = [
        ('Biomedical Devices', None, 'Medical devices and diagnostic equipment'),
        ('Lab Automation', None, 'Laboratory automation and robotics'),
        ('Diagnostics', None, 'Diagnostic tests and biomarkers'),
        ('Imaging Technology', None, 'Medical and scientific imaging systems'),
        ('Microfluidics', None, 'Microfluidic devices and lab-on-chip systems'),
        ('Genomics', None, 'Genomic analysis tools and sequencing'),
        ('AI/ML in Healthcare', None, 'Artificial intelligence applications in medicine'),
        ('Point-of-Care Testing', None, 'Portable and bedside diagnostic devices'),
        ('Biosensors', None, 'Biological sensing technologies'),
        ('Drug Discovery Tools', None, 'Tools and platforms for pharmaceutical research')
    ]
    
    for name, parent_id, description in categories:
        cursor.execute('''
            INSERT OR IGNORE INTO grant_categories (name, parent_id, description)
            VALUES (?, ?, ?)
        ''', (name, parent_id, description))
    
    print("   ✅ Inserted default categories")
    
    # Default scraping sources
    sources = [
        ('NSF', 'https://api.nsf.gov/services/v1/awards.json', 1),
        ('NIH', 'https://api.reporter.nih.gov/', 1),
        ('SBIR', 'https://www.sbir.gov/', 1),
        ('Grants.gov', 'https://www.grants.gov/', 1),
        ('CDC', 'https://www.cdc.gov/funding/', 1),
        ('DARPA', 'https://www.darpa.mil/', 1),
        ('DOE', 'https://www.energy.gov/', 1)
    ]
    
    for source_name, base_url, enabled in sources:
        cursor.execute('''
            INSERT OR IGNORE INTO scraping_sources (source_name, base_url, scraping_enabled)
            VALUES (?, ?, ?)
        ''', (source_name, base_url, enabled))
    
    print("   ✅ Inserted default scraping sources")
    
    conn.commit()
    conn.close()

def verify_migration():
    """Verify the migration was successful"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    print("\n🔍 Verifying migration...")
    
    # Check all tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    expected_tables = [
        'grants', 'grants_fts', 'grant_categories', 'grant_category_mapping',
        'search_history', 'grant_feedback', 'scraping_sources'
    ]
    
    for table in expected_tables:
        if table in tables:
            print(f"   ✅ {table} table exists")
        else:
            print(f"   ❌ {table} table missing")
    
    # Check grants count
    cursor.execute("SELECT COUNT(*) FROM grants")
    grants_count = cursor.fetchone()[0]
    print(f"   📊 Total grants: {grants_count}")
    
    # Check categories count
    cursor.execute("SELECT COUNT(*) FROM grant_categories")
    categories_count = cursor.fetchone()[0]
    print(f"   📂 Categories: {categories_count}")
    
    conn.close()

def main():
    """Run the complete database migration"""
    print("🚀 Starting Database Migration to Enhanced Schema")
    print("=" * 60)
    
    # Step 1: Backup existing database
    backup_database()
    
    # Step 2: Check existing structure
    existing_tables = check_existing_structure()
    
    # Step 3: Migrate grants table
    migrate_grants_table()
    
    # Step 4: Create full-text search
    create_fts_table()
    
    # Step 5: Create additional tables
    create_additional_tables()
    
    # Step 6: Create indexes
    create_indexes()
    
    # Step 7: Insert default data
    insert_default_data()
    
    # Step 8: Verify migration
    verify_migration()
    
    print("\n🎉 Database migration completed successfully!")
    print(f"💾 Backup saved as: {BACKUP_PATH}")
    print("\nYour enhanced search algorithm can now take advantage of:")
    print("  • Full-text search capabilities")
    print("  • Performance indexes")
    print("  • User feedback tracking")
    print("  • Search history analytics")
    print("  • Grant categorization")

if __name__ == "__main__":
    main()