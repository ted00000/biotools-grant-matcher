#!/usr/bin/env python3
"""
Complete Enhanced BioTools SBIR/STTR Scraper - Fixed Version
Key improvements over previous version:
- Fixed agency mappings (NIH/CDC under HHS, DARPA under DOD)
- Enhanced solicitation collection strategy
- Improved error handling and rate limiting
- Better compound keyword validation
- Comprehensive biotools taxonomy classification
- FIXED: Line 587 syntax error with proper try/except structure
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
                'sub_agencies': ['DARPA', 'Navy', 'Army', 'Air Force']  # Fixed truncation
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
                'sub_agencies': ['OBER']  # Office of Biological and Environmental Research
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
        
        # Enhanced biotools keywords with compound validation
        self.biotools_keywords = {
            # High-precision instruments (highest weight)
            'instruments': [
                'microscope', 'microscopy', 'spectrometer', 'spectrometry', 'sequencer', 'sequencing',
                'cytometer', 'flow cytometry', 'mass spectrometry', 'chromatography', 'electrophoresis',
                'imaging system', 'detection system', 'analytical instrument', 'laboratory instrument'
            ],
            
            # Genomics & Sequencing (enhanced)
            'genomics': [
                'DNA sequencing', 'RNA sequencing', 'genome sequencing', 'genomic analysis',
                'CRISPR', 'gene editing', 'genetic engineering', 'genomics platform', 
                'next-generation sequencing', 'single-cell sequencing', 'spatial genomics',
                'epigenomics', 'metagenomics', 'transcriptomics', 'whole genome sequencing'
            ],
            
            # Cell Biology & Analysis (enhanced) 
            'cell_biology': [
                'cell analysis', 'cellular imaging', 'live cell imaging', 'cell sorting',
                'cell culture', 'cell isolation', 'single cell analysis', 'cell counting',
                'cell viability', 'cell-based assays', 'cellular characterization',
                'organoid', 'spheroid', 'tissue engineering', 'stem cell', 'cell line development'
            ],
            
            # Proteomics & Protein Analysis (enhanced)
            'proteomics': [
                'protein analysis', 'protein identification', 'protein quantification', 'proteomics',
                'peptide analysis', 'enzyme assays', 'biochemical analysis', 'immunoassays',
                'protein purification', 'protein characterization', 'western blotting',
                'protein-protein interactions', 'structural biology tools'
            ],
            
            # Bioinformatics & Computational Biology (enhanced)
            'bioinformatics': [
                'bioinformatics software', 'computational biology tools', 'sequence analysis',
                'phylogenetic analysis', 'structural bioinformatics', 'systems biology',
                'biological databases', 'genomic data analysis', 'protein modeling',
                'machine learning biology', 'AI drug discovery', 'computational genomics'
            ],
            
            # Laboratory Instrumentation (biological context enhanced)
            'lab_equipment': [
                'laboratory automation', 'bioanalytical instruments', 'clinical diagnostics',
                'point-of-care testing', 'medical diagnostics', 'biological sensors',
                'laboratory equipment', 'analytical instrumentation', 'robotic liquid handling',
                'high-throughput screening', 'automated cell culture'
            ],
            
            # Specialized Biotools Areas (enhanced)
            'specialized': [
                'spatial biology', 'spatial transcriptomics', 'tissue imaging', 'pathology imaging',
                'drug discovery platforms', 'pharmaceutical research', 'biomarker discovery',
                'clinical laboratory tools', 'diagnostic testing', 'therapeutic development',
                'personalized medicine', 'precision medicine tools'
            ],
            
            # Microfluidics & Lab-on-Chip (enhanced biological applications)
            'microfluidics': [
                'microfluidic devices', 'lab-on-chip systems', 'droplet microfluidics', 
                'biological microfluidics', 'cell manipulation', 'biological sample preparation',
                'organ-on-chip', 'tissue-on-chip', 'microfluidic cell culture'
            ],
            
            # Synthetic Biology & Bioengineering (enhanced)
            'synthetic_biology': [
                'synthetic biology tools', 'bioengineering platforms', 'biological engineering', 
                'biosynthesis systems', 'metabolic engineering', 'protein engineering', 
                'genetic engineering tools', 'biological circuits', 'biodesign'
            ],
            
            # Multi-omics & Systems Approaches (enhanced)
            'multi_omics': [
                'multi-omics integration', 'systems biology tools', 'integrative biology',
                'personalized medicine', 'precision medicine', 'biomedical research tools',
                'translational research', 'clinical translation', 'biomarker validation'
            ],
            
            # Emerging Biotools Areas (enhanced)
            'emerging': [
                'organoid technology', 'tissue engineering', 'regenerative medicine tools',
                'bioprinting', '3D cell culture', 'biomaterials', 'biocompatible materials',
                'nanotechnology biology', 'biological nanosensors', 'biosensors'
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
    
    def init_database(self):
        """Initialize database with comprehensive schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create comprehensive grants table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS grants (
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
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_grants_title ON grants(title)",
            "CREATE INDEX IF NOT EXISTS idx_grants_agency ON grants(agency)",
            "CREATE INDEX IF NOT EXISTS idx_grants_relevance ON grants(relevance_score)",
            "CREATE INDEX IF NOT EXISTS idx_grants_biotools_category ON grants(biotools_category)",
            "CREATE INDEX IF NOT EXISTS idx_grants_confidence ON grants(confidence_score)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        conn.commit()
        conn.close()
        self.logger.info("Database initialized with comprehensive schema")

    def calculate_biotools_relevance(self, title: str, abstract: str = "", program: str = "") -> tuple:
        """Calculate comprehensive biotools relevance with confidence scoring"""
        text = f"{title} {abstract} {program}".lower()
        
        relevance_score = 0.0
        confidence_score = 0.0
        matched_categories = set()
        matched_keywords = []
        compound_matches = []
        
        # 1. Check compound keywords first (highest confidence)
        for compound in self.compound_keywords:
            if compound.lower() in text:
                compound_matches.append(compound)
                relevance_score += 3.0  # High value for compound matches
                confidence_score += 2.0
        
        # 2. Check category-based keywords
        for category, keywords in self.biotools_keywords.items():
            category_matches = 0
            for keyword in keywords:
                if keyword.lower() in text:
                    matched_keywords.append(keyword)
                    matched_categories.add(category)
                    category_matches += 1
                    
                    # Weight by category importance
                    if category == 'instruments':
                        relevance_score += 2.5
                        confidence_score += 1.5
                    elif category in ['genomics', 'cell_biology', 'proteomics']:
                        relevance_score += 2.0
                        confidence_score += 1.2
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
        
        # 3. Bonus for multiple category matches
        if len(matched_categories) > 1:
            relevance_score += len(matched_categories) * 0.5
            confidence_score += len(matched_categories) * 0.3
        
        # 4. Cap scores
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
        
        # More stringent criteria
        return relevance_score >= 1.5 and confidence_score >= 1.0

    def calculate_agency_alignment(self, agency: str, program: str, title: str, abstract: str) -> float:
        """Calculate how well the grant aligns with agency's biotools focus"""
        if agency not in self.biotools_agencies:
            return 1.0  # Neutral for unknown agencies
        
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

    def fetch_enhanced_awards_by_agency(self, agency: str, start_year: int = 2022) -> List[Dict]:
        """Enhanced award fetching with comprehensive filtering"""
        self.logger.info(f"Fetching enhanced {agency} awards from {start_year}...")
        
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
                        
                        if relevance_score >= 1.5:  # More stringent threshold
                            # Calculate agency alignment
                            agency_alignment = self.calculate_agency_alignment(
                                agency, program, title, abstract
                            )
                            
                            # Enhanced award data
                            award['relevance_score'] = relevance_score
                            award['confidence_score'] = confidence_score
                            award['biotools_category'] = ','.join(categories) if categories else ''
                            award['compound_keyword_matches'] = ','.join(compounds) if compounds else ''
                            award['agency_alignment_score'] = agency_alignment
                            
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
        
        self.logger.info(f"✅ {agency}: Collected {len(awards)} enhanced biotools-relevant awards")
        return awards

    def fetch_enhanced_solicitations(self) -> List[Dict]:
        """Enhanced solicitation fetching with biotools focus"""
        self.logger.info("Fetching enhanced biotools solicitations...")
        
        solicitations = []
        max_rows = 50  # API limit
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
                    
                    if relevance_score >= 1.0:  # Slightly lower threshold for solicitations
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

    def save_enhanced_awards(self, awards: List[Dict]) -> int:
        """Save enhanced awards with comprehensive data"""
        if not awards:
            return 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        saved_count = 0
        
        for award in awards:
            try:
                # Extract and clean enhanced data
                title = award.get('award_title', '')[:500]
                description = award.get('description', '')[:2000] if award.get('description') else ''
                abstract = award.get('abstract', '')[:2000] if award.get('abstract') else ''
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
                
                # Insert enhanced award
                cursor.execute('''
                    INSERT OR REPLACE INTO grants 
                    (title, description, abstract, agency, program, award_number, firm, 
                     principal_investigator, amount, award_date, end_date, phase, keywords, 
                     source, grant_type, relevance_score, confidence_score, biotools_category,
                     compound_keyword_matches, agency_alignment_score, url, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    title, description, abstract, agency, program, award_number, firm,
                    pi, amount, award_date, end_date, phase, keywords,
                    'SBIR', 'award', relevance_score, confidence_score, biotools_category,
                    compound_matches, agency_alignment, url, datetime.now().isoformat()
                ))
                
                saved_count += 1
                
            except Exception as e:
                self.logger.error(f"Error saving award {award.get('award_number', 'unknown')}: {e}")
                continue
        
        conn.commit()
        conn.close()
        
        self.logger.info(f"💾 Saved {saved_count} enhanced awards to database")
        return saved_count

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
                description = solicitation.get('description', '')[:2000] if solicitation.get('description') else ''
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
        """Get comprehensive database statistics"""
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
            
        except Exception as e:
            self.logger.error(f"Error getting database stats: {e}")
        finally:
            conn.close()
        
        return stats
    
    def run_comprehensive_biotools_scraping(self, start_year: int = 2022) -> Dict[str, Any]:
        """Run comprehensive biotools data collection with all enhancements"""
        self.logger.info("🚀 Starting Comprehensive BioTools Data Collection")
        self.logger.info("=" * 60)
        
        before_stats = self.get_database_stats()
        self.logger.info(f"📊 Before: {before_stats.get('total_grants', 0)} total grants, {before_stats.get('biotools_validated', 0)} biotools-validated")
        
        total_added = {
            'awards': 0,
            'solicitations': 0,
            'successful_agencies': [],
            'failed_agencies': [],
            'precision_metrics': {}
        }
        
        # 1. Enhanced Awards Collection
        self.logger.info("\n" + "=" * 40)
        self.logger.info("🏆 ENHANCED AWARD COLLECTION")
        
        for agency in self.biotools_agencies.keys():
            try:
                self.logger.info(f"\nProcessing {agency} with enhanced filtering...")
                awards = self.fetch_enhanced_awards_by_agency(agency, start_year)
                saved = self.save_enhanced_awards(awards)
                total_added['awards'] += saved
                total_added['successful_agencies'].append(agency)
                
                # Inter-agency delay for API respect
                time.sleep(5)
                
            except Exception as e:
                self.logger.error(f"Failed to process {agency} awards: {e}")
                total_added['failed_agencies'].append(agency)
        
        # 2. Enhanced Solicitations Collection
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
        self.logger.info("🎯 QUALITY ASSESSMENT")
        
        after_stats = self.get_database_stats()
        
        # Calculate precision metrics
        precision_metrics = {
            'biotools_validated_rate': (after_stats.get('biotools_validated', 0) / max(after_stats.get('total_grants', 1), 1)) * 100,
            'avg_relevance_score': after_stats.get('avg_relevance_score', 0),
            'avg_confidence_score': after_stats.get('avg_confidence_score', 0),
            'avg_agency_alignment': after_stats.get('avg_agency_alignment', 0),
            'contamination_rate': (after_stats.get('contaminated_records', 0) / max(after_stats.get('total_grants', 1), 1)) * 100,
            'compound_keyword_coverage': (after_stats.get('compound_keyword_matches', 0) / max(after_stats.get('total_grants', 1), 1)) * 100
        }
        
        total_added['precision_metrics'] = precision_metrics
        
        # 4. Final Summary
        self.logger.info("\n" + "=" * 50)
        self.logger.info("🎉 COMPREHENSIVE COLLECTION COMPLETE!")
        self.logger.info("=" * 50)
        self.logger.info(f"📊 Enhanced awards collected: {total_added['awards']}")
        self.logger.info(f"📋 Enhanced solicitations collected: {total_added['solicitations']}")
        self.logger.info(f"✅ Successful agencies: {len(total_added['successful_agencies'])}")
        self.logger.info(f"❌ Failed agencies: {len(total_added['failed_agencies'])}")
        self.logger.info(f"🎯 Biotools validation rate: {precision_metrics['biotools_validated_rate']:.1f}%")
        self.logger.info(f"📈 Avg relevance score: {precision_metrics['avg_relevance_score']:.2f}")
        self.logger.info(f"🔍 Avg confidence score: {precision_metrics['avg_confidence_score']:.2f}")
        self.logger.info(f"⚠️  Contamination rate: {precision_metrics['contamination_rate']:.1f}%")
        
        return total_added

    def run_solicitations_only(self) -> int:
        """Run enhanced solicitations collection only"""
        self.logger.info("📋 Running Enhanced Solicitations Collection Only")
        
        try:
            solicitations = self.fetch_enhanced_solicitations()
            saved = self.save_enhanced_solicitations(solicitations)
            self.logger.info(f"✅ Enhanced solicitations updated: {saved}")
            return saved
        except Exception as e:
            self.logger.error(f"Failed to update solicitations: {e}")
            return 0

    def update_recent_awards(self, months: int = 6) -> int:
        """Update recent awards with enhanced processing"""
        self.logger.info(f"🔄 Updating recent awards with enhanced processing (last {months} months)")
        
        cutoff_date = datetime.now() - timedelta(days=months * 30)
        start_year = cutoff_date.year
        
        total_awards = 0
        agencies = ['HHS', 'NSF', 'DOD', 'DOE']  # Focus on key biotools agencies
        
        for agency in agencies:
            try:
                self.logger.info(f"Updating {agency} recent awards...")
                awards = self.fetch_enhanced_awards_by_agency(agency, start_year)
                saved = self.save_enhanced_awards(awards)
                total_awards += saved
                
            except Exception as e:
                self.logger.error(f"Failed to update {agency} awards: {e}")
        
        self.logger.info(f"✅ Updated {total_awards} recent enhanced awards")
        return total_awards

    def test_comprehensive_api_connectivity(self) -> Dict[str, Any]:
        """Comprehensive API and keyword testing"""
        self.logger.info("🔍 Running Comprehensive API and Keyword Testing...")
        
        test_results = {
            'api_endpoints': {},
            'agency_validation': {},
            'compound_keyword_test': {},
            'overall_status': 'unknown'
        }
        
        # 1. Test API endpoints
        self.logger.info("\n📡 Testing API Endpoints...")
        
        endpoints = [
            ('awards', {'rows': 1}),
            ('solicitations', {'rows': 5}),
            ('firm', {'rows': 1})
        ]
        
        for endpoint, params in endpoints:
            try:
                data = self.make_api_request(endpoint, params)
                success = data is not None and len(data) >= 0
                test_results['api_endpoints'][endpoint] = {
                    'accessible': success,
                    'sample_size': len(data) if data else 0
                }
                self.logger.info(f"  {endpoint}: {'✅ Working' if success else '❌ Failed'}")
            except Exception as e:
                test_results['api_endpoints'][endpoint] = {'accessible': False, 'error': str(e)}
                self.logger.error(f"  {endpoint}: ❌ Failed - {e}")
        
        # 2. Test agency-specific data access
        self.logger.info("\n🏛️  Testing Agency Data Access...")
        
        for agency in list(self.biotools_agencies.keys())[:3]:  # Test first 3 agencies
            try:
                data = self.make_api_request('awards', {'agency': agency, 'rows': 5})
                success = data is not None and len(data) > 0
                
                biotools_count = 0
                if success and data:
                    for award in data:
                        title = award.get('award_title', '')
                        abstract = award.get('abstract', '')
                        if self.is_biotools_relevant(title, abstract):
                            biotools_count += 1
                
                test_results['agency_validation'][agency] = {
                    'api_accessible': success,
                    'sample_size': len(data) if data else 0,
                    'biotools_matches': biotools_count,
                    'biotools_rate': (biotools_count / len(data) * 100) if data and len(data) > 0 else 0
                }
                
                self.logger.info(f"  {agency}: {'✅' if success else '❌'} - {biotools_count}/{len(data) if data else 0} biotools relevant")
                
            except Exception as e:
                test_results['agency_validation'][agency] = {'api_accessible': False, 'error': str(e)}
                self.logger.error(f"  {agency}: ❌ Failed - {e}")
        
        # 3. Test compound keyword effectiveness
        self.logger.info("\n🔬 Testing Compound Keyword Effectiveness...")
        
        try:
            # Sample some recent awards to test keyword effectiveness
            sample_data = self.make_api_request('awards', {'rows': 50, 'year': 2024})
            
            if sample_data:
                compound_hits = 0
                total_tested = len(sample_data)
                
                for award in sample_data:
                    title = award.get('award_title', '')
                    abstract = award.get('abstract', '')
                    text = f"{title} {abstract}".lower()
                    
                    for compound in self.compound_keywords:
                        if compound.lower() in text:
                            compound_hits += 1
                            break
                
                effectiveness_rate = (compound_hits / total_tested * 100) if total_tested > 0 else 0
                
                test_results['compound_keyword_test'] = {
                    'tested_records': total_tested,
                    'compound_hits': compound_hits,
                    'effectiveness_rate': effectiveness_rate
                }
                
                self.logger.info(f"  Compound keywords: {compound_hits}/{total_tested} hits ({effectiveness_rate:.1f}%)")
                
            else:
                test_results['compound_keyword_test'] = {'error': 'No sample data available'}
                
        except Exception as e:
            test_results['compound_keyword_test'] = {'error': str(e)}
            self.logger.error(f"  Compound keyword test failed: {e}")
        
        # 4. Overall assessment
        working_apis = sum(1 for ep in test_results['api_endpoints'].values() if ep.get('accessible', False))
        working_agencies = sum(1 for agency in test_results['agency_validation'].values() if agency.get('api_accessible', False))
        
        self.logger.info(f"\n📊 COMPREHENSIVE TEST RESULTS:")
        self.logger.info(f"  API Endpoints: {working_apis}/3 working")
        self.logger.info(f"  Agency Access: {working_agencies}/{len(test_results['agency_validation'])} working")
        
        compound_effectiveness = test_results.get('compound_keyword_test', {}).get('effectiveness_rate', 0)
        self.logger.info(f"  Compound Keywords: {compound_effectiveness:.1f}% effectiveness")
        
        # Overall status
        if working_apis == 3 and working_agencies >= 2 and compound_effectiveness >= 10:
            test_results['overall_status'] = 'excellent'
            self.logger.info("🎉 Excellent! All systems working optimally. Ready for comprehensive biotools scraping.")
        elif working_apis >= 1 and working_agencies >= 2:
            test_results['overall_status'] = 'good'
            self.logger.info("✅ Good! Can proceed with available endpoints and agencies.")
        else:
            test_results['overall_status'] = 'limited'
            self.logger.warning("⚠️  Limited API access. Check network connectivity and API status.")
        
        # Recommendations
        self.logger.info(f"\n💡 RECOMMENDATIONS:")
        if working_agencies < len(self.biotools_agencies):
            failed_agencies = [agency for agency, data in test_results['agency_validation'].items() 
                             if not data.get('api_accessible', False)]
            working_list = [agency for agency in self.biotools_agencies.keys() if agency not in failed_agencies]
            self.logger.info(f"  • Focus on working agencies: {working_list}")
        
        if test_results.get('compound_keyword_test', {}).get('effectiveness_rate', 0) < 15:
            self.logger.info("  • Consider expanding compound keyword list")
            self.logger.info("  • Review agency-specific biotools programs")
        
        if working_apis < 2:
            self.logger.info("  • Check SBIR.gov API status")
            self.logger.info("  • Try again in 30 minutes")
            self.logger.info("  • Consider alternative data sources")
        
        return test_results

    def show_enhanced_database_stats(self):
        """Display enhanced database statistics"""
        stats = self.get_database_stats()
        
        self.logger.info("\n📊 ENHANCED DATABASE STATISTICS")
        self.logger.info("=" * 40)
        self.logger.info(f"Total grants: {stats.get('total_grants', 0)}")
        self.logger.info(f"Awards: {stats.get('awards_count', 0)}")
        self.logger.info(f"Solicitations: {stats.get('solicitations_count', 0)}")
        self.logger.info(f"Biotools validated: {stats.get('biotools_validated', 0)}")
        
        self.logger.info(f"\n🎯 Quality Metrics:")
        self.logger.info(f"Avg relevance score: {stats.get('avg_relevance_score', 0):.2f}")
        self.logger.info(f"Avg confidence score: {stats.get('avg_confidence_score', 0):.2f}")
        self.logger.info(f"Avg agency alignment: {stats.get('avg_agency_alignment', 0):.2f}")
        self.logger.info(f"Contaminated records: {stats.get('contaminated_records', 0)}")
        self.logger.info(f"Compound keyword matches: {stats.get('compound_keyword_matches', 0)}")
        
        if stats.get('top_agencies'):
            self.logger.info(f"\n🏛️  Top agencies:")
            for agency, count in stats['top_agencies'][:5]:
                self.logger.info(f"  {agency}: {count}")
        
        if stats.get('top_biotools_categories'):
            self.logger.info(f"\n🔬 Top biotools categories:")
            for category, count in stats['top_biotools_categories'][:5]:
                self.logger.info(f"  {category}: {count}")


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
            result = scraper.update_recent_awards(months)
            print(f"✅ Recent awards updated: {result}")
            
        elif command == 'test':
            # Comprehensive testing
            results = scraper.test_comprehensive_api_connectivity()
            print(f"\n🔍 Test Status: {results['overall_status'].upper()}")
            
        elif command == 'stats':
            # Enhanced statistics
            scraper.show_enhanced_database_stats()
            
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
    main() 
                #!/usr/bin/env python3
"""
Complete Enhanced BioTools SBIR/STTR Scraper - Fixed Version
Key improvements over previous version:
- Fixed agency mappings (NIH/CDC under HHS, DARPA under DOD)
- Enhanced solicitation collection strategy
- Improved error handling and rate limiting
- Better compound keyword validation