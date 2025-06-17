#!/usr/bin/env python3
"""
Clear Database Script - Reset for fresh data collection
This script safely clears existing grant data and prepares for a fresh scrape
"""

import sqlite3
import os
import shutil
from datetime import datetime
import sys

DATABASE_PATH = "data/grants.db"
BACKUP_DIR = "backups"

def create_backup():
    """Create a backup of the existing database before clearing"""
    if not os.path.exists(DATABASE_PATH):
        print("📝 No existing database found - nothing to backup")
        return None
    
    # Create backup directory
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    # Create backup filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{BACKUP_DIR}/grants_backup_{timestamp}.db"
    
    try:
        shutil.copy2(DATABASE_PATH, backup_path)
        print(f"✅ Database backed up to: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return None

def get_current_stats():
    """Get current database statistics before clearing"""
    if not os.path.exists(DATABASE_PATH):
        return None
    
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM grants")
        total = cursor.fetchone()[0]
        
        # Get by agency
        cursor.execute("SELECT agency, COUNT(*) FROM grants GROUP BY agency ORDER BY COUNT(*) DESC LIMIT 5")
        by_agency = cursor.fetchall()
        
        # Get by data source if column exists
        try:
            cursor.execute("SELECT data_source, COUNT(*) FROM grants WHERE data_source IS NOT NULL GROUP BY data_source")
            by_source = cursor.fetchall()
        except sqlite3.OperationalError:
            by_source = []
        
        # Get by grant type if column exists
        try:
            cursor.execute("SELECT grant_type, COUNT(*) FROM grants WHERE grant_type IS NOT NULL GROUP BY grant_type")
            by_type = cursor.fetchall()
        except sqlite3.OperationalError:
            by_type = []
        
        conn.close()
        
        return {
            'total': total,
            'by_agency': by_agency,
            'by_source': by_source,
            'by_type': by_type
        }
        
    except Exception as e:
        print(f"⚠️  Could not get current stats: {e}")
        return None

def clear_database():
    """Clear all grant data but preserve table structure"""
    if not os.path.exists(DATABASE_PATH):
        print("📝 No database exists - will be created fresh")
        return True
    
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Get list of all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"🗑️  Clearing data from {len(tables)} tables...")
        
        # Clear data from each table
        for table in tables:
            if table != 'sqlite_sequence':  # Don't clear SQLite's internal table
                cursor.execute(f"DELETE FROM {table}")
                print(f"   ✅ Cleared {table}")
        
        # Reset auto-increment counters
        cursor.execute("DELETE FROM sqlite_sequence")
        
        conn.commit()
        conn.close()
        
        print("✅ Database cleared successfully!")
        print("📋 Table structure preserved for fresh data")
        return True
        
    except Exception as e:
        print(f"❌ Failed to clear database: {e}")
        return False

def show_scraper_commands():
    """Show available scraper commands"""
    print("\n" + "="*60)
    print("🚀 SCRAPER COMMANDS")
    print("="*60)
    
    print("\n📊 Test API connectivity first:")
    print("   python app/scraper.py test")
    
    print("\n🔄 Quick scraping options:")
    print("   python app/scraper.py recent          # Recent awards (last 6 months)")
    print("   python app/scraper.py solicitations   # Open solicitations only")
    
    print("\n🏆 Full data collection:")
    print("   python app/scraper.py full            # Full scrape from 2020")
    print("   python app/scraper.py full 2022       # Full scrape from 2022")
    
    print("\n📈 Monitor progress:")
    print("   python app/scraper.py stats           # Show database statistics")
    
    print("\n💡 RECOMMENDED SEQUENCE:")
    print("   1. python app/scraper.py test         # Test APIs work")
    print("   2. python app/scraper.py full 2022    # Start with recent data") 
    print("   3. python app/scraper.py stats        # Check results")
    print("   4. python app/scraper.py solicitations # Add open opportunities")

def main():
    """Main execution function"""
    print("🧹 BioTools Grant Database Reset Tool")
    print("="*50)
    
    # Get current stats
    current_stats = get_current_stats()
    if current_stats:
        print(f"\n📊 CURRENT DATABASE:")
        print(f"   Total grants: {current_stats['total']}")
        if current_stats['by_agency']:
            print(f"   Top agencies:")
            for agency, count in current_stats['by_agency']:
                print(f"     {agency}: {count}")
        if current_stats['by_source']:
            print(f"   By source:")
            for source, count in current_stats['by_source']:
                print(f"     {source}: {count}")
        if current_stats['by_type']:
            print(f"   By type:")
            for gtype, count in current_stats['by_type']:
                print(f"     {gtype}: {count}")
    
    # Confirm clearing
    if current_stats and current_stats['total'] > 0:
        print(f"\n⚠️  This will DELETE {current_stats['total']} grants from the database!")
        print("💾 A backup will be created automatically")
        
        if len(sys.argv) > 1 and sys.argv[1] == '--force':
            confirm = 'y'
        else:
            confirm = input("\n🤔 Continue with database reset? (y/N): ").lower().strip()
        
        if confirm != 'y':
            print("❌ Database reset cancelled")
            return
    
    # Create backup
    backup_path = create_backup()
    if current_stats and current_stats['total'] > 0 and not backup_path:
        print("❌ Cannot proceed without backup")
        return
    
    # Clear database
    if clear_database():
        print("\n🎉 Database successfully reset!")
        
        if backup_path:
            print(f"💾 Your data is safely backed up at: {backup_path}")
        
        print("\n📁 Database file location: data/grants.db")
        print("🔍 Logs will be written to: logs/scraper.log")
        
        # Show scraper commands
        show_scraper_commands()
        
        print(f"\n✨ Ready for fresh data collection!")
        
    else:
        print("❌ Database reset failed")
        if backup_path:
            print(f"💾 Your original data is still safe at: {backup_path}")

if __name__ == "__main__":
    main()