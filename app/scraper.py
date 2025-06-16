#!/usr/bin/env python3
"""
SBIR/STTR Focused Scraper - Comprehensive Data Collection
Replaces the previous scraper to focus entirely on SBIR/STTR data
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
        
        # Setup logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)
        
        self.setup_database()
        
        # Biotools-relevant keywords for filtering
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
    
    def setup_database(self):
        """Create enhanced database schema for SBIR/STTR data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # First, check if grants table exists and what columns it has
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
                'last_scraped_at': 'TEXT DEFAULT CURRENT_TIMESTAMP'
            }
            
            for column_name, column_def in new_columns.items():
                if column_name not in existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE grants ADD COLUMN {column_name} {column_def}")
                        self.logger.info(f"Added column: {column_name}")
                    except sqlite3.Error as e:
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
                    amount_min INTEGER,
                    amount_max INTEGER,
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
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_scraped_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        
        # Create solicitations table for active opportunities
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS solicitations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                solicitation_number TEXT UNIQUE,
                solicitation_title TEXT,
                agency TEXT,
                branch TEXT,
                program TEXT,
                phase TEXT,
                solicitation_year INTEGER,
                release_date DATE,
                open_date DATE,
                close_date DATE,
                application_due_date TEXT, -- JSON array of dates
                occurrence_number INTEGER,
                solicitation_agency_url TEXT,
                current_status TEXT,
                
                -- Topics (JSON field)
                topics TEXT, -- JSON array of topic objects
                
                -- Metadata
                biotools_relevant BOOLEAN DEFAULT 0,
                relevance_score REAL DEFAULT 0.0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create companies table for business development
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sbir_companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT,
                uei TEXT UNIQUE,
                duns TEXT,
                address1 TEXT,
                address2 TEXT,
                city TEXT,
                state TEXT,
                zip TEXT,
                company_url TEXT,
                hubzone_owned BOOLEAN,
                socially_economically_disadvantaged BOOLEAN,
                woman_owned BOOLEAN,
                number_awards INTEGER,
                sbir_profile_url TEXT,
                
                -- Analysis fields
                biotools_relevant BOOLEAN DEFAULT 0,
                potential_partner BOOLEAN DEFAULT 0,
                last_award_year INTEGER,
                total_award_amount INTEGER,
                
                -- Metadata
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for performance - but only for columns that exist
        # Check which columns actually exist before creating indexes
        cursor.execute("PRAGMA table_info(grants);")
        available_columns = {row[1] for row in cursor.fetchall()}
        
        potential_indexes = [
            ("idx_grants_agency", "agency"),
            ("idx_grants_phase", "phase"),
            ("idx_grants_award_year", "award_year"),
            ("idx_grants_biotools", "biotools_category"),
            ("idx_grants_updated", "updated_at")
        ]
        
        for index_name, column_name in potential_indexes:
            if column_name in available_columns:
                try:
                    cursor.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON grants({column_name})")
                    self.logger.info(f"Created index: {index_name}")
                except sqlite3.Error as e:
                    self.logger.warning(f"Could not create index {index_name}: {e}")
        
        # Create indexes for other tables
        other_indexes = [
            "CREATE INDEX IF NOT EXISTS idx_solicitations_status ON solicitations(current_status)",
            "CREATE INDEX IF NOT EXISTS idx_solicitations_close_date ON solicitations(close_date)",
            "CREATE INDEX IF NOT EXISTS idx_companies_awards ON sbir_companies(number_awards)",
            "CREATE INDEX IF NOT EXISTS idx_companies_state ON sbir_companies(state)"
        ]
        
        for index_sql in other_indexes:
            try:
                cursor.execute(index_sql)
            except sqlite3.Error as e:
                self.logger.warning(f"Could not create index: {e}")
        
        conn.commit()
        conn.close()
        self.logger.info("Database schema initialized/updated successfully")
    
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
    
    def make_api_request(self, endpoint: str, params: Dict[str, Any] = None, max_retries: int = 3) -> Optional[Dict]:
        """Make API request with retry logic"""
        url = f"{self.base_url}/{endpoint}"
        
        self.logger.info(f"    Making request to: {url}")
        self.logger.info(f"    Params: {params}")
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, timeout=30)
                
                self.logger.info(f"    Response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    self.logger.info(f"    Response type: {type(data)}, length: {len(data) if isinstance(data, list) else 'N/A'}")
                    return data
                elif response.status_code == 429:
                    # Rate limited, wait longer
                    wait_time = (attempt + 1) * 10
                    self.logger.warning(f"Rate limited, waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"API request failed: {response.status_code}")
                    self.logger.error(f"Response text: {response.text[:200]}")
                    return None
                    
            except Exception as e:
                self.logger.error(f"API request error (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)
        
        self.logger.error(f"Failed after {max_retries} attempts")
        return None
    
    def fetch_awards_by_agency(self, agency: str, start_year: int = 2020) -> List[Dict]:
        """Fetch awards from specific agency"""
        self.logger.info(f"Fetching {agency} awards from {start_year}...")
        
        awards = []
        start = 0
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
                
                self.logger.info(f"    API call: agency={agency}, year={year}, start={year_start}, rows={rows_per_request}")
                data = self.make_api_request('awards', params)
                
                self.logger.info(f"    API response: {type(data)}, length: {len(data) if isinstance(data, list) else 'N/A'}")
                
                if not data or 'results' not in data:
                    break
                
                batch_awards = data['results']
                if not batch_awards:
                    break
                
                # Filter for biotools relevance
                relevant_awards = []
                for award in batch_awards:
                    title = award.get('award_title', '')
                    abstract = award.get('abstract', '')
                    keywords = award.get('research_area_keywords', '')
                    
                    if self.is_biotools_relevant(f"{title} {abstract} {keywords}"):
                        award['relevance_score'] = self.calculate_biotools_relevance_score(title, abstract, keywords)
                        relevant_awards.append(award)
                
                awards.extend(relevant_awards)
                year_awards += len(batch_awards)  # Track total processed
                self.logger.info(f"    Batch: {len(batch_awards)} total, {len(relevant_awards)} biotools-relevant")
                
                # If we got fewer results than requested, we're done with this year
                if len(batch_awards) < rows_per_request:
                    self.logger.info(f"    End of data for {agency} {year} (got {len(batch_awards)} < {rows_per_request})")
                    break
                
                year_start += rows_per_request
                time.sleep(1)  # Be respectful to the API
            
            self.logger.info(f"  {agency} {year}: {year_awards} total awards processed")
        
        self.logger.info(f"✅ {agency}: Collected {len(awards)} biotools-relevant awards")
        return awards
    
    def fetch_open_solicitations(self) -> List[Dict]:
        """Fetch currently open solicitations"""
        self.logger.info("Fetching open solicitations...")
        
        solicitations = []
        start = 0
        rows_per_request = 50  # Maximum for solicitations API
        
        while True:
            params = {
                'open': 1,
                'start': start,
                'rows': rows_per_request,
                'format': 'json'
            }
            
            data = self.make_api_request('solicitations', params)
            
            if not data or 'results' not in data:
                break
            
            batch_solicitations = data['results']
            if not batch_solicitations:
                break
            
            # Filter for biotools relevance
            relevant_solicitations = []
            for sol in batch_solicitations:
                title = sol.get('solicitation_title', '')
                
                # Check topics for biotools relevance
                topics_text = ""
                if 'solicitation_topics' in sol and sol['solicitation_topics']:
                    for topic in sol['solicitation_topics']:
                        topics_text += f" {topic.get('topic_title', '')} {topic.get('topic_description', '')}"
                
                combined_text = f"{title} {topics_text}"
                
                if self.is_biotools_relevant(combined_text):
                    sol['relevance_score'] = self.calculate_biotools_relevance_score(title, topics_text)
                    relevant_solicitations.append(sol)
            
            solicitations.extend(relevant_solicitations)
            self.logger.info(f"  Batch: {len(batch_solicitations)} total, {len(relevant_solicitations)} biotools-relevant")
            
            if len(batch_solicitations) < rows_per_request:
                break
            
            start += rows_per_request
            time.sleep(1)
        
        self.logger.info(f"✅ Collected {len(solicitations)} relevant open solicitations")
        return solicitations
    
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
            rows_per_request = 1000
            
            while True:
                params = {
                    'keyword': term,
                    'start': start,
                    'rows': rows_per_request,
                    'format': 'json'
                }
                
                data = self.make_api_request('firm', params)
                
                if not data or 'results' not in data:
                    break
                
                batch_companies = data['results']
                if not batch_companies:
                    break
                
                companies.extend(batch_companies)
                self.logger.info(f"    Found {len(batch_companies)} companies for '{term}'")
                
                if len(batch_companies) < rows_per_request:
                    break
                
                start += rows_per_request
                time.sleep(1)
        
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
        """Save awards to database"""
        if not awards:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        saved_count = 0
        current_time = datetime.now().isoformat()
        
        for award in awards:
            try:
                # Map SBIR award fields to our schema
                funding_opportunity_number = f"SBIR-{award.get('agency', '')}-{award.get('contract', '')}"
                
                cursor.execute('''
                    INSERT OR REPLACE INTO grants (
                        funding_opportunity_number, title, agency, branch, phase, program,
                        description, keywords, amount_max, award_amount,
                        agency_tracking_number, contract_number, proposal_award_date,
                        contract_end_date, solicitation_number, solicitation_year,
                        topic_code, award_year,
                        company_name, company_uei, company_duns, company_address,
                        company_city, company_state, company_zip, company_url,
                        hubzone_owned, socially_economically_disadvantaged, women_owned,
                        number_employees, poc_name, poc_title, poc_phone, poc_email,
                        pi_name, pi_phone, pi_email, ri_name, ri_poc_name, ri_poc_phone,
                        url, data_source, grant_type, biotools_category, relevance_score,
                        updated_at, last_scraped_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    funding_opportunity_number,
                    award.get('award_title', ''),
                    award.get('agency', ''),
                    award.get('branch', ''),
                    award.get('phase', ''),
                    award.get('program', ''),
                    award.get('abstract', ''),
                    award.get('research_area_keywords', ''),
                    award.get('award_amount', 0),
                    award.get('award_amount', 0),
                    award.get('agency_tracking_number', ''),
                    award.get('contract', ''),
                    award.get('proposal_award_date', None),
                    award.get('contract_end_date', None),
                    award.get('solicitation_number', ''),
                    award.get('solicitation_year', None),
                    award.get('topic_code', ''),
                    award.get('award_year', None),
                    award.get('firm', ''),
                    award.get('uei', ''),
                    award.get('duns', ''),
                    award.get('address1', ''),
                    award.get('city', ''),
                    award.get('state', ''),
                    award.get('zip', ''),
                    award.get('company_url', ''),
                    award.get('hubzone_owned') == 'Y',
                    award.get('socially_economically_disadvantaged') == 'Y',
                    award.get('women_owned') == 'Y',
                    award.get('number_employees', None),
                    award.get('poc_name', ''),
                    award.get('poc_title', ''),
                    award.get('poc_phone', ''),
                    award.get('poc_email', ''),
                    award.get('pi_name', ''),
                    award.get('pi_phone', ''),
                    award.get('pi_email', ''),
                    award.get('ri_name', ''),
                    award.get('ri_poc_name', ''),
                    award.get('ri_poc_phone', ''),
                    award.get('award_link', ''),
                    'SBIR',
                    'award',
                    'biotools',
                    award.get('relevance_score', 0.0),
                    current_time,
                    current_time
                ))
                
                saved_count += 1
                
            except sqlite3.Error as e:
                self.logger.error(f"Database error saving award: {e}")
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"💾 Saved {saved_count} awards to database")
        return saved_count
    
    def save_solicitations(self, solicitations: List[Dict]) -> int:
        """Save solicitations to database"""
        if not solicitations:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        saved_count = 0
        current_time = datetime.now().isoformat()
        
        for sol in solicitations:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO solicitations (
                        solicitation_number, solicitation_title, agency, branch,
                        program, phase, solicitation_year, release_date, open_date,
                        close_date, application_due_date, occurrence_number,
                        solicitation_agency_url, current_status, topics,
                        biotools_relevant, relevance_score, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    sol.get('solicitation_number', '') or str(sol.get('solicitation_id', '')),
                    sol.get('solicitation_title', ''),
                    sol.get('agency', ''),
                    sol.get('branch', ''),
                    sol.get('program', ''),
                    sol.get('phase', ''),
                    sol.get('solicitation_year', None),
                    sol.get('release_date', None),
                    sol.get('open_date', None),
                    sol.get('close_date', None),
                    json.dumps(sol.get('application_due_date', [])),
                    sol.get('occurrence_number', None),
                    sol.get('solicitation_agency_url', ''),
                    sol.get('current_status', ''),
                    json.dumps(sol.get('solicitation_topics', [])),
                    True,  # biotools_relevant
                    sol.get('relevance_score', 0.0),
                    current_time
                ))
                
                saved_count += 1
                
            except sqlite3.Error as e:
                self.logger.error(f"Database error saving solicitation: {e}")
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"💾 Saved {saved_count} solicitations to database")
        return saved_count
    
    def save_companies(self, companies: List[Dict]) -> int:
        """Save companies to database"""
        if not companies:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        saved_count = 0
        current_time = datetime.now().isoformat()
        
        for company in companies:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO sbir_companies (
                        company_name, uei, duns, address1, address2, city, state, zip,
                        company_url, hubzone_owned, socially_economically_disadvantaged,
                        woman_owned, number_awards, sbir_profile_url, biotools_relevant,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    company.get('company_name', ''),
                    company.get('uei', ''),
                    company.get('duns', ''),
                    company.get('address1', ''),
                    company.get('address2', ''),
                    company.get('city', ''),
                    company.get('state', ''),
                    company.get('zip', ''),
                    company.get('company_url', ''),
                    company.get('hubzone_owned') == 'Y',
                    company.get('socially_economically_disadvantaged') == 'Y',
                    company.get('woman_owned') == 'Y',
                    company.get('number_awards', 0),
                    company.get('sbir_url', ''),
                    True,  # biotools_relevant
                    current_time
                ))
                
                saved_count += 1
                
            except sqlite3.Error as e:
                self.logger.error(f"Database error saving company: {e}")
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"💾 Saved {saved_count} companies to database")
        return saved_count
    
    def get_database_stats(self) -> Dict[str, int]:
        """Get current database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Total grants (awards)
        cursor.execute("SELECT COUNT(*) FROM grants WHERE grant_type = 'award'")
        stats['total_awards'] = cursor.fetchone()[0]
        
        # Total solicitations
        cursor.execute("SELECT COUNT(*) FROM solicitations")
        stats['total_solicitations'] = cursor.fetchone()[0]
        
        # Total companies
        cursor.execute("SELECT COUNT(*) FROM sbir_companies")
        stats['total_companies'] = cursor.fetchone()[0]
        
        # By agency
        cursor.execute("SELECT agency, COUNT(*) FROM grants GROUP BY agency ORDER BY COUNT(*) DESC")
        stats['by_agency'] = cursor.fetchall()
        
        # By phase
        cursor.execute("SELECT phase, COUNT(*) FROM grants GROUP BY phase ORDER BY COUNT(*) DESC")
        stats['by_phase'] = cursor.fetchall()
        
        # Recent awards (last 2 years)
        current_year = datetime.now().year
        cursor.execute("SELECT COUNT(*) FROM grants WHERE award_year >= ?", (current_year - 1,))
        stats['recent_awards'] = cursor.fetchone()[0]
        
        # Open solicitations
        cursor.execute("SELECT COUNT(*) FROM solicitations WHERE current_status = 'Open'")
        stats['open_solicitations'] = cursor.fetchone()[0]
        
        conn.close()
        return stats
    
    def run_full_scraping(self, start_year: int = 2020) -> Dict[str, int]:
        """Run complete SBIR/STTR data collection"""
        self.logger.info("🚀 Starting SBIR/STTR Comprehensive Data Collection")
        self.logger.info("=" * 60)
        
        before_stats = self.get_database_stats()
        self.logger.info(f"📊 Before: {before_stats['total_awards']} awards, {before_stats['total_solicitations']} solicitations, {before_stats['total_companies']} companies")
        
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
                
                # Small delay between agencies
                time.sleep(2)
                
            except Exception as e:
                self.logger.error(f"Failed to process {agency} awards: {e}")
        
        # 2. Fetch Open Solicitations
        self.logger.info("\n" + "=" * 40)
        self.logger.info("📋 COLLECTING SOLICITATION DATA")
        
        try:
            solicitations = self.fetch_open_solicitations()
            saved = self.save_solicitations(solicitations)
            total_added['solicitations'] += saved
            
        except Exception as e:
            self.logger.error(f"Failed to process solicitations: {e}")
        
        # 3. Fetch Companies
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
        self.logger.info(f"  Awards: {before_stats['total_awards']} → {after_stats['total_awards']} (+{total_added['awards']})")
        self.logger.info(f"  Solicitations: {before_stats['total_solicitations']} → {after_stats['total_solicitations']} (+{total_added['solicitations']})")
        self.logger.info(f"  Companies: {before_stats['total_companies']} → {after_stats['total_companies']} (+{total_added['companies']})")
        
        self.logger.info("\n📊 BREAKDOWN BY AGENCY:")
        for agency, count in after_stats['by_agency']:
            self.logger.info(f"   {agency}: {count} awards")
        
        self.logger.info("\n📊 BREAKDOWN BY PHASE:")
        for phase, count in after_stats['by_phase']:
            self.logger.info(f"   Phase {phase}: {count} awards")
        
        self.logger.info(f"\n✅ Total new records added: {sum(total_added.values())}")
        
        if sum(total_added.values()) > 0:
            self.logger.info("🎉 SBIR/STTR database successfully expanded!")
            self.logger.info("📈 Your biotools grant matching system now includes:")
            self.logger.info("   • Historical award data for business development")
            self.logger.info("   • Active solicitations for funding opportunities")
            self.logger.info("   • Company profiles for partnership analysis")
        
        return total_added
    
    def run_solicitations_only(self) -> int:
        """Quick update of just open solicitations (for frequent updates)"""
        self.logger.info("🔄 Quick Update: Fetching Open Solicitations Only")
        
        try:
            solicitations = self.fetch_open_solicitations()
            saved = self.save_solicitations(solicitations)
            
            self.logger.info(f"✅ Updated {saved} solicitations")
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
            print(f"  Total Awards: {stats['total_awards']}")
            print(f"  Total Solicitations: {stats['total_solicitations']}")
            print(f"  Total Companies: {stats['total_companies']}")
            print(f"  Recent Awards: {stats['recent_awards']}")
            print(f"  Open Solicitations: {stats['open_solicitations']}")
            
        else:
            print("Usage:")
            print("  python sbir_scraper.py full [start_year]    # Full data collection")
            print("  python sbir_scraper.py solicitations       # Update solicitations only")
            print("  python sbir_scraper.py recent [months]     # Update recent awards")
            print("  python sbir_scraper.py stats               # Show database stats")
    else:
        # Default: run full scraping from 2020
        scraper.run_full_scraping(2020)


if __name__ == "__main__":
    main()