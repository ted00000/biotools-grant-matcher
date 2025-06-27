#!/usr/bin/env python3
"""
Enhanced BioTools SBIR/STTR Scraper with Comprehensive Contact Information
Captures company details, contact information, and PI data for better grant details
"""

import requests
import sqlite3
from datetime import datetime, timedelta
import time
import os
import json
from typing import List, Dict, Any, Optional, Set
import logging
import re

class CompleteBiotoolsScraperWithContacts:
    def __init__(self, db_path="data/grants.db"):
        self.db_path = db_path
        self.base_url = "https://api.www.sbir.gov/public/api"
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Enhanced headers for better API access
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; BiotoolsResearchMatcher/2.0; +https://biotools.research.edu)',
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
        os.makedirs('logs', exist_ok=True)
        
        # Biotools agencies and programs (same as before)
        self.biotools_agencies = {
            'HHS': {
                'programs': ['SBIR', 'STTR', 'biomedical', 'health technology', 'medical device', 
                           'diagnostic', 'therapeutic', 'clinical', 'health surveillance'],
                'exclude_programs': ['social services', 'education', 'administration', 'policy'],
                'sub_agencies': ['NIH', 'CDC', 'FDA']
            },
            'DOD': {
                'programs': ['biological technologies', 'biotechnology', 'biodefense', 
                           'biological systems', 'bioengineering', 'medical countermeasures'],
                'exclude_programs': ['weapons systems', 'communications', 'transportation', 
                                   'cybersecurity', 'logistics'],
                'sub_agencies': ['DARPA', 'Navy', 'Army', 'Air Force']
            },
            'NSF': {
                'programs': ['biotechnology', 'biological sciences', 'bioengineering', 
                           'molecular biosciences', 'biological systems'],
                'exclude_programs': ['computer science', 'mathematics', 'physics', 'engineering'],
                'sub_agencies': ['BIO', 'ENG']
            },
            'DOE': {
                'programs': ['biological sciences', 'biotechnology', 'bioenergy', 
                           'environmental biology', 'systems biology'],
                'exclude_programs': ['nuclear', 'fossil', 'renewable energy', 'climate'],
                'sub_agencies': ['OBER']
            },
            'EPA': {
                'programs': ['environmental monitoring', 'biological monitoring', 'environmental health'],
                'exclude_programs': ['air quality', 'water quality', 'waste management'],
                'sub_agencies': []
            },
            'USDA': {
                'programs': ['agricultural biotechnology', 'food safety', 'plant biology'],
                'exclude_programs': ['farming', 'rural development', 'forestry'],
                'sub_agencies': ['NIFA']
            },
            'NASA': {
                'programs': ['astrobiology', 'life sciences', 'biological research'],
                'exclude_programs': ['space technology', 'aeronautics', 'planetary science'],
                'sub_agencies': []
            }
        }
        
        # Enhanced biotools keywords (same as before)
        self.biotools_keywords = {
            'instruments': [
                'microscope', 'microscopy', 'spectrometer', 'spectrometry', 'sequencer', 'sequencing',
                'cytometer', 'flow cytometry', 'mass spectrometry', 'chromatography', 'electrophoresis',
                'imaging system', 'detection system', 'analytical instrument', 'laboratory instrument'
            ],
            'genomics': [
                'DNA sequencing', 'RNA sequencing', 'genome sequencing', 'genomic analysis',
                'CRISPR', 'gene editing', 'genetic engineering', 'genomics platform', 
                'next-generation sequencing', 'single-cell sequencing', 'spatial genomics',
                'epigenomics', 'metagenomics', 'transcriptomics', 'whole genome sequencing'
            ],
            'cell_biology': [
                'cell analysis', 'cellular imaging', 'live cell imaging', 'cell sorting',
                'cell culture', 'cell isolation', 'single cell analysis', 'cell counting',
                'cell viability', 'cell-based assays', 'cellular characterization',
                'organoid', 'spheroid', 'tissue engineering', 'stem cell', 'cell line development'
            ],
            'proteomics': [
                'protein analysis', 'protein identification', 'protein quantification', 'proteomics',
                'peptide analysis', 'enzyme assays', 'biochemical analysis', 'immunoassays',
                'protein purification', 'protein characterization', 'western blotting',
                'protein-protein interactions', 'structural biology tools'
            ],
            'bioinformatics': [
                'bioinformatics software', 'computational biology tools', 'sequence analysis',
                'phylogenetic analysis', 'structural bioinformatics', 'systems biology',
                'biological databases', 'genomic data analysis', 'protein modeling',
                'machine learning biology', 'AI drug discovery', 'computational genomics'
            ],
            'lab_equipment': [
                'laboratory automation', 'bioanalytical instruments', 'clinical diagnostics',
                'point-of-care testing', 'medical diagnostics', 'biological sensors',
                'laboratory equipment', 'analytical instrumentation', 'robotic liquid handling',
                'high-throughput screening', 'automated cell culture'
            ],
            'specialized': [
                'spatial biology', 'spatial transcriptomics', 'tissue imaging', 'pathology imaging',
                'drug discovery platforms', 'pharmaceutical research', 'biomarker discovery',
                'clinical laboratory tools', 'diagnostic testing', 'therapeutic development',
                'personalized medicine', 'precision medicine tools'
            ]
        }
        
        # Compound keyword validation (multi-word biotools terms)
        self.compound_keywords = [
            'lab-on-chip', 'point-of-care', 'high-throughput screening', 'single-cell analysis',
            'next-generation sequencing', 'mass spectrometry', 'flow cytometry', 'western blot',
            'CRISPR-Cas9', 'gene editing', 'protein purification', 'cell sorting',
            'tissue engineering', 'organ-on-chip', 'synthetic biology', 'systems biology',
            'computational biology', 'structural biology', 'molecular biology', 'cell biology',
            'biomedical engineering', 'laboratory automation', 'clinical diagnostics'
        ]
        
        self.init_database()
        
        # Company data cache for linking awards to companies
        self.company_cache = {}
    
    def init_database(self):
        """Initialize database with comprehensive schema including contact information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Drop existing table if it exists with old schema to avoid conflicts
            cursor.execute("DROP TABLE IF EXISTS grants")
            cursor.execute("DROP TABLE IF EXISTS companies")
            
            # Create comprehensive grants table with contact information
            cursor.execute('''
                CREATE TABLE grants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    abstract TEXT,
                    agency TEXT,
                    program TEXT,
                    award_number TEXT UNIQUE,
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
                    
                    -- Contact Information
                    poc_name TEXT,
                    poc_title TEXT,
                    poc_phone TEXT,
                    poc_email TEXT,
                    pi_phone TEXT,
                    pi_email TEXT,
                    ri_poc_name TEXT,
                    ri_poc_phone TEXT,
                    
                    -- Company Information
                    company_name TEXT,
                    company_url TEXT,
                    address1 TEXT,
                    address2 TEXT,
                    city TEXT,
                    state TEXT,
                    zip_code TEXT,
                    uei TEXT,
                    duns TEXT,
                    number_awards INTEGER,
                    hubzone_owned TEXT,
                    socially_economically_disadvantaged TEXT,
                    woman_owned TEXT,
                    
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create companies table for comprehensive company data
            cursor.execute('''
                CREATE TABLE companies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uei TEXT UNIQUE,
                    company_name TEXT,
                    duns TEXT,
                    number_awards INTEGER,
                    address1 TEXT,
                    address2 TEXT,
                    city TEXT,
                    state TEXT,
                    zip_code TEXT,
                    company_url TEXT,
                    hubzone_owned TEXT,
                    socially_economically_disadvantaged TEXT,
                    woman_owned TEXT,
                    last_updated TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            self.logger.info("Tables created successfully")
            
            # Create indexes for performance (after tables are created)
            try:
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_grants_title ON grants(title)",
                    "CREATE INDEX IF NOT EXISTS idx_grants_agency ON grants(agency)",
                    "CREATE INDEX IF NOT EXISTS idx_grants_relevance ON grants(relevance_score)",
                    "CREATE INDEX IF NOT EXISTS idx_grants_biotools_category ON grants(biotools_category)",
                    "CREATE INDEX IF NOT EXISTS idx_grants_confidence ON grants(confidence_score)",
                    "CREATE INDEX IF NOT EXISTS idx_grants_company_name ON grants(company_name)",
                    "CREATE INDEX IF NOT EXISTS idx_grants_uei ON grants(uei)",
                    "CREATE INDEX IF NOT EXISTS idx_companies_uei ON companies(uei)",
                    "CREATE INDEX IF NOT EXISTS idx_companies_name ON companies(company_name)"
                ]
                
                for index_sql in indexes:
                    try:
                        cursor.execute(index_sql)
                    except sqlite3.OperationalError as e:
                        self.logger.warning(f"Could not create index: {index_sql} - {e}")
                        continue
            except Exception as e:
                self.logger.warning(f"Error creating indexes: {e}")
            
            conn.commit()
            self.logger.info("Database initialized with comprehensive contact information schema")
            
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
            conn.rollback()
        finally:
            conn.close()

    def calculate_biotools_relevance(self, title: str, abstract: str = "", program: str = "") -> tuple:
        """Calculate comprehensive biotools relevance with confidence scoring"""
        text = f"{title} {abstract} {program}".lower()
        
        # Exclude space/aerospace terms immediately
        space_terms = ['space', 'satellite', 'orbital', 'spacecraft', 'space station', 'astronaut', 'rocket', 'launch']
        if any(term in text for term in space_terms):
            return (0.0, 0.0, [], [], [])
        
        relevance_score = 0.0
        confidence_score = 0.0
        matched_categories = set()
        matched_keywords = []
        compound_matches = []
        
        # 1. Check compound keywords first (highest confidence) - must be biological
        biological_compounds = [
            'DNA sequencing', 'RNA sequencing', 'protein analysis', 'cell culture',
            'gene editing', 'CRISPR', 'flow cytometry', 'mass spectrometry',
            'single-cell analysis', 'tissue engineering', 'biomarker detection'
        ]
        for compound in biological_compounds:
            if compound.lower() in text:
                compound_matches.append(compound)
                relevance_score += 4.0
                confidence_score += 3.0
        
        # 2. Require explicit biological context for other terms
        has_biological_context = any(bio_term in text for bio_term in [
            'biolog', 'gene', 'dna', 'rna', 'protein', 'cell', 'tissue', 'enzyme',
            'antibody', 'molecular', 'genomic', 'proteomic', 'biomedical', 'clinical',
            'diagnostic', 'therapeutic', 'pharmaceutical', 'biotech', 'life science'
        ])
        
        if not has_biological_context:
            return (0.0, 0.0, [], [], [])
        
        # 3. Check category-based keywords (only if biological context exists)
        for category, keywords in self.biotools_keywords.items():
            category_matches = 0
            for keyword in keywords:
                if keyword.lower() in text:
                    matched_keywords.append(keyword)
                    matched_categories.add(category)
                    category_matches += 1
                    
                    # Weight by category importance
                    if category == 'instruments':
                        relevance_score += 2.0
                        confidence_score += 1.5
                    elif category in ['genomics', 'cell_biology', 'proteomics']:
                        relevance_score += 3.0
                        confidence_score += 2.0
                    elif category in ['bioinformatics', 'lab_equipment']:
                        relevance_score += 1.5
                        confidence_score += 1.0
                    else:
                        relevance_score += 1.0
                        confidence_score += 0.8
            
            # Bonus for multiple matches in same category
            if category_matches > 1:
                relevance_score += category_matches * 0.3
                confidence_score += category_matches * 0.2
        
        # 4. Bonus for multiple category matches
        if len(matched_categories) > 1:
            relevance_score += len(matched_categories) * 0.5
            confidence_score += len(matched_categories) * 0.3
        
        # 5. Cap scores
        relevance_score = min(relevance_score, 10.0)
        confidence_score = min(confidence_score, 10.0)
        
        return (
            relevance_score, 
            confidence_score, 
            list(matched_categories), 
            matched_keywords, 
            compound_matches
        )

    def is_biotools_relevant(self, title: str, abstract: str = "", program: str = "") -> bool:
        """Enhanced biotools relevance check"""
        relevance_score, confidence_score, _, _, _ = self.calculate_biotools_relevance(title, abstract, program)
        return relevance_score >= 1.5 and confidence_score >= 1.0

    def calculate_agency_alignment(self, agency: str, program: str, title: str, abstract: str) -> float:
        """Calculate how well the grant aligns with agency's biotools focus"""
        if agency not in self.biotools_agencies:
            return 1.0
        
        agency_config = self.biotools_agencies[agency]
        text = f"{program} {title} {abstract}".lower()
        
        alignment_score = 0.0
        
        # Check for relevant programs
        for relevant_program in agency_config['programs']:
            if relevant_program.lower() in text:
                alignment_score += 1.0
        
        # Check for excluded programs (negative score)
        for excluded_program in agency_config['exclude_programs']:
            if excluded_program.lower() in text:
                alignment_score -= 0.5
        
        # Bonus for sub-agency alignment
        for sub_agency in agency_config['sub_agencies']:
            if sub_agency.lower() in text:
                alignment_score += 0.5
        
        return max(0.0, min(alignment_score, 5.0))

    def make_api_request(self, endpoint: str, params: Dict[str, Any] = None, max_retries: int = 3) -> Optional[List]:
        """Enhanced API request with proper error handling"""
        if endpoint == "solicitations":
            url = "https://api.www.sbir.gov/public/api/solicitations"
        elif endpoint == "firm":
            url = "https://api.www.sbir.gov/public/api/firm"
        else:
            url = f"{self.base_url}/{endpoint}"

        if params is None:
            params = {}

        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url,
                    headers=self.headers,
                    params=params,
                    timeout=30
                )
                
                self.logger.debug(f"API request: {response.url} → {response.status_code}")

                if response.status_code == 200:
                    try:
                        data = response.json()
                        return data if isinstance(data, list) else []
                    except json.JSONDecodeError as e:
                        self.logger.error(f"JSON decode error: {e}")
                        return None

                if response.status_code in (403, 404):
                    self.logger.warning(f"{response.status_code} for {response.url}")
                    return None

                if response.status_code == 429:
                    wait = (attempt + 1) * 15
                    self.logger.warning(f"429 rate limit — retrying in {wait}s")
                    time.sleep(wait)
                    continue

                self.logger.error(f"Unknown status {response.status_code} at {response.url}")
                return None

            except requests.RequestException as e:
                self.logger.error(f"Request exception on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(10)

        self.logger.error("Max retries exceeded")
        return None

    def fetch_company_data(self) -> Dict[str, Dict]:
        """Fetch comprehensive company data and cache it"""
        self.logger.info("Fetching comprehensive company data...")
        
        companies = {}
        rows_per_request = 1000
        start = 0
        
        while True:
            params = {
                'start': start,
                'rows': rows_per_request,
                'format': 'json'
            }
            
            try:
                data = self.make_api_request('firm', params)
                
                if not data or len(data) == 0:
                    break
                
                for company in data:
                    uei = company.get('uei')
                    if uei:
                        companies[uei] = company
                        
                        # Also index by company name for fallback matching
                        company_name = company.get('company_name', '').strip()
                        if company_name:
                            companies[company_name.lower()] = company
                
                self.logger.info(f"Fetched {len(data)} companies (total cached: {len(companies)})")
                
                if len(data) < rows_per_request:
                    break
                    
                start += rows_per_request
                time.sleep(2)  # Rate limiting
                
            except Exception as e:
                self.logger.error(f"Error fetching company data: {e}")
                break
        
        self.company_cache = companies
        self.logger.info(f"Company data cache built with {len(companies)} entries")
        return companies

    def get_company_info(self, firm_name: str = None, uei: str = None) -> Dict[str, Any]:
        """Get company information from cache"""
        if not self.company_cache:
            self.fetch_company_data()
        
        # Try UEI first (most reliable)
        if uei and uei in self.company_cache:
            return self.company_cache[uei]
        
        # Fallback to company name matching
        if firm_name:
            firm_lower = firm_name.lower().strip()
            if firm_lower in self.company_cache:
                return self.company_cache[firm_lower]
            
            # Fuzzy matching for similar company names
            for cached_name, company_data in self.company_cache.items():
                if isinstance(cached_name, str) and len(cached_name) > 10:  # Skip UEI keys
                    if firm_lower in cached_name or cached_name in firm_lower:
                        return company_data
        
        return {}

    def fetch_enhanced_awards_by_agency(self, agency: str, start_year: int = 2022) -> List[Dict]:
        """Enhanced award fetching with comprehensive contact and company information"""
        self.logger.info(f"Fetching enhanced {agency} awards with contact info from {start_year}...")
        
        # Ensure company data is loaded
        if not self.company_cache:
            self.fetch_company_data()
        
        awards = []
        rows_per_request = 1000
        current_year = datetime.now().year
        
        for year in range(start_year, current_year + 1):
            self.logger.info(f"  Processing {agency} {year}...")
            year_start = 0
            year_biotools_count = 0
            year_total_count = 0
            
            while True:
                params = {
                    'agency': agency,
                    'year': year,
                    'start': year_start,
                    'rows': rows_per_request,
                    'format': 'json'
                }
                
                try:
                    data = self.make_api_request('awards', params)
                    
                    if not data or len(data) == 0:
                        break
                    
                    year_total_count += len(data)
                    
                    for award in data:
                        title = award.get('award_title', '')
                        abstract = award.get('abstract', '')
                        program = award.get('program', '')
                        
                        # Enhanced relevance calculation
                        relevance_score, confidence_score, categories, keywords, compounds = \
                            self.calculate_biotools_relevance(title, abstract, program)
                        
                        if relevance_score >= 1.5:
                            # Calculate agency alignment
                            agency_alignment = self.calculate_agency_alignment(
                                agency, program, title, abstract
                            )
                            
                            # Get company information
                            firm_name = award.get('firm', '')
                            uei = award.get('uei', '')
                            company_info = self.get_company_info(firm_name, uei)
                            
                            # Enhanced award data with contact information
                            award['relevance_score'] = relevance_score
                            award['confidence_score'] = confidence_score
                            award['biotools_category'] = ','.join(categories) if categories else ''
                            award['compound_keyword_matches'] = ','.join(compounds) if compounds else ''
                            award['agency_alignment_score'] = agency_alignment
                            
                            # Add company information to award
                            if company_info:
                                award['company_name'] = company_info.get('company_name', firm_name)
                                award['company_url'] = company_info.get('company_url', '')
                                award['address1'] = company_info.get('address1', '')
                                award['address2'] = company_info.get('address2', '')
                                award['city'] = company_info.get('city', '')
                                award['state'] = company_info.get('state', '')
                                award['zip_code'] = company_info.get('zip', '')
                                award['uei'] = company_info.get('uei', uei)
                                award['duns'] = company_info.get('duns', '')
                                award['number_awards'] = company_info.get('number_awards', 0)
                                award['hubzone_owned'] = company_info.get('hubzone_owned', '')
                                award['socially_economically_disadvantaged'] = company_info.get('socially_economically_disadvantaged', '')
                                award['woman_owned'] = company_info.get('woman_owned', '')
                            
                            awards.append(award)
                            year_biotools_count += 1
                    
                    # Respectful delay
                    time.sleep(2)
                    
                    if len(data) < rows_per_request:
                        break
                    
                    year_start += rows_per_request
                    
                except Exception as e:
                    self.logger.error(f"Error fetching {agency} {year} awards: {e}")
                    break
            
            # Respectful delay between years
            time.sleep(1)
            
            relevance_rate = (year_biotools_count / year_total_count * 100) if year_total_count > 0 else 0
            self.logger.info(f"  {agency} {year}: {year_biotools_count}/{year_total_count} biotools-relevant ({relevance_rate:.1f}%)")
        
        self.logger.info(f"✅ {agency}: Collected {len(awards)} enhanced biotools-relevant awards with contact info")
        return awards

    def save_enhanced_awards(self, awards: List[Dict]) -> int:
        """Save enhanced awards with comprehensive contact and company data"""
        if not awards:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        saved_count = 0
        
        for award in awards:
            try:
                # Extract and clean enhanced data
                title = award.get('award_title', '')[:500]
                description = award.get('description', '')[:5000] if award.get('description') else ''  # Increased from 2000
                abstract = award.get('abstract', '')[:5000] if award.get('abstract') else ''  # Increased from 2000
                agency = award.get('agency', '')
                program = award.get('program', '')
                award_number = award.get('award_number', '')
                firm = award.get('firm', '')
                pi = award.get('principal_investigator', '')
                
                # Handle amount
                amount = 0
                if award.get('award_amount'):
                    try:
                        amount_str = str(award['award_amount']).replace(',', '').replace('$', '')
                        amount = int(float(amount_str))
                    except (ValueError, TypeError):
                        amount = 0
                
                award_date = award.get('award_date', '')
                end_date = award.get('end_date', '')
                phase = award.get('phase', '')
                keywords = award.get('keywords', '')
                
                # Enhanced scoring data
                relevance_score = award.get('relevance_score', 0.0)
                confidence_score = award.get('confidence_score', 0.0)
                biotools_category = award.get('biotools_category', '')
                compound_matches = award.get('compound_keyword_matches', '')
                agency_alignment = award.get('agency_alignment_score', 0.0)
                url = award.get('url', '')
                
                # Contact information
                poc_name = award.get('poc_name', '')
                poc_title = award.get('poc_title', '')
                poc_phone = award.get('poc_phone', '')
                poc_email = award.get('poc_email', '')
                pi_phone = award.get('pi_phone', '')
                pi_email = award.get('pi_email', '')
                ri_poc_name = award.get('ri_poc_name', '')
                ri_poc_phone = award.get('ri_poc_phone', '')
                
                # Company information
                company_name = award.get('company_name', firm)
                company_url = award.get('company_url', '')
                address1 = award.get('address1', '')
                address2 = award.get('address2', '')
                city = award.get('city', '')
                state = award.get('state', '')
                zip_code = award.get('zip_code', '')
                uei = award.get('uei', '')
                duns = award.get('duns', '')
                number_awards = award.get('number_awards', 0)
                hubzone_owned = award.get('hubzone_owned', '')
                socially_economically_disadvantaged = award.get('socially_economically_disadvantaged', '')
                woman_owned = award.get('woman_owned', '')
                
                # Insert enhanced award with contact information (43 columns total)
                cursor.execute('''
                    INSERT OR REPLACE INTO grants 
                    (title, description, abstract, agency, program, award_number, firm, 
                     principal_investigator, amount, award_date, end_date, phase, keywords, 
                     source, grant_type, relevance_score, confidence_score, biotools_category,
                     compound_keyword_matches, agency_alignment_score, url,
                     poc_name, poc_title, poc_phone, poc_email, pi_phone, pi_email,
                     ri_poc_name, ri_poc_phone, company_name, company_url, address1, address2,
                     city, state, zip_code, uei, duns, number_awards, hubzone_owned,
                     socially_economically_disadvantaged, woman_owned, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    title, description, abstract, agency, program, award_number, firm,
                    pi, amount, award_date, end_date, phase, keywords,
                    'SBIR', 'award', relevance_score, confidence_score, biotools_category,
                    compound_matches, agency_alignment, url,
                    poc_name, poc_title, poc_phone, poc_email, pi_phone, pi_email,
                    ri_poc_name, ri_poc_phone, company_name, company_url, address1, address2,
                    city, state, zip_code, uei, duns, number_awards, hubzone_owned,
                    socially_economically_disadvantaged, woman_owned, datetime.now().isoformat()
                ))
                
                saved_count += 1
                
            except Exception as e:
                award_id = award.get('award_number', award.get('award_title', 'unknown'))
                self.logger.error(f"Error saving award {award_id}: {e}")
                self.logger.debug(f"Award data keys: {list(award.keys())}")
                continue
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"💾 Saved {saved_count} enhanced awards with contact info to database")
        return saved_count

    def run_comprehensive_biotools_scraping(self, start_year: int = 2022) -> Dict[str, Any]:
        """Run comprehensive biotools data collection with contact information"""
        self.logger.info("🚀 Starting Comprehensive BioTools Data Collection with Contact Information")
        self.logger.info("=" * 70)
        
        # Pre-load company data for faster processing
        self.logger.info("📋 Pre-loading company data...")
        self.fetch_company_data()
        
        before_stats = self.get_database_stats()
        self.logger.info(f"📊 Before: {before_stats.get('total_grants', 0)} total grants, {before_stats.get('biotools_validated', 0)} biotools-validated")
        
        total_added = {
            'awards': 0,
            'solicitations': 0,
            'successful_agencies': [],
            'failed_agencies': [],
            'precision_metrics': {}
        }
        
        # 1. Enhanced Awards Collection with Contact Information
        self.logger.info("\n" + "=" * 40)
        self.logger.info("🏆 ENHANCED AWARD COLLECTION WITH CONTACTS")
        
        for agency in self.biotools_agencies.keys():
            try:
                self.logger.info(f"\nProcessing {agency} with enhanced contact filtering...")
                awards = self.fetch_enhanced_awards_by_agency(agency, start_year)
                saved = self.save_enhanced_awards(awards)
                total_added['awards'] += saved
                total_added['successful_agencies'].append(agency)
                
                # Inter-agency delay for API respect
                time.sleep(5)
                
            except Exception as e:
                self.logger.error(f"Failed to process {agency} awards: {e}")
                total_added['failed_agencies'].append(agency)
        
        # 2. Enhanced Solicitations Collection (same as before but with contact fields ready)
        self.logger.info("\n" + "=" * 40)
        self.logger.info("📋 ENHANCED SOLICITATION COLLECTION")
        self.logger.info("⏳ Waiting 10 seconds for API recovery...")
        time.sleep(10)
        
        try:
            solicitations = self.fetch_enhanced_solicitations()
            saved = self.save_enhanced_solicitations(solicitations)
            total_added['solicitations'] += saved
            
        except Exception as e:
            self.logger.error(f"Failed to process solicitations: {e}")
        
        # 3. Quality Assessment
        self.logger.info("\n" + "=" * 40)
        self.logger.info("🎯 QUALITY ASSESSMENT WITH CONTACT DATA")
        
        after_stats = self.get_database_stats()
        
        # Calculate precision metrics
        precision_metrics = {
            'biotools_validated_rate': (after_stats.get('biotools_validated', 0) / max(after_stats.get('total_grants', 1), 1)) * 100,
            'avg_relevance_score': after_stats.get('avg_relevance_score', 0),
            'avg_confidence_score': after_stats.get('avg_confidence_score', 0),
            'avg_agency_alignment': after_stats.get('avg_agency_alignment', 0),
            'contamination_rate': (after_stats.get('contaminated_records', 0) / max(after_stats.get('total_grants', 1), 1)) * 100,
            'compound_keyword_coverage': (after_stats.get('compound_keyword_matches', 0) / max(after_stats.get('total_grants', 1), 1)) * 100,
            'contact_coverage_rate': (after_stats.get('grants_with_contact_info', 0) / max(after_stats.get('total_grants', 1), 1)) * 100
        }
        
        total_added['precision_metrics'] = precision_metrics
        
        # 4. Final Summary
        self.logger.info("\n" + "=" * 60)
        self.logger.info("🎉 COMPREHENSIVE COLLECTION WITH CONTACTS COMPLETE!")
        self.logger.info("=" * 60)
        self.logger.info(f"📊 Enhanced awards collected: {total_added['awards']}")
        self.logger.info(f"📋 Enhanced solicitations collected: {total_added['solicitations']}")
        self.logger.info(f"✅ Successful agencies: {len(total_added['successful_agencies'])}")
        self.logger.info(f"❌ Failed agencies: {len(total_added['failed_agencies'])}")
        self.logger.info(f"🎯 Biotools validation rate: {precision_metrics['biotools_validated_rate']:.1f}%")
        self.logger.info(f"📞 Contact info coverage: {precision_metrics['contact_coverage_rate']:.1f}%")
        self.logger.info(f"📈 Avg relevance score: {precision_metrics['avg_relevance_score']:.2f}")
        
        return total_added

    def fetch_enhanced_solicitations(self) -> List[Dict]:
        """Enhanced solicitation fetching with biotools focus"""
        self.logger.info("Fetching enhanced biotools solicitations...")
        
        solicitations = []
        max_rows = 50
        start = 0
        
        while True:
            params = {
                'start': start,
                'rows': max_rows,
                'format': 'json'
            }
            
            try:
                data = self.make_api_request('solicitations', params)
                
                if not data or len(data) == 0:
                    break
                
                biotools_solicitations = []
                for solicitation in data:
                    title = solicitation.get('solicitation_title', '')
                    description = solicitation.get('description', '')
                    agency = solicitation.get('agency', '')
                    program = solicitation.get('program', '')
                    
                    # Enhanced relevance calculation
                    relevance_score, confidence_score, categories, keywords, compounds = \
                        self.calculate_biotools_relevance(title, description, program)
                    
                    if relevance_score >= 1.0:
                        # Calculate agency alignment
                        agency_alignment = self.calculate_agency_alignment(
                            agency, program, title, description
                        )
                        
                        solicitation['relevance_score'] = relevance_score
                        solicitation['confidence_score'] = confidence_score
                        solicitation['biotools_category'] = ','.join(categories) if categories else ''
                        solicitation['compound_keyword_matches'] = ','.join(compounds) if compounds else ''
                        solicitation['agency_alignment_score'] = agency_alignment
                        
                        biotools_solicitations.append(solicitation)
                
                solicitations.extend(biotools_solicitations)
                self.logger.info(f"  Found {len(biotools_solicitations)} biotools solicitations (total: {len(data)})")
                
                # Rate limiting
                time.sleep(3)
                
                if len(data) < max_rows:
                    break
                
                start += max_rows
                
            except Exception as e:
                self.logger.error(f"Error fetching solicitations: {e}")
                break
        
        self.logger.info(f"✅ Collected {len(solicitations)} enhanced biotools solicitations")
        return solicitations

    def save_enhanced_solicitations(self, solicitations: List[Dict]) -> int:
        """Save enhanced solicitations with comprehensive data"""
        if not solicitations:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        saved_count = 0
        
        for solicitation in solicitations:
            try:
                # Extract and clean enhanced data
                title = solicitation.get('solicitation_title', '')[:500]
                description = solicitation.get('description', '')[:5000] if solicitation.get('description') else ''
                agency = solicitation.get('agency', '')
                program = solicitation.get('program', '')
                solicitation_number = solicitation.get('solicitation_number', '')
                
                # Handle dates
                open_date = solicitation.get('open_date', '')
                close_date = solicitation.get('close_date', '')
                
                keywords = solicitation.get('keywords', '')
                
                # Enhanced scoring data
                relevance_score = solicitation.get('relevance_score', 0.0)
                confidence_score = solicitation.get('confidence_score', 0.0)
                biotools_category = solicitation.get('biotools_category', '')
                compound_matches = solicitation.get('compound_keyword_matches', '')
                agency_alignment = solicitation.get('agency_alignment_score', 0.0)
                url = solicitation.get('url', '')
                
                # Insert enhanced solicitation
                cursor.execute('''
                    INSERT OR REPLACE INTO grants 
                    (title, description, agency, program, award_number, award_date, 
                     end_date, keywords, source, grant_type, relevance_score, confidence_score,
                     biotools_category, compound_keyword_matches, agency_alignment_score, 
                     url, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    title, description, agency, program, solicitation_number, open_date,
                    close_date, keywords, 'SBIR', 'solicitation', relevance_score, confidence_score,
                    biotools_category, compound_matches, agency_alignment, url,
                    datetime.now().isoformat()
                ))
                
                saved_count += 1
                
            except Exception as e:
                self.logger.error(f"Error saving solicitation {solicitation.get('solicitation_number', 'unknown')}: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"💾 Saved {saved_count} enhanced solicitations to database")
        return saved_count

    def get_database_stats(self) -> Dict[str, Any]:
        """Get comprehensive database statistics including contact information coverage"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        try:
            # Basic counts
            cursor.execute("SELECT COUNT(*) FROM grants")
            stats['total_grants'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM grants WHERE grant_type = 'award'")
            stats['awards_count'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM grants WHERE grant_type = 'solicitation'")
            stats['solicitations_count'] = cursor.fetchone()[0]
            
            # Enhanced stats
            cursor.execute("SELECT COUNT(*) FROM grants WHERE relevance_score >= 1.5")
            stats['biotools_validated'] = cursor.fetchone()[0]
            
            # Contact information coverage
            cursor.execute("""
                SELECT COUNT(*) FROM grants 
                WHERE (poc_email IS NOT NULL AND poc_email != '') 
                   OR (pi_email IS NOT NULL AND pi_email != '')
                   OR (poc_phone IS NOT NULL AND poc_phone != '')
            """)
            stats['grants_with_contact_info'] = cursor.fetchone()[0]
            
            # Company information coverage
            cursor.execute("""
                SELECT COUNT(*) FROM grants 
                WHERE (company_url IS NOT NULL AND company_url != '') 
                   OR (address1 IS NOT NULL AND address1 != '')
            """)
            stats['grants_with_company_info'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT AVG(relevance_score), AVG(confidence_score), AVG(agency_alignment_score) FROM grants WHERE relevance_score > 0")
            result = cursor.fetchone()
            if result and result[0] is not None:
                avg_scores = result
                stats['avg_relevance_score'] = avg_scores[0] or 0
                stats['avg_confidence_score'] = avg_scores[1] or 0
                stats['avg_agency_alignment'] = avg_scores[2] or 0
            else:
                stats['avg_relevance_score'] = 0
                stats['avg_confidence_score'] = 0
                stats['avg_agency_alignment'] = 0
            
            # Category distribution
            cursor.execute("""
                SELECT biotools_category, COUNT(*) 
                FROM grants 
                WHERE biotools_category IS NOT NULL AND biotools_category != '' 
                GROUP BY biotools_category 
                ORDER BY COUNT(*) DESC 
                LIMIT 10
            """)
            stats['top_biotools_categories'] = cursor.fetchall()
            
            # Agency distribution
            cursor.execute("""
                SELECT agency, COUNT(*) 
                FROM grants 
                GROUP BY agency 
                ORDER BY COUNT(*) DESC 
                LIMIT 10
            """)
            stats['top_agencies'] = cursor.fetchall()
            
            # Contamination detection
            try:
                cursor.execute("SELECT COUNT(*) FROM grants WHERE relevance_score < 1.0 AND confidence_score < 1.0")
                stats['contaminated_records'] = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM grants WHERE compound_keyword_matches IS NOT NULL AND compound_keyword_matches != ''")
                stats['compound_keyword_matches'] = cursor.fetchone()[0]
                
            except sqlite3.OperationalError:
                stats['contaminated_records'] = 0
                stats['compound_keyword_matches'] = 0
            
        except Exception as e:
            self.logger.error(f"Error getting database stats: {e}")
        finally:
            conn.close()
        
        return stats


def main():
    """Enhanced main execution function with contact information collection"""
    scraper = CompleteBiotoolsScraperWithContacts()
    
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command in ['comprehensive', 'full', 'complete']:
            # Comprehensive biotools scraping with contact information
            start_year = int(sys.argv[2]) if len(sys.argv) > 2 else 2022
            results = scraper.run_comprehensive_biotools_scraping(start_year)
            
            print(f"\n🎯 COMPREHENSIVE SCRAPING WITH CONTACTS SUMMARY:")
            print(f"  Awards: {results['awards']}")
            print(f"  Solicitations: {results['solicitations']}")
            print(f"  Successful agencies: {len(results.get('successful_agencies', []))}")
            print(f"  Failed agencies: {len(results.get('failed_agencies', []))}")
            
            if 'precision_metrics' in results:
                metrics = results['precision_metrics']
                print(f"  Validation Rate: {metrics['biotools_validated_rate']:.1f}%")
                print(f"  Contact Coverage: {metrics['contact_coverage_rate']:.1f}%")
                print(f"  Avg Relevance: {metrics['avg_relevance_score']:.2f}")
                print(f"  Avg Confidence: {metrics['avg_confidence_score']:.2f}")
            
        elif command == 'solicitations':
            # Enhanced solicitations only
            result = scraper.run_solicitations_only()
            print(f"✅ Solicitations updated: {result}")
            
        elif command == 'companies':
            # Fetch and cache company data
            companies = scraper.fetch_company_data()
            print(f"✅ Company data cached: {len(companies)} entries")
            
        elif command == 'stats':
            # Enhanced statistics with contact info
            stats = scraper.get_database_stats()
            print(f"\n📊 ENHANCED DATABASE STATISTICS WITH CONTACT INFO:")
            print(f"  Total grants: {stats['total_grants']}")
            print(f"  Awards: {stats['awards_count']}")
            print(f"  Solicitations: {stats['solicitations_count']}")
            print(f"  Biotools validated: {stats['biotools_validated']}")
            print(f"  Grants with contact info: {stats.get('grants_with_contact_info', 0)}")
            print(f"  Grants with company info: {stats.get('grants_with_company_info', 0)}")
            
        else:
            print("Enhanced BioTools Scraper with Contact Information Usage:")
            print("  python app/scraper.py comprehensive [start_year]  # Complete collection with contacts")
            print("  python app/scraper.py solicitations              # Update solicitations")
            print("  python app/scraper.py companies                  # Fetch company data")
            print("  python app/scraper.py stats                      # Enhanced statistics")
            print("")
            print("New features:")
            print("  • Comprehensive contact information collection")
            print("  • Company details and addresses") 
            print("  • Principal Investigator contact data")
            print("  • Point of Contact information")
            print("  • Enhanced company matching and caching")
    else:
        # Default: run comprehensive biotools scraping with contacts from 2022
        print("🚀 Starting comprehensive biotools scraping with contact information from 2022...")
        scraper.run_comprehensive_biotools_scraping(2022)


if __name__ == "__main__":
    main()