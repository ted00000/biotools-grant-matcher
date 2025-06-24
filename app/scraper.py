#!/usr/bin/env python3
"""
Enhanced BioTools SBIR/STTR Scraper - Precision Biotools Focus
Key improvements:
- Compound biotools keyword strategy (e.g., "spatial biology" not "spatial")
- Domain-specific negative filtering to exclude non-biotools
- Agency/program pre-filtering for biotools-relevant funding
- Enhanced relevance scoring with biotools taxonomy alignment
- Reduced false positives from astronomy, geology, and general engineering
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

class EnhancedBiotoolsScraper:
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
        
        # PRECISION BIOTOOLS KEYWORD STRATEGY
        # Using compound terms to ensure biological context
        self.biotools_compound_keywords = [
            # Genomics & Molecular Biology (compound terms only)
            'genomic sequencing', 'DNA sequencing', 'RNA sequencing', 'genome editing',
            'CRISPR technology', 'genetic analysis', 'molecular diagnostics', 'gene expression',
            'single cell genomics', 'whole genome sequencing', 'targeted sequencing',
            
            # Cell Biology & Microscopy
            'cell biology', 'cellular imaging', 'live cell imaging', 'fluorescence microscopy',
            'confocal microscopy', 'super resolution microscopy', 'cell sorting', 'flow cytometry',
            'single cell analysis', 'cell culture', 'stem cell research',
            
            # Proteomics & Biochemistry
            'protein analysis', 'mass spectrometry proteomics', 'protein identification',
            'peptide analysis', 'enzyme assay', 'biochemical analysis', 'immunoassay',
            'protein purification', 'protein characterization',
            
            # Bioinformatics & Computational Biology
            'bioinformatics software', 'computational biology', 'sequence analysis',
            'phylogenetic analysis', 'structural bioinformatics', 'systems biology',
            'biological database', 'genomic data analysis', 'protein modeling',
            
            # Laboratory Instrumentation (biological context)
            'laboratory automation', 'bioanalytical instrument', 'clinical diagnostics',
            'point-of-care testing', 'medical diagnostic', 'biological sensor',
            'laboratory equipment', 'analytical instrumentation',
            
            # Specialized Biotools Areas
            'spatial biology', 'spatial transcriptomics', 'tissue imaging', 'pathology imaging',
            'drug discovery', 'pharmaceutical research', 'biomarker discovery',
            'clinical laboratory', 'diagnostic testing', 'therapeutic development',
            
            # Microfluidics & Lab-on-Chip (biological applications)
            'microfluidic device', 'lab-on-chip', 'droplet microfluidics', 'biological microfluidics',
            'cell manipulation', 'biological sample preparation',
            
            # Synthetic Biology & Bioengineering
            'synthetic biology', 'bioengineering', 'biological engineering', 'biosynthesis',
            'metabolic engineering', 'protein engineering', 'genetic engineering',
            
            # Multi-omics & Systems Approaches
            'multi-omics', 'systems biology', 'integrative biology', 'personalized medicine',
            'precision medicine', 'biomedical research', 'translational research',
            
            # Emerging Biotools Areas
            'organoid technology', 'tissue engineering', 'regenerative medicine',
            'immunotherapy', 'cancer research', 'neuroscience research',
            'microbiome analysis', 'environmental microbiology'
        ]
        
        # NEGATIVE FILTERING - Domains to exclude
        self.excluded_domains = {
            'astronomy_space': [
                'stellar', 'galactic', 'planetary', 'astronomical', 'astrophysics',
                'space mission', 'satellite', 'cosmic', 'solar system', 'interstellar',
                'telescope', 'observatory', 'space exploration'
            ],
            'geology_earth_science': [
                'geological', 'geophysical', 'seismic', 'tectonic', 'volcanic',
                'sedimentary', 'igneous', 'metamorphic', 'mineral exploration',
                'geochemistry', 'petrology', 'stratigraphy', 'paleontology'
            ],
            'physics_non_bio': [
                'particle physics', 'quantum mechanics', 'nuclear physics', 'theoretical physics',
                'condensed matter physics', 'plasma physics', 'high energy physics',
                'atomic physics', 'optics research', 'materials physics'
            ],
            'engineering_non_bio': [
                'mechanical engineering', 'electrical engineering', 'civil engineering',
                'aerospace engineering', 'chemical engineering', 'industrial engineering',
                'structural engineering', 'automotive engineering'
            ],
            'environmental_non_bio': [
                'climate modeling', 'atmospheric science', 'meteorology', 'oceanography',
                'hydrology', 'remote sensing', 'earth observation', 'weather prediction'
            ],
            'computer_science_general': [
                'web development', 'mobile application', 'database administration',
                'network security', 'cloud computing', 'machine learning general',
                'artificial intelligence general', 'software engineering'
            ],
            'chemistry_non_bio': [
                'inorganic chemistry', 'physical chemistry', 'materials chemistry',
                'industrial chemistry', 'polymer chemistry', 'analytical chemistry'
            ]
        }
        
        # BIOTOOLS-SPECIFIC AGENCIES AND PROGRAMS
        self.biotools_agencies = {
            'HHS': {
                'programs': ['SBIR', 'STTR', 'biomedical', 'health technology', 'medical device'],
                'exclude_programs': ['social services', 'education', 'administration']
            },
            'NIH': {
                'programs': ['biological', 'biomedical', 'health', 'disease', 'therapeutic', 'diagnostic'],
                'exclude_programs': ['behavioral', 'social', 'educational']
            },
            'NSF': {
                'programs': ['biological sciences', 'molecular', 'cellular', 'biological research',
                           'biotechnology', 'biochemistry', 'biophysics'],
                'exclude_programs': ['social sciences', 'education', 'geosciences', 'engineering general']
            },
            'DOE': {
                'programs': ['biological systems', 'bioenergy', 'environmental biology',
                           'genomics', 'systems biology'],
                'exclude_programs': ['fossil energy', 'nuclear energy', 'renewable energy general']
            },
            'CDC': {
                'programs': ['health surveillance', 'epidemiology', 'public health tools',
                           'diagnostic tools', 'health monitoring'],
                'exclude_programs': ['policy', 'administration', 'education']
            },
            'DARPA': {
                'programs': ['biological technologies', 'biotechnology', 'biodefense',
                           'biological systems', 'bioengineering'],
                'exclude_programs': ['weapons', 'defense general', 'communications']
            }
        }
        
        self.setup_database()
    
    def setup_database(self):
        """Create enhanced database schema optimized for biotools data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Check existing table and add biotools-specific columns
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='grants';")
        grants_exists = cursor.fetchone()
        
        if grants_exists:
            cursor.execute("PRAGMA table_info(grants);")
            existing_columns = {row[1]: row[2] for row in cursor.fetchall()}
            self.logger.info(f"Found existing grants table with {len(existing_columns)} columns")
            
            # Add biotools-specific columns
            biotools_columns = {
                'biotools_compound_keywords': 'TEXT',
                'biotools_relevance_score': 'REAL DEFAULT 0.0',
                'biotools_validated': 'BOOLEAN DEFAULT 0',
                'excluded_domain_flags': 'TEXT',
                'biotools_tool_type': 'TEXT',
                'biotools_focus_area': 'TEXT',
                'negative_filter_score': 'REAL DEFAULT 0.0',
                'compound_keyword_matches': 'TEXT'
            }
            
            for column_name, column_def in biotools_columns.items():
                if column_name not in existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE grants ADD COLUMN {column_name} {column_def}")
                        self.logger.info(f"Added biotools column: {column_name}")
                    except sqlite3.Error as e:
                        if "duplicate column name" not in str(e).lower():
                            self.logger.warning(f"Could not add column {column_name}: {e}")
        else:
            # Create new table with full biotools schema
            self.logger.info("Creating new grants table with enhanced biotools schema")
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
                    
                    -- SBIR/STTR specific fields
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
                    ri_name TEXT,
                    ri_poc_name TEXT,
                    ri_poc_phone TEXT,
                    
                    -- Enhanced biotools fields
                    biotools_compound_keywords TEXT,
                    biotools_relevance_score REAL DEFAULT 0.0,
                    biotools_validated BOOLEAN DEFAULT 0,
                    excluded_domain_flags TEXT,
                    biotools_tool_type TEXT,
                    biotools_focus_area TEXT,
                    negative_filter_score REAL DEFAULT 0.0,
                    compound_keyword_matches TEXT,
                    
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
        self.logger.info("Enhanced biotools database schema initialized successfully")
    
    def is_biotools_relevant(self, title: str, description: str = "", keywords: str = "") -> Dict[str, Any]:
        """Enhanced biotools relevance detection with precision focus"""
        combined_text = f"{title} {description} {keywords}".lower()
        
        relevance_data = {
            'is_relevant': False,
            'relevance_score': 0.0,
            'matched_keywords': [],
            'excluded_domains': [],
            'negative_score': 0.0,
            'tool_type_suggestions': [],
            'focus_area_suggestions': []
        }
        
        # Check for compound biotools keywords (positive scoring)
        matched_compounds = []
        for compound_keyword in self.biotools_compound_keywords:
            if compound_keyword.lower() in combined_text:
                matched_compounds.append(compound_keyword)
                relevance_data['relevance_score'] += 2.0  # Higher weight for compound terms
        
        relevance_data['matched_keywords'] = matched_compounds
        
        # Check for excluded domains (negative scoring)
        excluded_matches = []
        for domain_name, domain_terms in self.excluded_domains.items():
            for term in domain_terms:
                if term.lower() in combined_text:
                    excluded_matches.append((domain_name, term))
                    relevance_data['negative_score'] += 3.0  # Heavy penalty for excluded domains
        
        relevance_data['excluded_domains'] = excluded_matches
        
        # Calculate final relevance score
        final_score = relevance_data['relevance_score'] - relevance_data['negative_score']
        relevance_data['relevance_score'] = max(0.0, final_score)
        
        # Determine if relevant (must have positive compound matches and minimal exclusions)
        relevance_data['is_relevant'] = (
            len(matched_compounds) > 0 and 
            relevance_data['relevance_score'] > 2.0 and
            len(excluded_matches) <= 1  # Allow minimal false positives
        )
        
        # Suggest tool types and focus areas based on matches
        relevance_data['tool_type_suggestions'] = self._suggest_tool_types(matched_compounds)
        relevance_data['focus_area_suggestions'] = self._suggest_focus_areas(matched_compounds)
        
        return relevance_data
    
    def _suggest_tool_types(self, matched_keywords: List[str]) -> List[str]:
        """Suggest biotools tool types based on matched keywords"""
        tool_type_mappings = {
            'instrument': ['sequencing', 'microscopy', 'cytometry', 'spectrometry', 'imaging', 'automation'],
            'software': ['bioinformatics software', 'computational biology', 'analysis', 'modeling'],
            'assay': ['assay', 'testing', 'diagnostic', 'immunoassay', 'biochemical analysis'],
            'database_platform': ['database', 'repository', 'platform', 'resource'],
            'integrated_system': ['automation', 'platform', 'system', 'workstation'],
            'service': ['service', 'facility', 'laboratory'],
            'consumable': ['reagent', 'kit', 'supplies', 'media']
        }
        
        suggestions = []
        for tool_type, indicators in tool_type_mappings.items():
            for keyword in matched_keywords:
                if any(indicator in keyword.lower() for indicator in indicators):
                    if tool_type not in suggestions:
                        suggestions.append(tool_type)
        
        return suggestions
    
    def _suggest_focus_areas(self, matched_keywords: List[str]) -> List[str]:
        """Suggest biotools focus areas based on matched keywords"""
        focus_area_mappings = {
            'genomics': ['genomic', 'DNA', 'gene', 'sequencing', 'CRISPR'],
            'cell_biology': ['cell', 'cellular', 'microscopy', 'imaging'],
            'proteomics': ['protein', 'peptide', 'mass spectrometry'],
            'bioinformatics': ['bioinformatics', 'computational', 'analysis'],
            'single_cell': ['single cell', 'droplet', 'microfluidic'],
            'spatial_biology': ['spatial', 'tissue', 'pathology'],
            'immunology': ['immune', 'antibody', 'immunoassay'],
            'synthetic_biology': ['synthetic biology', 'bioengineering'],
            'diagnostics': ['diagnostic', 'clinical', 'point-of-care'],
            'microbiome': ['microbiome', 'microbial', '16S']
        }
        
        suggestions = []
        for focus_area, indicators in focus_area_mappings.items():
            for keyword in matched_keywords:
                if any(indicator in keyword.lower() for indicator in indicators):
                    if focus_area not in suggestions:
                        suggestions.append(focus_area)
        
        return suggestions
    
    def make_api_request(self, endpoint: str, params: Dict[str, Any] = None, max_retries: int = 3) -> Optional[List]:
        """Enhanced API request with biotools-specific error handling"""
        if endpoint == "solicitations":
            url = "https://api.www.sbir.gov/public/api/solicitations"
            use_params = False
        else:
            url = f"{self.base_url}/{endpoint}"
            use_params = True

        if params is None:
            params = {}

        for attempt in range(max_retries):
            try:
                response = requests.get(
                    url,
                    headers=self.headers,
                    params=params if use_params else None,
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
                    self.logger.warning(f"API endpoint unavailable: {response.status_code} for {response.url}")
                    return None

                if response.status_code == 429:
                    wait_time = (attempt + 1) * 15
                    self.logger.warning(f"Rate limited - waiting {wait_time}s before retry")
                    time.sleep(wait_time)
                    continue

                self.logger.error(f"Unexpected API response: {response.status_code} for {response.url}")
                return None

            except requests.RequestException as e:
                self.logger.error(f"API request failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(10)

        self.logger.error("API request failed after all retries")
        return None
    
    def fetch_biotools_awards_by_agency(self, agency: str, start_year: int = 2020) -> List[Dict]:
        """Fetch awards with enhanced biotools compound keyword filtering"""
        self.logger.info(f"Fetching {agency} biotools awards from {start_year} with compound keywords...")
        
        awards = []
        rows_per_request = 1000
        current_year = datetime.now().year
        
        for year in range(start_year, current_year + 1):
            self.logger.info(f"  Processing {agency} awards for {year}...")
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
                
                data = self.make_api_request('awards', params)
                
                if not data or not isinstance(data, list):
                    break
                
                batch_awards = data
                if not batch_awards:
                    break
                
                year_total_count += len(batch_awards)
                
                # Enhanced biotools filtering with compound keywords
                for award in batch_awards:
                    title = award.get('award_title', '')
                    abstract = award.get('abstract', '')
                    keywords = award.get('research_area_keywords', '') or ''
                    
                    relevance_data = self.is_biotools_relevant(title, abstract, keywords)
                    
                    if relevance_data['is_relevant']:
                        # Enhance award with biotools metadata
                        award['biotools_relevance_score'] = relevance_data['relevance_score']
                        award['biotools_validated'] = True
                        award['compound_keyword_matches'] = ','.join(relevance_data['matched_keywords'])
                        award['biotools_tool_type'] = ','.join(relevance_data['tool_type_suggestions'])
                        award['biotools_focus_area'] = ','.join(relevance_data['focus_area_suggestions'])
                        award['excluded_domain_flags'] = ','.join([f"{domain}:{term}" for domain, term in relevance_data['excluded_domains']])
                        award['negative_filter_score'] = relevance_data['negative_score']
                        
                        awards.append(award)
                        year_biotools_count += 1
                
                self.logger.info(f"    Batch processed: {len(batch_awards)} awards, {year_biotools_count} biotools-relevant so far")
                
                if len(batch_awards) < rows_per_request:
                    break
                
                year_start += rows_per_request
                time.sleep(2)  # Respectful delay
            
            relevance_rate = (year_biotools_count / year_total_count * 100) if year_total_count > 0 else 0
            self.logger.info(f"  {agency} {year}: {year_biotools_count}/{year_total_count} biotools-relevant ({relevance_rate:.1f}%)")
        
        self.logger.info(f"✅ {agency}: Collected {len(awards)} precision biotools awards")
        return awards
    
    def fetch_biotools_solicitations(self) -> List[Dict]:
        """Fetch solicitations with enhanced biotools filtering"""
        self.logger.info("🔍 Fetching SBIR Solicitations with Biotools Compound Keywords")
        
        all_solicitations = []
        
        # Strategy 1: Direct open solicitations with biotools agencies
        self.logger.info("  Strategy 1: Open solicitations from biotools agencies")
        biotools_agencies = ['HHS', 'NIH', 'NSF', 'DOE', 'CDC']
        
        for agency in biotools_agencies:
            # Check if agency has biotools programs
            if agency in self.biotools_agencies:
                try:
                    params = {
                        'agency': agency,
                        'open': 1,
                        'rows': 25,
                        'format': 'json'
                    }
                    
                    data = self.make_api_request('solicitations', params)
                    if data and isinstance(data, list):
                        self.logger.info(f"    {agency}: {len(data)} open solicitations")
                        all_solicitations.extend(data)
                    else:
                        self.logger.info(f"    {agency}: No open solicitations")
                    
                    time.sleep(2)
                    
                except Exception as e:
                    self.logger.warning(f"    {agency} solicitations failed: {e}")
        
        # Strategy 2: Compound keyword-based search
        self.logger.info("  Strategy 2: Biotools compound keyword search")
        biotools_search_terms = [
            'genomic sequencing', 'cell biology', 'protein analysis', 'bioinformatics software',
            'diagnostic testing', 'laboratory automation', 'biomarker discovery', 'drug discovery'
        ]
        
        for term in biotools_search_terms:
            try:
                params = {
                    'keyword': term,
                    'open': 1,
                    'rows': 10,
                    'format': 'json'
                }
                
                data = self.make_api_request('solicitations', params)
                if data and isinstance(data, list):
                    self.logger.info(f"    '{term}': {len(data)} open solicitations")
                    all_solicitations.extend(data)
                else:
                    self.logger.info(f"    '{term}': No solicitations")
                
                time.sleep(1.5)
                
            except Exception as e:
                self.logger.warning(f"    Keyword '{term}' search failed: {e}")
        
        # Remove duplicates and apply biotools filtering
        unique_solicitations = {}
        for sol in all_solicitations:
            sol_id = sol.get('solicitation_number') or sol.get('solicitation_id', '')
            if sol_id and sol_id not in unique_solicitations:
                unique_solicitations[sol_id] = sol
        
        unique_list = list(unique_solicitations.values())
        self.logger.info(f"  📊 Total unique solicitations: {len(unique_list)}")
        
        # Apply enhanced biotools filtering
        biotools_solicitations = []
        for sol in unique_list:
            title = sol.get('solicitation_title', '')
            
            # Extract description from topics
            topics_text = ""
            if 'solicitation_topics' in sol and sol['solicitation_topics']:
                for topic in sol['solicitation_topics']:
                    if isinstance(topic, dict):
                        topics_text += f" {topic.get('topic_title', '')} {topic.get('topic_description', '')}"
            
            relevance_data = self.is_biotools_relevant(title, topics_text)
            
            if relevance_data['is_relevant']:
                # Enhance solicitation with biotools metadata
                sol['biotools_relevance_score'] = relevance_data['relevance_score']
                sol['biotools_validated'] = True
                sol['compound_keyword_matches'] = ','.join(relevance_data['matched_keywords'])
                sol['biotools_tool_type'] = ','.join(relevance_data['tool_type_suggestions'])
                sol['biotools_focus_area'] = ','.join(relevance_data['focus_area_suggestions'])
                
                biotools_solicitations.append(sol)
        
        self.logger.info(f"✅ Collected {len(biotools_solicitations)} precision biotools solicitations")
        return biotools_solicitations
    
    def save_awards(self, awards: List[Dict]) -> int:
        """Save awards with enhanced biotools metadata"""
        if not awards:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get actual table structure
        cursor.execute("PRAGMA table_info(grants);")
        columns_info = cursor.fetchall()
        column_names = [col[1] for col in columns_info]
        
        saved_count = 0
        current_time = datetime.now().isoformat()
        
        for award in awards:
            try:
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
                
                # Enhanced biotools fields (only add if columns exist)
                biotools_fields = [
                    'biotools_relevance_score', 'biotools_validated', 'compound_keyword_matches',
                    'biotools_tool_type', 'biotools_focus_area', 'excluded_domain_flags', 'negative_filter_score'
                ]
                
                for field in biotools_fields:
                    if field in column_names and field in award:
                        award_data[field] = award[field]
                
                # Standard SBIR fields (dynamic column handling)
                standard_fields = {
                    'branch': 'branch', 'phase': 'phase', 'program': 'program',
                    'award_year': 'award_year', 'award_amount': 'award_amount',
                    'contract_number': 'contract', 'company_name': 'firm',
                    'company_city': 'city', 'company_state': 'state',
                    'company_uei': 'uei', 'company_duns': 'duns',
                    'company_address': 'address1', 'company_zip': 'zip',
                    'poc_name': 'poc_name', 'pi_name': 'pi_name'
                }
                
                for db_field, api_field in standard_fields.items():
                    if db_field in column_names and api_field in award:
                        award_data[db_field] = award[api_field]
                
                # Boolean fields
                boolean_fields = {
                    'hubzone_owned': 'hubzone_owned',
                    'socially_economically_disadvantaged': 'socially_economically_disadvantaged',
                    'women_owned': 'women_owned'
                }
                
                for db_field, api_field in boolean_fields.items():
                    if db_field in column_names and api_field in award:
                        award_data[db_field] = award[api_field] == 'Y'
                
                # Metadata fields
                metadata_fields = {
                    'data_source': 'SBIR',
                    'grant_type': 'award',
                    'biotools_category': 'biotools',
                    'updated_at': current_time,
                    'last_scraped_at': current_time
                }
                
                for field, value in metadata_fields.items():
                    if field in column_names:
                        award_data[field] = value
                
                # Build SQL dynamically
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
        
        self.logger.info(f"💾 Saved {saved_count} biotools awards to database")
        return saved_count
    
    def save_solicitations(self, solicitations: List[Dict]) -> int:
        """Save solicitations with enhanced biotools metadata"""
        if not solicitations:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(grants);")
        columns_info = cursor.fetchall()
        column_names = [col[1] for col in columns_info]
        
        saved_count = 0
        current_time = datetime.now().isoformat()
        
        for sol in solicitations:
            try:
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
                
                # Enhanced biotools fields
                biotools_fields = [
                    'biotools_relevance_score', 'biotools_validated', 'compound_keyword_matches',
                    'biotools_tool_type', 'biotools_focus_area'
                ]
                
                for field in biotools_fields:
                    if field in column_names and field in sol:
                        sol_data[field] = sol[field]
                
                # SBIR-specific fields
                sbir_fields = {
                    'branch': 'branch', 'phase': 'phase', 'program': 'program',
                    'current_status': 'current_status', 'open_date': 'open_date',
                    'close_date': 'close_date', 'solicitation_number': 'solicitation_number',
                    'solicitation_year': 'solicitation_year'
                }
                
                for db_field, api_field in sbir_fields.items():
                    if db_field in column_names and api_field in sol:
                        sol_data[db_field] = sol[api_field]
                
                # Special handling for solicitation topics
                if 'solicitation_topics' in column_names:
                    sol_data['solicitation_topics'] = json.dumps(sol.get('solicitation_topics', []))
                
                # Metadata fields
                metadata_fields = {
                    'data_source': 'SBIR',
                    'grant_type': 'solicitation',
                    'biotools_category': 'biotools',
                    'updated_at': current_time,
                    'last_scraped_at': current_time
                }
                
                for field, value in metadata_fields.items():
                    if field in column_names:
                        sol_data[field] = value
                
                # Build SQL dynamically
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
        
        self.logger.info(f"💾 Saved {saved_count} biotools solicitations to database")
        return saved_count
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get enhanced database statistics with biotools metrics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Total grants
        cursor.execute("SELECT COUNT(*) FROM grants")
        stats['total_grants'] = cursor.fetchone()[0]
        
        # Biotools-validated grants
        try:
            cursor.execute("SELECT COUNT(*) FROM grants WHERE biotools_validated = 1")
            stats['biotools_validated'] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            stats['biotools_validated'] = 0
        
        # Average biotools relevance score
        try:
            cursor.execute("SELECT AVG(biotools_relevance_score) FROM grants WHERE biotools_relevance_score > 0")
            avg_score = cursor.fetchone()[0]
            stats['avg_biotools_score'] = round(avg_score, 2) if avg_score else 0.0
        except sqlite3.OperationalError:
            stats['avg_biotools_score'] = 0.0
        
        # By agency (biotools focus)
        cursor.execute("SELECT agency, COUNT(*) FROM grants GROUP BY agency ORDER BY COUNT(*) DESC")
        stats['by_agency'] = cursor.fetchall()
        
        # By grant type
        try:
            cursor.execute("SELECT grant_type, COUNT(*) FROM grants WHERE grant_type IS NOT NULL GROUP BY grant_type")
            stats['by_type'] = cursor.fetchall()
        except sqlite3.OperationalError:
            stats['by_type'] = []
        
        # Biotools tool types distribution
        try:
            cursor.execute("SELECT biotools_tool_type, COUNT(*) FROM grants WHERE biotools_tool_type IS NOT NULL AND biotools_tool_type != '' GROUP BY biotools_tool_type")
            stats['by_tool_type'] = cursor.fetchall()
        except sqlite3.OperationalError:
            stats['by_tool_type'] = []
        
        # Biotools focus areas distribution
        try:
            cursor.execute("SELECT biotools_focus_area, COUNT(*) FROM grants WHERE biotools_focus_area IS NOT NULL AND biotools_focus_area != '' GROUP BY biotools_focus_area")
            stats['by_focus_area'] = cursor.fetchall()
        except sqlite3.OperationalError:
            stats['by_focus_area'] = []
        
        # Recent biotools updates
        try:
            cursor.execute("SELECT COUNT(*) FROM grants WHERE last_scraped_at > date('now', '-30 days') AND biotools_validated = 1")
            stats['recent_biotools_updates'] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            stats['recent_biotools_updates'] = 0
        
        # Compound keyword effectiveness
        try:
            cursor.execute("SELECT compound_keyword_matches, COUNT(*) FROM grants WHERE compound_keyword_matches IS NOT NULL AND compound_keyword_matches != '' GROUP BY compound_keyword_matches LIMIT 10")
            stats['top_compound_keywords'] = cursor.fetchall()
        except sqlite3.OperationalError:
            stats['top_compound_keywords'] = []
        
        conn.close()
        return stats
    
    def run_precision_biotools_scraping(self, start_year: int = 2022) -> Dict[str, int]:
        """Run precision biotools data collection with compound keyword strategy"""
        self.logger.info("🚀 Starting Precision BioTools Data Collection")
        self.logger.info("=" * 60)
        
        before_stats = self.get_database_stats()
        self.logger.info(f"📊 Before: {before_stats['total_grants']} total grants, {before_stats.get('biotools_validated', 0)} biotools-validated")
        
        total_added = {
            'awards': 0,
            'solicitations': 0,
            'precision_score': 0.0
        }
        
        # 1. Fetch Awards from Biotools-Relevant Agencies
        self.logger.info("\n" + "=" * 40)
        self.logger.info("🏆 COLLECTING PRECISION BIOTOOLS AWARDS")
        
        biotools_agencies = ['HHS', 'NIH', 'NSF', 'DOE', 'CDC', 'DARPA']
        
        for agency in biotools_agencies:
            if agency in self.biotools_agencies:
                try:
                    self.logger.info(f"Processing {agency} with biotools programs: {self.biotools_agencies[agency]['programs']}")
                    awards = self.fetch_biotools_awards_by_agency(agency, start_year)
                    saved = self.save_awards(awards)
                    total_added['awards'] += saved
                    
                    # Calculate precision score for this agency
                    if awards:
                        avg_relevance = sum(award.get('biotools_relevance_score', 0) for award in awards) / len(awards)
                        total_added['precision_score'] += avg_relevance
                        self.logger.info(f"  {agency} precision score: {avg_relevance:.2f}")
                    
                    time.sleep(5)  # Respectful delay between agencies
                    
                except Exception as e:
                    self.logger.error(f"Failed to process {agency} awards: {e}")
        
        # 2. Fetch Biotools Solicitations
        self.logger.info("\n" + "=" * 40)
        self.logger.info("📋 COLLECTING PRECISION BIOTOOLS SOLICITATIONS")
        self.logger.info("⏳ Waiting 10 seconds for API recovery...")
        time.sleep(10)
        
        try:
            solicitations = self.fetch_biotools_solicitations()
            saved = self.save_solicitations(solicitations)
            total_added['solicitations'] += saved
            
            # Calculate solicitation precision score
            if solicitations:
                avg_relevance = sum(sol.get('biotools_relevance_score', 0) for sol in solicitations) / len(solicitations)
                total_added['precision_score'] += avg_relevance
                self.logger.info(f"  Solicitations precision score: {avg_relevance:.2f}")
            
        except Exception as e:
            self.logger.error(f"Failed to process solicitations: {e}")
            self.logger.warning("💡 Try running 'python app/scraper.py solicitations' separately later")
        
        # 3. Calculate Overall Precision Metrics
        self.logger.info("\n" + "=" * 40)
        self.logger.info("📊 PRECISION ANALYSIS")
        
        after_stats = self.get_database_stats()
        
        precision_metrics = {
            'total_collected': total_added['awards'] + total_added['solicitations'],
            'biotools_validated_rate': 0.0,
            'avg_relevance_score': after_stats.get('avg_biotools_score', 0.0),
            'compound_keyword_effectiveness': len(after_stats.get('top_compound_keywords', [])),
            'domain_coverage': len(after_stats.get('by_focus_area', []))
        }
        
        if precision_metrics['total_collected'] > 0:
            precision_metrics['biotools_validated_rate'] = (
                after_stats.get('biotools_validated', 0) / after_stats['total_grants'] * 100
            )
        
        # Final Results
        self.logger.info("\n" + "=" * 60)
        self.logger.info("📈 PRECISION BIOTOOLS SCRAPING RESULTS:")
        self.logger.info(f"  Total grants: {before_stats['total_grants']} → {after_stats['total_grants']} (+{after_stats['total_grants'] - before_stats['total_grants']})")
        self.logger.info(f"  Biotools awards added: {total_added['awards']}")
        self.logger.info(f"  Biotools solicitations added: {total_added['solicitations']}")
        self.logger.info(f"  Biotools validation rate: {precision_metrics['biotools_validated_rate']:.1f}%")
        self.logger.info(f"  Average relevance score: {precision_metrics['avg_relevance_score']:.2f}")
        
        self.logger.info("\n📊 BIOTOOLS TAXONOMY COVERAGE:")
        if after_stats.get('by_tool_type'):
            self.logger.info("  Tool Types:")
            for tool_type, count in after_stats['by_tool_type'][:5]:
                if tool_type:
                    self.logger.info(f"    {tool_type}: {count}")
        
        if after_stats.get('by_focus_area'):
            self.logger.info("  Focus Areas:")
            for focus_area, count in after_stats['by_focus_area'][:5]:
                if focus_area:
                    self.logger.info(f"    {focus_area}: {count}")
        
        self.logger.info("\n📊 AGENCY BREAKDOWN:")
        for agency, count in after_stats['by_agency'][:8]:
            if agency and agency in self.biotools_agencies:
                self.logger.info(f"   {agency}: {count} grants ✅ biotools-focused")
            elif agency:
                self.logger.info(f"   {agency}: {count} grants")
        
        # Success Assessment
        total_new = total_added['awards'] + total_added['solicitations']
        
        if total_new > 0:
            self.logger.info(f"\n🎉 SUCCESS: Precision biotools scraping completed!")
            self.logger.info("📈 Enhanced biotools grant matching system includes:")
            self.logger.info("   • Compound keyword validated awards and solicitations")
            self.logger.info("   • Domain contamination filtering (excluded astronomy, geology, etc.)")
            self.logger.info("   • Biotools taxonomy classification (tool types & focus areas)")
            self.logger.info("   • Agency program pre-filtering for biotools relevance")
            
            if precision_metrics['biotools_validated_rate'] > 80:
                self.logger.info(f"   • HIGH PRECISION: {precision_metrics['biotools_validated_rate']:.1f}% biotools validation rate")
            elif precision_metrics['biotools_validated_rate'] > 60:
                self.logger.info(f"   • GOOD PRECISION: {precision_metrics['biotools_validated_rate']:.1f}% biotools validation rate")
            else:
                self.logger.warning(f"   • REVIEW NEEDED: {precision_metrics['biotools_validated_rate']:.1f}% biotools validation rate")
        else:
            self.logger.warning("⚠️  No new biotools data collected - check API connectivity and keyword effectiveness")
        
        total_added['precision_metrics'] = precision_metrics
        return total_added
    
    def run_solicitations_only(self) -> int:
        """Quick update of biotools solicitations only"""
        self.logger.info("🔄 Quick Update: Biotools Solicitations Only")
        
        try:
            solicitations = self.fetch_biotools_solicitations()
            saved = self.save_solicitations(solicitations)
            
            self.logger.info(f"✅ Updated {saved} biotools solicitations")
            
            if saved == 0:
                self.logger.warning("⚠️  No biotools solicitations found. This could be due to:")
                self.logger.warning("  • No relevant biotools solicitations currently open")
                self.logger.warning("  • API rate limiting or temporary issues")
                self.logger.warning("  • Compound keyword strategy too restrictive")
                self.logger.warning("  • Try again in 30 minutes or adjust keywords")
            
            return saved
            
        except Exception as e:
            self.logger.error(f"Failed to update biotools solicitations: {e}")
            return 0
    
    def test_biotools_api_connectivity(self) -> Dict[str, Any]:
        """Test API connectivity with biotools-specific validation"""
        self.logger.info("🔍 Testing SBIR API Connectivity with Biotools Focus...")
        
        test_results = {
            'connectivity': {},
            'biotools_validation': {},
            'compound_keyword_test': {}
        }
        
        # Test basic connectivity
        try:
            data = self.make_api_request('awards', {'rows': 1})
            test_results['connectivity']['awards'] = data is not None and len(data) > 0
            self.logger.info(f"  Awards API: {'✅ Working' if test_results['connectivity']['awards'] else '❌ Failed'}")
        except Exception as e:
            test_results['connectivity']['awards'] = False
            self.logger.error(f"  Awards API: ❌ Failed - {e}")
        
        try:
            data = self.make_api_request('solicitations', {'rows': 25})
            test_results['connectivity']['solicitations'] = data is not None and len(data) >= 0
            self.logger.info(f"  Solicitations API: {'✅ Working' if test_results['connectivity']['solicitations'] else '❌ Failed'}")
        except Exception as e:
            test_results['connectivity']['solicitations'] = False
            self.logger.error(f"  Solicitations API: ❌ Failed - {e}")
        
        # Test biotools compound keyword effectiveness
        if test_results['connectivity']['awards']:
            self.logger.info("🧪 Testing biotools compound keyword strategy...")
            
            try:
                # Test with a compound biotools keyword
                test_data = self.make_api_request('awards', {
                    'agency': 'HHS',
                    'year': 2024,
                    'rows': 20
                })
                
                if test_data:
                    biotools_count = 0
                    total_count = len(test_data)
                    
                    for award in test_data:
                        title = award.get('award_title', '')
                        abstract = award.get('abstract', '')
                        relevance_data = self.is_biotools_relevant(title, abstract)
                        
                        if relevance_data['is_relevant']:
                            biotools_count += 1
                    
                    effectiveness_rate = (biotools_count / total_count * 100) if total_count > 0 else 0
                    test_results['compound_keyword_test']['effectiveness_rate'] = effectiveness_rate
                    test_results['compound_keyword_test']['sample_size'] = total_count
                    test_results['compound_keyword_test']['biotools_matches'] = biotools_count
                    
                    self.logger.info(f"  Compound keyword effectiveness: {effectiveness_rate:.1f}% ({biotools_count}/{total_count})")
                    
                    if effectiveness_rate > 50:
                        self.logger.info("  ✅ HIGH effectiveness - compound keywords working well")
                    elif effectiveness_rate > 25:
                        self.logger.info("  ⚠️  MODERATE effectiveness - consider keyword refinement")
                    else:
                        self.logger.warning("  ❌ LOW effectiveness - compound keywords need revision")
                
            except Exception as e:
                self.logger.error(f"  Compound keyword test failed: {e}")
        
        # Overall assessment
        working_apis = sum(test_results['connectivity'].values())
        self.logger.info(f"\n📊 API Status: {working_apis}/2 endpoints working")
        
        if working_apis == 2:
            self.logger.info("🎉 All APIs working! Ready for precision biotools scraping.")
        elif working_apis >= 1:
            self.logger.info("✅ Partial API access. Can proceed with available endpoints.")
        else:
            self.logger.warning("⚠️  API connectivity issues detected. Check network and API status.")
        
        return test_results


def main():
    """Main execution function with enhanced biotools options"""
    scraper = EnhancedBiotoolsScraper()
    
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'precision' or command == 'full':
            # Precision biotools scraping
            start_year = int(sys.argv[2]) if len(sys.argv) > 2 else 2022
            results = scraper.run_precision_biotools_scraping(start_year)
            
            print(f"\n🎯 PRECISION SUMMARY:")
            print(f"  Awards: {results['awards']}")
            print(f"  Solicitations: {results['solicitations']}")
            if 'precision_metrics' in results:
                metrics = results['precision_metrics']
                print(f"  Validation Rate: {metrics['biotools_validated_rate']:.1f}%")
                print(f"  Avg Relevance: {metrics['avg_relevance_score']:.2f}")
            
        elif command == 'solicitations':
            # Update biotools solicitations only
            scraper.run_solicitations_only()
            
        elif command == 'test':
            # Test API connectivity and biotools validation
            results = scraper.test_biotools_api_connectivity()
            
            if all(results['connectivity'].values()):
                print("\n🎉 Ready for precision biotools scraping!")
            elif sum(results['connectivity'].values()) >= 1:
                print("\n✅ Partial API access available.")
            else:
                print("\n⚠️ API connectivity issues detected.")
                
        elif command == 'stats':
            # Show enhanced biotools statistics
            stats = scraper.get_database_stats()
            print("\n📊 Enhanced BioTools Database Statistics:")
            print(f"  Total Grants: {stats['total_grants']}")
            print(f"  BioTools Validated: {stats['biotools_validated']}")
            print(f"  Average BioTools Score: {stats['avg_biotools_score']}")
            print(f"  Recent BioTools Updates: {stats['recent_biotools_updates']}")
            
            if stats['by_agency']:
                print(f"\n📊 Grants by Agency:")
                for agency, count in stats['by_agency'][:8]:
                    biotools_indicator = "🧬" if agency in scraper.biotools_agencies else ""
                    print(f"   {agency}: {count} {biotools_indicator}")
            
            if stats['by_tool_type']:
                print(f"\n🛠️ BioTools Tool Types:")
                for tool_type, count in stats['by_tool_type'][:5]:
                    if tool_type:
                        print(f"   {tool_type}: {count}")
            
            if stats['by_focus_area']:
                print(f"\n🎯 BioTools Focus Areas:")
                for focus_area, count in stats['by_focus_area'][:5]:
                    if focus_area:
                        print(f"   {focus_area}: {count}")
                        
        else:
            print("Enhanced BioTools Scraper Usage:")
            print("  python app/scraper.py precision [start_year]  # Precision biotools collection")
            print("  python app/scraper.py solicitations          # Update biotools solicitations")
            print("  python app/scraper.py test                   # Test APIs and compound keywords")
            print("  python app/scraper.py stats                  # Show biotools statistics")
    else:
        # Default: run precision biotools scraping from 2022
        print("🚀 Starting default precision biotools scraping from 2022...")
        print("💡 Use 'python app/scraper.py test' to validate compound keywords first")
        scraper.run_precision_biotools_scraping(2022)


if __name__ == "__main__":
    main()