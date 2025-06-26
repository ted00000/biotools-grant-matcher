#!/usr/bin/env python3
"""
Fixed BioTools Grant Matcher Backend - Grant Details Issue Resolved
Key fixes:
1. Added missing grant detail page route
2. Fixed grant details API endpoint  
3. Enhanced error handling for grant details
4. Added proper HTML template serving for grant details
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
    
    def _determine_data_type(self, record: Dict[str, Any]) -> str:
        """Determine the data type of a record"""
        if record.get('grant_type'):
            return record['grant_type']
        
        if (record.get('solicitation_number') or 
            record.get('current_status') in ['open', 'active'] or
            record.get('close_date')):
            return 'solicitation'
        
        return 'award'
    
    def get_grant_by_id(self, grant_id: int) -> Optional[Dict[str, Any]]:
        """Get specific grant by ID with enhanced data formatting"""
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
                
                # Enhanced company name handling
                grant['display_company'] = grant.get('firm') or grant.get('company_name') or 'Unknown Company'
                
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
                
                logger.info(f"Retrieved grant details: id={grant_id}, type={grant['inferred_type']}, relevance={grant['biotools_relevance']:.2f}")
                return grant
            else:
                logger.warning(f"Grant not found: id={grant_id}")
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
            
            # Count companies (awards with company names) - handle both firm and company_name columns
            try:
                cursor.execute("SELECT COUNT(*) FROM grants WHERE company_name IS NOT NULL AND company_name != ''")
                companies_count = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                try:
                    cursor.execute("SELECT COUNT(*) FROM grants WHERE firm IS NOT NULL AND firm != ''")
                    companies_count = cursor.fetchone()[0]
                except sqlite3.OperationalError:
                    companies_count = 0
            
            stats['awards_count'] = type_counts['award']
            stats['solicitations_count'] = type_counts['solicitation'] 
            stats['companies_count'] = companies_count
            
            # Use stored relevance scores
            cursor.execute("SELECT COUNT(*) FROM grants WHERE relevance_score >= 1.5")
            biotools_relevant_count = cursor.fetchone()[0]
            
            stats['biotools_relevant_count'] = biotools_relevant_count
            stats['biotools_relevance_percentage'] = round((biotools_relevant_count / total_grants * 100), 1) if total_grants > 0 else 0
            
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


# FIXED: Added proper grant detail page route
@app.route('/grant/<int:grant_id>')
def grant_detail_page(grant_id):
    """Serve grant detail page with proper template"""
    return render_template('grant_detail.html', grant_id=grant_id)


# FIXED: Enhanced grant details API endpoint
@app.route('/api/grant/<int:grant_id>', methods=['GET'])
@limiter.limit("100 per hour;10 per minute")
def get_grant_details(grant_id):
    """Get detailed information about a specific grant with enhanced formatting"""
    client_ip = get_remote_address()
    
    try:
        if grant_id <= 0:
            logger.warning(f"Invalid grant ID requested: {grant_id} from {client_ip}")
            return jsonify({'error': 'Invalid grant ID'}), 400
        
        grant = biotools_matcher.get_grant_by_id(grant_id)
        
        if not grant:
            logger.info(f"Grant not found: id={grant_id}, ip={client_ip}")
            return jsonify({'error': 'Grant not found'}), 404
        
        logger.info(f"Grant details accessed: id={grant_id}, biotools_relevance={grant.get('biotools_relevance', 0):.1f}, ip={client_ip}")
        return jsonify({
            'success': True,
            'grant': grant,
            'meta': {
                'retrieved_at': datetime.now().isoformat(),
                'biotools_validated': grant.get('biotools_relevance', 0) >= 1.0
            }
        })
        
    except Exception as e:
        logger.error(f"Grant details error: id={grant_id}, ip={client_ip}, error={e}")
        return jsonify({'error': 'Internal server error'}), 500


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
        
        # Perform biotools-validated search (using existing matcher logic)
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