#!/usr/bin/env python3
"""
Secure Flask API Backend with Rate Limiting and Input Validation
Enhanced security features for production deployment
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
from typing import List, Dict, Any, Tuple
from collections import Counter, defaultdict
import math
import hashlib
import secrets
import logging
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

# Rate limiting configuration
# Try Redis first, fall back to memory storage
try:
    import redis
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    redis_client.ping()  # Test connection
    limiter = Limiter(
        app,
        key_func=get_remote_address,
        storage_uri="redis://localhost:6379",
        default_limits=["1000 per hour", "100 per minute"]
    )
    print("✅ Using Redis for rate limiting")
except (ImportError, redis.exceptions.ConnectionError, redis.exceptions.ResponseError):
    print("⚠️  Redis not available, using memory storage for rate limiting")
    limiter = Limiter(
        app,
        key_func=get_remote_address,
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

# Your existing EnhancedGrantMatcher class goes here
class EnhancedGrantMatcher:
    def __init__(self, db_path=DATABASE_PATH):
        self.db_path = db_path
        self.idf_cache = {}
        self._build_idf_cache()
    
    def _build_idf_cache(self):
        """Build IDF cache for TF-IDF scoring"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT COUNT(*) FROM grants")
            total_docs = cursor.fetchone()[0]
            
            if total_docs == 0:
                conn.close()
                return
            
            logger.info(f"Building IDF cache for {total_docs} documents...")
            
            cursor.execute("SELECT title, description, keywords FROM grants")
            documents = cursor.fetchall()
            
            term_doc_freq = Counter()
            
            for title, desc, keywords in documents:
                text = f"{title or ''} {desc or ''} {keywords or ''}"
                terms = set(self._extract_terms(text.lower()))
                
                for term in terms:
                    term_doc_freq[term] += 1
            
            for term, doc_freq in term_doc_freq.items():
                if doc_freq > 0:
                    self.idf_cache[term] = math.log(total_docs / doc_freq)
                    
            logger.info(f"IDF cache built with {len(self.idf_cache)} terms")
            
        except Exception as e:
            logger.error(f"Error building IDF cache: {e}")
        finally:
            conn.close()
    
    def _extract_terms(self, text: str) -> List[str]:
        """Extract meaningful terms from text"""
        if not text:
            return []
            
        text = re.sub(r'[^\w\s]', ' ', text)
        terms = text.split()
        
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 
            'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 
            'do', 'does', 'did', 'will', 'would', 'could', 'should', 'this', 'that', 
            'these', 'those', 'can', 'may', 'might', 'must', 'shall', 'from', 'up', 
            'out', 'down', 'off', 'over', 'under', 'again', 'further', 'then', 'once'
        }
        
        return [term for term in terms if len(term) > 2 and term.lower() not in stop_words]
    
    def _calculate_tf_idf_score(self, query_terms: List[str], document_text: str) -> float:
        """Calculate TF-IDF score for document against query"""
        doc_terms = self._extract_terms(document_text.lower())
        
        if not doc_terms:
            return 0.0
        
        tf_counts = Counter(doc_terms)
        max_tf = max(tf_counts.values()) if tf_counts else 1
        
        score = 0.0
        for query_term in query_terms:
            if query_term in tf_counts:
                tf = tf_counts[query_term] / max_tf
                idf = self.idf_cache.get(query_term, 0)
                score += tf * idf
        
        return score
    
    def _calculate_semantic_score(self, query: str, grant: Dict[str, Any]) -> float:
        """Calculate semantic similarity score"""
        term_clusters = {
            'diagnostics': ['diagnostic', 'biomarker', 'assay', 'test', 'detection', 'screening', 'analysis'],
            'devices': ['device', 'instrument', 'equipment', 'tool', 'apparatus', 'system', 'platform'],
            'automation': ['automation', 'robotic', 'automated', 'workflow', 'pipeline', 'high-throughput'],
            'analysis': ['analysis', 'analytical', 'measurement', 'quantification', 'characterization', 'monitoring'],
            'molecular': ['molecular', 'genomic', 'proteomic', 'genetic', 'sequencing', 'pcr', 'dna', 'rna'],
            'imaging': ['imaging', 'microscopy', 'visualization', 'optical', 'fluorescence', 'mri', 'ct'],
            'microfluidics': ['microfluidic', 'chip', 'miniaturized', 'portable', 'point-of-care', 'lab-on-chip'],
            'ai_ml': ['artificial intelligence', 'machine learning', 'deep learning', 'neural network', 'ai', 'ml', 'algorithm'],
            'clinical': ['clinical', 'patient', 'hospital', 'bedside', 'healthcare', 'medical', 'therapeutic'],
            'research': ['research', 'study', 'investigation', 'experiment', 'innovation', 'development']
        }
        
        query_lower = query.lower()
        grant_text = f"{grant.get('title', '')} {grant.get('description', '')} {grant.get('keywords', '')}".lower()
        
        score = 0.0
        
        for cluster_name, terms in term_clusters.items():
            query_matches = sum(1 for term in terms if term in query_lower)
            grant_matches = sum(1 for term in terms if term in grant_text)
            
            if query_matches > 0 and grant_matches > 0:
                cluster_score = (query_matches * grant_matches) / len(terms)
                score += cluster_score * 3.0
        
        return score
    
    def _calculate_keyword_score(self, query: str, grant: Dict[str, Any]) -> float:
        """Calculate score based on exact keyword matches"""
        score = 0.0
        query_lower = query.lower()
        
        if grant.get('title'):
            title_lower = grant['title'].lower()
            if query_lower in title_lower:
                score += 15.0
            query_words = query_lower.split()
            for word in query_words:
                if len(word) > 3 and word in title_lower:
                    score += 8.0
        
        if grant.get('keywords'):
            keywords = [k.strip().lower() for k in grant['keywords'].split(',')]
            for keyword in keywords:
                if keyword in query_lower or query_lower in keyword:
                    score += 6.0
                query_words = query_lower.split()
                for word in query_words:
                    if len(word) > 3 and word in keyword:
                        score += 3.0
        
        if grant.get('description'):
            desc_lower = grant['description'].lower()
            if query_lower in desc_lower:
                score += 4.0
            query_words = query_lower.split()
            for word in query_words:
                if len(word) > 3 and word in desc_lower:
                    score += 1.5
        
        biotools_agencies = ['nih', 'nsf', 'sbir', 'cdc', 'darpa', 'nist']
        if grant.get('agency'):
            agency_lower = grant['agency'].lower()
            for bio_agency in biotools_agencies:
                if bio_agency in agency_lower:
                    score += 2.0
                    break
        
        return score
    
    def _calculate_freshness_score(self, grant: Dict[str, Any]) -> float:
        """Calculate score based on grant freshness"""
        try:
            if grant.get('updated_at'):
                updated = datetime.fromisoformat(grant['updated_at'].replace('Z', '+00:00'))
                days_old = (datetime.now() - updated).days
                
                if days_old < 7:
                    return 5.0
                elif days_old < 30:
                    return 4.0
                elif days_old < 90:
                    return 3.0
                elif days_old < 180:
                    return 2.0
                else:
                    return 1.0
        except Exception as e:
            logger.error(f"Error calculating freshness score: {e}")
        
        return 1.0
    
    def _apply_filters(self, grants: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply user-specified filters to grants"""
        if not filters:
            return grants
        
        filtered_grants = []
        
        for grant in grants:
            if filters.get('agency') and grant.get('agency'):
                if filters['agency'].lower() not in grant['agency'].lower():
                    continue
            
            if filters.get('amount_min'):
                try:
                    min_amount = float(filters['amount_min'])
                    if grant.get('amount_max', 0) < min_amount:
                        continue
                except (ValueError, TypeError):
                    pass
            
            if filters.get('amount_max'):
                try:
                    max_amount = float(filters['amount_max'])
                    if grant.get('amount_min', 0) > max_amount:
                        continue
                except (ValueError, TypeError):
                    pass
            
            if filters.get('deadline'):
                try:
                    days_filter = int(filters['deadline'])
                    if grant.get('deadline'):
                        deadline = datetime.fromisoformat(grant['deadline'])
                        days_until_deadline = (deadline - datetime.now()).days
                        if days_until_deadline > days_filter:
                            continue
                except (ValueError, TypeError):
                    pass
            
            if filters.get('category'):
                category_keywords = {
                    'diagnostics': ['diagnostic', 'biomarker', 'assay', 'test', 'detection'],
                    'devices': ['device', 'instrument', 'equipment', 'tool'],
                    'automation': ['automation', 'robotic', 'automated', 'workflow'],
                    'ai': ['artificial intelligence', 'machine learning', 'ai', 'ml']
                }
                
                category = filters['category'].lower()
                if category in category_keywords:
                    grant_text = f"{grant.get('title', '')} {grant.get('description', '')} {grant.get('keywords', '')}".lower()
                    if not any(keyword in grant_text for keyword in category_keywords[category]):
                        continue
            
            if filters.get('keywords'):
                additional_keywords = [k.strip().lower() for k in filters['keywords'].split(',')]
                grant_text = f"{grant.get('title', '')} {grant.get('description', '')} {grant.get('keywords', '')}".lower()
                if not any(keyword in grant_text for keyword in additional_keywords):
                    continue
            
            filtered_grants.append(grant)
        
        return filtered_grants
    
    def search_grants(self, query: str, limit: int = 20, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Enhanced search using multiple scoring methods"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM grants")
            all_grants = cursor.fetchall()
            
            if not all_grants:
                return []
            
            query_terms = self._extract_terms(query.lower())
            if not query_terms:
                return []
            
            scored_grants = []
            
            for row in all_grants:
                grant = dict(row)
                
                combined_text = f"{grant.get('title', '')} {grant.get('description', '')} {grant.get('keywords', '')}"
                
                tf_idf_score = self._calculate_tf_idf_score(query_terms, combined_text)
                semantic_score = self._calculate_semantic_score(query, grant)
                keyword_score = self._calculate_keyword_score(query, grant)
                freshness_score = self._calculate_freshness_score(grant)
                
                final_score = (
                    tf_idf_score * 0.25 +
                    semantic_score * 0.35 +
                    keyword_score * 0.30 +
                    freshness_score * 0.10
                )
                
                grant['relevance_score'] = round(final_score, 2)
                
                if final_score > 0.5:
                    scored_grants.append(grant)
            
            if filters:
                scored_grants = self._apply_filters(scored_grants, filters)
            
            scored_grants.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            return scored_grants[:limit]
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
        finally:
            conn.close()
    
    def get_grant_by_id(self, grant_id: int) -> Dict[str, Any]:
        """Get specific grant by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM grants WHERE id = ?", (grant_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
        finally:
            conn.close()

# Security helper functions
def validate_input(data, required_fields, max_lengths=None):
    """Validate and sanitize input data"""
    if not isinstance(data, dict):
        raise ValueError("Invalid input format")
    
    for field in required_fields:
        if field not in data or not data[field]:
            raise ValueError(f"Missing required field: {field}")
    
    # Sanitize text inputs
    sanitized_data = {}
    for key, value in data.items():
        if isinstance(value, str):
            # Remove potentially dangerous characters
            value = re.sub(r'[<>"\'\x00-\x1f\x7f-\x9f]', '', value)
            value = value.strip()
            
            # Check length limits
            if max_lengths and key in max_lengths:
                if len(value) > max_lengths[key]:
                    raise ValueError(f"Field {key} exceeds maximum length of {max_lengths[key]}")
            
            sanitized_data[key] = value
        elif isinstance(value, (int, float)):
            sanitized_data[key] = value
        elif isinstance(value, dict):
            # Recursively validate nested objects
            sanitized_data[key] = validate_input(value, [], max_lengths)
        else:
            sanitized_data[key] = value
    
    return sanitized_data

def log_request(request_type, query=None, client_ip=None, results_count=0):
    """Log search requests for analytics and security monitoring"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO search_history (query, results_count, user_session, ip_address)
            VALUES (?, ?, ?, ?)
        """, (query or '', results_count, '', client_ip or get_remote_address()))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to log request: {e}")

