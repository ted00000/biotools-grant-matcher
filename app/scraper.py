#!/usr/bin/env python3
"""
Fixed SBIR Scraper - Addresses Solicitations API Issues
- Uses alternative API approaches when main endpoint fails
- Implements comprehensive error handling
- Falls back to alternative data sources
- Adds better logging for debugging API issues
"""

import requests
import sqlite3
from datetime import datetime, timedelta
import time
import os
import json
from typing import List, Dict, Any, Optional
import logging

class FixedSBIRScraper:
    def __init__(self, db_path="data/grants.db"):
        self.db_path = db_path
        self.base_url = "https://api.www.sbir.gov/public/api"
        self.legacy_url = "https://legacy.www.sbir.gov/api"  # Fallback URL
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Setup logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        self.setup_database()
        
        # Enhanced biotools keywords
        self.biotools_keywords = [
            'diagnostic', 'biomarker', 'assay', 'test', 'detection', 'screening',
            'laboratory', 'instrumentation', 'microscopy', 'spectrometry', 'imaging',
            'biotechnology', 'bioengineering', 'medical device', 'biosensor',
            'microfluidics', 'lab-on-chip', 'point-of-care', 'automation',
            'genomics', 'proteomics', 'molecular', 'analytical', 'chromatography',
            'electrophoresis', 'mass spectrometry', 'sequencing', 'pcr',
            'cell analysis', 'protein analysis', 'dna analysis', 'rna analysis',
            'bioinformatics', 'computational biology', 'machine learning',
            'artificial intelligence', 'high throughput', 'drug discovery',
            'pharmaceutical', 'therapeutics', 'clinical', 'biomedical',
            'sensor', 'monitor', 'measurement', 'analysis', 'research tool',
            'scientific instrument', 'clinical trial', 'medical', 'healthcare',
            'biological', 'biochemical', 'biomolecular', 'therapeutic'
        ]
        
        # User agent to appear more like a browser
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; GrantMatcher/1.0; +https://example.com/bot)',
            'Accept': 'application/json, text/html',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache'
        }
    
    def setup_database(self):
        """Setup database with proper error handling"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if grants table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='grants';")
        grants_exists = cursor.fetchone()
        
        if grants_exists:
            # Get existing columns
            cursor.execute("PRAGMA table_info(grants);")
            existing_columns = {row[1]: row[2] for row in cursor.fetchall()}
            self.logger.info(f"Found existing grants table with {len(existing_columns)} columns")
            
            # Add missing columns safely
            new_columns = {
                'data_source': 'TEXT',
                'solicitation_status': 'TEXT',
                'close_date': 'DATE',
                'open_date': 'DATE',
                'relevance_score': 'REAL DEFAULT 0.0',
                'last_scraped_at': 'TEXT'
            }
            
            for column_name, column_def in new_columns.items():
                if column_name not in existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE grants ADD COLUMN {column_name} {column_def}")
                        self.logger.info(f"Added column: {column_name}")
                    except sqlite3.Error as e:
                        self.logger.warning(f"Could not add column {column_name}: {e}")
        else:
            # Create new table
            self.logger.info("Creating new grants table")
            cursor.execute('''
                CREATE TABLE grants (
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
                    data_source TEXT DEFAULT 'SBIR',
                    solicitation_status TEXT,
                    close_date DATE,
                    open_date DATE,
                    relevance_score REAL DEFAULT 0.0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_scraped_at TEXT
                )
            ''')
        
        conn.commit()
        conn.close()
    
    def is_biotools_relevant(self, text: str) -> bool:
        """Check if content is relevant to biotools/life sciences"""
        if not text:
            return False
        
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.biotools_keywords)
    
    def calculate_biotools_relevance_score(self, title: str, description: str, keywords: str = "") -> float:
        """Calculate relevance score for biotools applications"""
        score = 0.0
        combined_text = f"{title} {description} {keywords}".lower()
        
        # High-value biotools terms (higher weight)
        high_value_terms = [
            'diagnostic', 'biomarker', 'medical device', 'biosensor', 'microfluidics',
            'lab-on-chip', 'point-of-care', 'sequencing', 'genomics', 'proteomics'
        ]
        
        # Medium-value terms
        medium_value_terms = [
            'laboratory', 'instrumentation', 'microscopy', 'biotechnology',
            'analytical', 'automation', 'imaging', 'molecular'
        ]
        
        # Count matches and weight them
        for term in high_value_terms:
            if term in combined_text:
                score += 3.0
        
        for term in medium_value_terms:
            if term in combined_text:
                score += 1.5
        
        # Additional scoring for biotools keywords
        for keyword in self.biotools_keywords:
            if keyword in combined_text:
                score += 1.0
        
        return min(score, 10.0)  # Cap at 10.0
    
    def make_api_request(self, endpoint: str, params: Dict[str, Any] = None, use_legacy: bool = False, max_retries: int = 3) -> Optional[List]:
        """Make API request with enhanced error handling and fallback URLs"""
        base_url = self.legacy_url if use_legacy else self.base_url
        url = f"{base_url}/{endpoint}"
        
        # Add format=json to params if not present
        if params is None:
            params = {}
        if 'format' not in params:
            params['format'] = 'json'
        
        for attempt in range(max_retries):
            try:
                self.logger.debug(f"API Request: {url} with params: {params}")
                response = requests.get(url, params=params, headers=self.headers, timeout=30)
                
                self.logger.debug(f"Response status: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        return data
                    except json.JSONDecodeError as e:
                        self.logger.error(f"JSON decode error: {e}")
                        self.logger.debug(f"Raw response: {response.text[:500]}")
                        return None
                        
                elif response.status_code == 403:
                    self.logger.warning(f"403 Forbidden - API access restricted: {url}")
                    if not use_legacy and endpoint == 'solicitations':
                        self.logger.info("Trying legacy API URL...")
                        return self.make_api_request(endpoint, params, use_legacy=True, max_retries=max_retries)
                    return None
                    
                elif response.status_code == 404:
                    self.logger.warning(f"404 Not Found - endpoint may not exist: {url}")
                    return None
                    
                elif response.status_code == 429:
                    wait_time = (attempt + 1) * 10
                    self.logger.warning(f"Rate limited, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    
                else:
                    self.logger.error(f"API request failed: {response.status_code}")
                    self.logger.debug(f"Response content: {response.text[:200]}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request exception (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)
        
        self.logger.error(f"Failed after {max_retries} attempts")
        return None
    
    def test_api_endpoints(self):
        """Test all API endpoints to see what's working"""
        self.logger.info("🔍 Testing SBIR API Endpoints...")
        
        endpoints_to_test = [
            ('awards', {'rows': 5}, 'Basic awards test'),
            ('awards', {'agency': 'HHS', 'rows': 5}, 'HHS awards test'),
            ('firm', {'rows': 5}, 'Companies test'),
            ('solicitations', {'rows': 5}, 'Solicitations test'),
            ('solicitations', {'open': 1, 'rows': 5}, 'Open solicitations test'),
            ('solicitations', {'agency': 'HHS', 'rows': 5}, 'HHS solicitations test'),
        ]
        
        working_endpoints = []
        
        for endpoint, params, description in endpoints_to_test:
            self.logger.info(f"  Testing: {description}")
            
            # Test main API
            data = self.make_api_request(endpoint, params)
            if data and isinstance(data, list) and len(data) > 0:
                self.logger.info(f"    ✅ Main API works: {len(data)} records")
                working_endpoints.append((endpoint, params, 'main'))
            else:
                self.logger.info(f"    ❌ Main API failed")
                
                # Test legacy API for solicitations
                if endpoint == 'solicitations':
                    self.logger.info(f"    🔄 Trying legacy API...")
                    legacy_data = self.make_api_request(endpoint, params, use_legacy=True)
                    if legacy_data and isinstance(legacy_data, list) and len(legacy_data) > 0:
                        self.logger.info(f"    ✅ Legacy API works: {len(legacy_data)} records")
                        working_endpoints.append((endpoint, params, 'legacy'))
                    else:
                        self.logger.info(f"    ❌ Legacy API also failed")
        
        self.logger.info(f"\n📊 Working endpoints: {len(working_endpoints)}")
        return working_endpoints
    
    def fetch_awards_robust(self, agency: str, start_year: int = 2020) -> List[Dict]:
        """Robust awards fetching with enhanced error handling"""
        self.logger.info(f"Fetching {agency} awards from {start_year}...")
        
        awards = []
        current_year = datetime.now().year
        
        for year in range(start_year, current_year + 1):
            self.logger.info(f"  Fetching {agency} awards for {year}...")
            
            start = 0
            batch_size = 1000
            
            while True:
                params = {
                    'agency': agency,
                    'year': year,
                    'start': start,
                    'rows': batch_size,
                    'format': 'json'
                }
                
                data = self.make_api_request('awards', params)
                
                if not data or not isinstance(data, list):
                    break
                
                if not data:  # Empty list
                    break
                
                # Filter for biotools relevance
                relevant_awards = []
                for award in data:
                    title = award.get('award_title', '')
                    abstract = award.get('abstract', '')
                    keywords = award.get('research_area_keywords', '') or ''
                    
                    combined_text = f"{title} {abstract} {keywords}"
                    
                    if self.is_biotools_relevant(combined_text):
                        award['relevance_score'] = self.calculate_biotools_relevance_score(title, abstract, keywords)
                        relevant_awards.append(award)
                
                awards.extend(relevant_awards)
                self.logger.info(f"    Batch: {len(data)} total, {len(relevant_awards)} biotools-relevant")
                
                # If we got fewer results than requested, we're done
                if len(data) < batch_size:
                    break
                
                start += batch_size
                time.sleep(1)  # Be respectful
        
        self.logger.info(f"✅ {agency}: Collected {len(awards)} biotools-relevant awards")
        return awards
    
    def fetch_solicitations_robust(self) -> List[Dict]:
        """Robust solicitations fetching with multiple fallback strategies"""
        self.logger.info("🔍 Fetching SBIR Solicitations with Robust Strategy...")
        
        all_solicitations = []
        
        # Strategy 1: Try open solicitations
        self.logger.info("  Strategy 1: Open solicitations...")
        try:
            params = {'open': 1, 'rows': 100, 'format': 'json'}
            data = self.make_api_request('solicitations', params)
            if data and isinstance(data, list):
                self.logger.info(f"    ✅ Found {len(data)} open solicitations")
                all_solicitations.extend(data)
            else:
                self.logger.info("    ❌ No open solicitations found")
        except Exception as e:
            self.logger.warning(f"    ❌ Open solicitations failed: {e}")
        
        # Strategy 2: Try all recent solicitations
        self.logger.info("  Strategy 2: All recent solicitations...")
        try:
            params = {'rows': 100, 'format': 'json'}
            data = self.make_api_request('solicitations', params)
            if data and isinstance(data, list):
                self.logger.info(f"    ✅ Found {len(data)} total solicitations")
                # Filter for recent ones
                recent_data = self._filter_recent_solicitations(data)
                self.logger.info(f"    📅 {len(recent_data)} are recent")
                all_solicitations.extend(recent_data)
            else:
                self.logger.info("    ❌ No solicitations found")
        except Exception as e:
            self.logger.warning(f"    ❌ All solicitations failed: {e}")
        
        # Strategy 3: Try agency-specific searches
        self.logger.info("  Strategy 3: Agency-specific searches...")
        agencies = ['HHS', 'NSF', 'DOD', 'DOE']
        
        for agency in agencies:
            try:
                params = {'agency': agency, 'rows': 50, 'format': 'json'}
                data = self.make_api_request('solicitations', params)
                if data and isinstance(data, list):
                    self.logger.info(f"    ✅ {agency}: {len(data)} solicitations")
                    all_solicitations.extend(data)
                else:
                    self.logger.info(f"    ❌ {agency}: No solicitations")
                time.sleep(1)  # Be respectful
            except Exception as e:
                self.logger.warning(f"    ❌ {agency} search failed: {e}")
        
        # Strategy 4: Try keyword searches for biotools terms
        self.logger.info("  Strategy 4: Keyword-based searches...")
        biotools_search_terms = ['diagnostic', 'biotech', 'medical', 'laboratory', 'biosensor']
        
        for keyword in biotools_search_terms:
            try:
                params = {'keyword': keyword, 'rows': 25, 'format': 'json'}
                data = self.make_api_request('solicitations', params)
                if data and isinstance(data, list):
                    self.logger.info(f"    ✅ '{keyword}': {len(data)} solicitations")
                    all_solicitations.extend(data)
                else:
                    self.logger.info(f"    ❌ '{keyword}': No solicitations")
                time.sleep(0.5)  # Be respectful
            except Exception as e:
                self.logger.warning(f"    ❌ Keyword '{keyword}' search failed: {e}")
        
        # Remove duplicates based on solicitation_number
        unique_solicitations = {}
        for sol in all_solicitations:
            sol_num = sol.get('solicitation_number') or sol.get('solicitation_id', '')
            if sol_num and sol_num not in unique_solicitations:
                unique_solicitations[sol_num] = sol
        
        unique_list = list(unique_solicitations.values())
        self.logger.info(f"  📊 Total unique solicitations: {len(unique_list)}")
        
        # Filter for biotools relevance
        relevant_solicitations = self._filter_biotools_solicitations(unique_list)
        
        self.logger.info(f"✅ Collected {len(relevant_solicitations)} biotools-relevant solicitations")
        return relevant_solicitations
    
    def _filter_recent_solicitations(self, solicitations: List[Dict]) -> List[Dict]:
        """Filter solicitations to only include recent ones"""
        recent_solicitations = []
        cutoff_date = datetime.now() - timedelta(days=365)  # Last year
        
        for sol in solicitations:
            is_recent = False
            
            # Check various date fields
            for date_field in ['close_date', 'open_date', 'release_date']:
                date_str = sol.get(date_field, '')
                if date_str:
                    try:
                        # Try to parse various date formats
                        for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ']:
                            try:
                                sol_date = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d')
                                if sol_date >= cutoff_date:
                                    is_recent = True
                                    break
                            except ValueError:
                                continue
                        if is_recent:
                            break
                    except Exception:
                        continue
            
            # Also check status
            status = sol.get('current_status', '').lower()
            if status in ['open', 'active', 'current']:
                is_recent = True
            
            if is_recent:
                recent_solicitations.append(sol)
        
        return recent_solicitations
    
    def _filter_biotools_solicitations(self, solicitations: List[Dict]) -> List[Dict]:
        """Filter solicitations for biotools relevance"""
        relevant_solicitations = []
        
        for sol in solicitations:
            title = sol.get('solicitation_title', '')
            
            # Check topics for biotools relevance
            topics_text = ""
            if 'solicitation_topics' in sol and sol['solicitation_topics']:
                for topic in sol['solicitation_topics']:
                    if isinstance(topic, dict):
                        topics_text += f" {topic.get('topic_title', '')} {topic.get('topic_description', '')}"
            
            combined_text = f"{title} {topics_text}"
            
            if self.is_biotools_relevant(combined_text):
                sol['relevance_score'] = self.calculate_biotools_relevance_score(title, topics_text)
                relevant_solicitations.append(sol)
        
        return relevant_solicitations
    
    def save_data_safely(self, data: List[Dict], data_type: str) -> int:
        """Save data to database with enhanced error handling"""
        if not data:
            self.logger.info(f"No {data_type} data to save")
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get actual table structure
        cursor.execute("PRAGMA table_info(grants);")
        columns_info = cursor.fetchall()
        column_names = [col[1] for col in columns_info]
        
        saved_count = 0
        current_time = datetime.now().isoformat()
        
        for item in data:
            try:
                # Create a safe mapping based on available columns
                safe_data = {}
                
                if data_type == 'awards':
                    safe_data['funding_opportunity_number'] = f"SBIR-{item.get('agency', '')}-{item.get('contract', '')}"
                    safe_data['title'] = item.get('award_title', '')[:250]
                    safe_data['agency'] = item.get('agency', '')
                    safe_data['description'] = item.get('abstract', '')[:1000] if item.get('abstract') else ''
                    safe_data['keywords'] = item.get('research_area_keywords', '')
                    safe_data['url'] = item.get('award_link', '')
                    
                    # Handle amount
                    amount = 0
                    if item.get('award_amount'):
                        try:
                            amount = int(float(str(item['award_amount'])))
                        except:
                            amount = 0
                    safe_data['amount_max'] = amount
                    safe_data['amount_min'] = 0
                    
                elif data_type == 'solicitations':
                    safe_data['funding_opportunity_number'] = f"SOL-{item.get('solicitation_number', '')}"
                    safe_data['title'] = item.get('solicitation_title', '')[:250]
                    safe_data['agency'] = item.get('agency', '')
                    safe_data['description'] = str(item.get('solicitation_topics', []))[:1000]
                    safe_data['deadline'] = item.get('close_date', '')
                    safe_data['url'] = item.get('solicitation_agency_url', '')
                    
                    if 'close_date' in column_names:
                        safe_data['close_date'] = item.get('close_date', '')
                    if 'open_date' in column_names:
                        safe_data['open_date'] = item.get('open_date', '')
                    if 'solicitation_status' in column_names:
                        safe_data['solicitation_status'] = item.get('current_status', '')
                
                # Add metadata
                safe_data['data_source'] = 'SBIR'
                if 'relevance_score' in column_names:
                    safe_data['relevance_score'] = item.get('relevance_score', 0.0)
                if 'updated_at' in column_names:
                    safe_data['updated_at'] = current_time
                if 'last_scraped_at' in column_names:
                    safe_data['last_scraped_at'] = current_time
                
                # Filter for available columns
                available_data = {k: v for k, v in safe_data.items() if k in column_names and v is not None}
                
                if not available_data:
                    continue
                
                # Build SQL
                columns = list(available_data.keys())
                values = list(available_data.values())
                placeholders = ', '.join(['?' for _ in values])
                
                sql = f'''
                    INSERT OR REPLACE INTO grants ({', '.join(columns)})
                    VALUES ({placeholders})
                '''
                
                cursor.execute(sql, values)
                saved_count += 1
                
            except sqlite3.Error as e:
                self.logger.error(f"Database error saving {data_type}: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"💾 Saved {saved_count} {data_type} to database")
        return saved_count
    
    def run_comprehensive_test(self):
        """Run comprehensive API testing and data collection"""
        self.logger.info("🚀 Starting Comprehensive SBIR Data Collection Test")
        self.logger.info("=" * 60)
        
        # Step 1: Test all endpoints
        self.logger.info("Step 1: Testing API Endpoints")
        working_endpoints = self.test_api_endpoints()
        
        if not working_endpoints:
            self.logger.error("❌ No working API endpoints found!")
            return
        
        # Step 2: Collect awards data
        self.logger.info("\nStep 2: Collecting Awards Data")
        all_awards = []
        
        # Test with just HHS first (smaller dataset)
        try:
            hhs_awards = self.fetch_awards_robust('HHS', 2023)  # Just last 2 years for testing
            all_awards.extend(hhs_awards)
        except Exception as e:
            self.logger.error(f"Failed to fetch HHS awards: {e}")
        
        # Step 3: Collect solicitations data
        self.logger.info("\nStep 3: Collecting Solicitations Data")
        solicitations = []
        
        try:
            solicitations = self.fetch_solicitations_robust()
        except Exception as e:
            self.logger.error(f"Failed to fetch solicitations: {e}")
        
        # Step 4: Save data
        self.logger.info("\nStep 4: Saving Data to Database")
        
        awards_saved = self.save_data_safely(all_awards, 'awards')
        solicitations_saved = self.save_data_safely(solicitations, 'solicitations')
        
        # Step 5: Results summary
        self.logger.info("\n" + "=" * 60)
        self.logger.info("📊 COMPREHENSIVE TEST RESULTS:")
        self.logger.info(f"  Working API endpoints: {len(working_endpoints)}")
        self.logger.info(f"  Awards collected: {len(all_awards)}")
        self.logger.info(f"  Awards saved: {awards_saved}")
        self.logger.info(f"  Solicitations collected: {len(solicitations)}")
        self.logger.info(f"  Solicitations saved: {solicitations_saved}")
        
        if awards_saved > 0 or solicitations_saved > 0:
            self.logger.info("🎉 SUCCESS: Data collection is working!")
        else:
            self.logger.warning("⚠️ No data was saved - check API issues")
        
        return {
            'working_endpoints': len(working_endpoints),
            'awards_collected': len(all_awards),
            'awards_saved': awards_saved,
            'solicitations_collected': len(solicitations),
            'solicitations_saved': solicitations_saved
        }


def main():
    """Main execution function for testing"""
    scraper = FixedSBIRScraper()
    
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'test':
            # Run comprehensive test
            scraper.run_comprehensive_test()
            
        elif command == 'endpoints':
            # Test endpoints only
            scraper.test_api_endpoints()
            
        elif command == 'solicitations':
            # Test solicitations only
            solicitations = scraper.fetch_solicitations_robust()
            print(f"\nFound {len(solicitations)} biotools-relevant solicitations")
            if solicitations:
                for i, sol in enumerate(solicitations[:3]):
                    print(f"\n{i+1}. {sol.get('solicitation_title', 'No title')}")
                    print(f"   Agency: {sol.get('agency', 'Unknown')}")
                    print(f"   Status: {sol.get('current_status', 'Unknown')}")
                    print(f"   Close Date: {sol.get('close_date', 'Unknown')}")
            
        elif command == 'awards':
            # Test awards only
            awards = scraper.fetch_awards_robust('HHS', 2024)
            print(f"\nFound {len(awards)} biotools-relevant awards")
            if awards:
                for i, award in enumerate(awards[:3]):
                    print(f"\n{i+1}. {award.get('award_title', 'No title')}")
                    print(f"   Company: {award.get('firm', 'Unknown')}")
                    print(f"   Amount: ${award.get('award_amount', 0):,}")
                    print(f"   Score: {award.get('relevance_score', 0):.1f}")
    else:
        print("Usage:")
        print("  python fixed_scraper.py test         # Run comprehensive test")
        print("  python fixed_scraper.py endpoints    # Test API endpoints")
        print("  python fixed_scraper.py solicitations # Test solicitations only")
        print("  python fixed_scraper.py awards       # Test awards only")

if __name__ == "__main__":
    main()