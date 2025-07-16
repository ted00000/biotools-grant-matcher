#!/usr/bin/env python3
"""
Enhanced BioTools Grant Matcher Backend with Comprehensive TABA Tracking and Business Development Exports
Handles company details, contact information, and enhanced TABA funding detection
"""

from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sqlite3
import json
import re
from datetime import datetime, timedelta
import requests
import os
from typing import List, Dict, Any, Tuple, Optional, Set
from collections import Counter, defaultdict
import math
import hashlib
import secrets
import logging
import time
import csv
import io
from functools import wraps

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
DATABASE_PATH = "data/grants.db"
DIGITALOCEAN_AGENT_API_KEY = os.getenv('DO_AGENT_API_KEY', '')
DIGITALOCEAN_AGENT_URL = os.getenv('DO_AGENT_URL', '')

# Security configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(16))
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1MB max request size

# Initialize limiter
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    storage_uri="memory://",
    default_limits=["200 per hour", "20 per minute"]
)

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create logs directory
os.makedirs('logs', exist_ok=True)

# Cache management
class SimpleCache:
    """Simple in-memory cache for frequently accessed data"""
    
    def __init__(self, max_size=1000, ttl=3600):
        self.cache = {}
        self.timestamps = {}
        self.max_size = max_size
        self.ttl = ttl
    
    def get(self, key):
        if key in self.cache:
            if time.time() - self.timestamps[key] < self.ttl:
                return self.cache[key]
            else:
                del self.cache[key]
                del self.timestamps[key]
        return None
    
    def set(self, key, value):
        if len(self.cache) >= self.max_size:
            # Simple LRU eviction
            oldest_key = min(self.timestamps.keys(), key=lambda k: self.timestamps[k])
            del self.cache[oldest_key]
            del self.timestamps[oldest_key]
        
        self.cache[key] = value
        self.timestamps[key] = time.time()
    
    def clear(self):
        self.cache.clear()
        self.timestamps.clear()

# Initialize cache
search_cache = SimpleCache(max_size=500, ttl=1800)  # 30 minutes TTL

