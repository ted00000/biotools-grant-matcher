#!/usr/bin/env python3
"""
Complete Final SBIR/STTR Scraper - All Fixes Applied
- Headers fix: ✅ Proper browser-like headers to avoid 403 errors
- Solicitations API: ✅ Follows exact API specifications (max 50 rows)
- Rate limiting: ✅ Proper delays and respectful API usage
- Error handling: ✅ Comprehensive logging and recovery
- Database schema: ✅ Dynamic column handling for all environments
"""

import requests
import sqlite3
from datetime import datetime, timedelta
import time
import os
import json
from typing import List, Dict, Any, Optional
import logging

class SBIRScraper:
    def __init__(self, db_path="data/grants.db"):
        self.db_path = db_path
        self.base_url = "https://api.www.sbir.gov/public/api"
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # 🔧 CRITICAL FIX: Browser-like headers to avoid 403 Forbidden
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; BiotoolsGrantMatcher/1.0; +https://biotools.example.com)',
            'Accept': 'application/json, text/html, application/xhtml+xml, application/xml;q=0.9, */*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        }
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO, 
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/scraper.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # Create logs directory
        os.makedirs('logs', exist_ok=True)
        
        self.setup_database()
        
        # Enhanced biotools-relevant keywords for filtering
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
            'biological', 'biochemical', 'biomolecular', 'therapeutic',
            'pathogen', 'vaccine', 'immunology', 'oncology', 'cardiology',
            'neurology', 'dermatology', 'ophthalmology', 'orthopedic'
        ]
    
    def setup_database(self):
        """Create enhanced database schema for SBIR/STTR data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check if grants table exists and what columns it has
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='grants';")
        grants_exists = cursor.fetchone()
        
        if grants_exists:
            # Get existing columns
            cursor.execute("PRAGMA table_info(grants);")
            existing_columns = {row[1]: row[2] for row in cursor.fetchall()}
            self.logger.info(f"Found existing grants table with {len(existing_columns)} columns")
            
            # Add missing SBIR columns to existing table
            new_columns = {
                'branch': 'TEXT',
                'phase': 'TEXT', 
                'program': 'TEXT',
                'agency_tracking_number': 'TEXT',
                'contract_number': 'TEXT',
                'proposal_award_date': 'DATE',
                'contract_end_date': 'DATE',
                'solicitation_number': 'TEXT',
                'solicitation_year': 'INTEGER',
                'topic_code': 'TEXT',
                'award_year': 'INTEGER',
                'award_amount': 'INTEGER',
                'company_name': 'TEXT',
                'company_uei': 'TEXT',
                'company_duns': 'TEXT',
                'company_address': 'TEXT',
                'company_city': 'TEXT',
                'company_state': 'TEXT',
                'company_zip': 'TEXT',
                'company_url': 'TEXT',
                'hubzone_owned': 'BOOLEAN',
                'socially_economically_disadvantaged': 'BOOLEAN',
                'women_owned': 'BOOLEAN',
                'number_employees': 'INTEGER',
                'poc_name': 'TEXT',
                'poc_title': 'TEXT',
                'poc_phone': 'TEXT',
                'poc_email': 'TEXT',
                'pi_name': 'TEXT',
                'pi_phone': 'TEXT',
                'pi_email': 'TEXT',
                'ri_name': 'TEXT',
                'ri_poc_name': 'TEXT',
                'ri_poc_phone': 'TEXT',
                'data_source': 'TEXT DEFAULT "SBIR"',
                'grant_type': 'TEXT',
                'current_status': 'TEXT',
                'relevance_score': 'REAL DEFAULT 0.0',
                'open_date': 'DATE',
                'close_date': 'DATE',
                'solicitation_topics': 'TEXT',
                'biotools_category': 'TEXT',
                'last_scraped_at': 'TEXT'
            }
            
            for column_name, column_def in new_columns.items():
                if column_name not in existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE grants ADD COLUMN {column_name} {column_def}")
                        self.logger.info(f"Added column: {column_name}")
                    except sqlite3.Error as e:
                        if "duplicate column name" not in str(e).lower():
                            self.logger.warning(f"Could not add column {column_name}: {e}")
        else:
            # Create new grants table with full SBIR schema
            self.logger.info("Creating new grants table with full SBIR schema")
            cursor.execute('''
                CREATE TABLE grants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    funding_opportunity_number TEXT UNIQUE,
                    title TEXT NOT NULL,
                    agency TEXT,
                    branch TEXT,
                    phase TEXT,
                    program TEXT,
                    deadline DATE,
                    amount_min INTEGER DEFAULT 0,
                    amount_max INTEGER DEFAULT 0,
                    description TEXT,
                    keywords TEXT,
                    eligibility TEXT,
                    url TEXT,
                    
                    -- SBIR-specific fields
                    agency_tracking_number TEXT,
                    contract_number TEXT,
                    proposal_award_date DATE,
                    contract_end_date DATE,
                    solicitation_number TEXT,
                    solicitation_year INTEGER,
                    topic_code TEXT,
                    award_year INTEGER,
                    award_amount INTEGER,
                    
                    -- Company information
                    company_name TEXT,
                    company_uei TEXT,
                    company_duns TEXT,
                    company_address TEXT,
                    company_city TEXT,
                    company_state TEXT,
                    company_zip TEXT,
                    company_url TEXT,
                    hubzone_owned BOOLEAN,
                    socially_economically_disadvantaged BOOLEAN,
                    women_owned BOOLEAN,
                    number_employees INTEGER,
                    
                    -- Contact information
                    poc_name TEXT,
                    poc_title TEXT,
                    poc_phone TEXT,
                    poc_email TEXT,
                    pi_name TEXT,
                    pi_phone TEXT,
                    pi_email TEXT,
                    
                    -- Research institution (STTR)
                    ri_name TEXT,
                    ri_poc_name TEXT,
                    ri_poc_phone TEXT,
                    
                    -- Metadata
                    data_source TEXT DEFAULT 'SBIR',
                    grant_type TEXT,
                    current_status TEXT,
                    biotools_category TEXT,
                    relevance_score REAL DEFAULT 0.0,
                    open_date DATE,
                    close_date DATE,
                    solicitation_topics TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_scraped_at TEXT
                )
            ''')
        
        conn.commit()
        conn.close()
        self.logger.info("Database schema initialized successfully")
    
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
            'lab-on-chip', 'point-of-care', 'sequencing', 'genomics', 'proteomics',
            'clinical trial', 'pharmaceutical', 'therapeutic'
        ]
        
        # Medium-value terms
        medium_value_terms = [
            'laboratory', 'instrumentation', 'microscopy', 'biotechnology',
            'analytical', 'automation', 'imaging', 'molecular', 'biomedical'
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
    
    def make_api_request(self, endpoint: str, params: Dict[str, Any] = None, max_retries: int = 3) -> Optional[List]:
        """Make API request with enhanced error handling and proper headers"""
        url = f"{self.base_url}/{endpoint}"
        
        # Ensure we have proper parameters
        if params is None:
            params = {}
        if 'format' not in params:
            params['format'] = 'json'
        
        for attempt in range(max_retries):
            try:
                self.logger.debug(f"API Request: {url} with params: {params}")
                
                # 🔧 CRITICAL: Use proper headers to avoid 403 Forbidden
                response = requests.get(url, params=params, headers=self.headers, timeout=30)
                
                self.logger.debug(f"Response status: {response.status_code}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        return data if isinstance(data, list) else []
                    except json.JSONDecodeError as e:
                        self.logger.error(f"JSON decode error: {e}")
                        return None
                        
                elif response.status_code == 403:
                    self.logger.error(f"403 Forbidden - API access denied: {url}")
                    self.logger.error("This suggests headers or rate limiting issues")
                    return None
                    
                elif response.status_code == 404:
                    self.logger.warning(f"404 Not Found - endpoint may not exist: {url}")
                    return None
                    
                elif response.status_code == 429:
                    wait_time = (attempt + 1) * 15  # Longer waits for rate limiting
                    self.logger.warning(f"Rate limited, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    
                else:
                    self.logger.error(f"API request failed: {response.status_code}")
                    self.logger.debug(f"Response content: {response.text[:200]}")
                    return None
                    
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request exception (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(10)  # Longer delays between retries
        
        self.logger.error(f"Failed after {max_retries} attempts")
        return None
    
    def fetch_awards_by_agency(self, agency: str, start_year: int = 2020) -> List[Dict]:
        """Fetch awards from specific agency with biotools filtering"""
        self.logger.info(f"Fetching {agency} awards from {start_year}...")
        
        awards = []
        rows_per_request = 1000  # Maximum for awards API
        current_year = datetime.now().year
        
        for year in range(start_year, current_year + 1):
            self.logger.info(f"  Fetching {agency} awards for {year}...")
            year_start = 0
            year_awards = 0
            
            while True:
                params = {
                    'agency': agency,
                    'year': year,
                    'start': year_start,
                    'rows': rows_per_request,
                    'format': 'json'
                }
                
                data = self.make_api_request('awards', params)
                
                if not data or not isinstance(data, list):
                    break
                
                batch_awards = data
                if not batch_awards:
                    break
                
                # Filter for biotools relevance
                relevant_awards = []
                for award in batch_awards:
                    title = award.get('award_title', '')
                    abstract = award.get('abstract', '')
                    keywords = award.get('research_area_keywords', '') or ''
                    
                    combined_text = f"{title} {abstract} {keywords}"
                    
                    if self.is_biotools_relevant(combined_text):
                        award['relevance_score'] = self.calculate_biotools_relevance_score(title, abstract, keywords)
                        relevant_awards.append(award)
                
                awards.extend(relevant_awards)
                year_awards += len(batch_awards)
                self.logger.info(f"    Batch: {len(batch_awards)} total, {len(relevant_awards)} biotools-relevant")
                
                # If we got fewer results than requested, we're done with this year
                if len(batch_awards) < rows_per_request:
                    break
                
                year_start += rows_per_request
                time.sleep(2)  # Longer delays to be more respectful
            
            self.logger.info(f"  {agency} {year}: {year_awards} total awards processed")
        
        self.logger.info(f"✅ {agency}: Collected {len(awards)} biotools-relevant awards")
        return awards
    
    def fetch_open_solicitations(self) -> List[Dict]:
        """🔧 FIXED: API-compliant solicitations fetching following exact specifications"""
        self.logger.info("🔍 Fetching SBIR Solicitations (API Specification Compliant)")
        
        all_solicitations = []
        
        # Strategy 1: Direct open solicitations (API spec: max 50 rows, default 25)
        self.logger.info("  Strategy 1: Open solicitations (API limits)")
        try:
            # Try with API documented default limit first
            params = {
                'open': 1,
                'rows': 25,  # API documented default
                'format': 'json'
            }
            
            data = self.make_api_request('solicitations', params)
            if data and isinstance(data, list):
                self.logger.info(f"    ✅ Found {len(data)} open solicitations (25 rows)")
                all_solicitations.extend(data)
            else:
                self.logger.info("    ❌ No open solicitations found (25 rows)")
                
                # Try with maximum API limit
                self.logger.info("    🔄 Trying maximum API limit...")
                params['rows'] = 50  # API documented maximum
                
                data = self.make_api_request('solicitations', params)
                if data and isinstance(data, list):
                    self.logger.info(f"    ✅ Found {len(data)} open solicitations (50 rows)")
                    all_solicitations.extend(data)
                else:
                    self.logger.info("    ❌ No open solicitations found (50 rows)")
            
            time.sleep(3)  # Longer delay after solicitations requests
            
        except Exception as e:
            self.logger.warning(f"    ❌ Open solicitations strategy failed: {e}")
        
        # Strategy 2: Agency-specific open solicitations (API compliant)
        self.logger.info("  Strategy 2: Agency-specific open solicitations")
        biotools_agencies = ['HHS', 'NSF', 'DOD', 'DOE', 'NASA']
        
        for agency in biotools_agencies:
            try:
                params = {
                    'agency': agency,
                    'open': 1,
                    'rows': 25,  # Conservative API limit
                    'format': 'json'
                }
                
                data = self.make_api_request('solicitations', params)
                if data and isinstance(data, list):
                    self.logger.info(f"    ✅ {agency}: {len(data)} open solicitations")
                    all_solicitations.extend(data)
                else:
                    self.logger.info(f"    ❌ {agency}: No open solicitations")
                
                time.sleep(2)  # Respectful delay between agencies
                
            except Exception as e:
                self.logger.warning(f"    ❌ {agency} open solicitations failed: {e}")
        
        # Strategy 3: Keyword-based open solicitations (API compliant)
        self.logger.info("  Strategy 3: Keyword-based open solicitations")
        biotools_keywords = ['biotech', 'medical', 'diagnostic', 'laboratory', 'biosensor']
        
        for keyword in biotools_keywords:
            try:
                params = {
                    'keyword': keyword,
                    'open': 1,
                    'rows': 25,  # Conservative API limit
                    'format': 'json'
                }
                
                data = self.make_api_request('solicitations', params)
                if data and isinstance(data, list):
                    self.logger.info(f"    ✅ '{keyword}': {len(data)} open solicitations")
                    all_solicitations.extend(data)
                else:
                    self.logger.info(f"    ❌ '{keyword}': No open solicitations")
                
                time.sleep(1.5)  # Respectful delay between keywords
                
            except Exception as e:
                self.logger.warning(f"    ❌ Keyword '{keyword}' search failed: {e}")
        
        # Strategy 4: Recent solicitations without open filter (fallback, API compliant)
        if len(all_solicitations) == 0:
            self.logger.info("  Strategy 4: Recent solicitations (fallback)")
            try:
                params = {
                    'rows': 50,  # API documented maximum
                    'format': 'json'
                }
                
                data = self.make_api_request('solicitations', params)
                if data and isinstance(data, list):
                    self.logger.info(f"    ✅ Found {len(data)} recent solicitations")
                    # Filter for potentially open ones
                    potential_open = self._filter_potentially_open_solicitations(data)
                    self.logger.info(f"    📅 {len(potential_open)} appear to be open/recent")
                    all_solicitations.extend(potential_open)
                else:
                    self.logger.info("    ❌ No recent solicitations found")
                
            except Exception as e:
                self.logger.warning(f"    ❌ Recent solicitations failed: {e}")
        
        # Remove duplicates based on solicitation_number
        unique_solicitations = {}
        for sol in all_solicitations:
            sol_id = sol.get('solicitation_number') or sol.get('solicitation_id', '')
            if sol_id and sol_id not in unique_solicitations:
                unique_solicitations[sol_id] = sol
        
        unique_list = list(unique_solicitations.values())
        self.logger.info(f"  📊 Total unique solicitations: {len(unique_list)}")
        
        # Filter for biotools relevance
        relevant_solicitations = self._filter_biotools_solicitations(unique_list)
        
        self.logger.info(f"✅ Collected {len(relevant_solicitations)} biotools-relevant solicitations")
        
        if len(relevant_solicitations) == 0:
            self.logger.warning("⚠️  NO BIOTOOLS SOLICITATIONS FOUND")
            self.logger.warning("This could indicate:")
            self.logger.warning("  • No biotools solicitations currently open")
            self.logger.warning("  • API rate limiting after awards collection")
            self.logger.warning("  • Temporary API issues")
            self.logger.warning("  • Try running solicitations-only later")
        
        return relevant_solicitations
    
    def _filter_potentially_open_solicitations(self, solicitations: List[Dict]) -> List[Dict]:
        """Filter for solicitations that might be open based on status and dates"""
        potentially_open = []
        current_date = datetime.now()
        
        for sol in solicitations:
            # Check status
            status = sol.get('current_status', '').lower()
            if status in ['open', 'active', 'current']:
                potentially_open.append(sol)
                continue
            
            # Check close date
            close_date_str = sol.get('close_date', '')
            if close_date_str:
                try:
                    # Try to parse close date
                    if 'T' in close_date_str:
                        close_date = datetime.fromisoformat(close_date_str.replace('Z', '+00:00'))
                    else:
                        close_date = datetime.strptime(close_date_str.split('T')[0], '%Y-%m-%d')
                    
                    # If close date is in the future, consider it potentially open
                    if close_date > current_date:
                        potentially_open.append(sol)
                        
                except Exception:
                    # If we can't parse the date, include it to be safe
                    potentially_open.append(sol)
        
        return potentially_open
    
    def _filter_recent_solicitations(self, solicitations: List[Dict]) -> List[Dict]:
        """Filter solicitations to only include recent ones"""
        recent_solicitations = []
        cutoff_date = datetime.now() - timedelta(days=180)  # Last 6 months
        
        for sol in solicitations:
            is_recent = False
            
            # Check various date fields
            for date_field in ['close_date', 'open_date', 'release_date']:
                date_str = sol.get(date_field, '')
                if date_str:
                    try:
                        # Try to parse the date
                        if 'T' in date_str:  # ISO format
                            sol_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        else:  # Try common formats
                            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%B %d, %Y']:
                                try:
                                    sol_date = datetime.strptime(date_str, fmt)
                                    break
                                except ValueError:
                                    continue
                            else:
                                continue  # Couldn't parse date
                        
                        if sol_date >= cutoff_date:
                            is_recent = True
                            break
                            
                    except Exception:
                        continue
            
            # Also check if status indicates it's current
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
    
    def fetch_biotools_companies(self) -> List[Dict]:
        """Fetch companies with biotools-relevant awards"""
        self.logger.info("Fetching biotools-relevant companies...")
        
        companies = []
        
        # Search for companies using biotools keywords
        biotools_search_terms = [
            'diagnostic', 'biomarker', 'medical device', 'biosensor',
            'microfluidics', 'genomics', 'biotechnology', 'laboratory'
        ]
        
        for term in biotools_search_terms:
            self.logger.info(f"  Searching companies with keyword: {term}")
            
            start = 0
            rows_per_request = 1000  # API allows up to 5000
            
            while True:
                params = {
                    'keyword': term,
                    'start': start,
                    'rows': rows_per_request,
                    'format': 'json'
                }
                
                data = self.make_api_request('firm', params)
                
                if not data or not isinstance(data, list):
                    break
                
                batch_companies = data
                if not batch_companies:
                    break
                
                companies.extend(batch_companies)
                self.logger.info(f"    Found {len(batch_companies)} companies for '{term}'")
                
                if len(batch_companies) < rows_per_request:
                    break
                
                start += rows_per_request
                time.sleep(2)  # Respectful delay
        
        # Remove duplicates based on UEI
        unique_companies = {}
        for company in companies:
            uei = company.get('uei')
            if uei and uei not in unique_companies:
                unique_companies[uei] = company
        
        companies = list(unique_companies.values())
        self.logger.info(f"✅ Collected {len(companies)} unique biotools companies")
        return companies
    
    def save_awards(self, awards: List[Dict]) -> int:
        """Save awards to database with dynamic column mapping"""
        if not awards:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get the actual table structure
        cursor.execute("PRAGMA table_info(grants);")
        columns_info = cursor.fetchall()
        column_names = [col[1] for col in columns_info]
        
        saved_count = 0
        current_time = datetime.now().isoformat()
        
        for award in awards:
            try:
                # Create a mapping of our data to available columns
                award_data = {}
                
                # Basic fields
                award_data['funding_opportunity_number'] = f"SBIR-{award.get('agency', '')}-{award.get('contract', '')}"
                award_data['title'] = award.get('award_title', '')[:250]
                award_data['agency'] = award.get('agency', '')
                award_data['description'] = award.get('abstract', '')[:1000] if award.get('abstract') else ''
                award_data['keywords'] = award.get('research_area_keywords', '')
                award_data['url'] = award.get('award_link', '')
                
                # Amount fields
                amount = award.get('award_amount', 0)
                if amount:
                    try:
                        amount = int(float(str(amount)))
                    except:
                        amount = 0
                
                award_data['amount_min'] = 0
                award_data['amount_max'] = amount
                
                # SBIR-specific fields (only add if columns exist)
                if 'branch' in column_names:
                    award_data['branch'] = award.get('branch', '')
                if 'phase' in column_names:
                    award_data['phase'] = award.get('phase', '')
                if 'program' in column_names:
                    award_data['program'] = award.get('program', '')
                if 'award_year' in column_names:
                    award_data['award_year'] = award.get('award_year', None)
                if 'award_amount' in column_names:
                    award_data['award_amount'] = amount
                if 'contract_number' in column_names:
                    award_data['contract_number'] = award.get('contract', '')
                if 'company_name' in column_names:
                    award_data['company_name'] = award.get('firm', '')
                if 'company_city' in column_names:
                    award_data['company_city'] = award.get('city', '')
                if 'company_state' in column_names:
                    award_data['company_state'] = award.get('state', '')
                if 'company_uei' in column_names:
                    award_data['company_uei'] = award.get('uei', '')
                if 'company_duns' in column_names:
                    award_data['company_duns'] = award.get('duns', '')
                if 'company_address' in column_names:
                    award_data['company_address'] = award.get('address1', '')
                if 'company_zip' in column_names:
                    award_data['company_zip'] = award.get('zip', '')
                if 'poc_name' in column_names:
                    award_data['poc_name'] = award.get('poc_name', '')
                if 'pi_name' in column_names:
                    award_data['pi_name'] = award.get('pi_name', '')
                
                # Boolean fields
                if 'hubzone_owned' in column_names:
                    award_data['hubzone_owned'] = award.get('hubzone_owned') == 'Y'
                if 'socially_economically_disadvantaged' in column_names:
                    award_data['socially_economically_disadvantaged'] = award.get('socially_economically_disadvantaged') == 'Y'
                if 'women_owned' in column_names:
                    award_data['women_owned'] = award.get('women_owned') == 'Y'
                
                # Metadata fields
                if 'data_source' in column_names:
                    award_data['data_source'] = 'SBIR'
                if 'grant_type' in column_names:
                    award_data['grant_type'] = 'award'
                if 'biotools_category' in column_names:
                    award_data['biotools_category'] = 'biotools'
                if 'relevance_score' in column_names:
                    award_data['relevance_score'] = award.get('relevance_score', 0.0)
                if 'updated_at' in column_names:
                    award_data['updated_at'] = current_time
                if 'last_scraped_at' in column_names:
                    award_data['last_scraped_at'] = current_time
                
                # Build the SQL dynamically based on available columns
                available_fields = {k: v for k, v in award_data.items() if k in column_names}
                
                if not available_fields:
                    continue
                
                columns = list(available_fields.keys())
                values = list(available_fields.values())
                placeholders = ', '.join(['?' for _ in values])
                
                sql = f'''
                    INSERT OR REPLACE INTO grants ({', '.join(columns)})
                    VALUES ({placeholders})
                '''
                
                cursor.execute(sql, values)
                saved_count += 1
                
            except sqlite3.Error as e:
                self.logger.error(f"Database error saving award: {e}")
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"💾 Saved {saved_count} awards to database")
        return saved_count
    
    def save_solicitations(self, solicitations: List[Dict]) -> int:
        """Save solicitations to database with proper handling"""
        if not solicitations:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get the actual table structure
        cursor.execute("PRAGMA table_info(grants);")
        columns_info = cursor.fetchall()
        column_names = [col[1] for col in columns_info]
        
        saved_count = 0
        current_time = datetime.now().isoformat()
        
        for sol in solicitations:
            try:
                # Create a mapping for solicitation data
                sol_data = {}
                
                # Basic fields
                sol_data['funding_opportunity_number'] = f"SOL-{sol.get('solicitation_number', '')}"
                sol_data['title'] = sol.get('solicitation_title', '')[:250]
                sol_data['agency'] = sol.get('agency', '')
                sol_data['deadline'] = sol.get('close_date', '')
                sol_data['url'] = sol.get('solicitation_agency_url', '')
                
                # Extract description from topics
                topics_description = ""
                if 'solicitation_topics' in sol and sol['solicitation_topics']:
                    for topic in sol['solicitation_topics']:
                        if isinstance(topic, dict):
                            topics_description += f"{topic.get('topic_title', '')} {topic.get('topic_description', '')} "
                
                sol_data['description'] = topics_description[:1000] if topics_description else ''
                
                # SBIR-specific fields (only add if columns exist)
                if 'branch' in column_names:
                    sol_data['branch'] = sol.get('branch', '')
                if 'phase' in column_names:
                    sol_data['phase'] = sol.get('phase', '')
                if 'program' in column_names:
                    sol_data['program'] = sol.get('program', '')
                if 'current_status' in column_names:
                    sol_data['current_status'] = sol.get('current_status', '')
                if 'open_date' in column_names:
                    sol_data['open_date'] = sol.get('open_date', '')
                if 'close_date' in column_names:
                    sol_data['close_date'] = sol.get('close_date', '')
                if 'solicitation_topics' in column_names:
                    sol_data['solicitation_topics'] = json.dumps(sol.get('solicitation_topics', []))
                if 'solicitation_number' in column_names:
                    sol_data['solicitation_number'] = sol.get('solicitation_number', '')
                if 'solicitation_year' in column_names:
                    sol_data['solicitation_year'] = sol.get('solicitation_year', None)
                
                # Metadata fields
                if 'data_source' in column_names:
                    sol_data['data_source'] = 'SBIR'
                if 'grant_type' in column_names:
                    sol_data['grant_type'] = 'solicitation'
                if 'biotools_category' in column_names:
                    sol_data['biotools_category'] = 'biotools'
                if 'relevance_score' in column_names:
                    sol_data['relevance_score'] = sol.get('relevance_score', 0.0)
                if 'updated_at' in column_names:
                    sol_data['updated_at'] = current_time
                if 'last_scraped_at' in column_names:
                    sol_data['last_scraped_at'] = current_time
                
                # Build the SQL dynamically based on available columns
                available_fields = {k: v for k, v in sol_data.items() if k in column_names}
                
                if not available_fields:
                    continue
                
                columns = list(available_fields.keys())
                values = list(available_fields.values())
                placeholders = ', '.join(['?' for _ in values])
                
                sql = f'''
                    INSERT OR REPLACE INTO grants ({', '.join(columns)})
                    VALUES ({placeholders})
                '''
                
                cursor.execute(sql, values)
                saved_count += 1
                
            except sqlite3.Error as e:
                self.logger.error(f"Database error saving solicitation: {e}")
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"💾 Saved {saved_count} solicitations to database")
        return saved_count
    
    def save_companies(self, companies: List[Dict]) -> int:
        """Save companies to database - placeholder for future enhancement"""
        # For now, we'll focus on awards and solicitations
        # Companies can be added later as a separate table
        self.logger.info(f"Company data collection noted: {len(companies)} companies found")
        return 0
    
    def get_database_stats(self) -> Dict[str, int]:
        """Get current database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Total grants
        cursor.execute("SELECT COUNT(*) FROM grants")
        stats['total_grants'] = cursor.fetchone()[0]
        
        # By data source
        try:
            cursor.execute("SELECT data_source, COUNT(*) FROM grants WHERE data_source IS NOT NULL GROUP BY data_source")
            stats['by_source'] = cursor.fetchall()
        except sqlite3.OperationalError:
            stats['by_source'] = []
        
        # By agency
        cursor.execute("SELECT agency, COUNT(*) FROM grants GROUP BY agency ORDER BY COUNT(*) DESC")
        stats['by_agency'] = cursor.fetchall()
        
        # By grant type
        try:
            cursor.execute("SELECT grant_type, COUNT(*) FROM grants WHERE grant_type IS NOT NULL GROUP BY grant_type")
            stats['by_type'] = cursor.fetchall()
        except sqlite3.OperationalError:
            stats['by_type'] = []
        
        # Recent data (last 30 days)
        try:
            cursor.execute("SELECT COUNT(*) FROM grants WHERE last_scraped_at > date('now', '-30 days')")
            stats['recent_updates'] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            stats['recent_updates'] = 0
        
        # Biotools relevance
        try:
            cursor.execute("SELECT COUNT(*) FROM grants WHERE relevance_score > 0")
            stats['biotools_relevant'] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            stats['biotools_relevant'] = 0
        
        # Open solicitations
        try:
            cursor.execute("SELECT COUNT(*) FROM grants WHERE grant_type = 'solicitation' AND current_status = 'open'")
            stats['open_solicitations'] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            stats['open_solicitations'] = 0
        
        conn.close()
        return stats
    
    def run_full_scraping(self, start_year: int = 2020) -> Dict[str, int]:
        """Run complete SBIR/STTR data collection with enhanced solicitations handling"""
        self.logger.info("🚀 Starting SBIR/STTR Comprehensive Data Collection")
        self.logger.info("=" * 60)
        
        before_stats = self.get_database_stats()
        self.logger.info(f"📊 Before: {before_stats['total_grants']} total grants")
        
        total_added = {
            'awards': 0,
            'solicitations': 0,
            'companies': 0
        }
        
        # 1. Fetch Awards by Agency
        self.logger.info("\n" + "=" * 40)
        self.logger.info("🏆 COLLECTING AWARD DATA")
        
        # Key agencies for biotools funding
        agencies = ['HHS', 'NSF', 'DOD', 'DOE', 'NASA', 'EPA', 'USDA']
        
        for agency in agencies:
            try:
                awards = self.fetch_awards_by_agency(agency, start_year)
                saved = self.save_awards(awards)
                total_added['awards'] += saved
                
                # Longer delay between agencies to be more respectful
                time.sleep(5)
                
            except Exception as e:
                self.logger.error(f"Failed to process {agency} awards: {e}")
        
        # 2. Fetch Open Solicitations (with longer delay after awards)
        self.logger.info("\n" + "=" * 40)
        self.logger.info("📋 COLLECTING SOLICITATION DATA")
        self.logger.info("⏳ Waiting 10 seconds after awards collection for API recovery...")
        time.sleep(10)  # Give API time to recover after heavy awards collection
        
        try:
            solicitations = self.fetch_open_solicitations()
            saved = self.save_solicitations(solicitations)
            total_added['solicitations'] += saved
            
        except Exception as e:
            self.logger.error(f"Failed to process solicitations: {e}")
            self.logger.warning("💡 Try running 'python app/scraper.py solicitations' separately later")
        
        # 3. Fetch Companies (basic collection)
        self.logger.info("\n" + "=" * 40)
        self.logger.info("🏢 COLLECTING COMPANY DATA")
        
        try:
            companies = self.fetch_biotools_companies()
            saved = self.save_companies(companies)
            total_added['companies'] += saved
            
        except Exception as e:
            self.logger.error(f"Failed to process companies: {e}")
        
        # Final Statistics
        self.logger.info("\n" + "=" * 60)
        after_stats = self.get_database_stats()
        
        self.logger.info("📈 SCRAPING RESULTS:")
        self.logger.info(f"  Total grants: {before_stats['total_grants']} → {after_stats['total_grants']} (+{after_stats['total_grants'] - before_stats['total_grants']})")
        self.logger.info(f"  Awards added: {total_added['awards']}")
        self.logger.info(f"  Solicitations added: {total_added['solicitations']}")
        self.logger.info(f"  Companies processed: {total_added['companies']}")
        
        self.logger.info("\n📊 BREAKDOWN BY AGENCY:")
        for agency, count in after_stats['by_agency'][:10]:  # Top 10
            if agency:  # Skip null agencies
                self.logger.info(f"   {agency}: {count} grants")
        
        if after_stats.get('by_type'):
            self.logger.info("\n📊 BREAKDOWN BY TYPE:")
            for grant_type, count in after_stats['by_type']:
                self.logger.info(f"   {grant_type}: {count}")
        
        # Special handling for solicitations
        if total_added['solicitations'] == 0:
            self.logger.warning("\n⚠️  NO SOLICITATIONS COLLECTED")
            self.logger.warning("This is often due to API rate limiting after awards collection.")
            self.logger.warning("RECOMMENDED ACTIONS:")
            self.logger.warning("  1. Wait 30 minutes, then run: python app/scraper.py solicitations")
            self.logger.warning("  2. Check logs for specific errors")
            self.logger.warning("  3. Try manual API test: curl with proper headers")
        else:
            self.logger.info(f"\n🎉 Successfully collected {total_added['solicitations']} open solicitations!")
        
        total_new = sum(total_added.values())
        self.logger.info(f"\n✅ Total new records added: {total_new}")
        
        if total_new > 0:
            self.logger.info("🎉 SBIR/STTR database successfully expanded!")
            self.logger.info("📈 Your biotools grant matching system now includes:")
            self.logger.info("   • Historical award data for business development")
            if total_added['solicitations'] > 0:
                self.logger.info("   • Active solicitations for funding opportunities")
            self.logger.info("   • Enhanced search and matching capabilities")
        
        return total_added
    
    def run_solicitations_only(self) -> int:
        """Quick update of just open solicitations (for frequent updates)"""
        self.logger.info("🔄 Quick Update: Fetching Open Solicitations Only")
        
        try:
            solicitations = self.fetch_open_solicitations()
            saved = self.save_solicitations(solicitations)
            
            self.logger.info(f"✅ Updated {saved} solicitations")
            
            if saved == 0:
                self.logger.warning("⚠️  No solicitations found. This could be due to:")
                self.logger.warning("  • No biotools solicitations currently open")
                self.logger.warning("  • API rate limiting or temporary issues")
                self.logger.warning("  • Try again in 30 minutes")
            
            return saved
            
        except Exception as e:
            self.logger.error(f"Failed to update solicitations: {e}")
            return 0
    
    def run_recent_awards_only(self, months_back: int = 6) -> int:
        """Update only recent awards (for incremental updates)"""
        self.logger.info(f"🔄 Quick Update: Fetching Awards from Last {months_back} Months")
        
        # Calculate start year for recent data
        cutoff_date = datetime.now() - timedelta(days=months_back * 30)
        start_year = cutoff_date.year
        
        total_awards = 0
        agencies = ['HHS', 'NSF', 'DOD']  # Focus on key agencies for quick updates
        
        for agency in agencies:
            try:
                awards = self.fetch_awards_by_agency(agency, start_year)
                saved = self.save_awards(awards)
                total_awards += saved
                
            except Exception as e:
                self.logger.error(f"Failed to update {agency} awards: {e}")
        
        self.logger.info(f"✅ Updated {total_awards} recent awards")
        return total_awards
    
    def test_api_connectivity(self) -> Dict[str, bool]:
        """Test all API endpoints to verify connectivity"""
        self.logger.info("🔍 Testing SBIR API Connectivity...")
        
        test_results = {}
        
        # Test awards API
        try:
            data = self.make_api_request('awards', {'rows': 1})
            test_results['awards'] = data is not None and len(data) > 0
            self.logger.info(f"  Awards API: {'✅ Working' if test_results['awards'] else '❌ Failed'}")
        except Exception as e:
            test_results['awards'] = False
            self.logger.error(f"  Awards API: ❌ Failed - {e}")
        
        # Test solicitations API with API-compliant parameters
        try:
            data = self.make_api_request('solicitations', {'rows': 25})  # API compliant
            test_results['solicitations'] = data is not None and len(data) >= 0
            self.logger.info(f"  Solicitations API: {'✅ Working' if test_results['solicitations'] else '❌ Failed'}")
        except Exception as e:
            test_results['solicitations'] = False
            self.logger.error(f"  Solicitations API: ❌ Failed - {e}")
        
        # Test companies API
        try:
            data = self.make_api_request('firm', {'rows': 1})
            test_results['companies'] = data is not None and len(data) > 0
            self.logger.info(f"  Companies API: {'✅ Working' if test_results['companies'] else '❌ Failed'}")
        except Exception as e:
            test_results['companies'] = False
            self.logger.error(f"  Companies API: ❌ Failed - {e}")
        
        working_count = sum(test_results.values())
        self.logger.info(f"\n📊 API Status: {working_count}/3 endpoints working")
        
        if working_count == 3:
            self.logger.info("🎉 All APIs are working! Ready for full scraping.")
        elif working_count >= 2:
            self.logger.info("✅ Most APIs working. Proceed with caution.")
        else:
            self.logger.warning("⚠️  Multiple API issues detected. Check logs.")
        
        return test_results


