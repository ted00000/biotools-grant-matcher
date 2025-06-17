#!/usr/bin/env python3
"""
Scraper Helper Script - Easy database management and scraping
"""

import os
import sys
import subprocess
import sqlite3
from datetime import datetime

def check_database_status():
    """Check current database status"""
    db_path = "data/grants.db"
    
    print("📊 DATABASE STATUS")
    print("-" * 30)
    
    if not os.path.exists(db_path):
        print("❌ No database found")
        print("🚀 Ready for fresh scraping!")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if grants table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='grants';")
        if not cursor.fetchone():
            print("❌ No grants table found")
            conn.close()
            return False
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM grants")
        total = cursor.fetchone()[0]
        
        print(f"✅ Database exists with {total} grants")
        
        if total > 0:
            # Get some stats
            cursor.execute("SELECT agency, COUNT(*) FROM grants GROUP BY agency ORDER BY COUNT(*) DESC LIMIT 5")
            agencies = cursor.fetchall()
            
            print("📈 Top agencies:")
            for agency, count in agencies:
                print(f"   {agency or 'Unknown'}: {count}")
            
            # Check for recent data
            try:
                cursor.execute("SELECT COUNT(*) FROM grants WHERE updated_at > date('now', '-30 days')")
                recent = cursor.fetchone()[0]
                print(f"📅 Recent updates (30 days): {recent}")
            except:
                pass
        
        conn.close()
        return total > 0
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

def run_command(command):
    """Run a command and show output"""
    print(f"\n🚀 Running: {command}")
    print("-" * 50)
    
    try:
        # Change to project directory
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        
        # Run command
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        # Show output
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print("✅ Command completed successfully!")
        else:
            print(f"❌ Command failed with code {result.returncode}")
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ Failed to run command: {e}")
        return False

def show_menu():
    """Show interactive menu"""
    print("\n" + "="*60)
    print("🧬 BIOTOOLS GRANT MATCHER - DATABASE MANAGER")
    print("="*60)
    
    has_data = check_database_status()
    
    print("\n🔧 AVAILABLE ACTIONS:")
    print("1. 🧹 Clear database and start fresh")
    print("2. 🔍 Test API connectivity")
    print("3. 🚀 Quick scrape (recent data)")
    print("4. 📋 Get open solicitations")
    print("5. 🏆 Full scrape from 2022")
    print("6. 📊 Show database stats")
    print("7. 🖥️  Start web server")
    print("8. ❌ Exit")
    
    return input("\n🤔 Choose an action (1-8): ").strip()

def main():
    """Interactive main function"""
    while True:
        choice = show_menu()
        
        if choice == '1':
            # Clear database
            if run_command("python clear_database_script.py"):
                print("\n💡 Database cleared! Ready for fresh scraping.")
                input("Press Enter to continue...")
        
        elif choice == '2':
            # Test APIs
            run_command("python app/scraper.py test")
            input("Press Enter to continue...")
        
        elif choice == '3':
            # Quick scrape
            print("\n🔄 Running quick scrape (recent 6 months)...")
            run_command("python app/scraper.py recent")
            input("Press Enter to continue...")
        
        elif choice == '4':
            # Solicitations only
            print("\n📋 Fetching open solicitations...")
            run_command("python app/scraper.py solicitations")
            input("Press Enter to continue...")
        
        elif choice == '5':
            # Full scrape
            print("\n🏆 Running full scrape from 2022...")
            print("⚠️  This may take 10-30 minutes depending on API responses")
            confirm = input("Continue? (y/N): ").lower().strip()
            if confirm == 'y':
                run_command("python app/scraper.py full 2022")
            input("Press Enter to continue...")
        
        elif choice == '6':
            # Show stats
            run_command("python app/scraper.py stats")
            input("Press Enter to continue...")
        
        elif choice == '7':
            # Start web server
            print("\n🖥️  Starting web server...")
            print("💡 Access at: http://localhost:5000")
            print("💡 Press Ctrl+C to stop server")
            run_command("python main.py")
            input("Press Enter to continue...")
        
        elif choice == '8':
            print("👋 Goodbye!")
            break
        
        else:
            print("❌ Invalid choice. Please try again.")
            input("Press Enter to continue...")

if __name__ == "__main__":
    main()