class EnhancedBiotoolsMatcherWithTABA:
    """Enhanced grant matcher with comprehensive TABA tracking and contact information"""
    
    def __init__(self, db_path=DATABASE_PATH):
        self.db_path = db_path
        self.idf_cache = {}
        
        # Biotools taxonomy (same as before)
        self.tool_types = {
            'instrument': {
                'keywords': ['microscope', 'sequencer', 'cytometer', 'spectrometer', 'analyzer', 
                           'scanner', 'reader', 'detector', 'sensor', 'device', 'equipment', 
                           'platform', 'system', 'apparatus', 'machine'],
                'compound_terms': ['flow cytometer', 'mass spectrometer', 'DNA sequencer', 
                                 'confocal microscope', 'plate reader', 'PCR machine']
            },
            'assay': {
                'keywords': ['assay', 'test', 'kit', 'protocol', 'method', 'procedure', 
                           'technique', 'reagent', 'probe', 'antibody', 'primer'],
                'compound_terms': ['ELISA assay', 'PCR assay', 'immunoassay', 'fluorescence assay',
                                 'biochemical assay', 'cell viability assay']
            },
            'software': {
                'keywords': ['software', 'algorithm', 'program', 'tool', 'pipeline', 'workflow',
                           'application', 'package', 'library', 'script', 'code'],
                'compound_terms': ['analysis software', 'bioinformatics tool', 'visualization software',
                                 'data analysis pipeline', 'sequence analysis tool']
            },
            'database_platform': {
                'keywords': ['database', 'repository', 'platform', 'resource', 'portal', 
                           'collection', 'archive', 'registry', 'catalog'],
                'compound_terms': ['sequence database', 'protein database', 'genomic database',
                                 'research platform', 'data repository']
            },
            'integrated_system': {
                'keywords': ['system', 'platform', 'workstation', 'station', 'setup', 
                           'configuration', 'integration', 'automation'],
                'compound_terms': ['laboratory automation system', 'integrated platform',
                                 'robotic system', 'automated workstation']
            },
            'service': {
                'keywords': ['service', 'facility', 'core', 'center', 'laboratory', 'lab'],
                'compound_terms': ['sequencing service', 'core facility', 'analytical service',
                                 'research service', 'laboratory service']
            },
            'consumable': {
                'keywords': ['reagent', 'kit', 'consumable', 'supplies', 'materials', 
                           'chemicals', 'media', 'buffer'],
                'compound_terms': ['research reagent', 'laboratory supplies', 'cell culture media',
                                 'molecular biology kit']
            }
        }
        
        self.focus_areas = {
            'genomics': {
                'keywords': ['genome', 'genomic', 'DNA', 'gene', 'genetic', 'sequencing',
                           'mutation', 'variant', 'SNP', 'GWAS', 'chromosome'],
                'compound_terms': ['whole genome sequencing', 'genomic analysis', 'DNA sequencing',
                                 'genetic variation', 'genome editing', 'CRISPR genomics']
            },
            'cell_biology': {
                'keywords': ['cell', 'cellular', 'cytology', 'organelle', 'nucleus', 'membrane',
                           'mitochondria', 'cytoplasm', 'cell cycle', 'apoptosis'],
                'compound_terms': ['cell culture', 'cell analysis', 'cellular imaging', 
                                 'cell sorting', 'cell viability', 'live cell imaging']
            },
            'proteomics': {
                'keywords': ['protein', 'proteome', 'peptide', 'amino acid', 'enzyme', 
                           'antibody', 'immunoglobulin', 'protease'],
                'compound_terms': ['protein analysis', 'mass spectrometry proteomics', 
                                 'protein identification', 'peptide sequencing']
            },
            'metabolomics': {
                'keywords': ['metabolome', 'metabolite', 'metabolism', 'biochemical', 
                           'small molecule', 'biomarker'],
                'compound_terms': ['metabolic profiling', 'metabolomics analysis', 
                                 'small molecule analysis', 'biochemical pathway']
            },
            'bioinformatics': {
                'keywords': ['bioinformatics', 'computational biology', 'algorithm', 'pipeline',
                           'analysis', 'modeling', 'simulation', 'data mining'],
                'compound_terms': ['sequence analysis', 'phylogenetic analysis', 'pathway analysis',
                                 'computational modeling', 'data visualization']
            },
            'single_cell': {
                'keywords': ['single cell', 'single-cell', 'sc-seq', 'droplet', 'microwell'],
                'compound_terms': ['single cell RNA sequencing', 'single cell analysis',
                                 'single cell proteomics', 'droplet microfluidics']
            },
            'spatial_biology': {
                'keywords': ['spatial', 'location', 'position', 'tissue', 'in situ', 'mapping'],
                'compound_terms': ['spatial transcriptomics', 'spatial proteomics', 'tissue imaging',
                                 'spatial analysis', 'cellular mapping']
            },
            'immunology': {
                'keywords': ['immune', 'immunology', 'antibody', 'T cell', 'B cell', 'cytokine',
                           'immunoassay', 'vaccination', 'antigen'],
                'compound_terms': ['immune profiling', 'immunological analysis', 'T cell analysis',
                                 'cytokine analysis', 'immune monitoring']
            },
            'synthetic_biology': {
                'keywords': ['synthetic biology', 'bioengineering', 'engineered', 'synthetic',
                           'biosynthesis', 'circuit'],
                'compound_terms': ['synthetic biology tools', 'genetic engineering', 
                                 'biosynthetic pathway', 'engineered organism']
            },
            'multi_omics': {
                'keywords': ['multi-omics', 'multiomics', 'integrative', 'systems biology',
                           'holistic', 'comprehensive'],
                'compound_terms': ['multi-omics analysis', 'integrative omics', 'systems biology',
                                 'omics integration']
            },
            'microbiome': {
                'keywords': ['microbiome', 'microbiota', 'microbial', 'bacteria', 'microorganism',
                           '16S', 'metagenome'],
                'compound_terms': ['microbiome analysis', 'microbial community', '16S sequencing',
                                 'metagenomic analysis']
            },
            'high_throughput_screening': {
                'keywords': ['high throughput', 'high-throughput', 'HTS', 'screening', 'robotics',
                           'automation', 'library'],
                'compound_terms': ['high throughput screening', 'automated screening', 
                                 'compound library screening', 'robotic screening']
            },
            'diagnostics': {
                'keywords': ['diagnostic', 'detection', 'biomarker', 'clinical', 'medical',
                           'point-of-care', 'rapid test'],
                'compound_terms': ['diagnostic assay', 'biomarker detection', 'clinical diagnostics',
                                 'point-of-care testing', 'rapid diagnostics']
            }
        }
        
        self.biotools_agencies = {
            'NIH': ['biological', 'biomedical', 'health', 'disease', 'therapeutic'],
            'NSF': ['biological sciences', 'molecular', 'cellular', 'biological research'],
            'HHS': ['SBIR', 'biomedical', 'health technology', 'medical device'],
            'DOE': ['biological systems', 'bioenergy', 'environmental biology'],
            'CDC': ['health surveillance', 'epidemiology', 'public health tools']
        }
        
        self._build_idf_cache()
    
    def get_grant_by_id(self, grant_id: int) -> Optional[Dict[str, Any]]:
        """Get specific grant by ID with enhanced TABA information"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM grants WHERE id = ?", (grant_id,))
            result = cursor.fetchone()
            
            if result:
                grant = dict(result)
                
                # Enhanced data processing for grant details
                grant['inferred_type'] = self._determine_data_type(grant)
                
                # Format monetary amounts
                if grant.get('amount'):
                    try:
                        grant['formatted_amount'] = f"${grant['amount']:,}"
                    except (TypeError, ValueError):
                        grant['formatted_amount'] = str(grant.get('amount', 'N/A'))
                else:
                    grant['formatted_amount'] = 'N/A'
                
                # NEW: Format TABA amount
                if grant.get('taba_amount') and grant['taba_amount'] > 0:
                    grant['formatted_taba_amount'] = f"${grant['taba_amount']:,}"
                else:
                    grant['formatted_taba_amount'] = 'N/A'
                
                # Format dates
                for date_field in ['award_date', 'end_date', 'close_date', 'updated_at']:
                    if grant.get(date_field):
                        try:
                            date_obj = datetime.fromisoformat(str(grant[date_field]).replace('Z', '+00:00'))
                            grant[f'formatted_{date_field}'] = date_obj.strftime('%B %d, %Y')
                        except (ValueError, TypeError):
                            grant[f'formatted_{date_field}'] = str(grant[date_field])
                    else:
                        grant[f'formatted_{date_field}'] = 'N/A'
                
                # Calculate biotools relevance score
                combined_text = f"{grant.get('title', '')} {grant.get('description', '')} {grant.get('keywords', '')}"
                grant['biotools_relevance'] = self._calculate_biotools_relevance(combined_text)
                
                # Process biotools categories
                if grant.get('biotools_category'):
                    grant['biotools_categories_list'] = [cat.strip() for cat in grant['biotools_category'].split(',') if cat.strip()]
                else:
                    grant['biotools_categories_list'] = []
                
                # Process compound keywords
                if grant.get('compound_keyword_matches'):
                    grant['compound_keywords_list'] = [kw.strip() for kw in grant['compound_keyword_matches'].split(',') if kw.strip()]
                else:
                    grant['compound_keywords_list'] = []
                
                # NEW: Process TABA information
                grant['has_taba_funding'] = bool(grant.get('has_taba_funding'))
                grant['taba_amount'] = grant.get('taba_amount') or 0
                grant['taba_type'] = grant.get('taba_type') or 'none'
                grant['taba_confidence_score'] = grant.get('taba_confidence_score') or 0.0
                grant['taba_eligible'] = bool(grant.get('taba_eligible'))
                
                # Parse TABA keywords
                if grant.get('taba_keywords_matched'):
                    grant['taba_keywords_list'] = [kw.strip() for kw in grant['taba_keywords_matched'].split(',') if kw.strip()]
                else:
                    grant['taba_keywords_list'] = []
                
                # Add TABA status information
                taba_type = grant.get('taba_type', 'none')
                if grant['has_taba_funding']:
                    if taba_type == 'explicit':
                        grant['taba_status_text'] = 'Explicitly mentions TABA funding'
                        grant['taba_status_icon'] = '🎯'
                        grant['taba_status_class'] = 'explicit'
                    elif taba_type == 'likely':
                        grant['taba_status_text'] = 'Likely has TABA funding'
                        grant['taba_status_icon'] = '🔍'
                        grant['taba_status_class'] = 'likely'
                    elif taba_type == 'commercialization':
                        grant['taba_status_text'] = 'Commercialization focus'
                        grant['taba_status_icon'] = '📈'
                        grant['taba_status_class'] = 'commercialization'
                    else:
                        grant['taba_status_text'] = 'TABA funding detected'
                        grant['taba_status_icon'] = '💰'
                        grant['taba_status_class'] = 'unknown'
                elif grant['taba_eligible']:
                    grant['taba_status_text'] = 'Eligible for TABA funding'
                    grant['taba_status_icon'] = '✅'
                    grant['taba_status_class'] = 'eligible'
                else:
                    grant['taba_status_text'] = 'No TABA funding'
                    grant['taba_status_icon'] = '❌'
                    grant['taba_status_class'] = 'not-eligible'
                
                # Enhanced company information processing
                grant['display_company'] = grant.get('company_name') or grant.get('firm') or 'Unknown Company'
                
                # Format full address
                address_parts = []
                if grant.get('address1'):
                    address_parts.append(grant['address1'])
                if grant.get('address2'):
                    address_parts.append(grant['address2'])
                
                city_state_zip = []
                if grant.get('city'):
                    city_state_zip.append(grant['city'])
                if grant.get('state'):
                    city_state_zip.append(grant['state'])
                if grant.get('zip_code'):
                    city_state_zip.append(grant['zip_code'])
                
                if city_state_zip:
                    address_parts.append(', '.join(city_state_zip))
                
                grant['formatted_address'] = '\n'.join(address_parts) if address_parts else 'N/A'
                grant['has_address'] = len(address_parts) > 0
                
                # Contact information availability flags
                grant['has_poc_contact'] = bool(grant.get('poc_name') or grant.get('poc_email') or grant.get('poc_phone'))
                grant['has_pi_contact'] = bool(grant.get('pi_email') or grant.get('pi_phone'))
                grant['has_company_website'] = bool(grant.get('company_url'))
                grant['has_any_contact'] = grant['has_poc_contact'] or grant['has_pi_contact'] or grant['has_company_website']
                
                # Format contact information for display
                contact_info = []
                if grant.get('poc_name'):
                    poc_details = [grant['poc_name']]
                    if grant.get('poc_title'):
                        poc_details.append(f"({grant['poc_title']})")
                    contact_info.append(' '.join(poc_details))
                
                grant['formatted_poc'] = ', '.join(contact_info) if contact_info else None
                
                # Company classification information
                classifications = []
                if grant.get('woman_owned') == 'Y':
                    classifications.append('Woman-Owned')
                if grant.get('socially_economically_disadvantaged') == 'Y':
                    classifications.append('Socially & Economically Disadvantaged')
                if grant.get('hubzone_owned') == 'Y':
                    classifications.append('HUBZone')
                
                grant['company_classifications'] = classifications
                grant['has_classifications'] = len(classifications) > 0
                
                # Award history information
                if grant.get('number_awards'):
                    try:
                        num_awards = int(grant['number_awards'])
                        if num_awards > 1:
                            grant['award_history_text'] = f"This company has won {num_awards} SBIR/STTR awards"
                        elif num_awards == 1:
                            grant['award_history_text'] = "This is the company's first SBIR/STTR award"
                        else:
                            grant['award_history_text'] = None
                    except (ValueError, TypeError):
                        grant['award_history_text'] = None
                else:
                    grant['award_history_text'] = None
                
                # Enhanced company name handling for different data types
                if grant['inferred_type'] == 'solicitation':
                    grant['display_title'] = grant.get('title', 'Untitled')
                    grant['display_subtitle'] = None
                else:
                    # For awards, show company name prominently if requested
                    grant['display_title'] = grant.get('title', 'Untitled')
                    grant['display_subtitle'] = None
                
                grant['company_name_display'] = grant.get('company_name') or grant.get('firm')
                
                # Add status information
                if grant['inferred_type'] == 'solicitation':
                    # Check if solicitation is still open
                    if grant.get('close_date') or grant.get('end_date'):
                        try:
                            close_date_str = grant.get('close_date') or grant.get('end_date')
                            close_date = datetime.fromisoformat(str(close_date_str).replace('Z', '+00:00'))
                            if close_date > datetime.now():
                                grant['status'] = 'Open'
                                grant['status_class'] = 'open'
                                days_remaining = (close_date - datetime.now()).days
                                grant['days_remaining'] = days_remaining
                            else:
                                grant['status'] = 'Closed'
                                grant['status_class'] = 'closed'
                        except (ValueError, TypeError):
                            grant['status'] = 'Unknown'
                            grant['status_class'] = 'unknown'
                    else:
                        grant['status'] = 'Unknown'
                        grant['status_class'] = 'unknown'
                else:
                    grant['status'] = 'Awarded'
                    grant['status_class'] = 'awarded'
                
                # Add contact quality score
                contact_score = 0
                if grant.get('poc_email'):
                    contact_score += 3
                if grant.get('pi_email'):
                    contact_score += 3
                if grant.get('poc_phone'):
                    contact_score += 2
                if grant.get('pi_phone'):
                    contact_score += 2
                if grant.get('company_url'):
                    contact_score += 2
                if grant.get('address1'):
                    contact_score += 1
                
                grant['contact_quality_score'] = contact_score
                grant['contact_quality_level'] = (
                    'excellent' if contact_score >= 8 else
                    'good' if contact_score >= 5 else
                    'basic' if contact_score >= 2 else
                    'minimal'
                )
                
                logger.info(f"Retrieved grant details: id={grant_id}, type={grant['inferred_type']}, "
                          f"relevance={grant['biotools_relevance']:.2f}, taba_type={grant['taba_type']}, "
                          f"contact_quality={grant['contact_quality_level']}")
                return grant
            else:
                logger.warning(f"Grant not found: id={grant_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting grant {grant_id}: {e}")
            return None
        finally:
            conn.close()
    
    def _determine_data_type(self, record: Dict[str, Any]) -> str:
        """Determine the data type of a record"""
        if record.get('grant_type'):
            return record['grant_type']
        
        if (record.get('solicitation_number') or 
            record.get('current_status') in ['open', 'active'] or
            record.get('close_date')):
            return 'solicitation'
        
        return 'award'
    
    def _calculate_biotools_relevance(self, text: str) -> float:
        """Calculate overall biotools relevance score for a text"""
        text_lower = text.lower()
        relevance_score = 0.0
        
        # Score based on biotools keyword density
        total_terms = len(text.split())
        biotools_terms = 0
        
        for tool_type_data in self.tool_types.values():
            for keyword in tool_type_data['keywords']:
                if keyword in text_lower:
                    biotools_terms += text_lower.count(keyword)
                    relevance_score += 1.0
        
        for focus_area_data in self.focus_areas.values():
            for keyword in focus_area_data['keywords']:
                if keyword in text_lower:
                    biotools_terms += text_lower.count(keyword)
                    relevance_score += 1.0
        
        # Calculate density score
        if total_terms > 0:
            density_score = (biotools_terms / total_terms) * 10.0
            relevance_score += density_score
        
        return min(relevance_score, 10.0)
    
    def _build_idf_cache(self):
        """Build IDF cache for TF-IDF scoring with biotools focus"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM grants")
            total_docs = cursor.fetchone()[0]
            
            if total_docs == 0:
                conn.close()
                return
            
            logger.info(f"Building biotools-focused IDF cache for {total_docs} documents...")
            
            cursor.execute("SELECT title, description, keywords FROM grants")
            documents = cursor.fetchall()
            
            term_doc_freq = Counter()
            
            for title, desc, keywords in documents:
                text = f"{title or ''} {desc or ''} {keywords or ''}"
                terms = set(self._extract_biotools_terms(text.lower()))
                
                for term in terms:
                    term_doc_freq[term] += 1
            
            # Only cache terms that appear in biotools context
            for term, doc_freq in term_doc_freq.items():
                if doc_freq > 0 and self._is_biotools_term(term):
                    self.idf_cache[term] = math.log(total_docs / doc_freq)
                    
            logger.info(f"Biotools IDF cache built with {len(self.idf_cache)} relevant terms")
            
        except Exception as e:
            logger.error(f"Error building IDF cache: {e}")
        finally:
            conn.close()
    
    def _extract_biotools_terms(self, text: str) -> List[str]:
        """Extract biotools-relevant terms only"""
        if not text:
            return []
            
        text = re.sub(r'[^\w\s]', ' ', text)
        terms = text.split()
        
        # Biotools stop words (domain-specific)
        biotools_stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 
            'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 
            'do', 'does', 'did', 'will', 'would', 'could', 'should', 'this', 'that', 
            'these', 'those', 'can', 'may', 'might', 'must', 'shall', 'from', 'up', 
            'out', 'down', 'off', 'over', 'under', 'again', 'further', 'then', 'once',
            'research', 'study', 'development', 'project', 'system', 'method', 'approach'
        }
        
        # Filter and return only biotools-relevant terms
        filtered_terms = []
        for term in terms:
            if (len(term) > 2 and 
                term.lower() not in biotools_stop_words and 
                self._is_biotools_term(term)):
                filtered_terms.append(term)
        
        return filtered_terms
    
    def _is_biotools_term(self, term: str) -> bool:
        """Check if a term is biotools-relevant"""
        term_lower = term.lower()
        
        # Check against all biotools keywords
        for tool_type_data in self.tool_types.values():
            if term_lower in [kw.lower() for kw in tool_type_data['keywords']]:
                return True
        
        for focus_area_data in self.focus_areas.values():
            if term_lower in [kw.lower() for kw in focus_area_data['keywords']]:
                return True
        
        # Check compound terms
        for tool_type_data in self.tool_types.values():
            for compound in tool_type_data['compound_terms']:
                if term_lower in compound.lower():
                    return True
        
        for focus_area_data in self.focus_areas.values():
            for compound in focus_area_data['compound_terms']:
                if term_lower in compound.lower():
                    return True
        
        return False

    def get_database_stats(self) -> Dict[str, Any]:
        """Get enhanced database statistics including TABA information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            stats = {}
            
            # Basic counts
            cursor.execute("SELECT COUNT(*) FROM grants")
            total_grants = cursor.fetchone()[0]
            stats['total_grants'] = total_grants
            
            cursor.execute("SELECT COUNT(*) FROM grants WHERE grant_type = 'award'")
            stats['awards_count'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM grants WHERE grant_type = 'solicitation'")
            stats['solicitations_count'] = cursor.fetchone()[0]
            
            # TABA statistics
            cursor.execute("SELECT COUNT(*) FROM grants WHERE has_taba_funding = 1")
            stats['total_taba_grants'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM grants WHERE taba_eligible = 1")
            stats['taba_eligible_grants'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT SUM(taba_amount) FROM grants WHERE has_taba_funding = 1")
            stats['total_taba_funding'] = cursor.fetchone()[0] or 0
            
            # TABA adoption rate
            if stats['taba_eligible_grants'] > 0:
                stats['taba_adoption_rate'] = (stats['total_taba_grants'] / stats['taba_eligible_grants']) * 100
            else:
                stats['taba_adoption_rate'] = 0.0
            
            # Biotools relevance
            cursor.execute("SELECT COUNT(*) FROM grants WHERE relevance_score >= 1.5")
            biotools_relevant_count = cursor.fetchone()[0]
            stats['biotools_relevant_count'] = biotools_relevant_count
            stats['biotools_relevance_percentage'] = round((biotools_relevant_count / total_grants * 100), 1) if total_grants > 0 else 0
            
            # Company and contact stats
            cursor.execute("""
                SELECT COUNT(*) FROM grants 
                WHERE (poc_email IS NOT NULL AND poc_email != '') 
                   OR (pi_email IS NOT NULL AND pi_email != '')
                   OR (poc_phone IS NOT NULL AND poc_phone != '')
                   OR (pi_phone IS NOT NULL AND pi_phone != '')
            """)
            grants_with_contact = cursor.fetchone()[0]
            stats['grants_with_contact_info'] = grants_with_contact
            
            cursor.execute("""
                SELECT COUNT(*) FROM grants 
                WHERE (company_url IS NOT NULL AND company_url != '') 
                   OR (address1 IS NOT NULL AND address1 != '')
            """)
            grants_with_company_info = cursor.fetchone()[0]
            stats['grants_with_company_info'] = grants_with_company_info
            
            # Contact coverage percentages
            stats['contact_coverage_percentage'] = round((grants_with_contact / total_grants * 100), 1) if total_grants > 0 else 0
            stats['company_info_coverage_percentage'] = round((grants_with_company_info / total_grants * 100), 1) if total_grants > 0 else 0
            
            # Companies count
            cursor.execute("""
                SELECT COUNT(*) FROM grants 
                WHERE (company_name IS NOT NULL AND company_name != '') 
                   OR (firm IS NOT NULL AND firm != '')
            """)
            companies_count = cursor.fetchone()[0]
            stats['companies_count'] = companies_count
            
            # Agency breakdown
            cursor.execute("SELECT agency, COUNT(*) FROM grants GROUP BY agency ORDER BY COUNT(*) DESC LIMIT 10")
            agencies = cursor.fetchall()
            stats['agencies'] = [{'name': agency[0] or 'Unknown', 'count': agency[1]} for agency in agencies]
            
            # Recent updates
            try:
                cursor.execute("SELECT COUNT(*) FROM grants WHERE updated_at > date('now', '-30 days')")
                stats['recent_grants'] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                stats['recent_grants'] = 0
            
            # Open solicitations
            try:
                cursor.execute("""
                    SELECT COUNT(*) FROM grants 
                    WHERE grant_type = 'solicitation'
                    AND (end_date IS NULL OR end_date > date('now'))
                """)
                stats['open_solicitations'] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                stats['open_solicitations'] = 0
            
            stats['last_updated'] = datetime.now().isoformat()
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {
                'total_grants': 0,
                'awards_count': 0,
                'solicitations_count': 0,
                'companies_count': 0,
                'biotools_relevant_count': 0,
                'biotools_relevance_percentage': 0,
                'total_taba_grants': 0,
                'taba_eligible_grants': 0,
                'total_taba_funding': 0,
                'taba_adoption_rate': 0,
                'grants_with_contact_info': 0,
                'grants_with_company_info': 0,
                'contact_coverage_percentage': 0,
                'company_info_coverage_percentage': 0,
                'recent_grants': 0,
                'open_solicitations': 0,
                'agencies': [],
                'last_updated': datetime.now().isoformat()
            }
        finally:
            conn.close()


def search_grants_with_contacts_and_taba(query: str, limit: int = 20, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Enhanced search function with TABA filtering support"""
    if not filters:
        filters = {}
    
    # Extract filters
    tool_types = filters.get('tool_types', [])
    focus_areas = filters.get('focus_areas', [])
    taba_filters = filters.get('taba_filters', [])  # NEW: TABA filters
    browse_mode = filters.get('browse_mode', False) or len(query.strip()) == 0
    data_type = filters.get('data_type', 'all')
    
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Build basic query
        base_query = "SELECT * FROM grants WHERE relevance_score >= 1.5"
        params = []
        
        # Add data type filter
        if data_type != 'all':
            if data_type == 'awards':
                base_query += " AND grant_type = 'award'"
            elif data_type == 'solicitations':
                base_query += " AND grant_type = 'solicitation'"
            elif data_type == 'companies':
                base_query += " AND (company_name IS NOT NULL OR firm IS NOT NULL)"
        
        # Add text search if not in browse mode
        if not browse_mode and query:
            base_query += " AND (title LIKE ? OR description LIKE ? OR keywords LIKE ?)"
            search_pattern = f"%{query}%"
            params.extend([search_pattern, search_pattern, search_pattern])
        
        # Add biotools category filtering
        category_filters = []
        for tool_type in tool_types:
            category_filters.append(f"biotools_category LIKE '%{tool_type}%'")
        for focus_area in focus_areas:
            category_filters.append(f"biotools_category LIKE '%{focus_area}%'")
        
        if category_filters:
            base_query += f" AND ({' OR '.join(category_filters)})"
        
        # NEW: Add TABA filtering
        if taba_filters:
            taba_conditions = []
            for taba_filter in taba_filters:
                if taba_filter == 'explicit':
                    taba_conditions.append("(has_taba_funding = 1 AND taba_type = 'explicit')")
                elif taba_filter == 'likely':
                    taba_conditions.append("(has_taba_funding = 1 AND taba_type = 'likely')")
                elif taba_filter == 'commercialization':
                    taba_conditions.append("(has_taba_funding = 1 AND taba_type = 'commercialization')")
                elif taba_filter == 'eligible':
                    taba_conditions.append("taba_eligible = 1")
            
            if taba_conditions:
                base_query += f" AND ({' OR '.join(taba_conditions)})"
        
        # Order by relevance and limit
        base_query += " ORDER BY relevance_score DESC, confidence_score DESC"
        if taba_filters:
            base_query += ", has_taba_funding DESC, taba_amount DESC"  # Prioritize TABA grants
        base_query += " LIMIT ?"
        params.append(limit)
        
        cursor.execute(base_query, params)
        results = cursor.fetchall()
        
        grants = []
        for row in results:
            grant = dict(row)
            
            # Add computed fields for display
            grant['inferred_type'] = grant.get('grant_type', 'award')
            grant['display_title'] = grant.get('title', 'Untitled')
            grant['company_name_display'] = grant.get('company_name') or grant.get('firm')
            
            # Add contact availability flags
            grant['has_any_contact'] = bool(
                grant.get('poc_email') or grant.get('pi_email') or 
                grant.get('poc_phone') or grant.get('pi_phone') or 
                grant.get('company_url')
            )
            
            # Ensure TABA fields are present
            grant['has_taba_funding'] = bool(grant.get('has_taba_funding'))
            grant['taba_amount'] = grant.get('taba_amount') or 0
            grant['taba_type'] = grant.get('taba_type') or 'none'
            grant['taba_confidence_score'] = grant.get('taba_confidence_score') or 0.0
            grant['taba_eligible'] = bool(grant.get('taba_eligible'))
            
            grants.append(grant)
        
        return grants
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []
    finally:
        conn.close()