def main():
    """Main execution function"""
    scraper = SBIRScraper()
    
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'full':
            # Full scraping (use for initial setup)
            start_year = int(sys.argv[2]) if len(sys.argv) > 2 else 2020
            scraper.run_full_scraping(start_year)
            
        elif command == 'solicitations':
            # Update only solicitations (daily)
            scraper.run_solicitations_only()
            
        elif command == 'recent':
            # Update only recent awards (weekly)
            months = int(sys.argv[2]) if len(sys.argv) > 2 else 6
            scraper.run_recent_awards_only(months)
            
        elif command == 'stats':
            # Show database statistics
            stats = scraper.get_database_stats()
            print("\n📊 SBIR Database Statistics:")
            print(f"  Total Grants: {stats['total_grants']}")
            print(f"  Biotools Relevant: {stats['biotools_relevant']}")
            print(f"  Recent Updates: {stats['recent_updates']}")
            print(f"  Open Solicitations: {stats['open_solicitations']}")
            
            if stats['by_agency']:
                print(f"\n📊 Grants by Agency:")
                for agency, count in stats['by_agency'][:10]:  # Top 10
                    if agency:
                        print(f"   {agency}: {count}")
            
            if stats['by_type']:
                print(f"\n📊 Grants by Type:")
                for grant_type, count in stats['by_type']:
                    print(f"   {grant_type}: {count}")
                    
        elif command == 'test':
            # Test API connectivity
            results = scraper.test_api_connectivity()
            if all(results.values()):
                print("\n🎉 All APIs are working! Ready to scrape.")
            elif sum(results.values()) >= 2:
                print("\n✅ Most APIs working. You can proceed.")
            else:
                print("\n⚠️ Multiple API issues detected. Check logs for details.")
            
        else:
            print("Usage:")
            print("  python app/scraper.py full [start_year]    # Full data collection")
            print("  python app/scraper.py solicitations       # Update solicitations only")
            print("  python app/scraper.py recent [months]     # Update recent awards")
            print("  python app/scraper.py stats               # Show database stats")
            print("  python app/scraper.py test                # Test API connectivity")
    else:
        # Default: run full scraping from 2020
        print("🚀 Starting default full scraping from 2020...")
        print("💡 Use 'python app/scraper.py test' to test APIs first")
        scraper.run_full_scraping(2020)


if __name__ == "__main__":
    main()