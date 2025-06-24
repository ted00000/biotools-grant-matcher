#!/usr/bin/env python3
"""
Complete Enhanced BioTools SBIR/STTR Scraper - Fixed Version
Key improvements over previous version:
- Fixed agency mappings (NIH/CDC under HHS, DARPA under DOD)
- Enhanced solicitation collection strategy
- Improved error handling and rate limiting
- Better compound keyword validation
- Comprehensive biotools taxonomy classification
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

class CompleteBiotoolsScraper:
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
        
        # FIXED: Correct agency mappings based on actual SBIR API structure
        self.biotools_agencies = {
            'HHS': {
                'programs': ['SBIR', 'STTR', 'biomedical', 'health technology', 'medical device', 
                           'diagnostic', 'therapeutic', 'clinical', 'health surveillance'],
                'exclude_programs': ['social services', 'education', 'administration', 'policy'],
                'sub_agencies': ['NIH', 'CDC', 'FDA']  # These are under HHS umbrella
            },
            'DOD': {
                'programs': ['biological technologies', 'biotechnology', 'biodefense', 
                           'biological systems', 'bioengineering', 'medical countermeasures'],
                'exclude_programs': ['weapons systems', 'communications', 'transportation', 
                                   'cybersecurity', 'logistics'],
                'sub_agencies': ['DARPA', 'Navy', 'Army', 'Air Force']  # DARPA is under DOD
            },
            'NSF': {
                'programs': ['biological sciences', 'molecular', 'cellular', 'biological research',
                           'biotechnology', 'biochemistry', 'biophysics', 'systems biology'],
                'exclude_programs': ['social sciences', 'education', 'geosciences', 'physics general',
                                   'engineering general', 'computer science general']
            },
            'DOE': {
                'programs': ['biological systems', 'bioenergy', 'environmental biology',
                           'genomics', 'systems biology', 'biotechnology research'],
                'exclude_programs': ['fossil energy', 'nuclear energy', 'renewable energy general',
                                   'grid modernization', 'energy efficiency general']
            },
            'NASA': {
                'programs': ['astrobiology', 'life sciences', 'biological systems',
                           'space biology', 'biomedical research', 'life support systems'],
                'exclude_programs': ['aerospace', 'communications', 'earth observation general',
                                   'space exploration general', 'materials general']
            },
            'EPA': {
                'programs': ['environmental biotechnology', 'biological monitoring',
                           'bioremediation', 'ecological research', 'environmental health'],
                'exclude_programs': ['policy', 'regulation', 'administration', 'climate general']
            }
        }
        
        # Enhanced compound biotools keywords - more specific biological context
        self.biotools_compound_keywords = [
            # Genomics & Molecular Biology (enhanced)
            'genomic sequencing', 'DNA sequencing', 'RNA sequencing', 'genome editing',
            'CRISPR technology', 'CRISPR screening', 'genetic analysis', 'molecular diagnostics', 
            'gene expression analysis', 'single cell genomics', 'whole genome sequencing', 
            'targeted sequencing', 'epigenetic analysis', 'ChIP-seq', 'ATAC-seq',
            
            # Cell Biology & Microscopy (enhanced)
            'cell biology tools', 'cellular imaging', 'live cell imaging', 'fluorescence microscopy',
            'confocal microscopy', 'super resolution microscopy', 'cell sorting', 'flow cytometry',
            'single cell analysis', 'cell culture systems', 'stem cell research tools',
            'cell viability assays', 'cell-based screening', 'organoid culture',
            
            # Proteomics & Biochemistry (enhanced)
            'protein analysis', 'mass spectrometry proteomics', 'protein identification',
            'peptide analysis', 'enzyme assays', 'biochemical analysis', 'immunoassays',
            'protein purification', 'protein characterization', 'western blotting',
            'protein-protein interactions', 'structural biology tools',
            
            # Bioinformatics & Computational Biology (enhanced)
            'bioinformatics software', 'computational biology tools', 'sequence analysis',
            'phylogenetic analysis', 'structural bioinformatics', 'systems biology',
            'biological databases', 'genomic data analysis', 'protein modeling',
            'machine learning biology', 'AI drug discovery', 'computational genomics',
            
            # Laboratory Instrumentation (biological context enhanced)
            'laboratory automation', 'bioanalytical instruments', 'clinical diagnostics',
            'point-of-care testing', 'medical diagnostics', 'biological sensors',
            'laboratory equipment', 'analytical instrumentation', 'robotic liquid handling',
            'high-throughput screening', 'automated cell culture',
            
            # Specialized Biotools Areas (enhanced)
            'spatial biology', 'spatial transcriptomics', 'tissue imaging', 'pathology imaging',
            'drug discovery platforms', 'pharmaceutical research', 'biomarker discovery',
            'clinical laboratory tools', 'diagnostic testing', 'therapeutic development',
            'personalized medicine', 'precision medicine tools',
            
            # Microfluidics & Lab-on-Chip (enhanced biological applications)
            'microfluidic devices', 'lab-on-chip systems', 'droplet microfluidics', 
            'biological microfluidics', 'cell manipulation', 'biological sample preparation',
            'organ-on-chip', 'tissue-on-chip', 'microfluidic cell culture',
            
            # Synthetic Biology & Bioengineering (enhanced)
            'synthetic biology tools', 'bioengineering platforms', 'biological engineering', 
            'biosynthesis systems', 'metabolic engineering', 'protein engineering', 
            'genetic engineering tools', 'biological circuits', 'biodesign',
            
            # Multi-omics & Systems Approaches (enhanced)
            'multi-omics integration', 'systems biology tools', 'integrative biology',
            'personalized medicine', 'precision medicine', 'biomedical research tools',
            'translational research', 'clinical translation', 'biomarker validation',
            
            # Emerging Biotools Areas (enhanced)
            'organoid technology', 'tissue engineering', 'regenerative medicine tools',
            'immunotherapy tools', 'cancer research tools', 'neuroscience research tools',
            'microbiome analysis', 'environmental microbiology', 'metagenomics',
            'long-read sequencing', 'nanopore sequencing', 'real-time PCR'
        ]
        
        # Enhanced negative filtering - more comprehensive exclusion
        self.excluded_domains = {
            'astronomy_space': [
                'stellar', 'galactic', 'planetary', 'astronomical', 'astrophysics',
                'space mission', 'satellite communication', 'cosmic ray', 'solar system', 
                'interstellar', 'telescope design', 'observatory', 'space exploration general',
                'rocket propulsion', 'spacecraft', 'orbital mechanics'
            ],
            'geology_earth_science': [
                'geological mapping', 'geophysical', 'seismic', 'tectonic', 'volcanic',
                'sedimentary', 'igneous', 'metamorphic', 'mineral exploration',
                'geochemistry', 'petrology', 'stratigraphy', 'paleontology',
                'hydrogeology', 'geological survey'
            ],
            'physics_non_bio': [
                'particle physics', 'quantum mechanics', 'nuclear physics', 'theoretical physics',
                'condensed matter physics', 'plasma physics', 'high energy physics',
                'atomic physics', 'optics research', 'materials physics',
                'semiconductor physics', 'superconductivity'
            ],
            'engineering_non_bio': [
                'mechanical engineering', 'electrical engineering', 'civil engineering',
                'aerospace engineering', 'chemical engineering general', 'industrial engineering',
                'structural engineering', 'automotive engineering', 'manufacturing engineering',
                'systems engineering general'
            ],
            'environmental_non_bio': [
                'climate modeling', 'atmospheric science', 'meteorology', 'oceanography general',
                'hydrology', 'remote sensing general', 'earth observation', 'weather prediction',
                'greenhouse gas', 'carbon sequestration general'
            ],
            'computer_science_general': [
                'web development', 'mobile application', 'database administration',
                'network security', 'cloud computing', 'cybersecurity',
                'software engineering general', 'information systems',
                'computer graphics', 'user interface'
            ],
            'chemistry_non_bio': [
                'inorganic chemistry', 'physical chemistry', 'materials chemistry',
                'industrial chemistry', 'polymer chemistry general', 'analytical chemistry general',
                'catalysis general', 'electrochemistry general'
            ],
            'energy_non_bio': [
                'solar panels', 'wind energy', 'fossil fuels', 'nuclear energy',
                'grid infrastructure', 'energy storage general', 'smart grid',
                'power systems', 'electrical grid'
            ]
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
            
            # Add enhanced biotools-specific columns
            biotools_columns = {
                'biotools_compound_keywords': 'TEXT',
                'biotools_relevance_score': 'REAL DEFAULT 0.0',
                'biotools_validated': 'BOOLEAN DEFAULT 0',
                'excluded_domain_flags': 'TEXT',
                'biotools_tool_type': 'TEXT',
                'biotools_focus_area': 'TEXT',
                'negative_filter_score': 'REAL DEFAULT 0.0',
                'compound_keyword_matches': 'TEXT',
                'agency_biotools_alignment': 'REAL DEFAULT 0.0',
                'biotools_confidence_score': 'REAL DEFAULT 0.0'
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
                    agency_biotools_alignment REAL DEFAULT 0.0,
                    biotools_confidence_score REAL DEFAULT 0.0,
                    
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
        """Enhanced biotools relevance detection with comprehensive validation"""
        combined_text = f"{title} {description} {keywords}".lower()
        
        relevance_data = {
            'is_relevant': False,
            'relevance_score': 0.0,
            'matched_keywords': [],
            'excluded_domains': [],
            'negative_score': 0.0,
            'tool_type_suggestions': [],
            'focus_area_suggestions': [],
            'confidence_score': 0.0
        }
        
        # Check for compound biotools keywords (positive scoring)
        matched_compounds = []
        for compound_keyword in self.biotools_compound_keywords:
            if compound_keyword.lower() in combined_text:
                matched_compounds.append(compound_keyword)
                # Weight by specificity - longer compound terms get higher scores
                term_weight = len(compound_keyword.split()) * 1.5
                relevance_data['relevance_score'] += term_weight
        
        relevance_data['matched_keywords'] = matched_compounds
        
        # Check for excluded domains (negative scoring)
        excluded_matches = []
        for domain_name, domain_terms in self.excluded_domains.items():
            for term in domain_terms:
                if term.lower() in combined_text:
                    excluded_matches.append((domain_name, term))
                    # Heavy penalty for excluded domains
                    relevance_data['negative_score'] += 4.0
        
        relevance_data['excluded_domains'] = excluded_matches
        
        # Calculate confidence based on match quality
        if matched_compounds:
            # Higher confidence for multiple compound matches
            relevance_data['confidence_score'] = min(len(matched_compounds) * 2.0, 10.0)
            
            # Boost confidence for highly specific terms
            specific_terms = ['CRISPR', 'sequencing', 'proteomics', 'bioinformatics', 'microfluidic']
            for term in specific_terms:
                if any(term.lower() in compound.lower() for compound in matched_compounds):
                    relevance_data['confidence_score'] += 2.0
        
        # Calculate final relevance score
        final_score = relevance_data['relevance_score'] - relevance_data['negative_score']
        relevance_data['relevance_score'] = max(0.0, final_score)
        
        # Enhanced relevance criteria
        relevance_data['is_relevant'] = (
            len(matched_compounds) > 0 and  # Must have compound matches
            relevance_data['relevance_score'] > 3.0 and  # Higher threshold
            len(excluded_matches) <= 1 and  # Minimal contamination
            relevance_data['confidence_score'] > 2.0  # Sufficient confidence
        )
        
        # Enhanced suggestions
        relevance_data['tool_type_suggestions'] = self._suggest_tool_types(matched_compounds)
        relevance_data['focus_area_suggestions'] = self._suggest_focus_areas(matched_compounds)
        
        return relevance_data
    
    def _suggest_tool_types(self, matched_keywords: List[str]) -> List[str]:
        """Enhanced tool type suggestions"""
        tool_type_mappings = {
            'instrument': ['sequencing', 'microscopy', 'cytometry', 'spectrometry', 'imaging', 
                          'automation', 'analyzer', 'scanner', 'detector', 'reader'],
            'software': ['bioinformatics software', 'computational biology', 'analysis', 
                        'modeling', 'algorithm', 'pipeline', 'machine learning'],
            'assay': ['assay', 'testing', 'diagnostic', 'immunoassay', 'biochemical analysis',
                     'screening', 'PCR', 'ELISA', 'western blot'],
            'database_platform': ['database', 'repository', 'platform', 'resource', 
                                 'portal', 'registry'],
            'integrated_system': ['automation', 'platform', 'system', 'workstation', 
                                 'robotic', 'high-throughput'],
            'service': ['service', 'facility', 'core', 'laboratory', 'clinical'],
            'consumable': ['reagent', 'kit', 'supplies', 'media', 'buffer', 'antibody']
        }
        
        suggestions = []
        for tool_type, indicators in tool_type_mappings.items():
            for keyword in matched_keywords:
                if any(indicator in keyword.lower() for indicator in indicators):
                    if tool_type not in suggestions:
                        suggestions.append(tool_type)
        
        return suggestions
    
    def _suggest_focus_areas(self, matched_keywords: List[str]) -> List[str]:
        """Enhanced focus area suggestions"""
        focus_area_mappings = {
            'genomics': ['genomic', 'DNA', 'gene', 'sequencing', 'CRISPR', 'genetic'],
            'cell_biology': ['cell', 'cellular', 'microscopy', 'imaging', 'culture', 'organoid'],
            'proteomics': ['protein', 'peptide', 'mass spectrometry', 'immunoassay'],
            'bioinformatics': ['bioinformatics', 'computational', 'analysis', 'algorithm'],
            'single_cell': ['single cell', 'droplet', 'microfluidic', 'cell sorting'],
            'spatial_biology': ['spatial', 'tissue', 'pathology', 'imaging'],
            'immunology': ['immune', 'antibody', 'immunoassay', 'cytometry'],
            'synthetic_biology': ['synthetic biology', 'bioengineering', 'metabolic'],
            'diagnostics': ['diagnostic', 'clinical', 'point-of-care', 'biomarker'],
            'microbiome': ['microbiome', 'microbial', '16S', 'metagenome'],
            'multi_omics': ['multi-omics', 'integrative', 'systems biology'],
            'high_throughput_screening': ['high throughput', 'screening', 'automation']
        }
        
        suggestions = []
        for focus_area, indicators in focus_area_mappings.items():
            for keyword in matched_keywords:
                if any(indicator in keyword.lower() for indicator in indicators):
                    if focus_area not in suggestions:
                        suggestions.append(focus_area)
        
        return suggestions
    
    def make_api_request(self, endpoint: str, params: Dict[str, Any] = None, max_retries: int = 3) -> Optional[List]:
        """Enhanced API request with better error handling and rate limiting"""
        if endpoint == "solicitations":
            url = "https://api.www.sbir.gov/public/api/solicitations"
            use_params = True  # Changed: solicitations endpoint does accept params
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
                    self.logger.warning(f"API endpoint issue: {response.status_code} for {response.url}")
                    return None

                if response.status_code == 429:
                    wait_time = (attempt + 1) * 20  # Longer waits
                    self.logger.warning(f"Rate limited - waiting {wait_time}s before retry")
                    time.sleep(wait_time)
                    continue
                
                if response.status_code == 400:
                    self.logger.warning(f"Bad request (400) for {response.url} - possibly invalid agency/params")
                    return None

                self.logger.error(f"Unexpected API response: {response.status_code} for {response.url}")
                return None

            except requests.RequestException as e:
                self.logger.error(f"API request failed (attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(15)  # Longer delay between retries

        self.logger.error("API request failed after all retries")
        return None
    
    def fetch_biotools_awards_by_agency(self, agency: str, start_year: int = 2020) -> List[Dict]:
        """Enhanced biotools award fetching with better validation"""
        self.logger.info(f"Fetching {agency} biotools awards from {start_year} with enhanced validation...")
        
        awards = []
        rows_per_request = 1000
        current_year = datetime.now().year
        
        # Get agency-specific programs for better filtering
        agency_info = self.biotools_agencies.get(agency, {})
        expected_programs = agency_info.get('programs', [])
        
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
                
                # Enhanced biotools filtering
                for award in batch_awards:
                    title = award.get('award_title', '')
                    abstract = award.get('abstract', '')
                    keywords = award.get('research_area_keywords', '') or ''
                    program = award.get('program', '')
                    
                    # Pre-filter by agency program alignment
                    program_aligned = False
                    if program:
                        program_lower = program.lower()
                        for expected_prog in expected_programs:
                            if expected_prog.lower() in program_lower:
                                program_aligned = True
                                break
                    else:
                        program_aligned = True  # No program info, allow through
                    
                    if not program_aligned:
                        continue
                    
                    relevance_data = self.is_biotools_relevant(title, abstract, keywords)
                    
                    if relevance_data['is_relevant']:
                        # Calculate agency alignment score
                        agency_alignment = self._calculate_agency_alignment(award, agency)
                        
                        # Enhance award with comprehensive biotools metadata
                        award['biotools_relevance_score'] = relevance_data['relevance_score']
                        award['biotools_validated'] = True
                        award['compound_keyword_matches'] = ','.join(relevance_data['matched_keywords'])
                        award['biotools_tool_type'] = ','.join(relevance_data['tool_type_suggestions'])
                        award['biotools_focus_area'] = ','.join(relevance_data['focus_area_suggestions'])
                        award['excluded_domain_flags'] = ','.join([f"{domain}:{term}" for domain, term in relevance_data['excluded_domains']])
                        award['negative_filter_score'] = relevance_data['negative_score']
                        award['agency_biotools_alignment'] = agency_alignment
                        award['biotools_confidence_score'] = relevance_data['confidence_score']
                        
                        awards.append(award)
                        year_biotools_count += 1
                
                self.logger.info(f"    Batch processed: {len(batch_awards)} awards, {year_biotools_count} biotools-relevant so far")
                
                if len(batch_awards) < rows_per_request:
                    break
                
                year_start += rows_per_request
                time.sleep(3)  # Respectful delay
                
            except Exception as e:
                self.logger.warning(f"    {agency} open solicitations failed: {e}")
        
        # Strategy 2: General open solicitations (no agency filter)
        self.logger.info("  Strategy 2: General open solicitations")
        try:
            params = {
                'open': 1,
                'rows': 100,  # Get more general solicitations
                'format': 'json'
            }
            
            data = self.make_api_request('solicitations', params)
            if data and isinstance(data, list):
                self.logger.info(f"    General open: {len(data)} solicitations")
                all_solicitations.extend(data)
            else:
                self.logger.info("    No general open solicitations")
                
        except Exception as e:
            self.logger.warning(f"    General open solicitations failed: {e}")
        
        # Strategy 3: Recent solicitations (regardless of open status)
        self.logger.info("  Strategy 3: Recent solicitations (any status)")
        try:
            # Get recent solicitations from biotools agencies
            for agency in ['HHS', 'DOD', 'NSF']:  # Focus on major biotools agencies
                params = {
                    'agency': agency,
                    'rows': 25,
                    'format': 'json'
                }
                
                data = self.make_api_request('solicitations', params)
                if data and isinstance(data, list):
                    # Filter for recent ones (last 6 months)
                    recent_solicitations = self._filter_recent_solicitations(data)
                    self.logger.info(f"    {agency} recent: {len(recent_solicitations)} solicitations")
                    all_solicitations.extend(recent_solicitations)
                
                time.sleep(2)
                
        except Exception as e:
            self.logger.warning(f"    Recent solicitations strategy failed: {e}")
        
        # Strategy 4: Keyword-based search with enhanced terms
        self.logger.info("  Strategy 4: Enhanced keyword-based search")
        enhanced_search_terms = [
            'biomedical', 'biotechnology', 'diagnostic', 'therapeutic',
            'genomics', 'proteomics', 'bioinformatics', 'cell biology',
            'molecular biology', 'synthetic biology', 'systems biology'
        ]
        
        for term in enhanced_search_terms:
            try:
                params = {
                    'keyword': term,
                    'rows': 20,
                    'format': 'json'
                }
                
                data = self.make_api_request('solicitations', params)
                if data and isinstance(data, list):
                    self.logger.info(f"    '{term}': {len(data)} solicitations")
                    all_solicitations.extend(data)
                else:
                    self.logger.info(f"    '{term}': No solicitations")
                
                time.sleep(1.5)
                
            except Exception as e:
                self.logger.warning(f"    Keyword '{term}' search failed: {e}")
        
        # Remove duplicates based on solicitation_number and ID
        unique_solicitations = {}
        for sol in all_solicitations:
            # Try multiple ID fields
            sol_id = (sol.get('solicitation_number') or 
                     sol.get('solicitation_id') or 
                     sol.get('id') or 
                     f"{sol.get('agency', 'unknown')}_{sol.get('solicitation_title', 'untitled')}")
            
            if sol_id not in unique_solicitations:
                unique_solicitations[sol_id] = sol
        
        unique_list = list(unique_solicitations.values())
        self.logger.info(f"  📊 Total unique solicitations collected: {len(unique_list)}")
        
        # Apply enhanced biotools filtering
        biotools_solicitations = []
        for sol in unique_list:
            title = sol.get('solicitation_title', '')
            
            # Extract description from multiple sources
            description_sources = []
            
            # From topics
            if 'solicitation_topics' in sol and sol['solicitation_topics']:
                for topic in sol['solicitation_topics']:
                    if isinstance(topic, dict):
                        topic_title = topic.get('topic_title', '')
                        topic_desc = topic.get('topic_description', '')
                        description_sources.append(f"{topic_title} {topic_desc}")
            
            # From other description fields
            description_sources.append(sol.get('description', ''))
            description_sources.append(sol.get('solicitation_description', ''))
            
            topics_text = ' '.join(filter(None, description_sources))
            
            relevance_data = self.is_biotools_relevant(title, topics_text)
            
            if relevance_data['is_relevant']:
                # Calculate agency alignment for solicitations
                agency_alignment = self._calculate_agency_alignment(sol, sol.get('agency', ''))
                
                # Enhance solicitation with biotools metadata
                sol['biotools_relevance_score'] = relevance_data['relevance_score']
                sol['biotools_validated'] = True
                sol['compound_keyword_matches'] = ','.join(relevance_data['matched_keywords'])
                sol['biotools_tool_type'] = ','.join(relevance_data['tool_type_suggestions'])
                sol['biotools_focus_area'] = ','.join(relevance_data['focus_area_suggestions'])
                sol['agency_biotools_alignment'] = agency_alignment
                sol['biotools_confidence_score'] = relevance_data['confidence_score']
                
                biotools_solicitations.append(sol)
        
        self.logger.info(f"✅ Collected {len(biotools_solicitations)} precision biotools solicitations")
        
        if len(biotools_solicitations) == 0:
            self.logger.warning("⚠️  NO BIOTOOLS SOLICITATIONS FOUND")
            self.logger.warning("This could indicate:")
            self.logger.warning("  • No biotools solicitations currently available")
            self.logger.warning("  • API limitations or rate limiting")
            self.logger.warning("  • Enhanced filtering may be too restrictive")
            self.logger.warning("  • Try manual verification at SBIR.gov")
        
        return biotools_solicitations
    
    def _filter_recent_solicitations(self, solicitations: List[Dict]) -> List[Dict]:
        """Filter for recent solicitations (last 6 months)"""
        recent_solicitations = []
        cutoff_date = datetime.now() - timedelta(days=180)
        
        for sol in solicitations:
            is_recent = False
            
            # Check various date fields
            date_fields = ['close_date', 'open_date', 'release_date', 'created_date', 'updated_date']
            for date_field in date_fields:
                date_str = sol.get(date_field, '')
                if date_str:
                    try:
                        # Handle different date formats
                        if 'T' in date_str:  # ISO format
                            sol_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        else:  # Try common formats
                            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%B %d, %Y', '%Y-%m-%d %H:%M:%S']:
                                try:
                                    sol_date = datetime.strptime(date_str.split('T')[0], fmt)
                                    break
                                except ValueError:
                                    continue
                            else:
                                continue
                        
                        if sol_date >= cutoff_date:
                            is_recent = True
                            break
                            
                    except Exception:
                        continue
            
            # Also include if status indicates it's current
            status = sol.get('current_status', '').lower()
            if status in ['open', 'active', 'current', 'accepting']:
                is_recent = True
            
            if is_recent:
                recent_solicitations.append(sol)
        
        return recent_solicitations
    
    def save_awards(self, awards: List[Dict]) -> int:
        """Enhanced award saving with comprehensive biotools metadata"""
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
                contract_id = award.get('contract', '') or award.get('contract_number', '')
                award_data['funding_opportunity_number'] = f"SBIR-{award.get('agency', '')}-{contract_id}"
                award_data['title'] = award.get('award_title', '')[:250]
                award_data['agency'] = award.get('agency', '')
                award_data['description'] = award.get('abstract', '')[:2000] if award.get('abstract') else ''
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
                
                # Enhanced biotools fields (comprehensive)
                biotools_fields = {
                    'biotools_relevance_score': 'biotools_relevance_score',
                    'biotools_validated': 'biotools_validated',
                    'compound_keyword_matches': 'compound_keyword_matches',
                    'biotools_tool_type': 'biotools_tool_type',
                    'biotools_focus_area': 'biotools_focus_area',
                    'excluded_domain_flags': 'excluded_domain_flags',
                    'negative_filter_score': 'negative_filter_score',
                    'agency_biotools_alignment': 'agency_biotools_alignment',
                    'biotools_confidence_score': 'biotools_confidence_score'
                }
                
                for db_field, award_field in biotools_fields.items():
                    if db_field in column_names and award_field in award:
                        award_data[db_field] = award[award_field]
                
                # Standard SBIR fields (comprehensive mapping)
                standard_fields = {
                    'branch': 'branch',
                    'phase': 'phase', 
                    'program': 'program',
                    'award_year': 'award_year',
                    'award_amount': 'award_amount',
                    'contract_number': ['contract', 'contract_number'],
                    'agency_tracking_number': 'agency_tracking_number',
                    'topic_code': 'topic_code',
                    'solicitation_number': 'solicitation_number',
                    'solicitation_year': 'solicitation_year',
                    'company_name': ['firm', 'company_name'],
                    'company_city': ['city', 'company_city'],
                    'company_state': ['state', 'company_state'],
                    'company_uei': ['uei', 'company_uei'],
                    'company_duns': ['duns', 'company_duns'],
                    'company_address': ['address1', 'company_address', 'address'],
                    'company_zip': ['zip', 'company_zip', 'zipcode'],
                    'poc_name': 'poc_name',
                    'pi_name': 'pi_name',
                    'ri_name': 'ri_name'
                }
                
                for db_field, api_fields in standard_fields.items():
                    if db_field in column_names:
                        if isinstance(api_fields, list):
                            # Try multiple possible field names
                            for api_field in api_fields:
                                if api_field in award:
                                    award_data[db_field] = award[api_field]
                                    break
                        else:
                            if api_fields in award:
                                award_data[db_field] = award[api_fields]
                
                # Boolean fields with enhanced handling
                boolean_fields = {
                    'hubzone_owned': 'hubzone_owned',
                    'socially_economically_disadvantaged': 'socially_economically_disadvantaged',
                    'women_owned': 'women_owned'
                }
                
                for db_field, api_field in boolean_fields.items():
                    if db_field in column_names and api_field in award:
                        value = award[api_field]
                        if isinstance(value, str):
                            award_data[db_field] = value.upper() in ['Y', 'YES', 'TRUE', '1']
                        else:
                            award_data[db_field] = bool(value)
                
                # Date fields
                date_fields = {
                    'proposal_award_date': 'proposal_award_date',
                    'contract_end_date': 'contract_end_date'
                }
                
                for db_field, api_field in date_fields.items():
                    if db_field in column_names and api_field in award:
                        date_value = award[api_field]
                        if date_value:
                            try:
                                # Try to parse and format date
                                if 'T' in str(date_value):
                                    parsed_date = datetime.fromisoformat(str(date_value).replace('Z', '+00:00'))
                                    award_data[db_field] = parsed_date.date().isoformat()
                                else:
                                    award_data[db_field] = str(date_value)
                            except:
                                award_data[db_field] = str(date_value)
                
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
                
                # Build SQL dynamically based on available columns
                available_fields = {k: v for k, v in award_data.items() if k in column_names and v is not None}
                
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
            except Exception as e:
                self.logger.error(f"General error saving award: {e}")
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"💾 Saved {saved_count} enhanced biotools awards to database")
        return saved_count
    
    def save_solicitations(self, solicitations: List[Dict]) -> int:
        """Enhanced solicitation saving with comprehensive metadata"""
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
                
                # Basic fields with multiple fallbacks
                sol_number = (sol.get('solicitation_number') or 
                             sol.get('solicitation_id') or 
                             sol.get('id') or 
                             f"SOL-{sol.get('agency', 'UNK')}-{int(time.time())}")
                
                sol_data['funding_opportunity_number'] = f"SOL-{sol_number}"
                sol_data['title'] = (sol.get('solicitation_title') or 
                                   sol.get('title') or 
                                   'Untitled Solicitation')[:250]
                sol_data['agency'] = sol.get('agency', '')
                sol_data['deadline'] = sol.get('close_date', '')
                sol_data['url'] = (sol.get('solicitation_agency_url') or 
                                 sol.get('agency_url') or 
                                 sol.get('url', ''))
                
                # Enhanced description extraction
                description_parts = []
                
                # From direct description fields
                for desc_field in ['description', 'solicitation_description', 'summary']:
                    if sol.get(desc_field):
                        description_parts.append(sol[desc_field])
                
                # From topics with better handling
                if 'solicitation_topics' in sol and sol['solicitation_topics']:
                    topics = sol['solicitation_topics']
                    if isinstance(topics, list):
                        for topic in topics:
                            if isinstance(topic, dict):
                                topic_title = topic.get('topic_title', '')
                                topic_desc = topic.get('topic_description', '')
                                if topic_title or topic_desc:
                                    description_parts.append(f"{topic_title} {topic_desc}".strip())
                    elif isinstance(topics, str):
                        description_parts.append(topics)
                
                sol_data['description'] = ' '.join(description_parts)[:2000] if description_parts else ''
                
                # Enhanced biotools fields
                biotools_fields = {
                    'biotools_relevance_score': 'biotools_relevance_score',
                    'biotools_validated': 'biotools_validated',
                    'compound_keyword_matches': 'compound_keyword_matches',
                    'biotools_tool_type': 'biotools_tool_type',
                    'biotools_focus_area': 'biotools_focus_area',
                    'agency_biotools_alignment': 'agency_biotools_alignment',
                    'biotools_confidence_score': 'biotools_confidence_score'
                }
                
                for db_field, sol_field in biotools_fields.items():
                    if db_field in column_names and sol_field in sol:
                        sol_data[db_field] = sol[sol_field]
                
                # SBIR-specific fields with fallbacks
                sbir_fields = {
                    'branch': 'branch',
                    'phase': ['phase', 'solicitation_phase'],
                    'program': ['program', 'solicitation_program'],
                    'current_status': ['current_status', 'status', 'solicitation_status'],
                    'open_date': ['open_date', 'release_date', 'start_date'],
                    'close_date': ['close_date', 'deadline', 'due_date'],
                    'solicitation_number': ['solicitation_number', 'solicitation_id', 'id'],
                    'solicitation_year': ['solicitation_year', 'year']
                }
                
                for db_field, api_fields in sbir_fields.items():
                    if db_field in column_names:
                        if isinstance(api_fields, list):
                            for api_field in api_fields:
                                if api_field in sol and sol[api_field]:
                                    sol_data[db_field] = sol[api_field]
                                    break
                        else:
                            if api_fields in sol:
                                sol_data[db_field] = sol[api_fields]
                
                # Special handling for solicitation topics (JSON storage)
                if 'solicitation_topics' in column_names and 'solicitation_topics' in sol:
                    try:
                        topics = sol['solicitation_topics']
                        if isinstance(topics, (list, dict)):
                            sol_data['solicitation_topics'] = json.dumps(topics)
                        else:
                            sol_data['solicitation_topics'] = str(topics)
                    except:
                        sol_data['solicitation_topics'] = str(sol.get('solicitation_topics', ''))
                
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
                available_fields = {k: v for k, v in sol_data.items() if k in column_names and v is not None}
                
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
            except Exception as e:
                self.logger.error(f"General error saving solicitation: {e}")
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"💾 Saved {saved_count} enhanced biotools solicitations to database")
        return saved_count
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Enhanced database statistics with comprehensive biotools metrics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # Basic counts
        cursor.execute("SELECT COUNT(*) FROM grants")
        stats['total_grants'] = cursor.fetchone()[0]
        
        # Enhanced biotools metrics
        try:
            cursor.execute("SELECT COUNT(*) FROM grants WHERE biotools_validated = 1")
            stats['biotools_validated'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT AVG(biotools_relevance_score) FROM grants WHERE biotools_relevance_score > 0")
            avg_score = cursor.fetchone()[0]
            stats['avg_biotools_score'] = round(avg_score, 2) if avg_score else 0.0
            
            cursor.execute("SELECT AVG(biotools_confidence_score) FROM grants WHERE biotools_confidence_score > 0")
            avg_confidence = cursor.fetchone()[0]
            stats['avg_confidence_score'] = round(avg_confidence, 2) if avg_confidence else 0.0
            
            cursor.execute("SELECT AVG(agency_biotools_alignment) FROM grants WHERE agency_biotools_alignment > 0")
            avg_alignment = cursor.fetchone()[0]
            stats['avg_agency_alignment'] = round(avg_alignment, 2) if avg_alignment else 0.0
            
        except sqlite3.OperationalError:
            stats['biotools_validated'] = 0
            stats['avg_biotools_score'] = 0.0
            stats['avg_confidence_score'] = 0.0
            stats['avg_agency_alignment'] = 0.0
        
        # Agency breakdown
        cursor.execute("SELECT agency, COUNT(*) FROM grants GROUP BY agency ORDER BY COUNT(*) DESC")
        stats['by_agency'] = cursor.fetchall()
        
        # Grant type breakdown
        try:
            cursor.execute("SELECT grant_type, COUNT(*) FROM grants WHERE grant_type IS NOT NULL GROUP BY grant_type")
            stats['by_type'] = cursor.fetchall()
        except sqlite3.OperationalError:
            stats['by_type'] = []
        
        # Enhanced biotools taxonomy breakdown
        try:
            cursor.execute("""
                SELECT biotools_tool_type, COUNT(*) 
                FROM grants 
                WHERE biotools_tool_type IS NOT NULL AND biotools_tool_type != '' 
                GROUP BY biotools_tool_type 
                ORDER BY COUNT(*) DESC
            """)
            stats['by_tool_type'] = cursor.fetchall()
            
            cursor.execute("""
                SELECT biotools_focus_area, COUNT(*) 
                FROM grants 
                WHERE biotools_focus_area IS NOT NULL AND biotools_focus_area != '' 
                GROUP BY biotools_focus_area 
                ORDER BY COUNT(*) DESC
            """)
            stats['by_focus_area'] = cursor.fetchall()
            
        except sqlite3.OperationalError:
            stats['by_tool_type'] = []
            stats['by_focus_area'] = []
        
        # Recent activity
        try:
            cursor.execute("SELECT COUNT(*) FROM grants WHERE last_scraped_at > date('now', '-30 days')")
            stats['recent_biotools_updates'] = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            stats['recent_biotools_updates'] = 0
        
        # Quality metrics
        try:
            cursor.execute("SELECT COUNT(*) FROM grants WHERE excluded_domain_flags IS NOT NULL AND excluded_domain_flags != ''")
            stats['contaminated_records'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM grants WHERE compound_keyword_matches IS NOT NULL AND compound_keyword_matches != ''")
            stats['compound_keyword_matches'] = cursor.fetchone()[0]
            
        except sqlite3.OperationalError:
            stats['contaminated_records'] = 0
            stats['compound_keyword_matches'] = 0
        
        # Top compound keywords
        try:
            cursor.execute("""
                SELECT compound_keyword_matches, COUNT(*) 
                FROM grants 
                WHERE compound_keyword_matches IS NOT NULL AND compound_keyword_matches != '' 
                GROUP BY compound_keyword_matches 
                ORDER BY COUNT(*) DESC 
                LIMIT 10
            """)
            stats['top_compound_keywords'] = cursor.fetchall()
        except sqlite3.OperationalError:
            stats['top_compound_keywords'] = []
        
        conn.close()
        return stats
    
    def run_comprehensive_biotools_scraping(self, start_year: int = 2022) -> Dict[str, Any]:
        """Run comprehensive biotools data collection with all enhancements"""
        self.logger.info("🚀 Starting Comprehensive BioTools Data Collection")
        self.logger.info("=" * 60)
        
        before_stats = self.get_database_stats()
        self.logger.info(f"📊 Before: {before_stats['total_grants']} total grants, {before_stats.get('biotools_validated', 0)} biotools-validated")
        
        total_added = {
            'awards': 0,
            'solicitations': 0,
            'precision_score': 0.0,
            'confidence_score': 0.0,
            'agency_alignment_score': 0.0
        }
        
        # 1. Comprehensive Award Collection
        self.logger.info("\n" + "=" * 40)
        self.logger.info("🏆 COMPREHENSIVE BIOTOOLS AWARDS COLLECTION")
        
        # Process all agencies with proper error handling
        successful_agencies = []
        failed_agencies = []
        
        for agency in self.biotools_agencies.keys():
            try:
                self.logger.info(f"Processing {agency} with biotools programs: {self.biotools_agencies[agency]['programs']}")
                awards = self.fetch_biotools_awards_by_agency(agency, start_year)
                if awards:
                    saved = self.save_awards(awards)
                    total_added['awards'] += saved
                    successful_agencies.append((agency, saved))
                    
                    # Calculate agency-specific scores
                    if awards:
                        avg_relevance = sum(award.get('biotools_relevance_score', 0) for award in awards) / len(awards)
                        avg_confidence = sum(award.get('biotools_confidence_score', 0) for award in awards) / len(awards)
                        avg_alignment = sum(award.get('agency_biotools_alignment', 0) for award in awards) / len(awards)
                        
                        total_added['precision_score'] += avg_relevance
                        total_added['confidence_score'] += avg_confidence
                        total_added['agency_alignment_score'] += avg_alignment
                        
                        self.logger.info(f"  {agency} scores - Relevance: {avg_relevance:.2f}, Confidence: {avg_confidence:.2f}, Alignment: {avg_alignment:.2f}")
                else:
                    self.logger.warning(f"  {agency}: No biotools awards collected")
                
                time.sleep(8)  # Longer delay between agencies
                
            except Exception as e:
                self.logger.error(f"Failed to process {agency} awards: {e}")
                failed_agencies.append(agency)
        
        # 2. Enhanced Solicitation Collection
        self.logger.info("\n" + "=" * 40)
        self.logger.info("📋 COMPREHENSIVE BIOTOOLS SOLICITATIONS COLLECTION")
        self.logger.info("⏳ Waiting 15 seconds for API recovery...")
        time.sleep(15)
        
        try:
            solicitations = self.fetch_biotools_solicitations()
            if solicitations:
                saved = self.save_solicitations(solicitations)
                total_added['solicitations'] += saved
                
                # Calculate solicitation scores
                if solicitations:
                    avg_relevance = sum(sol.get('biotools_relevance_score', 0) for sol in solicitations) / len(solicitations)
                    avg_confidence = sum(sol.get('biotools_confidence_score', 0) for sol in solicitations) / len(solicitations)
                    total_added['precision_score'] += avg_relevance
                    total_added['confidence_score'] += avg_confidence
                    self.logger.info(f"  Solicitations scores - Relevance: {avg_relevance:.2f}, Confidence: {avg_confidence:.2f}")
            
        except Exception as e:
            self.logger.error(f"Failed to process solicitations: {e}")
            self.logger.warning("💡 Try running 'python app/scraper.py solicitations' separately later")
        
        # 3. Comprehensive Analysis
        self.logger.info("\n" + "=" * 40)
        self.logger.info("📊 COMPREHENSIVE BIOTOOLS ANALYSIS")
        
        after_stats = self.get_database_stats()
        
        # Calculate comprehensive metrics
        precision_metrics = {
            'total_collected': total_added['awards'] + total_added['solicitations'],
            'successful_agencies': len(successful_agencies),
            'failed_agencies': len(failed_agencies),
            'biotools_validated_rate': 0.0,
            'avg_relevance_score': after_stats.get('avg_biotools_score', 0.0),
            'avg_confidence_score': after_stats.get('avg_confidence_score', 0.0),
            'avg_agency_alignment': after_stats.get('avg_agency_alignment', 0.0),
            'compound_keyword_effectiveness': after_stats.get('compound_keyword_matches', 0),
            'domain_coverage': len(after_stats.get('by_focus_area', [])),
            'contamination_rate': 0.0
        }
        
        if precision_metrics['total_collected'] > 0:
            precision_metrics['biotools_validated_rate'] = (
                after_stats.get('biotools_validated', 0) / after_stats['total_grants'] * 100
            )
            
            precision_metrics['contamination_rate'] = (
                after_stats.get('contaminated_records', 0) / after_stats['total_grants'] * 100
            )
        
        # Final Results Report
        self.logger.info("\n" + "=" * 60)
        self.logger.info("📈 COMPREHENSIVE BIOTOOLS SCRAPING RESULTS:")
        self.logger.info(f"  Total grants: {before_stats['total_grants']} → {after_stats['total_grants']} (+{after_stats['total_grants'] - before_stats['total_grants']})")
        self.logger.info(f"  Biotools awards added: {total_added['awards']}")
        self.logger.info(f"  Biotools solicitations added: {total_added['solicitations']}")
        self.logger.info(f"  Biotools validation rate: {precision_metrics['biotools_validated_rate']:.1f}%")
        self.logger.info(f"  Average relevance score: {precision_metrics['avg_relevance_score']:.2f}")
        self.logger.info(f"  Average confidence score: {precision_metrics['avg_confidence_score']:.2f}")
        self.logger.info(f"  Average agency alignment: {precision_metrics['avg_agency_alignment']:.2f}")
        self.logger.info(f"  Contamination rate: {precision_metrics['contamination_rate']:.1f}%")
        
        # Agency Success/Failure Report
        self.logger.info("\n📊 AGENCY COLLECTION REPORT:")
        self.logger.info("  Successful agencies:")
        for agency, count in successful_agencies:
            biotools_indicator = "🧬" if agency in self.biotools_agencies else ""
            self.logger.info(f"    {agency}: {count} grants {biotools_indicator}")
        
        if failed_agencies:
            self.logger.info("  Failed agencies:")
            for agency in failed_agencies:
                self.logger.info(f"    {agency}: API access failed")
        
        # Enhanced Taxonomy Coverage Report
        self.logger.info("\n📊 ENHANCED BIOTOOLS TAXONOMY COVERAGE:")
        if after_stats.get('by_tool_type'):
            self.logger.info("  Tool Types:")
            for tool_type, count in after_stats['by_tool_type'][:8]:
                if tool_type:
                    self.logger.info(f"    {tool_type}: {count}")
        
        if after_stats.get('by_focus_area'):
            self.logger.info("  Focus Areas:")
            for focus_area, count in after_stats['by_focus_area'][:8]:
                if focus_area:
                    self.logger.info(f"    {focus_area}: {count}")
        
        # Quality Metrics Report
        self.logger.info("\n📊 DATA QUALITY METRICS:")
        self.logger.info(f"  Compound keyword matches: {precision_metrics['compound_keyword_effectiveness']}")
        self.logger.info(f"  Domain contamination: {after_stats.get('contaminated_records', 0)} records")
        
        if after_stats.get('top_compound_keywords'):
            self.logger.info("  Top compound keywords:")
            for keyword_set, count in after_stats['top_compound_keywords'][:5]:
                if keyword_set:
                    keywords = keyword_set.split(',')[:3]  # Show first 3
                    self.logger.info(f"    {', '.join(keywords)}: {count}")
        
        # Success Assessment with Enhanced Criteria
        total_new = total_added['awards'] + total_added['solicitations']
        
        if total_new > 0:
            self.logger.info(f"\n🎉 SUCCESS: Comprehensive biotools scraping completed!")
            self.logger.info("📈 Enhanced biotools grant matching system includes:")
            self.logger.info("   • Multi-strategy compound keyword validation")
            self.logger.info("   • Comprehensive domain contamination filtering")
            self.logger.info("   • Advanced biotools taxonomy classification")
            self.logger.info("   • Agency-specific program alignment scoring")
            self.logger.info("   • Enhanced confidence scoring and validation")
            
            # Quality Assessment
            if precision_metrics['biotools_validated_rate'] > 90:
                self.logger.info(f"   • EXCELLENT PRECISION: {precision_metrics['biotools_validated_rate']:.1f}% biotools validation rate")
            elif precision_metrics['biotools_validated_rate'] > 75:
                self.logger.info(f"   • GOOD PRECISION: {precision_metrics['biotools_validated_rate']:.1f}% biotools validation rate")
            else:
                self.logger.warning(f"   • REVIEW NEEDED: {precision_metrics['biotools_validated_rate']:.1f}% biotools validation rate")
            
            if precision_metrics['contamination_rate'] < 5:
                self.logger.info(f"   • EXCELLENT PURITY: {precision_metrics['contamination_rate']:.1f}% contamination rate")
            elif precision_metrics['contamination_rate'] < 15:
                self.logger.info(f"   • GOOD PURITY: {precision_metrics['contamination_rate']:.1f}% contamination rate")
            else:
                self.logger.warning(f"   • REVIEW NEEDED: {precision_metrics['contamination_rate']:.1f}% contamination rate")
            
            if precision_metrics['avg_confidence_score'] > 6:
                self.logger.info(f"   • HIGH CONFIDENCE: {precision_metrics['avg_confidence_score']:.1f} average confidence score")
            elif precision_metrics['avg_confidence_score'] > 3:
                self.logger.info(f"   • MODERATE CONFIDENCE: {precision_metrics['avg_confidence_score']:.1f} average confidence score")
            else:
                self.logger.warning(f"   • LOW CONFIDENCE: {precision_metrics['avg_confidence_score']:.1f} average confidence score")
                
        else:
            self.logger.warning("⚠️  No new biotools data collected")
            self.logger.warning("Possible issues:")
            self.logger.warning("  • API connectivity problems")
            self.logger.warning("  • Compound keyword strategy too restrictive")
            self.logger.warning("  • Agency mapping issues")
            self.logger.warning("  • Rate limiting or temporary API issues")
        
        total_added['precision_metrics'] = precision_metrics
        total_added['successful_agencies'] = successful_agencies
        total_added['failed_agencies'] = failed_agencies
        
        return total_added
    
    def run_solicitations_only(self) -> int:
        """Enhanced solicitations-only update"""
        self.logger.info("🔄 Enhanced Update: Biotools Solicitations Only")
        
        try:
            solicitations = self.fetch_biotools_solicitations()
            saved = self.save_solicitations(solicitations)
            
            self.logger.info(f"✅ Updated {saved} biotools solicitations")
            
            if saved == 0:
                self.logger.warning("⚠️  No biotools solicitations found. This could be due to:")
                self.logger.warning("  • No relevant biotools solicitations currently open")
                self.logger.warning("  • API rate limiting or temporary issues")
                self.logger.warning("  • Enhanced compound keyword strategy filtering")
                self.logger.warning("  • Seasonal variations in solicitation availability")
                self.logger.warning("  • Try again in 30-60 minutes or check SBIR.gov manually")
            
            return saved
            
        except Exception as e:
            self.logger.error(f"Failed to update biotools solicitations: {e}")
            return 0
    
    def run_recent_awards_only(self, months_back: int = 6) -> int:
        """Enhanced recent awards update"""
        self.logger.info(f"🔄 Enhanced Update: Recent Biotools Awards (Last {months_back} Months)")
        
        # Calculate start year for recent data
        cutoff_date = datetime.now() - timedelta(days=months_back * 30)
        start_year = cutoff_date.year
        
        total_awards = 0
        successful_agencies = []
        failed_agencies = []
        
        # Focus on major biotools agencies for quick updates
        priority_agencies = ['HHS', 'DOD', 'NSF']
        
        for agency in priority_agencies:
            try:
                self.logger.info(f"Updating recent {agency} biotools awards...")
                awards = self.fetch_biotools_awards_by_agency(agency, start_year)
                if awards:
                    saved = self.save_awards(awards)
                    total_awards += saved
                    successful_agencies.append((agency, saved))
                    
                    # Calculate and log quality metrics
                    avg_relevance = sum(award.get('biotools_relevance_score', 0) for award in awards) / len(awards)
                    avg_confidence = sum(award.get('biotools_confidence_score', 0) for award in awards) / len(awards)
                    self.logger.info(f"  {agency}: {saved} awards (relevance: {avg_relevance:.1f}, confidence: {avg_confidence:.1f})")
                
                time.sleep(5)  # Respectful delay
                
            except Exception as e:
                self.logger.error(f"Failed to update {agency} recent awards: {e}")
                failed_agencies.append(agency)
        
        # Summary
        self.logger.info(f"✅ Recent awards update completed:")
        self.logger.info(f"  Total new awards: {total_awards}")
        self.logger.info(f"  Successful agencies: {[agency for agency, _ in successful_agencies]}")
        if failed_agencies:
            self.logger.info(f"  Failed agencies: {failed_agencies}")
        
        return total_awards
    
    def test_comprehensive_api_connectivity(self) -> Dict[str, Any]:
        """Comprehensive API connectivity testing with enhanced validation"""
        self.logger.info("🔍 Comprehensive SBIR API Connectivity Testing...")
        
        test_results = {
            'connectivity': {},
            'biotools_validation': {},
            'compound_keyword_test': {},
            'solicitation_analysis': {},
            'agency_validation': {}
        }
        
        # Test 1: Basic API Connectivity
        self.logger.info("  Test 1: Basic API connectivity")
        
        # Awards API
        try:
            data = self.make_api_request('awards', {'rows': 1})
            test_results['connectivity']['awards'] = data is not None and len(data) > 0
            self.logger.info(f"    Awards API: {'✅ Working' if test_results['connectivity']['awards'] else '❌ Failed'}")
        except Exception as e:
            test_results['connectivity']['awards'] = False
            self.logger.error(f"    Awards API: ❌ Failed - {e}")
        
        # Solicitations API
        try:
            data = self.make_api_request('solicitations', {'rows': 5})
            test_results['connectivity']['solicitations'] = data is not None and len(data) >= 0
            self.logger.info(f"    Solicitations API: {'✅ Working' if test_results['connectivity']['solicitations'] else '❌ Failed'}")
            
            # Analyze solicitation structure if available
            if data and len(data) > 0:
                first_sol = data[0]
                test_results['solicitation_analysis'] = {
                    'sample_fields': list(first_sol.keys()),
                    'has_title': 'solicitation_title' in first_sol,
                    'has_topics': 'solicitation_topics' in first_sol,
                    'has_status': 'current_status' in first_sol,
                    'sample_status': first_sol.get('current_status', 'Not found')
                }
                self.logger.info(f"    Solicitation fields: {len(first_sol.keys())} available")
                
        except Exception as e:
            test_results['connectivity']['solicitations'] = False
            self.logger.error(f"    Solicitations API: ❌ Failed - {e}")
        
        # Test 2: Agency Validation
        self.logger.info("  Test 2: Agency validation")
        
        for agency in self.biotools_agencies.keys():
            try:
                # Test with minimal request
                test_data = self.make_api_request('awards', {
                    'agency': agency,
                    'rows': 1
                })
                
                agency_works = test_data is not None and isinstance(test_data, list)
                test_results['agency_validation'][agency] = {
                    'api_accessible': agency_works,
                    'sample_size': len(test_data) if test_data else 0
                }
                
                status = "✅ Working" if agency_works else "❌ Failed"
                self.logger.info(f"    {agency} API: {status}")
                
                if agency_works and test_data:
                    # Quick biotools relevance check
                    sample_award = test_data[0]
                    title = sample_award.get('award_title', '')
                    abstract = sample_award.get('abstract', '')
                    relevance = self.is_biotools_relevant(title, abstract)
                    test_results['agency_validation'][agency]['sample_biotools_relevant'] = relevance['is_relevant']
                
                time.sleep(2)  # Rate limiting
                
            except Exception as e:
                test_results['agency_validation'][agency] = {
                    'api_accessible': False,
                    'error': str(e)
                }
                self.logger.error(f"    {agency} API: ❌ Failed - {e}")
        
        # Test 3: Enhanced Compound Keyword Effectiveness
        if test_results['connectivity'].get('awards'):
            self.logger.info("  Test 3: Enhanced compound keyword effectiveness")
            
            try:
                # Test with HHS data (usually has biotools content)
                test_data = self.make_api_request('awards', {
                    'agency': 'HHS',
                    'year': 2024,
                    'rows': 50  # Larger sample for better statistics
                })
                
                if test_data:
                    biotools_count = 0
                    high_confidence_count = 0
                    total_count = len(test_data)
                    confidence_scores = []
                    
                    for award in test_data:
                        title = award.get('award_title', '')
                        abstract = award.get('abstract', '')
                        relevance_data = self.is_biotools_relevant(title, abstract)
                        
                        if relevance_data['is_relevant']:
                            biotools_count += 1
                            confidence_scores.append(relevance_data['confidence_score'])
                            
                            if relevance_data['confidence_score'] > 5.0:
                                high_confidence_count += 1
                    
                    effectiveness_rate = (biotools_count / total_count * 100) if total_count > 0 else 0
                    high_confidence_rate = (high_confidence_count / biotools_count * 100) if biotools_count > 0 else 0
                    avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
                    
                    test_results['compound_keyword_test'] = {
                        'effectiveness_rate': effectiveness_rate,
                        'high_confidence_rate': high_confidence_rate,
                        'avg_confidence_score': avg_confidence,
                        'sample_size': total_count,
                        'biotools_matches': biotools_count,
                        'high_confidence_matches': high_confidence_count
                    }
                    
                    self.logger.info(f"    Compound keyword effectiveness: {effectiveness_rate:.1f}% ({biotools_count}/{total_count})")
                    self.logger.info(f"    High confidence rate: {high_confidence_rate:.1f}%")
                    self.logger.info(f"    Average confidence score: {avg_confidence:.1f}")
                    
                    # Assessment
                    if effectiveness_rate > 40:
                        self.logger.info("    ✅ EXCELLENT effectiveness - compound keywords working very well")
                    elif effectiveness_rate > 20:
                        self.logger.info("    ✅ GOOD effectiveness - compound keywords working well")
                    elif effectiveness_rate > 10:
                        self.logger.info("    ⚠️  MODERATE effectiveness - consider keyword refinement")
                    else:
                        self.logger.warning("    ❌ LOW effectiveness - compound keywords need revision")
                
            except Exception as e:
                self.logger.error(f"    Compound keyword test failed: {e}")
        
        # Test 4: Overall Assessment
        working_apis = sum(1 for result in test_results['connectivity'].values() if result)
        working_agencies = sum(1 for agency_data in test_results['agency_validation'].values() 
                              if agency_data.get('api_accessible', False))
        
        self.logger.info(f"\n📊 COMPREHENSIVE TEST RESULTS:")
        self.logger.info(f"  API Endpoints: {working_apis}/2 working")
        self.logger.info(f"  Agencies: {working_agencies}/{len(self.biotools_agencies)} accessible")
        
        if working_apis == 2 and working_agencies >= 3:
            self.logger.info("🎉 Excellent! Ready for comprehensive biotools scraping.")
        elif working_apis >= 1 and working_agencies >= 2:
            self.logger.info("✅ Good! Can proceed with available endpoints and agencies.")
        else:
            self.logger.warning("⚠️  Limited API access. Check network connectivity and API status.")
        
        # Recommendations
        self.logger.info(f"\n💡 RECOMMENDATIONS:")
        if working_agencies < len(self.biotools_agencies):
            failed_agencies = [agency for agency, data in test_results['agency_validation'].items() 
                             if not data.get('api_accessible', False)]
            self.logger.info(f"  • Focus on working agencies: {[agency for agency in self.biotools_agencies.keys() if agency not in failed_agencies]}")
        
        if test_results.get('compound_keyword_test', {}).get('effectiveness_rate', 0) < 15:
            self.logger.info("  • Consider expanding compound keyword list")
            self.logger.info("  • Review agency-specific biotools programs")
        
        if working_apis < 2:
            self.logger.info("  • Check SBIR.gov API status")
            self.logger.info("  • Try again in 30 minutes")
            self.logger.info("  • Consider alternative data sources")
        
        return test_results


def main():
    """Enhanced main execution function with comprehensive options"""
    scraper = CompleteBiotoolsScraper()
    
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command in ['comprehensive', 'full', 'complete']:
            # Comprehensive biotools scraping
            start_year = int(sys.argv[2]) if len(sys.argv) > 2 else 2022
            results = scraper.run_comprehensive_biotools_scraping(start_year)
            
            print(f"\n🎯 COMPREHENSIVE SCRAPING SUMMARY:")
            print(f"  Awards: {results['awards']}")
            print(f"  Solicitations: {results['solicitations']}")
            print(f"  Successful agencies: {len(results.get('successful_agencies', []))}")
            print(f"  Failed agencies: {len(results.get('failed_agencies', []))}")
            
            if 'precision_metrics' in results:
                metrics = results['precision_metrics']
                print(f"  Validation Rate: {metrics['biotools_validated_rate']:.1f}%")
                print(f"  Avg Relevance: {metrics['avg_relevance_score']:.2f}")
                print(f"  Avg Confidence: {metrics['avg_confidence_score']:.2f}")
                print(f"  Contamination: {metrics['contamination_rate']:.1f}%")
            
        elif command == 'solicitations':
            # Enhanced solicitations only
            result = scraper.run_solicitations_only()
            print(f"✅ Solicitations updated: {result}")
            
        elif command == 'recent':
            # Enhanced recent awards
            months = int(sys.argv[2]) if len(sys.argv) > 2 else 6
            result = scraper.run_recent_awards_only(months)
            print(f"✅ Recent awards updated: {result}")
            
        elif command == 'test':
            # Comprehensive API testing
            results = scraper.test_comprehensive_api_connectivity()
            
            working_apis = sum(1 for result in results['connectivity'].values() if result)
            working_agencies = sum(1 for agency_data in results['agency_validation'].values() 
                                  if agency_data.get('api_accessible', False))
            
            print(f"\n🎯 API TEST SUMMARY:")
            print(f"  Working APIs: {working_apis}/2")
            print(f"  Accessible agencies: {working_agencies}/{len(scraper.biotools_agencies)}")
            
            if results.get('compound_keyword_test'):
                test = results['compound_keyword_test']
                print(f"  Keyword effectiveness: {test.get('effectiveness_rate', 0):.1f}%")
                print(f"  Average confidence: {test.get('avg_confidence_score', 0):.1f}")
            
            if working_apis >= 1 and working_agencies >= 2:
                print("\n🎉 Ready for biotools scraping!")
            else:
                print("\n⚠️ API issues detected. Check logs for details.")
                
        elif command == 'stats':
            # Enhanced biotools statistics
            stats = scraper.get_database_stats()
            print("\n📊 Enhanced BioTools Database Statistics:")
            print(f"  Total Grants: {stats['total_grants']}")
            print(f"  BioTools Validated: {stats['biotools_validated']}")
            print(f"  Average Relevance Score: {stats['avg_biotools_score']}")
            print(f"  Average Confidence Score: {stats['avg_confidence_score']}")
            print(f"  Average Agency Alignment: {stats['avg_agency_alignment']}")
            print(f"  Contaminated Records: {stats['contaminated_records']}")
            print(f"  Compound Keyword Matches: {stats['compound_keyword_matches']}")
            
            if stats['by_agency']:
                print(f"\n📊 Grants by Agency:")
                for agency, count in stats['by_agency'][:10]:
                    biotools_indicator = "🧬" if agency in scraper.biotools_agencies else ""
                    print(f"   {agency}: {count} {biotools_indicator}")
            
            if stats['by_tool_type']:
                print(f"\n🛠️ BioTools Tool Types:")
                for tool_type, count in stats['by_tool_type'][:8]:
                    if tool_type:
                        print(f"   {tool_type}: {count}")
            
            if stats['by_focus_area']:
                print(f"\n🎯 BioTools Focus Areas:")
                for focus_area, count in stats['by_focus_area'][:8]:
                    if focus_area:
                        print(f"   {focus_area}: {count}")
                        
        else:
            print("Complete Enhanced BioTools Scraper Usage:")
            print("  python app/scraper.py comprehensive [start_year]  # Complete biotools collection")
            print("  python app/scraper.py solicitations              # Update biotools solicitations")
            print("  python app/scraper.py recent [months]            # Update recent awards")
            print("  python app/scraper.py test                       # Comprehensive API testing")
            print("  python app/scraper.py stats                      # Enhanced biotools statistics")
            print("")
            print("Aliases:")
            print("  'full', 'complete' → comprehensive")
            print("  Default behavior: comprehensive scraping from 2022")
    else:
        # Default: run comprehensive biotools scraping from 2022
        print("🚀 Starting default comprehensive biotools scraping from 2022...")
        print("💡 Use 'python app/scraper.py test' to validate APIs and keywords first")
        scraper.run_comprehensive_biotools_scraping(2022)


if __name__ == "__main__":
    main() Respectful delay
            
            relevance_rate = (year_biotools_count / year_total_count * 100) if year_total_count > 0 else 0
            self.logger.info(f"  {agency} {year}: {year_biotools_count}/{year_total_count} biotools-relevant ({relevance_rate:.1f}%)")
        
        self.logger.info(f"✅ {agency}: Collected {len(awards)} precision biotools awards")
        return awards
    
    def _calculate_agency_alignment(self, award: Dict[str, Any], agency: str) -> float:
        """Calculate how well an award aligns with agency's biotools focus"""
        score = 0.0
        
        agency_info = self.biotools_agencies.get(agency, {})
        expected_programs = agency_info.get('programs', [])
        excluded_programs = agency_info.get('exclude_programs', [])
        
        program = award.get('program', '').lower()
        title = award.get('award_title', '').lower()
        abstract = award.get('abstract', '').lower()
        
        combined_text = f"{program} {title} {abstract}"
        
        # Positive scoring for expected programs
        for expected_prog in expected_programs:
            if expected_prog.lower() in combined_text:
                score += 2.0
        
        # Negative scoring for excluded programs
        for excluded_prog in excluded_programs:
            if excluded_prog.lower() in combined_text:
                score -= 3.0
        
        # Bonus for agency-specific biotools indicators
        agency_specific_indicators = {
            'HHS': ['clinical', 'medical', 'health', 'diagnostic', 'therapeutic'],
            'DOD': ['defense', 'countermeasure', 'battlefield', 'military'],
            'NSF': ['fundamental', 'basic research', 'innovation', 'discovery'],
            'DOE': ['energy', 'biofuel', 'environmental', 'sustainability'],
            'NASA': ['space', 'microgravity', 'astrobiology', 'life support'],
            'EPA': ['environmental', 'pollution', 'contamination', 'monitoring']
        }
        
        if agency in agency_specific_indicators:
            for indicator in agency_specific_indicators[agency]:
                if indicator in combined_text:
                    score += 1.0
        
        return max(0.0, score)
    
    def fetch_biotools_solicitations(self) -> List[Dict]:
        """Enhanced solicitation fetching with comprehensive strategy"""
        self.logger.info("🔍 Enhanced SBIR Solicitations Collection with Multiple Strategies")
        
        all_solicitations = []
        
        # Strategy 1: Agency-specific open solicitations
        self.logger.info("  Strategy 1: Agency-specific open solicitations")
        for agency in self.biotools_agencies.keys():
            try:
                params = {
                    'agency': agency,
                    'open': 1,
                    'rows': 50,  # Increased from 25
                    'format': 'json'
                }
                
                data = self.make_api_request('solicitations', params)
                if data and isinstance(data, list):
                    self.logger.info(f"    {agency}: {len(data)} open solicitations")
                    all_solicitations.extend(data)
                else:
                    self.logger.info(f"    {agency}: No open solicitations")
                
                time.sleep(3)  #