# Initialize the enhanced biotools matcher with TABA
biotools_matcher = EnhancedBiotoolsMatcherWithTABA()

# Security headers
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self' 'unsafe-inline' 'unsafe-eval'; img-src 'self' data:; connect-src 'self'"
    response.headers.pop('Server', None)
    return response

@app.route('/')
def index():
    """Serve the enhanced biotools interface"""
    return render_template('index.html')

@app.route('/grant/<int:grant_id>')
def grant_detail_page(grant_id):
    """Serve grant detail page with comprehensive contact and TABA information"""
    return render_template('grant_detail.html', grant_id=grant_id)

@app.route('/api/grant/<int:grant_id>', methods=['GET'])
@limiter.limit("100 per hour;10 per minute")
def get_grant_details(grant_id):
    """Get detailed information about a specific grant with comprehensive TABA information"""
    client_ip = get_remote_address()
    
    try:
        if grant_id <= 0:
            logger.warning(f"Invalid grant ID requested: {grant_id} from {client_ip}")
            return jsonify({'error': 'Invalid grant ID'}), 400
        
        grant = biotools_matcher.get_grant_by_id(grant_id)
        
        if not grant:
            logger.info(f"Grant not found: id={grant_id}, ip={client_ip}")
            return jsonify({'error': 'Grant not found'}), 404
        
        # Ensure TABA fields are properly formatted
        grant['has_taba_funding'] = bool(grant.get('has_taba_funding'))
        grant['taba_amount'] = grant.get('taba_amount') or 0
        grant['taba_type'] = grant.get('taba_type') or 'none'
        grant['taba_confidence_score'] = grant.get('taba_confidence_score') or 0.0
        grant['taba_eligible'] = bool(grant.get('taba_eligible'))
        
        # Format TABA amount for display
        if grant['taba_amount'] > 0:
            grant['formatted_taba_amount'] = f"${grant['taba_amount']:,}"
        else:
            grant['formatted_taba_amount'] = 'N/A'
        
        # Parse TABA keywords if present
        if grant.get('taba_keywords_matched'):
            grant['taba_keywords_list'] = [kw.strip() for kw in grant['taba_keywords_matched'].split(',') if kw.strip()]
        else:
            grant['taba_keywords_list'] = []
        
        # Add TABA status description
        taba_type = grant.get('taba_type', 'none')
        if taba_type == 'explicit':
            grant['taba_status_description'] = 'Explicitly mentions TABA funding or amounts'
        elif taba_type == 'likely':
            grant['taba_status_description'] = 'Strong indicators of TABA funding'
        elif taba_type == 'commercialization':
            grant['taba_status_description'] = 'Focus on commercialization activities'
        elif grant.get('taba_eligible'):
            grant['taba_status_description'] = 'Eligible for TABA funding from this agency'
        else:
            grant['taba_status_description'] = 'No TABA funding indicators'
        
        logger.info(f"Grant details accessed: id={grant_id}, biotools_relevance={grant.get('biotools_relevance', 0):.1f}, "
                   f"taba_status={taba_type}, contact_quality={grant.get('contact_quality_level', 'unknown')}, ip={client_ip}")
        
        return jsonify({
            'success': True,
            'grant': grant,
            'meta': {
                'retrieved_at': datetime.now().isoformat(),
                'biotools_validated': grant.get('biotools_relevance', 0) >= 1.0,
                'has_contact_info': grant.get('has_any_contact', False),
                'contact_quality': grant.get('contact_quality_level', 'minimal'),
                'has_taba_funding': grant.get('has_taba_funding', False),
                'taba_type': grant.get('taba_type', 'none'),
                'taba_eligible': grant.get('taba_eligible', False)
            }
        })
        
    except Exception as e:
        logger.error(f"Grant details error: id={grant_id}, ip={client_ip}, error={e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/stats', methods=['GET'])
@limiter.limit("60 per hour;10 per minute")
def get_stats():
    """Get enhanced database statistics with TABA information metrics"""
    try:
        stats = biotools_matcher.get_database_stats()
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'total_grants': 0,
            'awards_count': 0,
            'solicitations_count': 0,
            'companies_count': 0,
            'biotools_relevant_count': 0,
            'biotools_relevance_percentage': 0,
            'total_taba_grants': 0,
            'taba_eligible_grants': 0,
            'total_taba_funding': 0,
            'taba_adoption_rate': 0,
            'grants_with_contact_info': 0,
            'grants_with_company_info': 0,
            'contact_coverage_percentage': 0,
            'company_info_coverage_percentage': 0,
            'recent_grants': 0,
            'open_solicitations': 0,
            'agencies': [],
            'last_updated': datetime.now().isoformat()
        }), 500

