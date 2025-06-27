#!/usr/bin/env python3
"""
Enhanced BioTools Scraper with Advanced TABA Detection and Tracking
Identifies TABA funding in SBIR/STTR awards and tracks amounts/status
"""

import requests
import sqlite3
from datetime import datetime, timedelta
import time
import os
import json
from typing import List, Dict, Any, Optional, Set, Tuple
import logging
import re

class EnhancedBiotoolsScraperWithTABA:
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
        
        # Enhanced TABA detection patterns
        self.taba_keywords = {
            'explicit_taba': [
                'TABA', 'Technical and Business Assistance', 'Technical & Business Assistance',
                'commercialization assistance', 'business assistance funding',
                'technical assistance funding', 'TABA funding', 'TABA funds',
                'TABA supplement', 'TABA services', 'TABA provider'
            ],
            'commercialization_indicators': [
                'commercialization plan', 'market assessment', 'customer discovery',
                'intellectual property strategy', 'IP protection', 'regulatory strategy',
                'business strategy', 'manufacturing plan', 'market validation',
                'commercialization activities', 'technology transfer'
            ],
            'vendor_services': [
                'third-party service provider', 'commercialization vendor',
                'business consultant', 'technical consultant', 'IP consultant',
                'market research consultant', 'regulatory consultant'
            ],
            'funding_amounts': [
                '$6,500', '$6500', 'six thousand five hundred',
                '$50,000', '$50000', 'fifty thousand',
                'additional funding', 'supplemental funding', 'over and above'
            ]
        }
        
        # TABA amount patterns for extraction
        self.taba_amount_patterns = [
            r'\$?6[,.]?500',  # $6,500 or $6500 or 6500
            r'\$?50[,.]?000',  # $50,000 or $50000 or 50000
            r'six thousand five hundred',
            r'fifty thousand',
            r'TABA.*?\$?(\d{1,2}[,.]?\d{3})',  # TABA followed by amount
            r'technical.*?assistance.*?\$?(\d{1,2}[,.]?\d{3})',
            r'commercialization.*?assistance.*?\$?(\d{1,2}[,.]?\d{3})'
        ]
        
        # Biotools agencies and programs (keeping existing structure)
        self.biotools_agencies = {
            'HHS': {
                'programs': ['SBIR', 'STTR', 'biomedical', 'health technology', 'medical device', 
                           'diagnostic', 'therapeutic', 'clinical', 'health surveillance'],
                'exclude_programs': ['social services', 'education', 'administration', 'policy'],
                'sub_agencies': ['NIH', 'CDC', 'FDA'],
                'taba_available': True,
                'taba_phase1_max': 6500,
                'taba_phase2_max': 50000
            },
            'DOD': {
                'programs': ['biological technologies', 'biotechnology', 'biodefense', 
                           'biological systems', 'bioengineering', 'medical countermeasures'],
                'exclude_programs': ['weapons systems', 'communications', 'transportation', 
                                   'cybersecurity', 'logistics'],
                'sub_agencies': ['DARPA', 'Navy', 'Army', 'Air Force'],
                'taba_available': True,  # Varies by component
                'taba_phase1_max': 6500,
                'taba_phase2_max': 50000
            },
            'NSF': {
                'programs': ['biotechnology', 'biological sciences', 'bioengineering', 
                           'molecular biosciences', 'biological systems'],
                'exclude_programs': ['computer science', 'mathematics', 'physics', 'engineering'],
                'sub_agencies': ['BIO', 'ENG'],
                'taba_available': True,
                'taba_phase1_max': 6500,
                'taba_phase2_max': 50000
            },
            'DOE': {
                'programs': ['biological sciences', 'biotechnology', 'bioenergy', 
                           'environmental biology', 'systems biology'],
                'exclude_programs': ['nuclear', 'fossil', 'renewable energy', 'climate'],
                'sub_agencies': ['OBER'],
                'taba_available': True,  # Called "Commercialization Assistance"
                'taba_phase1_max': 6500,
                'taba_phase2_max': 50000
            },
            'USDA': {
                'programs': ['agricultural biotechnology', 'food safety', 'plant biology'],
                'exclude_programs': ['farming', 'rural development', 'forestry'],
                'sub_agencies': ['NIFA'],
                'taba_available': True,
                'taba_phase1_max': 6500,
                'taba_phase2_max': 50000
            },
            'NASA': {
                'programs': ['astrobiology', 'life sciences', 'biological research'],
                'exclude_programs': ['space technology', 'aeronautics', 'planetary science'],
                'sub_agencies': [],
                'taba_available': True,
                'taba_phase1_max': 6500,
                'taba_phase2_max': 50000
            }
        }
        
        # Enhanced biotools keywords (keeping existing structure)
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
        
        self.init_enhanced_database()
        self.company_cache = {}
    
    def init_enhanced_database(self):
        """Initialize database with enhanced TABA tracking"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Drop existing table if it exists
            cursor.execute("DROP TABLE IF EXISTS grants")
            cursor.execute("DROP TABLE IF EXISTS companies")
            
            # Create comprehensive grants table with TABA tracking
            cursor.execute('''
                CREATE TABLE grants (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    abstract TEXT,
                    agency TEXT,
                    program TEXT,
                    award_number TEXT,
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
                    
                    -- Enhanced TABA Tracking
                    has_taba_funding BOOLEAN DEFAULT FALSE,
                    taba_amount INTEGER DEFAULT 0,
                    taba_type TEXT,  -- 'explicit', 'likely', 'commercialization', 'none'
                    taba_keywords_matched TEXT,
                    taba_confidence_score REAL DEFAULT 0.0,
                    taba_eligible BOOLEAN DEFAULT FALSE,
                    
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
                    
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    
                    -- Create a unique constraint on combination of fields
                    UNIQUE(award_number, agency, title)
                )
            ''')
            
            # Create companies table (unchanged)
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
            self.logger.info("Enhanced database with TABA tracking created successfully")
            
            # Create enhanced indexes
            try:
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_grants_title ON grants(title)",
                    "CREATE INDEX IF NOT EXISTS idx_grants_agency ON grants(agency)",
                    "CREATE INDEX IF NOT EXISTS idx_grants_relevance ON grants(relevance_score)",
                    "CREATE INDEX IF NOT EXISTS idx_grants_biotools_category ON grants(biotools_category)",
                    "CREATE INDEX IF NOT EXISTS idx_grants_confidence ON grants(confidence_score)",
                    "CREATE INDEX IF NOT EXISTS idx_grants_taba_funding ON grants(has_taba_funding)",
                    "CREATE INDEX IF NOT EXISTS idx_grants_taba_amount ON grants(taba_amount)",
                    "CREATE INDEX IF NOT EXISTS idx_grants_taba_type ON grants(taba_type)",
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
            self.logger.info("Enhanced database with TABA tracking initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing enhanced database: {e}")
            conn.rollback()
        finally:
            conn.close()

    def detect_taba_funding(self, title: str, abstract: str, program: str, phase: str, agency: str) -> Tuple[bool, int, str, List[str], float]:
        """
        Advanced TABA detection with confidence scoring
        Returns: (has_taba, amount, type, matched_keywords, confidence_score)
        """
        combined_text = f"{title} {abstract} {program}".lower()
        
        has_taba = False
        taba_amount = 0
        taba_type = 'none'
        matched_keywords = []
        confidence_score = 0.0
        
        # Check if agency offers TABA
        agency_config = self.biotools_agencies.get(agency, {})
        taba_eligible = agency_config.get('taba_available', False)
        
        if not taba_eligible:
            return False, 0, 'none', [], 0.0
        
        # 1. Explicit TABA mentions (highest confidence)
        for keyword in self.taba_keywords['explicit_taba']:
            if keyword.lower() in combined_text:
                has_taba = True
                taba_type = 'explicit'
                matched_keywords.append(keyword)
                confidence_score += 3.0
        
        # 2. Extract TABA amounts
        for pattern in self.taba_amount_patterns:
            matches = re.findall(pattern, combined_text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, str):
                    # Clean and convert amount
                    amount_str = re.sub(r'[^\d]', '', match)
                    if amount_str:
                        amount = int(amount_str)
                        if amount in [6500, 50000]:  # Standard TABA amounts
                            has_taba = True
                            taba_amount = amount
                            taba_type = 'explicit'
                            confidence_score += 4.0
                            matched_keywords.append(f"${amount:,}")
        
        # 3. Commercialization indicators (medium confidence)
        commercialization_matches = 0
        for keyword in self.taba_keywords['commercialization_indicators']:
            if keyword.lower() in combined_text:
                commercialization_matches += 1
                matched_keywords.append(keyword)
                confidence_score += 1.0
        
        if commercialization_matches >= 2:
            if not has_taba:  # Only set if not already explicit
                has_taba = True
                taba_type = 'commercialization'
        
        # 4. Vendor service indicators (lower confidence)
        vendor_matches = 0
        for keyword in self.taba_keywords['vendor_services']:
            if keyword.lower() in combined_text:
                vendor_matches += 1
                matched_keywords.append(keyword)
                confidence_score += 0.5
        
        if vendor_matches >= 1 and commercialization_matches >= 1:
            if not has_taba:
                has_taba = True
                taba_type = 'likely'
        
        # 5. Funding amount indicators
        for keyword in self.taba_keywords['funding_amounts']:
            if keyword.lower() in combined_text:
                matched_keywords.append(keyword)
                confidence_score += 1.5
                if not has_taba:
                    has_taba = True
                    taba_type = 'likely'
        
        # 6. Set default amounts based on phase if not detected
        if has_taba and taba_amount == 0:
            if phase and 'I' in phase.upper() and 'II' not in phase.upper():
                taba_amount = agency_config.get('taba_phase1_max', 6500)
            elif phase and 'II' in phase.upper():
                taba_amount = agency_config.get('taba_phase2_max', 50000)
            else:
                taba_amount = 6500  # Default to Phase I
        
        # Cap confidence score
        confidence_score = min(confidence_score, 10.0)
        
        # Remove duplicates from matched keywords
        matched_keywords = list(set(matched_keywords))
        
        self.logger.debug(f"TABA Detection: {title[:50]}... -> {has_taba}, ${taba_amount}, {taba_type}, {confidence_score:.1f}")
        
        return has_taba, taba_amount, taba_type, matched_keywords, confidence_score

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
        
        # Check compound keywords first
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
        
        # Require explicit biological context
        has_biological_context = any(bio_term in text for bio_term in [
            'biolog', 'gene', 'dna', 'rna', 'protein', 'cell', 'tissue', 'enzyme',
            'antibody', 'molecular', 'genomic', 'proteomic', 'biomedical', 'clinical',
            'diagnostic', 'therapeutic', 'pharmaceutical', 'biotech', 'life science'
        ])
        
        if not has_biological_context:
            return (0.0, 0.0, [], [], [])
        
        # Check category-based keywords
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
        
        # Bonus for multiple category matches
        if len(matched_categories) > 1:
            relevance_score += len(matched_categories) * 0.5
            confidence_score += len(matched_categories) * 0.3
        
        # Cap scores
        relevance_score = min(relevance_score, 10.0)
        confidence_score = min(confidence_score, 10.0)
        
        return (
            relevance_score, 
            confidence_score, 
            list(matched_categories), 
            matched_keywords, 
            compound_matches
        )

    def save_enhanced_awards_with_taba(self, awards: List[Dict]) -> int:
        """Save enhanced awards with comprehensive TABA detection and tracking"""
        if not awards:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        saved_count = 0
        taba_count = 0
        
        try:
            for award in awards:
                try:
                    # Extract basic award data
                    title = award.get('award_title', '')[:500]
                    description = award.get('description', '')[:5000] if award.get('description') else ''
                    abstract = award.get('abstract', '')[:5000] if award.get('abstract') else ''
                    agency = award.get('agency', '')
                    program = award.get('program', '')
                    award_number = award.get('contract', '') or award.get('award_number', '')
                    firm = award.get('firm', '')
                    pi = award.get('pi_name', '') or award.get('principal_investigator', '')
                    phase = award.get('phase', '')
                    
                    # Handle amount properly
                    amount = 0
                    if award.get('award_amount'):
                        try:
                            amount_str = str(award['award_amount']).replace(',', '').replace('$', '')
                            amount = int(float(amount_str))
                        except (ValueError, TypeError):
                            amount = 0
                    
                    award_date = award.get('proposal_award_date', '') or award.get('award_date', '')
                    end_date = award.get('contract_end_date', '') or award.get('end_date', '')
                    keywords = award.get('research_area_keywords', '') or award.get('keywords', '')
                    
                    # Enhanced biotools scoring
                    relevance_score = award.get('relevance_score', 0.0)
                    confidence_score = award.get('confidence_score', 0.0)
                    biotools_category = award.get('biotools_category', '')
                    compound_matches = award.get('compound_keyword_matches', '')
                    agency_alignment = award.get('agency_alignment_score', 0.0)
                    url = award.get('award_link', '') or award.get('url', '')
                    
                    # ENHANCED TABA DETECTION
                    has_taba, taba_amount, taba_type, taba_keywords, taba_confidence = self.detect_taba_funding(
                        title, abstract, program, phase, agency
                    )
                    
                    # Check if agency offers TABA (for eligibility flag)
                    agency_config = self.biotools_agencies.get(agency, {})
                    taba_eligible = agency_config.get('taba_available', False)
                    
                    if has_taba:
                        taba_count += 1
                    
                    # Extract contact information
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
                    zip_code = award.get('zip', '') or award.get('zip_code', '')
                    uei = award.get('uei', '')
                    duns = award.get('duns', '')
                    
                    # Handle number_awards safely
                    number_awards = 0
                    if award.get('number_awards'):
                        try:
                            number_awards = int(award['number_awards'])
                        except (ValueError, TypeError):
                            number_awards = 0
                    
                    hubzone_owned = award.get('hubzone_owned', '')
                    socially_economically_disadvantaged = award.get('socially_economically_disadvantaged', '')
                    woman_owned = award.get('women_owned', '') or award.get('woman_owned', '')
                    
                    # Insert with enhanced TABA tracking
                    cursor.execute('''
                        INSERT OR IGNORE INTO grants 
                        (title, description, abstract, agency, program, award_number, firm, 
                         principal_investigator, amount, award_date, end_date, phase, keywords, 
                         source, grant_type, relevance_score, confidence_score, biotools_category,
                         compound_keyword_matches, agency_alignment_score, url,
                         has_taba_funding, taba_amount, taba_type, taba_keywords_matched, 
                         taba_confidence_score, taba_eligible,
                         poc_name, poc_title, poc_phone, poc_email, pi_phone, pi_email,
                         ri_poc_name, ri_poc_phone, company_name, company_url, address1, address2,
                         city, state, zip_code, uei, duns, number_awards, hubzone_owned,
                         socially_economically_disadvantaged, woman_owned, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        title, description, abstract, agency, program, award_number, firm,
                        pi, amount, award_date, end_date, phase, keywords,
                        'SBIR', 'award', relevance_score, confidence_score, biotools_category,
                        compound_matches, agency_alignment, url,
                        has_taba, taba_amount, taba_type, ','.join(taba_keywords) if taba_keywords else '',
                        taba_confidence, taba_eligible,
                        poc_name, poc_title, poc_phone, poc_email, pi_phone, pi_email,
                        ri_poc_name, ri_poc_phone, company_name, company_url, address1, address2,
                        city, state, zip_code, uei, duns, number_awards, hubzone_owned,
                        socially_economically_disadvantaged, woman_owned, datetime.now().isoformat()
                    ))
                    
                    if cursor.rowcount > 0:
                        saved_count += 1
                    
                    # Commit every 50 records
                    if saved_count % 50 == 0:
                        conn.commit()
                        self.logger.info(f"Committed {saved_count} records, {taba_count} with TABA...")
                    
                except sqlite3.IntegrityError as e:
                    award_id = award.get('contract', award.get('award_title', 'unknown'))
                    self.logger.warning(f"Duplicate award {award_id}: {e}")
                    continue
                except Exception as e:
                    award_id = award.get('contract', award.get('award_title', 'unknown'))
                    self.logger.error(f"Error saving award {award_id}: {e}")
                    continue
            
            # Final commit
            conn.commit()
            
        except Exception as e:
            self.logger.error(f"Database error during save: {e}")
            conn.rollback()
        finally:
            conn.close()
        
        self.logger.info(f"💾 Saved {saved_count} awards with TABA tracking ({taba_count} with TABA funding)")
        return saved_count

    def get_taba_statistics(self) -> Dict[str, Any]:
        """Get comprehensive TABA statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        try:
            # Basic TABA counts
            cursor.execute("SELECT COUNT(*) FROM grants WHERE has_taba_funding = 1")
            stats['total_taba_grants'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM grants WHERE taba_eligible = 1")
            stats['taba_eligible_grants'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM grants")
            total_grants = cursor.fetchone()[0]
            stats['total_grants'] = total_grants
            
            # TABA adoption rate
            if stats['taba_eligible_grants'] > 0:
                stats['taba_adoption_rate'] = (stats['total_taba_grants'] / stats['taba_eligible_grants']) * 100
            else:
                stats['taba_adoption_rate'] = 0.0
            
            # TABA by type
            cursor.execute("SELECT taba_type, COUNT(*) FROM grants WHERE has_taba_funding = 1 GROUP BY taba_type")
            taba_by_type = cursor.fetchall()
            stats['taba_by_type'] = {ttype: count for ttype, count in taba_by_type}
            
            # TABA by agency
            cursor.execute("SELECT agency, COUNT(*) FROM grants WHERE has_taba_funding = 1 GROUP BY agency")
            taba_by_agency = cursor.fetchall()
            stats['taba_by_agency'] = {agency: count for agency, count in taba_by_agency}
            
            # TABA amounts distribution
            cursor.execute("SELECT taba_amount, COUNT(*) FROM grants WHERE has_taba_funding = 1 AND taba_amount > 0 GROUP BY taba_amount ORDER BY taba_amount")
            taba_amounts = cursor.fetchall()
            stats['taba_amounts_distribution'] = {amount: count for amount, count in taba_amounts}
            
            # Total TABA funding
            cursor.execute("SELECT SUM(taba_amount) FROM grants WHERE has_taba_funding = 1")
            total_taba_funding = cursor.fetchone()[0] or 0
            stats['total_taba_funding'] = total_taba_funding
            
            # Average TABA confidence
            cursor.execute("SELECT AVG(taba_confidence_score) FROM grants WHERE has_taba_funding = 1")
            avg_confidence = cursor.fetchone()[0] or 0
            stats['avg_taba_confidence'] = avg_confidence
            
            # TABA by biotools relevance
            cursor.execute("SELECT COUNT(*) FROM grants WHERE has_taba_funding = 1 AND relevance_score >= 1.5")
            stats['biotools_relevant_with_taba'] = cursor.fetchone()[0]
            
            # Phase distribution for TABA
            cursor.execute("SELECT phase, COUNT(*) FROM grants WHERE has_taba_funding = 1 GROUP BY phase")
            taba_by_phase = cursor.fetchall()
            stats['taba_by_phase'] = {phase or 'Unknown': count for phase, count in taba_by_phase}
            
        except Exception as e:
            self.logger.error(f"Error getting TABA statistics: {e}")
        finally:
            conn.close()
        
        return stats

    # Include all the other methods from the previous scraper...
    # (make_api_request, fetch_company_data, get_company_info, etc.)
    
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
                        company_name = company.get('firm', '').strip()
                        if company_name:
                            companies[company_name.lower()] = company
                
                self.logger.info(f"Fetched {len(data)} companies (total cached: {len(companies)})")
                
                if len(data) < rows_per_request:
                    break
                    
                start += rows_per_request
                time.sleep(2)
                
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
        
        # Try UEI first
        if uei and uei in self.company_cache:
            return self.company_cache[uei]
        
        # Fallback to company name matching
        if firm_name:
            firm_lower = firm_name.lower().strip()
            if firm_lower in self.company_cache:
                return self.company_cache[firm_lower]
            
            # Fuzzy matching for similar company names
            for cached_name, company_data in self.company_cache.items():
                if isinstance(cached_name, str) and len(cached_name) > 10:
                    if firm_lower in cached_name or cached_name in firm_lower:
                        return company_data
        
        return {}

    def fetch_enhanced_awards_by_agency(self, agency: str, start_year: int = 2022) -> List[Dict]:
        """Enhanced award fetching with TABA detection"""
        self.logger.info(f"Fetching enhanced {agency} awards with TABA detection from {start_year}...")
        
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
            year_taba_count = 0
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
                        phase = award.get('phase', '')
                        
                        # Enhanced relevance calculation
                        relevance_score, confidence_score, categories, keywords, compounds = \
                            self.calculate_biotools_relevance(title, abstract, program)
                        
                        if relevance_score >= 1.5:
                            # TABA detection
                            has_taba, taba_amount, taba_type, taba_keywords, taba_confidence = \
                                self.detect_taba_funding(title, abstract, program, phase, agency)
                            
                            if has_taba:
                                year_taba_count += 1
                            
                            # Get company information
                            firm_name = award.get('firm', '')
                            uei = award.get('uei', '')
                            company_info = self.get_company_info(firm_name, uei)
                            
                            # Enhanced award data with TABA tracking
                            award['relevance_score'] = relevance_score
                            award['confidence_score'] = confidence_score
                            award['biotools_category'] = ','.join(categories) if categories else ''
                            award['compound_keyword_matches'] = ','.join(compounds) if compounds else ''
                            award['has_taba_funding'] = has_taba
                            award['taba_amount'] = taba_amount
                            award['taba_type'] = taba_type
                            award['taba_keywords_matched'] = taba_keywords
                            award['taba_confidence_score'] = taba_confidence
                            
                            # Add company information to award
                            if company_info:
                                award['company_name'] = company_info.get('firm', firm_name)
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
                                award['woman_owned'] = company_info.get('women_owned', '')
                            
                            awards.append(award)
                            year_biotools_count += 1
                    
                    time.sleep(2)
                    
                    if len(data) < rows_per_request:
                        break
                    
                    year_start += rows_per_request
                    
                except Exception as e:
                    self.logger.error(f"Error fetching {agency} {year} awards: {e}")
                    break
            
            time.sleep(1)
            
            relevance_rate = (year_biotools_count / year_total_count * 100) if year_total_count > 0 else 0
            taba_rate = (year_taba_count / year_biotools_count * 100) if year_biotools_count > 0 else 0
            self.logger.info(f"  {agency} {year}: {year_biotools_count}/{year_total_count} biotools-relevant ({relevance_rate:.1f}%), {year_taba_count} with TABA ({taba_rate:.1f}%)")
        
        self.logger.info(f"✅ {agency}: Collected {len(awards)} enhanced biotools-relevant awards with TABA tracking")
        return awards

    def run_comprehensive_biotools_scraping_with_taba(self, start_year: int = 2022) -> Dict[str, Any]:
        """Run comprehensive biotools data collection with enhanced TABA tracking"""
        self.logger.info("🚀 Starting Comprehensive BioTools Data Collection with Enhanced TABA Tracking")
        self.logger.info("=" * 70)
        
        # Pre-load company data for faster processing
        self.logger.info("📋 Pre-loading company data...")
        self.fetch_company_data()
        
        before_stats = self.get_taba_statistics()
        self.logger.info(f"📊 Before: {before_stats.get('total_grants', 0)} total grants, {before_stats.get('total_taba_grants', 0)} with TABA")
        
        total_added = {
            'awards': 0,
            'taba_awards': 0,
            'successful_agencies': [],
            'failed_agencies': [],
            'taba_metrics': {}
        }
        
        # Enhanced Awards Collection with TABA Detection
        self.logger.info("\n" + "=" * 40)
        self.logger.info("🏆 ENHANCED AWARD COLLECTION WITH TABA DETECTION")
        
        for agency in self.biotools_agencies.keys():
            try:
                self.logger.info(f"\nProcessing {agency} with enhanced TABA detection...")
                awards = self.fetch_enhanced_awards_by_agency(agency, start_year)
                saved = self.save_enhanced_awards_with_taba(awards)
                total_added['awards'] += saved
                total_added['successful_agencies'].append(agency)
                
                # Count TABA awards for this agency
                taba_awards_count = sum(1 for award in awards if award.get('has_taba_funding', False))
                total_added['taba_awards'] += taba_awards_count
                
                # Inter-agency delay for API respect
                time.sleep(5)
                
            except Exception as e:
                self.logger.error(f"Failed to process {agency} awards: {e}")
                total_added['failed_agencies'].append(agency)
        
        # Quality Assessment with TABA Metrics
        self.logger.info("\n" + "=" * 40)
        self.logger.info("🎯 QUALITY ASSESSMENT WITH TABA METRICS")
        
        after_stats = self.get_taba_statistics()
        
        # Calculate TABA metrics
        taba_metrics = {
            'total_taba_grants': after_stats.get('total_taba_grants', 0),
            'taba_adoption_rate': after_stats.get('taba_adoption_rate', 0),
            'total_taba_funding': after_stats.get('total_taba_funding', 0),
            'avg_taba_confidence': after_stats.get('avg_taba_confidence', 0),
            'biotools_relevant_with_taba': after_stats.get('biotools_relevant_with_taba', 0),
            'taba_by_type': after_stats.get('taba_by_type', {}),
            'taba_by_agency': after_stats.get('taba_by_agency', {}),
            'taba_amounts_distribution': after_stats.get('taba_amounts_distribution', {})
        }
        
        total_added['taba_metrics'] = taba_metrics
        
        # Final Summary
        self.logger.info("\n" + "=" * 60)
        self.logger.info("🎉 COMPREHENSIVE COLLECTION WITH TABA TRACKING COMPLETE!")
        self.logger.info("=" * 60)
        self.logger.info(f"📊 Enhanced awards collected: {total_added['awards']}")
        self.logger.info(f"💰 Awards with TABA funding: {taba_metrics['total_taba_grants']}")
        self.logger.info(f"💵 Total TABA funding tracked: ${taba_metrics['total_taba_funding']:,}")
        self.logger.info(f"📈 TABA adoption rate: {taba_metrics['taba_adoption_rate']:.1f}%")
        self.logger.info(f"🎯 Avg TABA confidence: {taba_metrics['avg_taba_confidence']:.2f}")
        self.logger.info(f"🧬 Biotools awards with TABA: {taba_metrics['biotools_relevant_with_taba']}")
        
        # Log TABA by type
        self.logger.info("\n📋 TABA Detection Breakdown:")
        for taba_type, count in taba_metrics['taba_by_type'].items():
            self.logger.info(f"  {taba_type}: {count} awards")
        
        return total_added


def main():
    """Enhanced main execution function with TABA tracking"""
    scraper = EnhancedBiotoolsScraperWithTABA()
    
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command in ['comprehensive', 'full', 'complete']:
            # Comprehensive biotools scraping with TABA tracking
            start_year = int(sys.argv[2]) if len(sys.argv) > 2 else 2022
            results = scraper.run_comprehensive_biotools_scraping_with_taba(start_year)
            
            print(f"\n🎯 COMPREHENSIVE SCRAPING WITH TABA TRACKING SUMMARY:")
            print(f"  Awards: {results['awards']}")
            print(f"  TABA Awards: {results['taba_awards']}")
            print(f"  Successful agencies: {len(results.get('successful_agencies', []))}")
            print(f"  Failed agencies: {len(results.get('failed_agencies', []))}")
            
            if 'taba_metrics' in results:
                metrics = results['taba_metrics']
                print(f"  Total TABA Funding: ${metrics['total_taba_funding']:,}")
                print(f"  TABA Adoption Rate: {metrics['taba_adoption_rate']:.1f}%")
                print(f"  Avg TABA Confidence: {metrics['avg_taba_confidence']:.2f}")
                
        elif command == 'taba-stats':
            # Show detailed TABA statistics
            stats = scraper.get_taba_statistics()
            print(f"\n💰 DETAILED TABA STATISTICS:")
            print(f"  Total grants: {stats['total_grants']}")
            print(f"  TABA eligible grants: {stats['taba_eligible_grants']}")
            print(f"  Grants with TABA: {stats['total_taba_grants']}")
            print(f"  TABA adoption rate: {stats['taba_adoption_rate']:.1f}%")
            print(f"  Total TABA funding: ${stats['total_taba_funding']:,}")
            print(f"  Average TABA confidence: {stats['avg_taba_confidence']:.2f}")
            
            print(f"\n📋 TABA by Type:")
            for taba_type, count in stats.get('taba_by_type', {}).items():
                print(f"    {taba_type}: {count}")
                
            print(f"\n🏛️ TABA by Agency:")
            for agency, count in stats.get('taba_by_agency', {}).items():
                print(f"    {agency}: {count}")
                
            print(f"\n💵 TABA Amount Distribution:")
            for amount, count in stats.get('taba_amounts_distribution', {}).items():
                print(f"    ${amount:,}: {count} awards")
            
        else:
            print("Enhanced BioTools Scraper with TABA Tracking Usage:")
            print("  python app/scraper.py comprehensive [start_year]  # Complete collection with TABA tracking")
            print("  python app/scraper.py taba-stats                  # Detailed TABA statistics")
            print("")
            print("New TABA features:")
            print("  • Advanced TABA funding detection and classification")
            print("  • TABA amount extraction and tracking")
            print("  • TABA confidence scoring")
            print("  • Comprehensive TABA statistics and reporting")
            print("  • Agency-specific TABA eligibility tracking")
    else:
        # Default: run comprehensive biotools scraping with TABA from 2022
        print("🚀 Starting comprehensive biotools scraping with TABA tracking from 2022...")
        scraper.run_comprehensive_biotools_scraping_with_taba(2022)


if __name__ == "__main__":
    main()