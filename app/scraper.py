#!/usr/bin/env python3
"""
Fixed Scraper - Focus on Working APIs and Fix NSF Issues
"""

import requests
import sqlite3
from datetime import datetime
import time
import os

class FixedScraper:
    def __init__(self, db_path="data/grants.db"):
        self.db_path = db_path
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
                biotools_category TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def fetch_nsf_grants_fixed(self):
        """Fixed NSF API calls with proper parameters"""
        print("🔬 Fetching NSF grants (fixed API calls)...")
        
        grants = []
        
        # Simplified search terms that NSF API can handle
        simple_terms = [
            "biotechnology",
            "instrumentation", 
            "laboratory",
            "microscopy",
            "spectrometry"
        ]
        
        for term in simple_terms:
            try:
                # Simplified NSF API call
                url = "https://api.nsf.gov/services/v1/awards.json"
                
                # Basic parameters only
                params = {
                    'keyword': term,
                    'rpp': '25'
                }
                
                print(f"  Testing NSF API with '{term}'...")
                
                # Add headers to look more like a browser
                headers = {
                    'User-Agent': 'Mozilla/5.0 (compatible; Research/1.0)',
                    'Accept': 'application/json'
                }
                
                response = requests.get(url, params=params, headers=headers, timeout=15)
                
                print(f"    Status: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        
                        # Debug: show response structure
                        print(f"    Response type: {type(data)}")
                        if isinstance(data, dict):
                            print(f"    Keys: {list(data.keys())}")
                        
                        # Process awards if found
                        awards = self.extract_nsf_awards(data)
                        print(f"    Found {len(awards)} awards")
                        
                        for award in awards:
                            if self.is_biotools_relevant(award.get('title', '') + ' ' + award.get('abstractText', '')):
                                grant = self.parse_nsf_award(award)
                                if grant:
                                    grants.append(grant)
                                    print(f"      ✅ Added: {award.get('title', '')[:50]}...")
                    
                    except Exception as e:
                        print(f"    JSON parsing error: {e}")
                
                elif response.status_code == 400:
                    print(f"    400 Error - Bad Request for '{term}'")
                    print(f"    Response: {response.text[:200]}...")
                    # Try with even simpler parameters
                    continue
                
                else:
                    print(f"    HTTP {response.status_code}: {response.text[:100]}...")
                
                # Longer delay to be extra respectful
                time.sleep(3)
                
            except requests.exceptions.Timeout:
                print(f"    Timeout for '{term}'")
                continue
            except Exception as e:
                print(f"    Error for '{term}': {e}")
                continue
        
        print(f"✅ NSF: Collected {len(grants)} grants")
        return grants
    
    def extract_nsf_awards(self, data):
        """Extract awards from NSF API response"""
        awards = []
        
        try:
            if isinstance(data, dict):
                if 'response' in data:
                    response_data = data['response']
                    if isinstance(response_data, dict) and 'award' in response_data:
                        awards_data = response_data['award']
                        if isinstance(awards_data, list):
                            awards = awards_data
                        elif isinstance(awards_data, dict):
                            awards = [awards_data]
        except Exception as e:
            print(f"      Award extraction error: {e}")
        
        return awards
    
    def fetch_nih_grants_expanded(self):
        """Expanded NIH search since it's working well"""
        print("🧬 Fetching NIH grants (expanded search)...")
        
        grants = []
        
        # Expanded NIH search queries for life science tools
        search_queries = [
            "laboratory instrumentation OR research instrumentation",
            "microscopy OR imaging OR spectroscopy",
            "biotechnology OR bioengineering",
            "analytical instrumentation OR analytical methods",
            "laboratory automation OR high throughput",
            "molecular biology tools OR molecular techniques",
            "protein analysis OR genomics OR proteomics",
            "cell biology tools OR cell analysis",
            "bioinformatics OR computational biology",
            "diagnostic tools OR biosensors",
            "chromatography OR electrophoresis OR mass spectrometry",
            "laboratory equipment OR scientific instruments"
        ]
        
        for i, search_text in enumerate(search_queries):
            try:
                url = "https://api.reporter.nih.gov/v2/projects/search"
                
                payload = {
                    "criteria": {
                        "advanced_text_search": {
                            "operator": "and",
                            "search_field": "projecttitle,terms,abstracttext",
                            "search_text": search_text
                        },
                        "fiscal_years": [2022, 2023, 2024, 2025]
                    },
                    "include_fields": [
                        "ProjectTitle", "AbstractText", "AgencyCode", 
                        "TotalCostAmount", "Organization", "ApplId", "Terms"
                    ],
                    "limit": 50
                }
                
                print(f"  [{i+1:2d}/{len(search_queries)}] '{search_text[:40]}...'")
                
                response = requests.post(url, json=payload, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'results' in data and data['results']:
                        projects = data['results']
                        relevant_count = 0
                        
                        for project in projects:
                            title = project.get('project_title', '')
                            abstract = project.get('abstract_text', '')
                            
                            if self.is_biotools_relevant(title, abstract):
                                grant = self.parse_nih_project(project)
                                if grant:
                                    grants.append(grant)
                                    relevant_count += 1
                        
                        print(f"      Found {relevant_count} relevant biotools grants")
                    else:
                        print("      No results")
                
                else:
                    print(f"      Error {response.status_code}")
                
                time.sleep(1)  # Short delay
                
            except Exception as e:
                print(f"      Error: {e}")
                continue
        
        print(f"✅ NIH: Collected {len(grants)} grants")
        return grants
    
    def test_nsf_api(self):
        """Test NSF API with minimal request to debug 400 errors"""
        print("🔍 Testing NSF API connectivity...")
        
        try:
            # Most basic possible request
            url = "https://api.nsf.gov/services/v1/awards.json"
            params = {'rpp': '5'}  # Just get 5 records, no keyword
            
            response = requests.get(url, params=params, timeout=10)
            
            print(f"  Basic test: {response.status_code}")
            
            if response.status_code == 200:
                print("  ✅ NSF API is accessible")
                data = response.json()
                print(f"  Response has {len(data.get('response', {}).get('award', []))} awards")
                return True
            else:
                print(f"  ❌ NSF API error: {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                return False
                
        except Exception as e:
            print(f"  ❌ NSF API connection failed: {e}")
            return False
    
    def is_biotools_relevant(self, title, abstract=''):
        """Check if content is relevant to life science tools"""
        text = (title + ' ' + abstract).lower()
        
        # Life science tool keywords
        biotools_terms = [
            'laboratory', 'instrumentation', 'microscopy', 'spectrometry', 
            'biotechnology', 'bioengineering', 'analytical', 'diagnostic',
            'protein analysis', 'dna analysis', 'cell analysis', 'genomics',
            'proteomics', 'bioinformatics', 'molecular biology', 'chromatography',
            'electrophoresis', 'mass spectrometry', 'imaging', 'automation',
            'high throughput', 'assay', 'biosensor', 'lab equipment',
            'research tool', 'scientific instrument'
        ]
        
        return any(term in text for term in biotools_terms)
    
    def parse_nsf_award(self, award):
        """Parse NSF award data"""
        try:
            award_id = award.get('id', '')
            title = award.get('title', '')
            abstract = award.get('abstractText', '')
            
            amount = 0
            if 'fundsObligatedAmt' in award:
                try:
                    amount = int(float(str(award['fundsObligatedAmt'])))
                except:
                    amount = 0
            
            org = "Research Institution"
            if 'awardee' in award and isinstance(award['awardee'], dict):
                org = award['awardee'].get('name', org)[:200]
            
            return {
                'funding_opportunity_number': f"NSF-{award_id}",
                'title': title[:250] if title else f"NSF Award {award_id}",
                'agency': 'NSF',
                'description': abstract[:1000] if abstract else '',
                'amount_min': 0,
                'amount_max': amount,
                'keywords': self.extract_keywords(title + ' ' + abstract),
                'eligibility': org,
                'url': f"https://www.nsf.gov/awardsearch/showAward?AWD_ID={award_id}",
                'biotools_category': 'nsf_research',
                'deadline': None
            }
            
        except Exception as e:
            return None
    
    def parse_nih_project(self, project):
        """Parse NIH project data"""
        try:
            appl_id = project.get('appl_id', '')
            title = project.get('project_title', '')
            abstract = project.get('abstract_text', '')
            
            amount = 0
            if 'total_cost_amount' in project:
                try:
                    amount = int(project['total_cost_amount'])
                except:
                    amount = 0
            
            org = "Research Institution"
            if 'organization' in project and isinstance(project['organization'], dict):
                org = project['organization'].get('org_name', org)[:200]
            
            return {
                'funding_opportunity_number': f"NIH-{appl_id}",
                'title': title[:250] if title else f"NIH Project {appl_id}",
                'agency': 'NIH',
                'description': abstract[:1000] if abstract else '',
                'amount_min': 0,
                'amount_max': amount,
                'keywords': self.extract_keywords(title + ' ' + abstract),
                'eligibility': org,
                'url': f"https://reporter.nih.gov/project-details/{appl_id}",
                'biotools_category': 'nih_research',
                'deadline': None
            }
            
        except Exception as e:
            return None
    
    def extract_keywords(self, text):
        """Extract relevant keywords"""
        if not text:
            return ''
        
        keywords = [
            'microscopy', 'spectrometry', 'chromatography', 'biotechnology',
            'proteomics', 'genomics', 'bioinformatics', 'analytical',
            'instrumentation', 'automation', 'imaging', 'laboratory'
        ]
        
        found = []
        text_lower = text.lower()
        for keyword in keywords:
            if keyword in text_lower and keyword not in found:
                found.append(keyword)
        
        return ', '.join(found[:8])
    
    def save_grants(self, grants, source_name):
        """Save grants to database"""
        if not grants:
            print(f"⚠️ No {source_name} grants to save")
            return 0
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Add category column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE grants ADD COLUMN biotools_category TEXT")
        except sqlite3.OperationalError:
            pass
        
        saved_count = 0
        duplicate_count = 0
        current_time = datetime.now().isoformat()
        
        for grant in grants:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO grants 
                    (funding_opportunity_number, title, agency, description, 
                     amount_min, amount_max, keywords, eligibility, url, 
                     biotools_category, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    grant['biotools_category'],
                    current_time
                ))
                
                if cursor.rowcount > 0:
                    saved_count += 1
                else:
                    duplicate_count += 1
                    
            except sqlite3.Error as e:
                print(f"Database error: {e}")
        
        conn.commit()
        conn.close()
        
        print(f"✅ Saved {saved_count} new {source_name} grants")
        if duplicate_count > 0:
            print(f"📝 Skipped {duplicate_count} {source_name} duplicates")
        
        return saved_count
    
    def get_stats(self):
        """Get database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM grants")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT agency, COUNT(*) FROM grants GROUP BY agency ORDER BY COUNT(*) DESC")
        by_agency = cursor.fetchall()
        
        conn.close()
        return total, by_agency
    
    def run_scraper(self):
        """Run the fixed scraper"""
        print("🚀 Starting Fixed Life Science Tools Scraper")
        print("=" * 50)
        
        before_total, _ = self.get_stats()
        print(f"📊 Current database: {before_total} grants")
        
        total_added = 0
        
        # Test NSF API first
        print("\n" + "="*40)
        nsf_working = self.test_nsf_api()
        
        if nsf_working:
            try:
                nsf_grants = self.fetch_nsf_grants_fixed()
                total_added += self.save_grants(nsf_grants, "NSF")
            except Exception as e:
                print(f"❌ NSF scraping failed: {e}")
        else:
            print("⚠️ Skipping NSF due to API issues")
        
        # Focus on NIH since it's working
        print("\n" + "="*40)
        try:
            nih_grants = self.fetch_nih_grants_expanded()
            total_added += self.save_grants(nih_grants, "NIH")
        except Exception as e:
            print(f"❌ NIH scraping failed: {e}")
        
        # Final results
        print("\n" + "="*50)
        after_total, by_agency = self.get_stats()
        
        print(f"📈 Final database: {after_total} grants (+{after_total - before_total})")
        print("\n📊 Grants by agency:")
        for agency, count in by_agency:
            print(f"   {agency}: {count}")
        
        print(f"\n✅ Added {total_added} new grants this run")
        
        if total_added > 0:
            print("🎉 Success! Database expanded with real life science tool grants")
        
        return total_added

def main():
    scraper = FixedScraper()
    scraper.run_scraper()

if __name__ == "__main__":
    main()