@app.route('/api/search', methods=['POST'])
@limiter.limit("50 per hour;5 per minute")
def search_grants():
    """Enhanced biotools search with TABA support"""
    client_ip = get_remote_address()
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Query is now optional (can be empty for browse mode)
        query = data.get('query', '').strip()
        limit = min(data.get('limit', 20), 50)
        filters = data.get('filters', {})
        
        # Extract biotools taxonomy requirements
        tool_types = filters.get('tool_types', [])
        focus_areas = filters.get('focus_areas', [])
        taba_filters = filters.get('taba_filters', [])  # NEW: TABA filters
        browse_mode = filters.get('browse_mode', False) or len(query) == 0
        
        # Validate biotools requirements
        if not tool_types or not focus_areas:
            return jsonify({
                'error': 'Biotools taxonomy validation failed',
                'message': 'Must select at least one Tool Type and Focus Area for precision biotools search',
                'required': {
                    'tool_types': tool_types,
                    'focus_areas': focus_areas
                }
            }), 400
        
        # Validate query if provided (not in browse mode)
        if not browse_mode and len(query) < 2:
            return jsonify({'error': 'Query too short (minimum 2 characters)'}), 400
        
        # Check for suspicious patterns in query if provided
        if query:
            suspicious_patterns = ['union', 'select', 'drop', 'delete', 'insert', '--', '/*', '*/', ';']
            query_lower = query.lower()
            if any(pattern in query_lower for pattern in suspicious_patterns):
                logger.warning(f"Suspicious query detected from {client_ip}: {query}")
                return jsonify({'error': 'Invalid query format'}), 400
        
        # Perform biotools-validated search with TABA support
        grants = search_grants_with_contacts_and_taba(query, limit, filters)
        
        # Log the search with biotools context
        data_type = filters.get('data_type', 'all')
        mode = "browse" if browse_mode else "search"
        taba_info = f", taba_filters={taba_filters}" if taba_filters else ""
        logger.info(f"Biotools {mode}: query='{query}', types={tool_types}, areas={focus_areas}{taba_info}, results={len(grants)}, ip={client_ip}")
        
        # Create display query for frontend
        if browse_mode:
            display_query = f"Browsing: {', '.join(tool_types)} • {', '.join(focus_areas)}"
        else:
            display_query = query
        
        # Add TABA info to display query if filters applied
        if taba_filters:
            display_query += f" (TABA: {', '.join(taba_filters)})"
        
        return jsonify({
            'query': display_query,
            'original_query': query,
            'browse_mode': browse_mode,
            'data_type': data_type,
            'tool_types': tool_types,
            'focus_areas': focus_areas,
            'taba_filters': taba_filters,  # NEW: Return TABA filters
            'results': grants,
            'total_found': len(grants),
            'biotools_validated': True,
            'taba_enabled': True,  # NEW: Indicate TABA support
            'precision_mode': True,
            'timestamp': datetime.now().isoformat()
        })
        
    except ValueError as e:
        logger.warning(f"Validation error from {client_ip}: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Search error from {client_ip}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# NEW: Business Development Export Endpoints

@app.route('/api/export/business-development', methods=['GET'])
@limiter.limit("5 per hour;1 per minute")
def export_business_development_data():
    """Export actionable business development data as CSV"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Get all biotools-relevant grants with real contact and company data
        cursor.execute("""
            SELECT 
                title,
                agency,
                program,
                firm,
                company_name,
                principal_investigator,
                amount,
                phase,
                award_date,
                end_date,
                award_number,
                
                -- Contact Information (REAL data)
                poc_name,
                poc_title,
                poc_email,
                poc_phone,
                pi_email,
                pi_phone,
                ri_poc_name,
                ri_poc_phone,
                
                -- Company Information (REAL data)
                company_url,
                address1,
                city,
                state,
                zip_code,
                uei,
                duns,
                number_awards,
                
                -- Business Intelligence
                relevance_score,
                biotools_category,
                compound_keyword_matches,
                
                -- Company Classifications
                woman_owned,
                socially_economically_disadvantaged,
                hubzone_owned,
                
                -- Additional useful fields
                keywords,
                description,
                url
                
            FROM grants 
            WHERE relevance_score >= 1.5
            ORDER BY relevance_score DESC, amount DESC
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return jsonify({'error': 'No biotools-relevant grants found'}), 404
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write comprehensive business development headers
        headers = [
            # Grant Basics
            'Grant_Title', 'Agency', 'Program', 'Award_Amount', 'Phase', 'Award_Date', 'End_Date', 'Award_Number',
            
            # Company Information (Key for BD)
            'Company_Name', 'Company_URL', 'Address', 'City', 'State', 'ZIP', 'UEI', 'DUNS', 'Previous_Awards',
            
            # Primary Contacts (Most Important for BD)
            'Principal_Investigator', 'PI_Email', 'PI_Phone',
            'POC_Name', 'POC_Title', 'POC_Email', 'POC_Phone',
            'RI_Contact_Name', 'RI_Contact_Phone',
            
            # Business Intelligence
            'Biotools_Relevance_Score', 'Biotools_Categories', 'Key_Technology_Terms',
            
            # Company Classifications (Good for targeting)
            'Woman_Owned', 'Socially_Disadvantaged', 'HUBZone',
            
            # Additional Context
            'Keywords', 'Description_Preview', 'Source_URL'
        ]
        writer.writerow(headers)
        
        # Write data rows
        for row in results:
            # Clean and format the data for business use
            title = (row[0] or '')[:100]  # Truncate long titles
            agency = row[1] or ''
            program = row[2] or ''
            company_display = row[4] or row[3] or ''  # company_name or firm
            pi = row[5] or ''
            
            # Format amount nicely
            amount = ''
            if row[6]:
                try:
                    amount = f"${int(row[6]):,}"
                except (ValueError, TypeError):
                    amount = str(row[6])
            
            phase = row[7] or ''
            award_date = row[8] or ''
            end_date = row[9] or ''
            award_number = row[10] or ''
            
            # Contact information
            poc_name = row[11] or ''
            poc_title = row[12] or ''
            poc_email = row[13] or ''
            poc_phone = row[14] or ''
            pi_email = row[15] or ''
            pi_phone = row[16] or ''
            ri_poc_name = row[17] or ''
            ri_poc_phone = row[18] or ''
            
            # Company details
            company_url = row[19] or ''
            address1 = row[20] or ''
            city = row[21] or ''
            state = row[22] or ''
            zip_code = row[23] or ''
            uei = row[24] or ''
            duns = row[25] or ''
            number_awards = row[26] or ''
            
            # Business intelligence
            relevance_score = f"{row[27]:.1f}" if row[27] else ''
            biotools_category = row[28] or ''
            compound_matches = row[29] or ''
            
            # Company classifications
            woman_owned = 'Yes' if row[30] == 'Y' else 'No' if row[30] else ''
            socially_disadvantaged = 'Yes' if row[31] == 'Y' else 'No' if row[31] else ''
            hubzone = 'Yes' if row[32] == 'Y' else 'No' if row[32] else ''
            
            # Additional fields
            keywords = (row[33] or '')[:200]  # Truncate long keywords
            description_preview = (row[34] or '')[:300] + '...' if row[34] and len(row[34]) > 300 else (row[34] or '')
            source_url = row[35] or ''
            
            writer.writerow([
                title, agency, program, amount, phase, award_date, end_date, award_number,
                company_display, company_url, address1, city, state, zip_code, uei, duns, number_awards,
                pi, pi_email, pi_phone,
                poc_name, poc_title, poc_email, poc_phone,
                ri_poc_name, ri_poc_phone,
                relevance_score, biotools_category, compound_matches,
                woman_owned, socially_disadvantaged, hubzone,
                keywords, description_preview, source_url
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        # Return CSV as download
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=biotools_business_development_{datetime.now().strftime("%Y%m%d")}.csv'
            }
        )
        
    except Exception as e:
        logger.error(f"Business development export error: {e}")
        return jsonify({'error': 'Export failed'}), 500


@app.route('/api/export/contact-focused', methods=['GET'])
@limiter.limit("5 per hour;1 per minute") 
def export_contact_focused_data():
    """Export grants with emphasis on contact information quality"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Focus on grants with good contact information
        cursor.execute("""
            SELECT 
                title,
                agency,
                firm,
                company_name,
                principal_investigator,
                amount,
                phase,
                award_date,
                
                -- Contact scoring and info
                poc_name,
                poc_title, 
                poc_email,
                poc_phone,
                pi_email,
                pi_phone,
                company_url,
                
                -- Address for direct contact
                address1,
                city,
                state,
                
                relevance_score,
                biotools_category,
                number_awards,
                award_number
                
            FROM grants 
            WHERE relevance_score >= 1.5
            AND (
                (poc_email IS NOT NULL AND poc_email != '') OR
                (pi_email IS NOT NULL AND pi_email != '') OR  
                (poc_phone IS NOT NULL AND poc_phone != '') OR
                (pi_phone IS NOT NULL AND pi_phone != '') OR
                (company_url IS NOT NULL AND company_url != '')
            )
            ORDER BY 
                CASE 
                    WHEN poc_email IS NOT NULL AND poc_email != '' THEN 4
                    WHEN pi_email IS NOT NULL AND pi_email != '' THEN 3  
                    WHEN poc_phone IS NOT NULL AND poc_phone != '' THEN 2
                    WHEN company_url IS NOT NULL AND company_url != '' THEN 1
                    ELSE 0
                END DESC,
                relevance_score DESC
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return jsonify({'error': 'No grants with contact information found'}), 404
        
        # Create CSV for contact-focused outreach
        output = io.StringIO()
        writer = csv.writer(output)
        
        headers = [
            'Company_Name', 'Grant_Title', 'Award_Amount', 'Phase', 'Agency',
            'Principal_Investigator', 'PI_Email', 'PI_Phone',
            'POC_Name', 'POC_Title', 'POC_Email', 'POC_Phone', 
            'Company_Website', 'Address', 'City', 'State',
            'Biotools_Score', 'Technology_Categories', 'Previous_Awards', 'Award_Number'
        ]
        writer.writerow(headers)
        
        for row in results:
            company_name = row[3] or row[2] or ''
            title = (row[0] or '')[:80]
            
            amount = ''
            if row[5]:
                try:
                    amount = f"${int(row[5]):,}"
                except:
                    amount = str(row[5])
            
            writer.writerow([
                company_name, title, amount, row[6] or '', row[1] or '',
                row[4] or '', row[13] or '', row[14] or '',
                row[9] or '', row[10] or '', row[11] or '', row[12] or '',
                row[15] or '', row[16] or '', row[17] or '', row[18] or '',
                f"{row[19]:.1f}" if row[19] else '', row[20] or '', row[21] or '', row[22] or ''
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=biotools_contacts_{datetime.now().strftime("%Y%m%d")}.csv'
            }
        )
        
    except Exception as e:
        logger.error(f"Contact export error: {e}")
        return jsonify({'error': 'Export failed'}), 500

@app.route('/api/taba-stats', methods=['GET'])
@limiter.limit("60 per hour;10 per minute")
def get_taba_stats():
    """Get detailed TABA statistics"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        stats = {}
        
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
            stats['taba_adoption_rate'] = round((stats['total_taba_grants'] / stats['taba_eligible_grants']) * 100, 1)
        else:
            stats['taba_adoption_rate'] = 0.0
        
        # TABA by type
        cursor.execute("SELECT taba_type, COUNT(*) FROM grants WHERE has_taba_funding = 1 GROUP BY taba_type")
        taba_by_type = cursor.fetchall()
        stats['taba_by_type'] = {ttype: count for ttype, count in taba_by_type}
        
        # TABA by agency
        cursor.execute("SELECT agency, COUNT(*) FROM grants WHERE has_taba_funding = 1 GROUP BY agency ORDER BY COUNT(*) DESC")
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
        stats['avg_taba_confidence'] = round(avg_confidence, 2)
        
        # TABA by biotools relevance
        cursor.execute("SELECT COUNT(*) FROM grants WHERE has_taba_funding = 1 AND relevance_score >= 1.5")
        stats['biotools_relevant_with_taba'] = cursor.fetchone()[0]
        
        # Phase distribution for TABA
        cursor.execute("SELECT phase, COUNT(*) FROM grants WHERE has_taba_funding = 1 GROUP BY phase")
        taba_by_phase = cursor.fetchall()
        stats['taba_by_phase'] = {phase or 'Unknown': count for phase, count in taba_by_phase}
        
        # TABA trends by year (if award_date is available)
        cursor.execute("""
            SELECT substr(award_date, 1, 4) as year, COUNT(*)
            FROM grants 
            WHERE has_taba_funding = 1 AND award_date IS NOT NULL AND award_date != ''
            GROUP BY substr(award_date, 1, 4)
            ORDER BY year DESC
            LIMIT 5
        """)
        taba_by_year = cursor.fetchall()
        stats['taba_by_year'] = {year: count for year, count in taba_by_year if year}
        
        conn.close()
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"TABA stats error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'total_taba_grants': 0,
            'taba_eligible_grants': 0,
            'total_grants': 0,
            'taba_adoption_rate': 0.0,
            'taba_by_type': {},
            'taba_by_agency': {},
            'taba_amounts_distribution': {},
            'total_taba_funding': 0,
            'avg_taba_confidence': 0.0,
            'biotools_relevant_with_taba': 0,
            'taba_by_phase': {},
            'taba_by_year': {}
        }), 500

@app.route('/api/export/taba', methods=['GET'])
@limiter.limit("10 per hour;2 per minute")
def export_taba_data():
    """Export TABA grants data as CSV"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT title, agency, program, firm, principal_investigator, amount, award_date, phase,
                   has_taba_funding, taba_type, taba_amount, taba_confidence_score,
                   taba_keywords_matched, relevance_score, biotools_category
            FROM grants 
            WHERE has_taba_funding = 1
            ORDER BY taba_amount DESC, relevance_score DESC
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        if not results:
            return jsonify({'error': 'No TABA grants found'}), 404
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        headers = [
            'Title', 'Agency', 'Program', 'Company', 'Principal Investigator',
            'Award Amount', 'Award Date', 'Phase', 'TABA Type', 'TABA Amount',
            'TABA Confidence', 'TABA Keywords', 'Biotools Score', 'Biotools Categories'
        ]
        writer.writerow(headers)
        
        # Write data
        for row in results:
            writer.writerow([
                row[0] or '',  # title
                row[1] or '',  # agency
                row[2] or '',  # program
                row[3] or '',  # firm
                row[4] or '',  # principal_investigator
                row[5] or '',  # amount
                row[6] or '',  # award_date
                row[7] or '',  # phase
                row[9] or '',  # taba_type
                row[10] or '',  # taba_amount
                row[11] or '',  # taba_confidence_score
                row[12] or '',  # taba_keywords_matched
                row[13] or '',  # relevance_score
                row[14] or ''  # biotools_category
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        # Return CSV as response
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=biotools_taba_grants_{datetime.now().strftime("%Y%m%d")}.csv'
            }
        )
        
    except Exception as e:
        logger.error(f"TABA export error: {e}")
        return jsonify({'error': 'Export failed'}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM grants LIMIT 1")
        count = cursor.fetchone()[0]
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database_accessible': True,
            'total_grants': count,
            'cache_size': len(search_cache.cache)
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'timestamp': datetime.now().isoformat(),
            'error': str(e)
        }), 500

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    if request.path.startswith('/api/'):
        return jsonify({'error': 'API endpoint not found'}), 404
    return render_template('index.html'), 404

