#!/usr/bin/env python3
"""
Complete Enhanced BioTools Grant Matcher Backend - Full Production Version
Combines original functionality with all enhancements and new features
"""

from flask import Flask, request, jsonify, render_template
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


class EnhancedBiotoolsMatcher:
    """Enhanced grant matcher with precision biotools focus"""
    
    def __init__(self, db_path=DATABASE_PATH):
        self.db_path = db_path
        self.idf_cache = {}
        
        # Official Biotools Taxonomy - Complete Implementation
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
        
        # Non-biotools domains to exclude (negative filtering)
        self.excluded_domains = {
            'astronomy': ['star', 'galaxy', 'planet', 'telescope', 'astronomical', 'cosmic', 'space'],
            'geology': ['rock', 'mineral', 'geological', 'earth science', 'sediment', 'fossil'],
            'physics': ['particle physics', 'quantum', 'theoretical physics', 'nuclear physics'],
            'chemistry_non_bio': ['inorganic chemistry', 'physical chemistry', 'materials chemistry'],
            'engineering_non_bio': ['mechanical engineering', 'electrical engineering', 'civil engineering'],
            'environmental_non_bio': ['climate change', 'weather', 'atmospheric', 'oceanography'],
            'computer_science_general': ['web development', 'mobile app', 'database management', 'networking']
        }
        
        # Biotools-specific agencies and programs
        self.biotools_agencies = {
            'NIH': ['biological', 'biomedical', 'health', 'disease', 'therapeutic'],
            'NSF': ['biological sciences', 'molecular', 'cellular', 'biological research'],
            'HHS': ['SBIR', 'biomedical', 'health technology', 'medical device'],
            'DOE': ['biological systems', 'bioenergy', 'environmental biology'],
            'CDC': ['health surveillance', 'epidemiology', 'public health tools']
        }
        
        self._build_idf_cache()
    
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
            # Domain-specific stop words
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
    
    def _has_biotools_relevance(self, text: str, tool_types: List[str], focus_areas: List[str]) -> bool:
        """Check if text has basic biotools relevance"""
        text_lower = text.lower()
        
        # Must match at least one term from selected taxonomy
        has_tool_type_match = False
        has_focus_area_match = False
        
        for tool_type in tool_types:
            if tool_type in self.tool_types:
                for keyword in self.tool_types[tool_type]['keywords']:
                    if keyword in text_lower:
                        has_tool_type_match = True
                        break
                if has_tool_type_match:
                    break
        
        for focus_area in focus_areas:
            if focus_area in self.focus_areas:
                for keyword in self.focus_areas[focus_area]['keywords']:
                    if keyword in text_lower:
                        has_focus_area_match = True
                        break
                if has_focus_area_match:
                    break
        
        # Must have relevance to both tool type and focus area
        return has_tool_type_match and has_focus_area_match
    
    def _calculate_biotools_keyword_score(self, query: str, grant: Dict[str, Any], 
                                        tool_types: List[str], focus_areas: List[str]) -> float:
        """Enhanced keyword scoring with biotools context validation"""
        if not query or not query.strip():
            return 0.0
            
        score = 0.0
        query_lower = query.lower().strip()
        query_words = [w.strip() for w in query_lower.split() if len(w.strip()) > 3]
        
        if not query_words:
            return 0.0
        
        biotools_matches_found = False
        
        # Title matching with biotools validation
        if grant.get('title'):
            title_lower = grant['title'].lower()
            
            # Exact phrase match (must be biotools-relevant)
            if query_lower in title_lower and self._is_phrase_biotools_relevant(query_lower, tool_types, focus_areas):
                score += 25.0
                biotools_matches_found = True
            
            # Individual biotools word matches
            for word in query_words:
                if self._is_biotools_term(word) and re.search(r'\b' + re.escape(word) + r'\b', title_lower):
                    score += 12.0
                    biotools_matches_found = True
        
        # Keywords matching with biotools validation
        if grant.get('keywords'):
            keywords_text = grant['keywords'].lower()
            
            # Exact phrase match in keywords
            if query_lower in keywords_text and self._is_phrase_biotools_relevant(query_lower, tool_types, focus_areas):
                score += 10.0
                biotools_matches_found = True
            
            # Individual biotools word matches
            for word in query_words:
                if self._is_biotools_term(word) and re.search(r'\b' + re.escape(word) + r'\b', keywords_text):
                    score += 6.0
                    biotools_matches_found = True
        
        # Description matching with biotools validation
        if grant.get('description'):
            desc_lower = grant['description'].lower()
            
            # Exact phrase match
            if query_lower in desc_lower and self._is_phrase_biotools_relevant(query_lower, tool_types, focus_areas):
                score += 8.0
                biotools_matches_found = True
            
            # Individual biotools word matches
            for word in query_words:
                if self._is_biotools_term(word) and re.search(r'\b' + re.escape(word) + r'\b', desc_lower):
                    score += 3.0
                    biotools_matches_found = True
        
        # Company name matching (for company searches)
        if grant.get('company_name') or grant.get('firm'):
            company_lower = (grant.get('company_name') or grant.get('firm') or '').lower()
            
            if query_lower in company_lower:
                score += 15.0
                biotools_matches_found = True
            
            for word in query_words:
                if re.search(r'\b' + re.escape(word) + r'\b', company_lower):
                    score += 8.0
                    biotools_matches_found = True
        
        # ONLY award agency bonus if biotools matches were found
        if biotools_matches_found and grant.get('agency'):
            agency_lower = grant['agency'].lower()
            for agency, programs in self.biotools_agencies.items():
                if agency.lower() in agency_lower:
                    # Check if agency focus aligns with biotools
                    if any(program in grant.get('description', '').lower() for program in programs):
                        score += 3.0
                        break
        
        return score if biotools_matches_found else 0.0
    
    def _is_phrase_biotools_relevant(self, phrase: str, tool_types: List[str], focus_areas: List[str]) -> bool:
        """Check if a phrase is biotools-relevant given the selected taxonomy"""
        phrase_lower = phrase.lower()
        
        # Check against selected tool types
        for tool_type in tool_types:
            if tool_type in self.tool_types:
                for compound in self.tool_types[tool_type]['compound_terms']:
                    if phrase_lower in compound.lower() or compound.lower() in phrase_lower:
                        return True
        
        # Check against selected focus areas
        for focus_area in focus_areas:
            if focus_area in self.focus_areas:
                for compound in self.focus_areas[focus_area]['compound_terms']:
                    if phrase_lower in compound.lower() or compound.lower() in phrase_lower:
                        return True
        
        return False
    
    def _calculate_tf_idf_score(self, query_terms: List[str], document_text: str) -> float:
        """Calculate TF-IDF score focusing on biotools terms only"""
        if not query_terms or not document_text:
            return 0.0
            
        doc_terms = self._extract_biotools_terms(document_text.lower())
        
        if not doc_terms:
            return 0.0
        
        tf_counts = Counter(doc_terms)
        max_tf = max(tf_counts.values()) if tf_counts else 1
        
        score = 0.0
        biotools_matches_found = False
        
        for query_term in query_terms:
            if query_term in tf_counts and self._is_biotools_term(query_term):
                tf = tf_counts[query_term] / max_tf
                idf = self.idf_cache.get(query_term, 0)
                score += tf * idf
                biotools_matches_found = True
        
        return score if biotools_matches_found else 0.0
    
    def _calculate_freshness_score(self, grant: Dict[str, Any]) -> float:
        """Calculate freshness score (minimal impact for biotools precision)"""
        try:
            if grant.get('close_date'):
                close_date = datetime.fromisoformat(grant['close_date'].replace('Z', '+00:00'))
                days_until_close = (close_date - datetime.now()).days
                
                if days_until_close < 0:
                    return 0.0
                elif days_until_close <= 30:
                    return 2.0
                elif days_until_close <= 90:
                    return 1.5
                else:
                    return 1.0
            
            if grant.get('updated_at'):
                updated = datetime.fromisoformat(grant['updated_at'].replace('Z', '+00:00'))
                days_old = (datetime.now() - updated).days
                
                if days_old < 30:
                    return 1.0
                elif days_old < 180:
                    return 0.5
                else:
                    return 0.2
        except Exception:
            pass
        
        return 0.2
    
    def _determine_data_type(self, record: Dict[str, Any]) -> str:
        """Determine the data type of a record"""
        if record.get('grant_type'):
            return record['grant_type']
        
        if (record.get('solicitation_number') or 
            record.get('current_status') in ['open', 'active'] or
            record.get('close_date')):
            return 'solicitation'
        
        return 'award'
    
    def _apply_filters(self, grants: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply additional filters with biotools focus"""
        if not filters:
            return grants
        
        filtered_grants = []
        
        for grant in grants:
            # Standard filters
            if filters.get('agency') and grant.get('agency'):
                if filters['agency'].lower() not in grant['agency'].lower():
                    continue
            
            if filters.get('amount_min'):
                try:
                    min_amount = float(filters['amount_min'])
                    grant_amount = grant.get('amount_max') or grant.get('award_amount') or grant.get('amount') or 0
                    if grant_amount < min_amount:
                        continue
                except (ValueError, TypeError):
                    pass
            
            if filters.get('deadline'):
                try:
                    days_filter = int(filters['deadline'])
                    deadline_field = grant.get('deadline') or grant.get('close_date')
                    if deadline_field:
                        deadline = datetime.fromisoformat(deadline_field.replace('Z', '+00:00'))
                        days_until_deadline = (deadline - datetime.now()).days
                        if days_until_deadline > days_filter:
                            continue
                except (ValueError, TypeError):
                    pass
            
            # Biotools-specific validation
            if filters.get('biotools_validated', False):
                # Ensure grant meets biotools relevance criteria
                combined_text = f"{grant.get('title', '')} {grant.get('description', '')} {grant.get('keywords', '')}"
                tool_types = filters.get('tool_types', [])
                focus_areas = filters.get('focus_areas', [])
                
                if not self._has_biotools_relevance(combined_text, tool_types, focus_areas):
                    continue
            
            filtered_grants.append(grant)
        
        return filtered_grants
    
    def search_grants(self, query: str, limit: int = 20, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Enhanced biotools-specific search with optional query text (browse mode)"""
        if not filters:
            filters = {}
        
        # Extract biotools taxonomy from filters
        tool_types = filters.get('tool_types', [])
        focus_areas = filters.get('focus_areas', [])
        browse_mode = filters.get('browse_mode', False) or len(query.strip()) == 0
        
        # Validate biotools requirements
        if not tool_types or not focus_areas:
            logger.warning(f"Biotools validation failed: missing tool_types ({len(tool_types)}) or focus_areas ({len(focus_areas)})")
            return []
        
        # For browse mode, create a taxonomy-based query
        if browse_mode:
            expanded_query = self._create_taxonomy_query(tool_types, focus_areas)
            logger.info(f"Browse mode: searching taxonomy categories {tool_types} + {focus_areas}")
        else:
            # Expand query with biotools context for text searches
            expanded_query = self._expand_biotools_query(query, tool_types, focus_areas)
            logger.info(f"Expanded biotools query: '{query}' -> '{expanded_query}'")
        
        # Get data type filter
        data_type = filters.get('data_type', 'all')
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM grants")
            all_grants = cursor.fetchall()
            
            if not all_grants:
                return []
            
            scored_grants = []
            
            for row in all_grants:
                grant = dict(row)
                
                # Apply data type filter early
                if data_type != 'all':
                    if data_type == 'awards' and self._determine_data_type(grant) != 'award':
                        continue
                    elif data_type == 'solicitations' and self._determine_data_type(grant) != 'solicitation':
                        continue
                    elif data_type == 'companies' and not (grant.get('company_name') or grant.get('firm')):
                        continue
                
                combined_text = f"{grant.get('title', '')} {grant.get('description', '')} {grant.get('keywords', '')}"
                
                # Pre-filter: Must contain biotools-relevant terms
                if not self._has_biotools_relevance(combined_text, tool_types, focus_areas):
                    continue
                
                # Calculate scores with different strategy for browse vs search mode
                if browse_mode:
                    # For browse mode, focus on taxonomy alignment
                    tf_idf_score = 0.0  # No text to score
                    semantic_score = self._calculate_taxonomy_alignment_score(grant, tool_types, focus_areas)
                    keyword_score = self._calculate_biotools_keyword_score(expanded_query, grant, tool_types, focus_areas)
                    freshness_score = self._calculate_freshness_score(grant)
                    
                    # Browse mode weighting (emphasize taxonomy alignment)
                    final_score = (
                        semantic_score * 0.60 +  # Higher weight for taxonomy alignment
                        keyword_score * 0.30 +
                        freshness_score * 0.10
                    )
                else:
                    # For text search mode, use full scoring
                    query_terms = self._extract_biotools_terms(expanded_query.lower())
                    
                    tf_idf_score = self._calculate_tf_idf_score(query_terms, combined_text)
                    semantic_score = self._calculate_biotools_semantic_score(expanded_query, grant, tool_types, focus_areas)
                    keyword_score = self._calculate_biotools_keyword_score(expanded_query, grant, tool_types, focus_areas)
                    freshness_score = self._calculate_freshness_score(grant)
                    
                    # Text search weighting
                    final_score = (
                        tf_idf_score * 0.20 +
                        semantic_score * 0.45 +
                        keyword_score * 0.30 +
                        freshness_score * 0.05
                    )
                
                # Adjust threshold for browse vs search mode
                score_threshold = 2.0 if browse_mode else 3.0
                
                if final_score > score_threshold:
                    grant['relevance_score'] = round(final_score, 2)
                    grant['inferred_type'] = self._determine_data_type(grant)
                    grant['search_mode'] = 'browse' if browse_mode else 'search'
                    scored_grants.append(grant)
            
            # Apply additional filters
            if filters:
                scored_grants = self._apply_filters(scored_grants, filters)
            
            # Sort by relevance and biotools specificity
            scored_grants.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            mode_text = "browse" if browse_mode else "search"
            logger.info(f"Biotools {mode_text} returned {len(scored_grants)} validated results")
            return scored_grants[:limit]
            
        except Exception as e:
            logger.error(f"Biotools search error for '{query}': {e}")
            return []
        finally:
            conn.close()
    
    def _create_taxonomy_query(self, tool_types: List[str], focus_areas: List[str]) -> str:
        """Create a query based on selected taxonomy for browse mode"""
        query_terms = []
        
        # Add tool type keywords
        for tool_type in tool_types:
            if tool_type in self.tool_types:
                query_terms.extend(self.tool_types[tool_type]['keywords'][:3])  # Top 3 keywords
        
        # Add focus area keywords
        for focus_area in focus_areas:
            if focus_area in self.focus_areas:
                query_terms.extend(self.focus_areas[focus_area]['keywords'][:3])  # Top 3 keywords
        
        return ' '.join(query_terms[:10])  # Limit to avoid overly long queries
    
    def _expand_biotools_query(self, query: str, tool_types: List[str], focus_areas: List[str]) -> str:
        """Expand query with biotools-specific context"""
        expanded_terms = [query]
        
        # Add relevant compound terms from selected taxonomy
        for tool_type in tool_types:
            if tool_type in self.tool_types:
                # Add most relevant compound terms
                relevant_compounds = []
                for compound in self.tool_types[tool_type]['compound_terms']:
                    if any(word in query.lower() for word in compound.split()):
                        relevant_compounds.append(compound)
                
                expanded_terms.extend(relevant_compounds[:2])  # Limit to 2 most relevant
        
        for focus_area in focus_areas:
            if focus_area in self.focus_areas:
                # Add most relevant compound terms
                relevant_compounds = []
                for compound in self.focus_areas[focus_area]['compound_terms']:
                    if any(word in query.lower() for word in compound.split()):
                        relevant_compounds.append(compound)
                
                expanded_terms.extend(relevant_compounds[:2])  # Limit to 2 most relevant
        
        return ' '.join(expanded_terms)
    
    def _calculate_taxonomy_alignment_score(self, grant: Dict[str, Any], 
                                          tool_types: List[str], focus_areas: List[str]) -> float:
        """Calculate how well a grant aligns with selected taxonomy"""
        score = 0.0
        grant_text = f"{grant.get('title', '')} {grant.get('description', '')} {grant.get('keywords', '')}".lower()
        
        # Tool type alignment
        for tool_type in tool_types:
            if tool_type in self.tool_types:
                type_data = self.tool_types[tool_type]
                
                # Count keyword matches
                for keyword in type_data['keywords']:
                    if keyword in grant_text:
                        score += 2.0
                
                # Compound term matches (higher weight)
                for compound in type_data['compound_terms']:
                    if compound.lower() in grant_text:
                        score += 4.0
        
        # Focus area alignment
        for focus_area in focus_areas:
            if focus_area in self.focus_areas:
                area_data = self.focus_areas[focus_area]
                
                # Count keyword matches
                for keyword in area_data['keywords']:
                    if keyword in grant_text:
                        score += 2.0
                
                # Compound term matches (higher weight)
                for compound in area_data['compound_terms']:
                    if compound.lower() in grant_text:
                        score += 4.0
        
        # Bonus for multiple taxonomy alignment
        if len(tool_types) > 1 and len(focus_areas) > 1:
            score += 3.0
        
        return min(score, 20.0)  # Cap the score
    
    def _calculate_biotools_semantic_score(self, query: str, grant: Dict[str, Any], 
                                         tool_types: List[str], focus_areas: List[str]) -> float:
        """Enhanced semantic scoring with biotools specificity"""
        score = 0.0
        grant_text = f"{grant.get('title', '')} {grant.get('description', '')} {grant.get('keywords', '')}".lower()
        query_lower = query.lower()
        
        # Tool type alignment scoring
        for tool_type in tool_types:
            if tool_type in self.tool_types:
                type_data = self.tool_types[tool_type]
                
                # Keyword matches
                for keyword in type_data['keywords']:
                    if keyword in grant_text:
                        score += 3.0
                
                # Compound term matches (higher weight)
                for compound in type_data['compound_terms']:
                    if compound.lower() in grant_text:
                        score += 5.0
        
        # Focus area alignment scoring
        for focus_area in focus_areas:
            if focus_area in self.focus_areas:
                area_data = self.focus_areas[focus_area]
                
                # Keyword matches
                for keyword in area_data['keywords']:
                    if keyword in grant_text:
                        score += 3.0
                
                # Compound term matches (higher weight)
                for compound in area_data['compound_terms']:
                    if compound.lower() in grant_text:
                        score += 5.0
        
        # Cross-domain relevance (tool type + focus area combinations)
        cross_domain_bonus = 0.0
        for tool_type in tool_types:
            for focus_area in focus_areas:
                if self._has_cross_domain_relevance(grant_text, tool_type, focus_area):
                    cross_domain_bonus += 2.0
        
        score += min(cross_domain_bonus, 10.0)  # Cap cross-domain bonus
        
        # Penalize non-biotools contamination
        contamination_penalty = 0.0
        for domain, terms in self.excluded_domains.items():
            for term in terms:
                if term in grant_text:
                    contamination_penalty += 5.0
        
        score = max(0.0, score - contamination_penalty)
        
        return min(score, 25.0)  # Cap total semantic score
    
    def _has_cross_domain_relevance(self, text: str, tool_type: str, focus_area: str) -> bool:
        """Check for cross-domain biotools relevance"""
        # Define high-value combinations
        high_value_combinations = {
            ('instrument', 'genomics'): ['sequencer', 'PCR', 'DNA analyzer'],
            ('instrument', 'single_cell'): ['flow cytometer', 'cell sorter', 'droplet'],
            ('software', 'bioinformatics'): ['analysis pipeline', 'algorithm', 'computational'],
            ('assay', 'proteomics'): ['mass spectrometry', 'protein assay', 'immunoassay'],
            ('instrument', 'spatial_biology'): ['imaging', 'microscopy', 'spatial analysis']
        }
        
        combination_key = (tool_type, focus_area)
        if combination_key in high_value_combinations:
            terms = high_value_combinations[combination_key]
            return any(term in text for term in terms)
        
        return False
    
    def get_grant_by_id(self, grant_id: int) -> Optional[Dict[str, Any]]:
        """Get specific grant by ID with biotools validation"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM grants WHERE id = ?", (grant_id,))
            result = cursor.fetchone()
            if result:
                grant = dict(result)
                grant['inferred_type'] = self._determine_data_type(grant)
                # Add biotools relevance score
                combined_text = f"{grant.get('title', '')} {grant.get('description', '')} {grant.get('keywords', '')}"
                grant['biotools_relevance'] = self._calculate_biotools_relevance(combined_text)
                return grant
            return None
        except Exception as e:
            logger.error(f"Error getting grant {grant_id}: {e}")
            return None
        finally:
            conn.close()
    
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
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics with biotools relevance breakdown"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            stats = {}
            
            # Total counts
            cursor.execute("SELECT COUNT(*) FROM grants")
            total_grants = cursor.fetchone()[0]
            stats['total_grants'] = total_grants
            
            # Count by type with biotools validation
            cursor.execute("SELECT grant_type, COUNT(*) FROM grants WHERE grant_type IS NOT NULL GROUP BY grant_type")
            type_counts_raw = cursor.fetchall()
            type_counts = {'award': 0, 'solicitation': 0}
            
            for gtype, count in type_counts_raw:
                if gtype in type_counts:
                    type_counts[gtype] = count
            
            # Count companies (awards with company names)
            cursor.execute("SELECT COUNT(*) FROM grants WHERE (company_name IS NOT NULL AND company_name != '') OR (firm IS NOT NULL AND firm != '')")
            companies_count = cursor.fetchone()[0]
            
            stats['awards_count'] = type_counts['award']
            stats['solicitations_count'] = type_counts['solicitation'] 
            stats['companies_count'] = companies_count
            
            # Biotools relevance statistics
            cursor.execute("SELECT title, description, keywords FROM grants")
            all_grants = cursor.fetchall()
            
            biotools_relevant_count = 0
            for title, desc, keywords in all_grants:
                combined_text = f"{title or ''} {desc or ''} {keywords or ''}"
                if self._calculate_biotools_relevance(combined_text) > 3.0:
                    biotools_relevant_count += 1
            
            stats['biotools_relevant_count'] = biotools_relevant_count
            stats['biotools_relevance_percentage'] = round((biotools_relevant_count / total_grants * 100), 1) if total_grants > 0 else 0
            
            # Agency breakdown (biotools-focused)
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
                    AND (close_date IS NULL OR close_date > date('now'))
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
                'recent_grants': 0,
                'open_solicitations': 0,
                'agencies': [],
                'last_updated': datetime.now().isoformat()
            }
        finally:
            conn.close()


# Initialize the enhanced biotools matcher
biotools_matcher = EnhancedBiotoolsMatcher()


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


@app.route('/<int:grant_id>')
def grant_detail_page(grant_id):
    """Serve grant detail page"""
    return render_template('index.html')


@app.route('/api/search', methods=['POST'])
@limiter.limit("50 per hour;5 per minute")
def search_grants():
    """Enhanced biotools search with mandatory taxonomy validation and browse mode support"""
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
        
        # Perform biotools-validated search
        grants = biotools_matcher.search_grants(query, limit, filters)
        
        # Log the search with biotools context
        data_type = filters.get('data_type', 'all')
        mode = "browse" if browse_mode else "search"
        logger.info(f"Biotools {mode}: query='{query}', types={tool_types}, areas={focus_areas}, results={len(grants)}, ip={client_ip}")
        
        # Create display query for frontend
        if browse_mode:
            display_query = f"Browsing: {', '.join(tool_types)} • {', '.join(focus_areas)}"
        else:
            display_query = query
        
        return jsonify({
            'query': display_query,
            'original_query': query,
            'browse_mode': browse_mode,
            'data_type': data_type,
            'tool_types': tool_types,
            'focus_areas': focus_areas,
            'results': grants,
            'total_found': len(grants),
            'biotools_validated': True,
            'precision_mode': True,
            'timestamp': datetime.now().isoformat()
        })
        
    except ValueError as e:
        logger.warning(f"Validation error from {client_ip}: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Search error from {client_ip}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/grant/<int:grant_id>', methods=['GET'])
@limiter.limit("100 per hour;10 per minute")
def get_grant_details(grant_id):
    """Get detailed information about a specific grant with biotools validation"""
    client_ip = get_remote_address()
    
    try:
        if grant_id <= 0:
            return jsonify({'error': 'Invalid grant ID'}), 400
        
        grant = biotools_matcher.get_grant_by_id(grant_id)
        
        if not grant:
            logger.info(f"Grant not found: id={grant_id}, ip={client_ip}")
            return jsonify({'error': 'Grant not found'}), 404
        
        logger.info(f"Grant details accessed: id={grant_id}, biotools_relevance={grant.get('biotools_relevance', 0):.1f}, ip={client_ip}")
        return jsonify(grant)
        
    except Exception as e:
        logger.error(f"Grant details error: id={grant_id}, ip={client_ip}, error={e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/stats', methods=['GET'])
@limiter.limit("60 per hour;10 per minute")
def get_stats():
    """Get enhanced database statistics with biotools relevance metrics"""
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
            'recent_grants': 0,
            'open_solicitations': 0,
            'agencies': [],
            'last_updated': datetime.now().isoformat()
        }), 500


@app.route('/api/grants/trending', methods=['GET'])
@limiter.limit("60 per hour;10 per minute")
def get_trending_grants():
    """Get trending grants based on recent activity and high relevance scores"""
    try:
        limit = min(request.args.get('limit', 20, type=int), 50)
        days = min(request.args.get('days', 30, type=int), 90)
        
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get trending grants with high relevance scores and recent updates
        cursor.execute("""
            SELECT *, 
                   (COALESCE(relevance_score, 0) * 0.7 + 
                    CASE 
                        WHEN updated_at > date('now', '-7 days') THEN 3.0
                        WHEN updated_at > date('now', '-30 days') THEN 2.0
                        ELSE 1.0
                    END * 0.3) as trending_score
            FROM grants 
            WHERE COALESCE(relevance_score, 0) >= 2.0 
            AND (biotools_category IS NOT NULL AND biotools_category != '')
            ORDER BY trending_score DESC, relevance_score DESC
            LIMIT ?
        """, (limit,))
        
        grants = [dict(row) for row in cursor.fetchall()]
        
        # Add trending indicators
        for grant in grants:
            grant['is_trending'] = True
            grant['trending_score'] = round(grant['trending_score'], 2)
            grant['inferred_type'] = biotools_matcher._determine_data_type(grant)
        
        conn.close()
        
        return jsonify({
            'trending_grants': grants,
            'total_found': len(grants),
            'period_days': days,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Trending grants error: {e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Check database connectivity
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM grants LIMIT 1")
        grant_count = cursor.fetchone()[0]
        conn.close()
        
        # Check biotools matcher
        matcher_status = len(biotools_matcher.idf_cache) > 0
        
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': {
                'connected': True,
                'grant_count': grant_count
            },
            'biotools_matcher': {
                'initialized': matcher_status,
                'idf_cache_size': len(biotools_matcher.idf_cache)
            },
            'version': '2.0.0'
        }
        
        return jsonify(health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


@app.route('/api/feedback', methods=['POST'])
@limiter.limit("20 per hour;2 per minute")
def submit_feedback():
    """Submit user feedback with validation"""
    client_ip = get_remote_address()
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Validate required fields
        required_fields = ['grant_id', 'feedback_type']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Validate values
        valid_types = ['helpful', 'not_helpful', 'applied', 'bookmarked']
        if data['feedback_type'] not in valid_types:
            return jsonify({'error': 'Invalid feedback type'}), 400
        
        grant_id = data['grant_id']
        if not isinstance(grant_id, int) or grant_id <= 0:
            return jsonify({'error': 'Invalid grant ID'}), 400
        
        # Sanitize text fields
        notes = data.get('notes', '')
        if len(notes) > 500:
            return jsonify({'error': 'Notes too long (maximum 500 characters)'}), 400
        
        search_query = data.get('search_query', '')
        if len(search_query) > 200:
            return jsonify({'error': 'Search query too long (maximum 200 characters)'}), 400
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS grant_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                grant_id INTEGER NOT NULL,
                search_query TEXT,
                feedback_type TEXT CHECK (feedback_type IN ('helpful', 'not_helpful', 'applied', 'bookmarked')),
                user_session TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (grant_id) REFERENCES grants(id) ON DELETE CASCADE
            )
        """)
        
        cursor.execute("""
            INSERT INTO grant_feedback 
            (grant_id, search_query, feedback_type, user_session, notes, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            grant_id,
            search_query,
            data['feedback_type'],
            client_ip,
            notes,
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Feedback submitted: grant_id={grant_id}, type={data['feedback_type']}, ip={client_ip}")
        
        return jsonify({'status': 'success', 'message': 'Feedback recorded'})
        
    except Exception as e:
        logger.error(f"Feedback error from {client_ip}: {e}")
        return jsonify({'error': 'Internal server error'}), 500


# Database optimization functions
def optimize_database():
    """Optimize database for better performance"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        logger.info("Starting database optimization...")
        
        # Analyze tables
        cursor.execute("ANALYZE grants")
        
        # Rebuild indexes
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_grants_title ON grants(title)",
            "CREATE INDEX IF NOT EXISTS idx_grants_agency ON grants(agency)",
            "CREATE INDEX IF NOT EXISTS idx_grants_relevance ON grants(relevance_score)",
            "CREATE INDEX IF NOT EXISTS idx_grants_biotools_category ON grants(biotools_category)",
            "CREATE INDEX IF NOT EXISTS idx_grants_confidence ON grants(confidence_score)",
            "CREATE INDEX IF NOT EXISTS idx_grants_amount ON grants(amount)",
            "CREATE INDEX IF NOT EXISTS idx_grants_award_date ON grants(award_date)",
            "CREATE INDEX IF NOT EXISTS idx_grants_updated_at ON grants(updated_at)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        # Vacuum database
        cursor.execute("VACUUM")
        
        # Update statistics
        cursor.execute("PRAGMA optimize")
        
        conn.commit()
        logger.info("Database optimization completed successfully")
        
    except Exception as e:
        logger.error(f"Database optimization failed: {e}")
        raise
    finally:
        conn.close()


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404


@app.errorhandler(429)
def rate_limit_handler(error):
    client_ip = get_remote_address()
    logger.warning(f"Rate limit exceeded for {client_ip}")
    return jsonify({
        'error': 'Rate limit exceeded',
        'message': 'Please wait before making more requests'
    }), 429


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    if not os.path.exists(DATABASE_PATH):
        logger.error("Database not found. Run the scraper first.")
        exit(1)
    else:
        logger.info("Enhanced BioTools Grant Matcher with Precision Focus initialized successfully!")
        logger.info(f"Biotools IDF cache contains {len(biotools_matcher.idf_cache)} terms")
        
        # Log initial stats with biotools metrics
        stats = biotools_matcher.get_database_stats()
        logger.info(f"Database: {stats['total_grants']} total grants, {stats['biotools_relevant_count']} biotools-relevant ({stats['biotools_relevance_percentage']}%)")
        logger.info(f"Breakdown: {stats['awards_count']} awards, {stats['solicitations_count']} solicitations, {stats['companies_count']} companies")
    
    app.run(debug=False, host='0.0.0.0', port=5000)