# Initialize grant matcher
grant_matcher = EnhancedGrantMatcher()

# Security headers
@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = "default-src 'self' 'unsafe-inline' 'unsafe-eval'; img-src 'self' data:; connect-src 'self'"
    
    # Remove server information
    response.headers.pop('Server', None)
    
    return response

# Routes
@app.route('/')
def index():
    """Serve the main application page"""
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
@limiter.limit("50 per hour;5 per minute")  # More restrictive for search
def search_grants():
    """Enhanced search for grants with security validation"""
    client_ip = get_remote_address()
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Validate and sanitize input
        sanitized_data = validate_input(
            data, 
            required_fields=['query'],
            max_lengths={'query': 200, 'keywords': 100}
        )
        
        query = sanitized_data['query']
        limit = min(sanitized_data.get('limit', 20), 50)  # Cap at 50 results
        filters = sanitized_data.get('filters', {})
        
        # Additional query validation
        if len(query.strip()) < 2:
            return jsonify({'error': 'Query too short (minimum 2 characters)'}), 400
        
        # Check for potential SQL injection patterns
        suspicious_patterns = ['union', 'select', 'drop', 'delete', 'insert', '--', '/*', '*/', ';']
        query_lower = query.lower()
        if any(pattern in query_lower for pattern in suspicious_patterns):
            logger.warning(f"Suspicious query detected from {client_ip}: {query}")
            return jsonify({'error': 'Invalid query format'}), 400
        
        # Search grants with enhanced algorithm
        grants = grant_matcher.search_grants(query, limit, filters)
        
        # Log the search for analytics
        log_request('search', query, client_ip, len(grants))
        
        # Use DigitalOcean agent to enhance results (if configured)
        if DIGITALOCEAN_AGENT_API_KEY and DIGITALOCEAN_AGENT_URL and grants:
            enhanced_grants = enhance_with_agent(query, grants)
            grants = enhanced_grants if enhanced_grants else grants
        
        logger.info(f"Search completed: query='{query}', results={len(grants)}, ip={client_ip}")
        
        return jsonify({
            'query': query,
            'results': grants,
            'total_found': len(grants),
            'filters_applied': bool(filters),
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
    """Get detailed information about a specific grant"""
    client_ip = get_remote_address()
    
    try:
        # Validate grant_id
        if grant_id <= 0:
            return jsonify({'error': 'Invalid grant ID'}), 400
        
        grant = grant_matcher.get_grant_by_id(grant_id)
        
        if not grant:
            logger.info(f"Grant not found: id={grant_id}, ip={client_ip}")
            return jsonify({'error': 'Grant not found'}), 404
        
        logger.info(f"Grant details accessed: id={grant_id}, ip={client_ip}")
        return jsonify(grant)
        
    except Exception as e:
        logger.error(f"Grant details error: id={grant_id}, ip={client_ip}, error={e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/stats', methods=['GET'])
@limiter.limit("20 per hour;2 per minute")
def get_stats():
    """Get database statistics"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM grants")
        total_grants = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM grants WHERE updated_at > date('now', '-30 days')")
        recent_grants = cursor.fetchone()[0]
        
        cursor.execute("SELECT agency, COUNT(*) FROM grants GROUP BY agency ORDER BY COUNT(*) DESC LIMIT 10")
        agencies = cursor.fetchall()
        
        # Get search analytics
        cursor.execute("SELECT COUNT(*) FROM search_history WHERE timestamp > datetime('now', '-7 days')")
        recent_searches = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'total_grants': total_grants,
            'recent_grants': recent_grants,
            'recent_searches': recent_searches,
            'agencies': [{'name': agency[0], 'count': agency[1]} for agency in agencies],
            'last_updated': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/feedback', methods=['POST'])
@limiter.limit("20 per hour;2 per minute")
def submit_feedback():
    """Submit user feedback with validation"""
    client_ip = get_remote_address()
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Validate input
        sanitized_data = validate_input(
            data,
            required_fields=['grant_id', 'feedback_type'],
            max_lengths={'notes': 500, 'search_query': 200}
        )
        
        # Validate feedback type
        valid_types = ['helpful', 'not_helpful', 'applied', 'bookmarked']
        if sanitized_data['feedback_type'] not in valid_types:
            return jsonify({'error': 'Invalid feedback type'}), 400
        
        # Validate grant_id
        grant_id = sanitized_data['grant_id']
        if not isinstance(grant_id, int) or grant_id <= 0:
            return jsonify({'error': 'Invalid grant ID'}), 400
        
        # Store feedback in database
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO grant_feedback 
            (grant_id, search_query, feedback_type, user_session, notes, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            grant_id,
            sanitized_data.get('search_query', ''),
            sanitized_data['feedback_type'],
            client_ip,
            sanitized_data.get('notes', ''),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Feedback submitted: grant_id={grant_id}, type={sanitized_data['feedback_type']}, ip={client_ip}")
        
        return jsonify({'status': 'success', 'message': 'Feedback recorded'})
        
    except ValueError as e:
        logger.warning(f"Feedback validation error from {client_ip}: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Feedback error from {client_ip}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

def enhance_with_agent(query: str, grants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Use DigitalOcean agent to enhance grant matching"""
    try:
        agent_payload = {
            'query': query,
            'grants': grants[:10],
            'task': 'rank_and_enhance_grants'
        }
        
        headers = {
            'Authorization': f'Bearer {DIGITALOCEAN_AGENT_API_KEY}',
            'Content-Type': 'application/json'
        }
        
        response = requests.post(DIGITALOCEAN_AGENT_URL, 
                               json=agent_payload, 
                               headers=headers, 
                               timeout=30)
        
        if response.status_code == 200:
            enhanced_data = response.json()
            return enhanced_data.get('enhanced_grants', grants)
        
    except Exception as e:
        logger.warning(f"Agent enhancement failed: {e}")
    
    return grants

# Error handlers
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
    # Check if database exists
    if not os.path.exists(DATABASE_PATH):
        logger.error("Database not found. Run the scraper first.")
        exit(1)
    else:
        logger.info("Enhanced Grant Matcher with Security initialized successfully!")
        logger.info(f"IDF cache contains {len(grant_matcher.idf_cache)} terms")
    
    # Run Flask app
    app.run(debug=False, host='0.0.0.0', port=5000)