@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit errors"""
    logger.warning(f"Rate limit exceeded: {get_remote_address()}")
    return jsonify({
        'error': 'Rate limit exceeded',
        'message': 'Too many requests. Please slow down.',
        'retry_after': str(e.retry_after)
    }), 429

@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

# Performance monitoring
@app.before_request
def before_request():
    """Log request start time for performance monitoring"""
    request.start_time = time.time()

@app.after_request
def after_request(response):
    """Log request completion and performance metrics"""
    if hasattr(request, 'start_time'):
        duration = time.time() - request.start_time
        if duration > 1.0:  # Log slow requests
            logger.warning(f"Slow request: {request.method} {request.path} took {duration:.2f}s")
    
    return response

if __name__ == '__main__':
    # Validate database exists
    if not os.path.exists(DATABASE_PATH):
        logger.error(f"Database not found at {DATABASE_PATH}")
        exit(1)
    
    # Validate required directories
    os.makedirs('logs', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    # Initialize cache
    try:
        biotools_matcher._build_idf_cache()
        logger.info("BioTools Grant Matcher with TABA Support initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize biotools matcher: {e}")
        exit(1)
    
    # Run the application
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') == 'development'
    
    logger.info(f"Starting Enhanced BioTools Grant Matcher with TABA Support on port {port}")
    logger.info(f"Debug mode: {debug}")
    logger.info(f"Database: {DATABASE_PATH}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        threaded=True
    )