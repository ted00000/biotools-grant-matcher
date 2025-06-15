#!/usr/bin/env python3
"""
Real NIH Grant Data Scraper - Fixed API Integration
Fetches actual NIH grants and adds them to existing sample data
"""

import requests
import sqlite3
from datetime import datetime
import time
import os

class RealNIHScraper:
    def __init__(self, db_path="data/grants.db"):
        self.db_path = db_path
        self.api_url = "https://api.reporter.nih.gov/v2/projects/search"
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.setup_database()
    
    def setup_database(self):
        """Create database tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS grants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                funding_opportunity_number TEXT UNIQUE,
                title TEXT NOT NULL,
                agency TEXT,
                deadline DATE,
                amount_min INTEGER,
                amount_max INTEGER,
                description TEXT,
                keywords TEXT,
                eligibility TEXT,
                url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def fetch_nih_grants_simple(self):
        """Fetch NIH grants with a simpler, more reliable API call"""
        print("🔍 Fetching real NIH data (simplified approach)...")
        
        # Much simpler payload that's more likely to work
        payload = {
            "criteria": {
                "fiscal_years": [2024, 2025],
                "activity_codes": ["R01", "R21", "R43", "R44"],  # Common grant types
                "agencies": ["NIH"]
            },
            "include_fields": [
                "ProjectTitle",
                "AbstractText",
                "ProjectNum",
                "Organization",
                "ProjectStartDate",
                "ProjectEndDate",
                "AwardAmount",
                "ActivityCode",
                "Agency"
            ],
            "offset": 0,
            "limit": 100,  # Start smaller
            "sort_field": "project_start_date",
            "sort_order": "desc"
        }
        
        try:
            print(f"Making API request to: {self.api_url}")
            response = requests.post(
                self.api_url, 
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                projects = data.get('results', [])
                print(f"✅ Successfully fetched {len(projects)} NIH projects")
                return self.process_nih_projects(projects)
            else:
                print(f"❌ API Error: {response.status_code}")
                print(f"Response: {response.text[:500]}")
                return []
                
        except requests.RequestException as e:
            print(f"❌ Network error: {e}")
            return []
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return []
    
    def process_nih_projects(self, projects):
        """Convert NIH API projects to our grant format"""
        grants = []
        
        biotools_keywords = [
            'biomarker', 'diagnostic', 'device', 'biosensor', 'microfluidic',
            'imaging', 'sequencing', 'automation', 'point-of-care', 'wearable',
            'artificial intelligence', 'machine learning', 'genomic', 'proteomic',
            'bioinformatics', 'lab-on-chip', 'molecular', 'assay', 'screening'
        ]
        
        for project in projects:
            title = project.get('project_title', '')
            abstract = project.get('abstract_text', '')
            
            # Only include projects that seem related to biotools
            if self.is_biotools_related(title + ' ' + abstract, biotools_keywords):
                
                # Extract keywords from abstract
                keywords = self.extract_keywords(abstract, biotools_keywords)
                
                grant = {
                    'funding_opportunity_number': project.get('project_num', ''),
                    'title': title,
                    'agency': 'NIH',
                    'description': abstract[:1000] if abstract else '',  # Truncate long abstracts
                    'amount_min': 0,
                    'amount_max': project.get('award_amount', 0) or 0,
                    'keywords': ', '.join(keywords),
                    'eligibility': project.get('organization', {}).get('org_name', ''),
                    'url': f"https://reporter.nih.gov/search/{project.get('project_num', '')}"
                }
                grants.append(grant)
        
        print(f"📊 Filtered to {len(grants)} biotools-related grants")
        return grants
    
    def is_biotools_related(self, text, keywords):
        """Check if project text contains biotools-related keywords"""
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in keywords)
    
    def extract_keywords(self, text, keyword_list):
        """Extract relevant keywords from project text"""
        if not text:
            return []
        
        text_lower = text.lower()
        found_keywords = []
        
        for keyword in keyword_list:
            if keyword in text_lower:
                found_keywords.append(keyword)
        
        return found_keywords[:8]  # Limit to 8 keywords
    
    def save_grants(self, grants):
        """Save grants to database (add to existing data)"""
        if not grants:
            print("⚠️ No grants to save")
            return 0
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        saved_count = 0
        duplicate_count = 0
        
        for grant in grants:
            try:
                # Try to insert, ignore if duplicate
                cursor.execute('''
                    INSERT OR IGNORE INTO grants 
                    (funding_opportunity_number, title, agency, description, 
                     amount_min, amount_max, keywords, eligibility, url, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    grant['funding_opportunity_number'],
                    grant['title'],
                    grant['agency'],
                    grant['description'],
                    grant['amount_min'],
                    grant['amount_max'],
                    grant['keywords'],
                    grant['eligibility'],
                    grant['url'],
                    datetime.now()
                ))
                
                if cursor.rowcount > 0:
                    saved_count += 1
                else:
                    duplicate_count += 1
                    
            except sqlite3.Error as e:
                print(f"Error saving grant {grant.get('title', 'Unknown')}: {e}")
        
        conn.commit()
        conn.close()
        
        print(f"✅ Saved {saved_count} new grants")
        if duplicate_count > 0:
            print(f"📝 Skipped {duplicate_count} duplicates")
        
        return saved_count
    
    def get_current_stats(self):
        """Get current database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM grants")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM grants WHERE agency = 'NIH'")
        nih_count = cursor.fetchone()[0]
        
        conn.close()
        return total, nih_count
    
    def run_scraper(self):
        """Run the complete scraping process"""
        print("🧬 Starting Real NIH Grant Scraper...")
        
        # Get current stats
        before_total, before_nih = self.get_current_stats()
        print(f"📊 Current database: {before_total} total grants ({before_nih} from NIH)")
        
        # Fetch real NIH data
        nih_grants = self.fetch_nih_grants_simple()
        
        # Save to database
        saved_count = self.save_grants(nih_grants)
        
        # Get final stats
        after_total, after_nih = self.get_current_stats()
        
        print(f"\n📈 Final database: {after_total} total grants ({after_nih} from NIH)")
        print(f"✅ Added {saved_count} new real NIH grants")
        
        if saved_count > 0:
            print(f"🚀 Success! Your database now has real NIH data.")
        else:
            print("ℹ️ No new grants added (API might be down or no new biotools grants found)")
        
        return saved_count

def main():
    scraper = RealNIHScraper()
    scraper.run_scraper()

if __name__ == "__main__":
    main()