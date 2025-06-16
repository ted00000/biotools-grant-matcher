#!/usr/bin/env python3
"""
Flask API Backend for Grant Matching Service with Enhanced Search
Integrates TF-IDF and semantic matching algorithms
"""

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3
import json
import re
from datetime import datetime
import requests
import os
from typing import List, Dict, Any, Tuple
from collections import Counter
import math

app = Flask(__name__)
CORS(app)

# Configuration
DATABASE_PATH = "data/grants.db"
DIGITALOCEAN_AGENT_API_KEY = os.getenv('DO_AGENT_API_KEY', '')
DIGITALOCEAN_AGENT_URL = os.getenv('DO_AGENT_URL', '')

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
            
            print(f"Building IDF cache for {total_docs} documents...")
            
            # Get all text content
            cursor.execute("SELECT title, description, keywords FROM grants")
            documents = cursor.fetchall()
            
            # Count document frequency for each term
            term_doc_freq = Counter()
            
            for title, desc, keywords in documents:
                # Combine all text and extract terms
                text = f"{title or ''} {desc or ''} {keywords or ''}"
                terms = set(self._extract_terms(text.lower()))
                
                for term in terms:
                    term_doc_freq[term] += 1
            
            # Calculate IDF for each term
            for term, doc_freq in term_doc_freq.items():
                if doc_freq > 0:
                    self.idf_cache[term] = math.log(total_docs / doc_freq)
                    
            print(f"IDF cache built with {len(self.idf_cache)} terms")
            
        except Exception as e:
            print(f"Error building IDF cache: {e}")
        finally:
            conn.close()
    
    def _extract_terms(self, text: str) -> List[str]:
        """Extract meaningful terms from text"""
        if not text:
            return []
            
        # Remove punctuation and split
        text = re.sub(r'[^\w\s]', ' ', text)
        terms = text.split()
        
        # Filter out common stop words and short terms
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
        
        # Calculate term frequency
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
        # Define biotools-related term clusters
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
        
        # Check for cluster matches
        for cluster_name, terms in term_clusters.items():
            query_matches = sum(1 for term in terms if term in query_lower)
            grant_matches = sum(1 for term in terms if term in grant_text)
            
            if query_matches > 0 and grant_matches > 0:
                # Calculate cluster score based on overlap
                cluster_score = (query_matches * grant_matches) / len(terms)
                score += cluster_score * 3.0  # Boost semantic matches
        
        return score
    
    def _calculate_keyword_score(self, query: str, grant: Dict[str, Any]) -> float:
        """Calculate score based on exact keyword matches"""
        score = 0.0
        query_lower = query.lower()
        
        # Title matches (highest weight)
        if grant.get('title'):
            title_lower = grant['title'].lower()
            if query_lower in title_lower:
                score += 15.0
            # Partial word matches in title
            query_words = query_lower.split()
            for word in query_words:
                if len(word) > 3 and word in title_lower:
                    score += 8.0
        
        # Exact keyword matches
        if grant.get('keywords'):
            keywords = [k.strip().lower() for k in grant['keywords'].split(',')]
            for keyword in keywords:
                if keyword in query_lower or query_lower in keyword:
                    score += 6.0
                # Partial matches
                query_words = query_lower.split()
                for word in query_words:
                    if len(word) > 3 and word in keyword:
                        score += 3.0
        
        # Description matches
        if grant.get('description'):
            desc_lower = grant['description'].lower()
            if query_lower in desc_lower:
                score += 4.0
            # Word-level matches in description
            query_words = query_lower.split()
            for word in query_words:
                if len(word) > 3 and word in desc_lower:
                    score += 1.5
        
        # Agency boost for relevant agencies
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
                
                # Fresher grants get higher scores
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
            print(f"Error calculating freshness score: {e}")
        
        return 1.0  # Default score
    
    def _apply_filters(self, grants: List[Dict[str, Any]], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply user-specified filters to grants"""
        if not filters:
            return grants
        
        filtered_grants = []
        
        for grant in grants:
            # Agency filter
            if filters.get('agency') and grant.get('agency'):
                if filters['agency'].lower() not in grant['agency'].lower():
                    continue
            
            # Amount filters
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
            
            # Deadline filter
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
            
            # Category filter (semantic matching)
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
            
            # Additional keywords filter
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
            # Get all grants for scoring
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
                
                # Combine text for scoring
                combined_text = f"{grant.get('title', '')} {grant.get('description', '')} {grant.get('keywords', '')}"
                
                # Calculate multiple scores
                tf_idf_score = self._calculate_tf_idf_score(query_terms, combined_text)
                semantic_score = self._calculate_semantic_score(query, grant)
                keyword_score = self._calculate_keyword_score(query, grant)
                freshness_score = self._calculate_freshness_score(grant)
                
                # Weighted final score
                final_score = (
                    tf_idf_score * 0.25 +      # TF-IDF for content relevance
                    semantic_score * 0.35 +    # Semantic clusters for domain relevance
                    keyword_score * 0.30 +     # Exact keyword matches
                    freshness_score * 0.10     # Recency boost
                )
                
                grant['relevance_score'] = round(final_score, 2)
                
                # Only include grants with meaningful scores
                if final_score > 0.5:  # Minimum threshold
                    scored_grants.append(grant)
            
            # Apply user filters
            if filters:
                scored_grants = self._apply_filters(scored_grants, filters)
            
            # Sort by relevance and return top results
            scored_grants.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            return scored_grants[:limit]
            
        except Exception as e:
            print(f"Search error: {e}")
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

# Initialize enhanced grant matcher
grant_matcher = EnhancedGrantMatcher()

@app.route('/')
def index():
    """Serve the main application page"""
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def search_grants():
    """Enhanced search for grants based on research query"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        limit = min(data.get('limit', 20), 50)  # Cap at 50 results
        filters = data.get('filters', {})
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        if len(query) < 2:
            return jsonify({'error': 'Query too short (minimum 2 characters)'}), 400
        
        # Search grants with enhanced algorithm
        grants = grant_matcher.search_grants(query, limit, filters)
        
        # Use DigitalOcean agent to enhance results (if configured)
        if DIGITALOCEAN_AGENT_API_KEY and DIGITALOCEAN_AGENT_URL and grants:
            enhanced_grants = enhance_with_agent(query, grants)
            grants = enhanced_grants if enhanced_grants else grants
        
        return jsonify({
            'query': query,
            'results': grants,
            'total_found': len(grants),
            'filters_applied': filters,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"Search error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/grant/<int:grant_id>', methods=['GET'])
def get_grant_details(grant_id):
    """Get detailed information about a specific grant"""
    try:
        grant = grant_matcher.get_grant_by_id(grant_id)
        
        if not grant:
            return jsonify({'error': 'Grant not found'}), 404
        
        return jsonify(grant)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
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
        
        # Calculate average relevance score for recent searches (mock data for now)
        avg_relevance = 7.2
        
        conn.close()
        
        return jsonify({
            'total_grants': total_grants,
            'recent_grants': recent_grants,
            'average_relevance': avg_relevance,
            'agencies': [{'name': agency[0], 'count': agency[1]} for agency in agencies],
            'last_updated': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """Submit user feedback on grant recommendations"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data or 'grant_id' not in data or 'feedback_type' not in data:
            return jsonify({'error': 'Missing required fields'}), 400
        
        # For MVP, just log feedback
        feedback_data = {
            'grant_id': data['grant_id'],
            'feedback_type': data['feedback_type'],
            'search_query': data.get('search_query', ''),
            'timestamp': datetime.now().isoformat(),
            'user_session': request.remote_addr  # Simple session tracking
        }
        
        print(f"Feedback received: {feedback_data}")
        
        # TODO: Store in database for learning
        
        return jsonify({'status': 'success', 'message': 'Feedback recorded'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def enhance_with_agent(query: str, grants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Use DigitalOcean agent to enhance grant matching"""
    try:
        # Prepare agent request
        agent_payload = {
            'query': query,
            'grants': grants[:10],  # Send top 10 grants to agent
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
        print(f"Agent enhancement failed: {e}")
    
    return grants

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Check if database exists
    if not os.path.exists(DATABASE_PATH):
        print("Warning: Database not found. Run the scraper first.")
    else:
        print("Enhanced Grant Matcher initialized successfully!")
        print(f"IDF cache contains {len(grant_matcher.idf_cache)} terms")
    
    # Run Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)