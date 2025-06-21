#!/usr/bin/env python3
"""
Enhanced Flask API Backend with Data Type Support - FIXED VERSION
- Awards, Solicitations, and Companies filtering ✅
- Enhanced search with type-specific logic ✅
- Updated stats endpoint ✅
- Fixed data type inference for actual schema ✅
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
from typing import List, Dict, Any, Tuple, Optional
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

# Initialize limiter with memory storage
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
    
    def _determine_data_type(self, record: Dict[str, Any]) -> str:
        """Determine the data type of a record - FIXED VERSION"""
        # Check for explicit grant_type field first
        if record.get('grant_type'):
            return record['grant_type']
        
        # Check for solicitation indicators
        if (record.get('solicitation_number') or 
            record.get('current_status') in ['open', 'active'] or
            record.get('close_date')):
            return 'solicitation'
        
        # All SBIR awards are company awards by nature since they go to companies
        # We don't need separate company records - the awards ARE the company data
        return 'award'
    
    def _apply_data_type_filter(self, grants: List[Dict[str, Any]], data_type: str) -> List[Dict[str, Any]]:
        """Filter grants by data type"""
        if data_type == 'all':
            return grants
        
        filtered_grants = []
        for grant in grants:
            record_type = self._determine_data_type(grant)
            
            # Map data types properly
            if data_type == 'awards' and record_type == 'award':
                filtered_grants.append(grant)
            elif data_type == 'solicitations' and record_type == 'solicitation':
                filtered_grants.append(grant)
            elif data_type == 'companies':
                # Companies filter: show awards but group/present them as company data
                if record_type == 'award' and grant.get('company_name'):
                    # Transform award record to look like company data for frontend
                    company_view = grant.copy()
                    company_view['display_type'] = 'company'
                    company_view['company_title'] = f"{grant.get('company_name')} - {grant.get('title', '')}"
                    filtered_grants.append(company_view)
            elif data_type.rstrip('s') == record_type:  # Handle singular forms
                filtered_grants.append(grant)
        
        return filtered_grants
    
    def _calculate_tf_idf_score(self, query_terms: List[str], document_text: str) -> float:
        """Calculate TF-IDF score for document against query"""
        if not query_terms or not document_text:
            return 0.0
            
        doc_terms = self._extract_terms(document_text.lower())
        
        if not doc_terms:
            return 0.0
        
        tf_counts = Counter(doc_terms)
        max_tf = max(tf_counts.values()) if tf_counts else 1
        
        score = 0.0
        matches_found = False
        
        for query_term in query_terms:
            if query_term in tf_counts:
                tf = tf_counts[query_term] / max_tf
                idf = self.idf_cache.get(query_term, 0)
                score += tf * idf
                matches_found = True
        
        # Only return score if actual matches were found
        return score if matches_found else 0.0
    
    def _calculate_semantic_score(self, query: str, grant: Dict[str, Any], data_type: str = 'all') -> float:
        """Calculate semantic similarity score with data type awareness"""
        # Base term clusters
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
            'research': ['research', 'study', 'investigation', 'experiment', 'innovation', 'development'],
            'cell': ['cell', 'cellular', 'single cell', 'stem cell', 'cancer cell', 'immune cell', 'blood cell'],
            'genomics': ['genomic', 'genome', 'genetics', 'gene', 'dna', 'rna', 'sequencing', 'mutation']
        }
        
        # Data type specific clusters
        if data_type in ['awards', 'award']:
            term_clusters['historical'] = ['previous', 'completed', 'funded', 'awarded', 'successful', 'proven']
        elif data_type in ['solicitations', 'solicitation']:
            term_clusters['opportunity'] = ['open', 'apply', 'proposal', 'submit', 'deadline', 'rfp', 'solicitation']
        elif data_type in ['companies', 'company']:
            term_clusters['business'] = ['company', 'startup', 'corporation', 'business', 'commercial', 'venture']
        
        query_lower = query.lower()
        grant_text = f"{grant.get('title', '')} {grant.get('description', '')} {grant.get('keywords', '')}".lower()
        
        score = 0.0
        total_query_matches = 0
        total_grant_matches = 0
        
        for cluster_name, terms in term_clusters.items():
            query_matches = sum(1 for term in terms if term in query_lower)
            grant_matches = sum(1 for term in terms if term in grant_text)
            
            total_query_matches += query_matches
            total_grant_matches += grant_matches
            
            if query_matches > 0 and grant_matches > 0:
                cluster_score = (query_matches * grant_matches) / len(terms)
                # Boost score for data-type relevant clusters
                if ((data_type in ['awards', 'award'] and cluster_name == 'historical') or
                    (data_type in ['solicitations', 'solicitation'] and cluster_name == 'opportunity') or
                    (data_type in ['companies', 'company'] and cluster_name == 'business')):
                    cluster_score *= 2.0
                score += cluster_score * 3.0
        
        # CRITICAL: Only return semantic score if query is actually biotools-related
        # If query has no biotools terms, return 0
        if total_query_matches == 0:
            return 0.0
        
        return score
    
    def _calculate_keyword_score(self, query: str, grant: Dict[str, Any]) -> float:
        """Calculate score based on exact keyword matches - BULLETPROOF VERSION"""
        if not query or not query.strip():
            return 0.0
            
        score = 0.0
        query_lower = query.lower().strip()
        query_words = [w.strip() for w in query_lower.split() if len(w.strip()) > 3]  # Only words > 3 chars
        
        if not query_words:
            return 0.0
        
        matches_found = False
        
        # Title matching (highest weight)
        if grant.get('title'):
            title_lower = grant['title'].lower()
            
            # Exact phrase match
            if query_lower in title_lower:
                score += 20.0
                matches_found = True
            
            # Individual word matches (must be whole words)
            for word in query_words:
                # Use word boundaries to avoid partial matches
                import re
                if re.search(r'\b' + re.escape(word) + r'\b', title_lower):
                    score += 10.0
                    matches_found = True
        
        # Keywords matching (high weight)  
        if grant.get('keywords'):
            keywords_text = grant['keywords'].lower()
            
            # Exact phrase match in keywords
            if query_lower in keywords_text:
                score += 8.0
                matches_found = True
            
            # Individual word matches in keywords
            for word in query_words:
                import re
                if re.search(r'\b' + re.escape(word) + r'\b', keywords_text):
                    score += 4.0
                    matches_found = True
        
        # Description matching (medium weight)
        if grant.get('description'):
            desc_lower = grant['description'].lower()
            
            # Exact phrase match
            if query_lower in desc_lower:
                score += 6.0
                matches_found = True
            
            # Individual word matches
            for word in query_words:
                import re
                if re.search(r'\b' + re.escape(word) + r'\b', desc_lower):
                    score += 2.0
                    matches_found = True
        
        # Company name matching
        if grant.get('company_name'):
            company_lower = grant['company_name'].lower()
            
            # Exact phrase match
            if query_lower in company_lower:
                score += 12.0
                matches_found = True
            
            # Individual word matches
            for word in query_words:
                import re
                if re.search(r'\b' + re.escape(word) + r'\b', company_lower):
                    score += 6.0
                    matches_found = True
        
        # ONLY award agency bonus if actual content matches were found
        if matches_found and grant.get('agency'):
            biotools_agencies = ['nih', 'nsf', 'sbir', 'cdc', 'darpa', 'nist', 'hhs']
            agency_lower = grant['agency'].lower()
            for bio_agency in biotools_agencies:
                if bio_agency in agency_lower:
                    score += 2.0
                    break
        
        return score if matches_found else 0.0
    
    def _calculate_freshness_score(self, grant: Dict[str, Any]) -> float:
        """Calculate score based on grant freshness - only for records that already have content matches"""
        # Freshness should only boost already relevant results, not create relevance
        # This will be applied only to records that pass other scoring thresholds
        try:
            # For solicitations, check close_date for urgency
            if grant.get('close_date'):
                close_date = datetime.fromisoformat(grant['close_date'].replace('Z', '+00:00'))
                days_until_close = (close_date - datetime.now()).days
                
                if days_until_close < 0:
                    return 0.0  # Closed
                elif days_until_close <= 30:
                    return 3.0  # Very urgent - reduced from 8.0
                elif days_until_close <= 90:
                    return 2.0  # Urgent - reduced from 6.0  
                else:
                    return 1.0  # Future opportunity - reduced from 4.0
            
            # For awards and general records, minimal freshness boost
            if grant.get('updated_at'):
                updated = datetime.fromisoformat(grant['updated_at'].replace('Z', '+00:00'))
                days_old = (datetime.now() - updated).days
                
                if days_old < 7:
                    return 1.0  # Reduced from 5.0
                elif days_old < 30:
                    return 0.8  # Reduced from 4.0
                elif days_old < 90:
                    return 0.6  # Reduced from 3.0
                elif days_old < 180:
                    return 0.4  # Reduced from 2.0
                else:
                    return 0.2  # Reduced from 1.0
        except Exception as e:
            logger.error(f"Error calculating freshness score: {e}")
        
        return 0.2  # Minimal baseline - reduced from 1.0
    
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
                    grant_amount = grant.get('amount_max') or grant.get('award_amount') or 0
                    if grant_amount < min_amount:
                        continue
                except (ValueError, TypeError):
                    pass
            
            if filters.get('amount_max'):
                try:
                    max_amount = float(filters['amount_max'])
                    grant_amount = grant.get('amount_min') or grant.get('award_amount') or 0
                    if grant_amount > max_amount:
                        continue
                except (ValueError, TypeError):
                    pass
            
            # Phase filter (SBIR/STTR)
            if filters.get('phase') and grant.get('phase'):
                if filters['phase'].upper() not in grant['phase'].upper():
                    continue
            
            # Deadline filter
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
            
            # Additional keywords filter
            if filters.get('keywords'):
                additional_keywords = [k.strip().lower() for k in filters['keywords'].split(',')]
                grant_text = f"{grant.get('title', '')} {grant.get('description', '')} {grant.get('keywords', '')}".lower()
                if not any(keyword in grant_text for keyword in additional_keywords):
                    continue
            
            # Data type filter
            if filters.get('data_type') and filters['data_type'] != 'all':
                data_type_filter = filters['data_type']
                if data_type_filter == 'awards':
                    record_type = self._determine_data_type(grant)
                    if record_type != 'award':
                        continue
                elif data_type_filter == 'solicitations':
                    record_type = self._determine_data_type(grant)
                    if record_type != 'solicitation':
                        continue
                elif data_type_filter == 'companies':
                    # For companies, only include awards with company names
                    if not grant.get('company_name'):
                        continue
            
            filtered_grants.append(grant)
        
        return filtered_grants
    
    def _simple_search(self, query: str, limit: int = 20, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Simple fallback search that always works"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            query_pattern = f'%{query.lower()}%'
            
            # Build WHERE clause for data type filtering
            where_conditions = [
                "(LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR LOWER(keywords) LIKE ?)"
            ]
            params = [query_pattern, query_pattern, query_pattern]
            
            # Add data type filtering to SQL if specified
            if filters and filters.get('data_type') and filters['data_type'] != 'all':
                data_type = filters['data_type']
                if data_type == 'solicitations':
                    where_conditions.append(
                        "(grant_type = 'solicitation' OR solicitation_number IS NOT NULL OR current_status IN ('open', 'active'))"
                    )
                elif data_type == 'companies':
                    # For companies, we want awards that have company names (SBIR awards to companies)
                    where_conditions.append("company_name IS NOT NULL AND company_name != ''")
                # For 'awards' or default, no additional filter needed since most records are awards
            
            sql = f"""
                SELECT *, 
                       CASE 
                           WHEN LOWER(title) LIKE ? THEN 15
                           WHEN LOWER(keywords) LIKE ? THEN 10
                           WHEN LOWER(description) LIKE ? THEN 7
                           ELSE 0
                       END as relevance_score
                FROM grants 
                WHERE ({' AND '.join(where_conditions)})
                AND (LOWER(title) LIKE ? OR LOWER(keywords) LIKE ? OR LOWER(description) LIKE ?)
                ORDER BY relevance_score DESC, title
                LIMIT ?
            """
            
            # Only add the LIKE patterns to the final WHERE clause, not to the calculation
            all_params = params + [query_pattern, query_pattern, query_pattern, query_pattern, query_pattern, query_pattern, limit]
            cursor.execute(sql, all_params)
            
            results = [dict(row) for row in cursor.fetchall()]
            
            # Apply additional filters if provided
            if filters:
                results = self._apply_filters(results, filters)
            
            return results
            
        finally:
            conn.close()
    
    def search_grants(self, query: str, limit: int = 20, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Enhanced search with data type support and fallback"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            query_terms = self._extract_terms(query.lower())
            
            if not query_terms:
                return self._simple_search(query, limit, filters)
            
            # Get data type filter
            data_type = 'all'
            if filters and filters.get('data_type'):
                data_type = filters['data_type']
            
            cursor.execute("SELECT * FROM grants")
            all_grants = cursor.fetchall()
            
            if not all_grants:
                return []
            
            scored_grants = []
            
            for row in all_grants:
                grant = dict(row)
                
                # Apply data type filter early if specified
                if data_type != 'all':
                    if data_type == 'awards':
                        record_type = self._determine_data_type(grant)
                        if record_type != 'award':
                            continue
                    elif data_type == 'solicitations':
                        record_type = self._determine_data_type(grant)
                        if record_type != 'solicitation':
                            continue
                    elif data_type == 'companies':
                        # For companies, only include awards that have company names
                        if not grant.get('company_name'):
                            continue
                        # Add company display metadata
                        grant['display_type'] = 'company'
                
                combined_text = f"{grant.get('title', '')} {grant.get('description', '')} {grant.get('keywords', '')}"
                
                # CRITICAL: Pre-filter - only score records that might be relevant
                query_lower = query.lower()
                text_lower = combined_text.lower()
                
                # Quick relevance check - must contain at least one query word
                has_basic_match = False
                for word in query_terms:
                    if word in text_lower:
                        has_basic_match = True
                        break
                
                # Skip records with no basic word matches
                if not has_basic_match:
                    continue
                
                tf_idf_score = self._calculate_tf_idf_score(query_terms, combined_text)
                semantic_score = self._calculate_semantic_score(query, grant, data_type)
                keyword_score = self._calculate_keyword_score(query, grant)
                freshness_score = self._calculate_freshness_score(grant)
                
                # CRITICAL: All content scores must be > 0 for any final score
                content_score = tf_idf_score + semantic_score + keyword_score
                if content_score <= 0:
                    continue
                
                # Adjust weights based on data type
                if data_type in ['solicitations', 'solicitation']:
                    # For solicitations, prioritize freshness (deadlines) and keywords
                    final_score = (
                        tf_idf_score * 0.20 +
                        semantic_score * 0.30 +
                        keyword_score * 0.30 +
                        freshness_score * 0.20
                    )
                elif data_type in ['companies', 'company']:
                    # For companies, prioritize keywords and semantic matching
                    final_score = (
                        tf_idf_score * 0.25 +
                        semantic_score * 0.40 +
                        keyword_score * 0.30 +
                        freshness_score * 0.05
                    )
                else:
                    # Default weights for awards and mixed searches
                    final_score = (
                        tf_idf_score * 0.25 +
                        semantic_score * 0.35 +
                        keyword_score * 0.30 +
                        freshness_score * 0.10
                    )
                
                # Lower threshold for better recall - INCREASED TO FIX RELEVANCE
                if final_score > 2.0:  # Increased from 0.5 to 2.0 for better filtering
                    grant['relevance_score'] = round(final_score, 2)
                    # Add inferred data type for frontend
                    grant['inferred_type'] = self._determine_data_type(grant)
                    scored_grants.append(grant)
            
            if not scored_grants:
                logger.info(f"Enhanced search found no results for '{query}' in {data_type}, using simple search")
                simple_results = self._simple_search(query, limit, filters)
                if simple_results:
                    return simple_results
                else:
                    logger.warning(f"No results found for '{query}' in any search method")
                    return []
            
            # Apply additional filters
            if filters:
                scored_grants = self._apply_filters(scored_grants, filters)
            
            scored_grants.sort(key=lambda x: x['relevance_score'], reverse=True)
            return scored_grants[:limit]
            
        except Exception as e:
            logger.error(f"Enhanced search error for '{query}': {e}")
            return self._simple_search(query, limit, filters)
        finally:
            conn.close()
    
    def get_grant_by_id(self, grant_id: int) -> Optional[Dict[str, Any]]:
        """Get specific grant by ID with type inference"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM grants WHERE id = ?", (grant_id,))
            result = cursor.fetchone()
            if result:
                grant = dict(result)
                grant['inferred_type'] = self._determine_data_type(grant)
                return grant
            return None
        except Exception as e:
            logger.error(f"Error getting grant {grant_id}: {e}")
            return None
        finally:
            conn.close()
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get enhanced database statistics with data type breakdown"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            stats = {}
            
            # Total counts
            cursor.execute("SELECT COUNT(*) FROM grants")
            total_grants = cursor.fetchone()[0]
            stats['total_grants'] = total_grants
            
            # Count by grant_type field and infer companies from awards
            cursor.execute("SELECT grant_type, COUNT(*) FROM grants WHERE grant_type IS NOT NULL GROUP BY grant_type")
            type_counts_raw = cursor.fetchall()
            type_counts = {'award': 0, 'solicitation': 0}
            
            for gtype, count in type_counts_raw:
                if gtype in type_counts:
                    type_counts[gtype] = count
            
            # Count companies as awards with company names (since SBIR awards go to companies)
            cursor.execute("SELECT COUNT(*) FROM grants WHERE company_name IS NOT NULL AND company_name != ''")
            companies_count = cursor.fetchone()[0]
            
            stats['awards_count'] = type_counts['award']
            stats['solicitations_count'] = type_counts['solicitation'] 
            stats['companies_count'] = companies_count
            
            # Recent updates
            try:
                cursor.execute("SELECT COUNT(*) FROM grants WHERE updated_at > date('now', '-30 days')")
                stats['recent_grants'] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                stats['recent_grants'] = 0
            
            # Agency breakdown
            cursor.execute("SELECT agency, COUNT(*) FROM grants GROUP BY agency ORDER BY COUNT(*) DESC LIMIT 10")
            agencies = cursor.fetchall()
            stats['agencies'] = [{'name': agency[0] or 'Unknown', 'count': agency[1]} for agency in agencies]
            
            # Open solicitations (active ones)
            try:
                # First check total solicitations
                cursor.execute("SELECT COUNT(*) FROM grants WHERE grant_type = 'solicitation'")
                total_solicitations = cursor.fetchone()[0]
                
                # Then check open ones
                cursor.execute("""
                    SELECT COUNT(*) FROM grants 
                    WHERE grant_type = 'solicitation'
                    AND (close_date IS NULL OR close_date > date('now'))
                """)
                open_solicitations = cursor.fetchone()[0]
                
                stats['total_solicitations'] = total_solicitations
                stats['open_solicitations'] = open_solicitations
                
                # Use total solicitations for the main count, not just open ones
                stats['solicitations_count'] = total_solicitations
                
            except sqlite3.OperationalError:
                stats['total_solicitations'] = 0
                stats['open_solicitations'] = 0
                stats['solicitations_count'] = 0
            
            stats['last_updated'] = datetime.now().isoformat()
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {
                'total_grants': 0,
                'awards_count': 0,
                'solicitations_count': 0,
                'companies_count': 0,
                'recent_grants': 0,
                'open_solicitations': 0,
                'agencies': [],
                'last_updated': datetime.now().isoformat()
            }
        finally:
            conn.close()


def validate_input(data, required_fields, max_lengths=None):
    """Validate and sanitize input data"""
    if not isinstance(data, dict):
        raise ValueError("Invalid input format")
    
    for field in required_fields:
        if field not in data or not data[field]:
            raise ValueError(f"Missing required field: {field}")
    
    sanitized_data = {}
    for key, value in data.items():
        if isinstance(value, str):
            value = re.sub(r'[<>"\'\x00-\x1f\x7f-\x9f]', '', value)
            value = value.strip()
            
            if max_lengths and key in max_lengths:
                if len(value) > max_lengths[key]:
                    raise ValueError(f"Field {key} exceeds maximum length of {max_lengths[key]}")
            
            sanitized_data[key] = value
        elif isinstance(value, (int, float)):
            sanitized_data[key] = value
        elif isinstance(value, dict):
            sanitized_data[key] = validate_input(value, [], max_lengths)
        else:
            sanitized_data[key] = value
    
    return sanitized_data


def log_request(request_type, query=None, client_ip=None, results_count=0, data_type='all'):
    """Log search requests for analytics with data type tracking"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                data_type TEXT DEFAULT 'all',
                results_count INTEGER DEFAULT 0,
                user_session TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT
            )
        """)
        
        cursor.execute("""
            INSERT INTO search_history (query, data_type, results_count, user_session, ip_address)
            VALUES (?, ?, ?, ?, ?)
        """, (query or '', data_type, results_count, '', client_ip or get_remote_address()))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to log request: {e}")


# Initialize grant matcher
grant_matcher = EnhancedGrantMatcher()


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
    """Serve the main application page"""
    return render_template('index.html')


@app.route('/<int:grant_id>')
def grant_detail_page(grant_id):
    """Serve grant detail page"""
    return render_template('index.html')


@app.route('/api/search', methods=['POST'])
@limiter.limit("50 per hour;5 per minute")
def search_grants():
    """Enhanced search for grants with data type support"""
    client_ip = get_remote_address()
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        sanitized_data = validate_input(
            data, 
            required_fields=['query'],
            max_lengths={'query': 200, 'keywords': 100}
        )
        
        query = sanitized_data['query']
        limit = min(sanitized_data.get('limit', 20), 50)
        filters = sanitized_data.get('filters', {})
        
        if len(query.strip()) < 2:
            return jsonify({'error': 'Query too short (minimum 2 characters)'}), 400
        
        suspicious_patterns = ['union', 'select', 'drop', 'delete', 'insert', '--', '/*', '*/', ';']
        query_lower = query.lower()
        if any(pattern in query_lower for pattern in suspicious_patterns):
            logger.warning(f"Suspicious query detected from {client_ip}: {query}")
            return jsonify({'error': 'Invalid query format'}), 400
        
        # Extract data type for logging
        data_type = filters.get('data_type', 'all')
        
        grants = grant_matcher.search_grants(query, limit, filters)
        
        log_request('search', query, client_ip, len(grants), data_type)
        
        if DIGITALOCEAN_AGENT_API_KEY and DIGITALOCEAN_AGENT_URL and grants:
            enhanced_grants = enhance_with_agent(query, grants)
            grants = enhanced_grants if enhanced_grants else grants
        
        logger.info(f"Search completed: query='{query}', type={data_type}, results={len(grants)}, ip={client_ip}")
        
        return jsonify({
            'query': query,
            'data_type': data_type,
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
        if grant_id <= 0:
            return jsonify({'error': 'Invalid grant ID'}), 400
        
        grant = grant_matcher.get_grant_by_id(grant_id)
        
        if not grant:
            logger.info(f"Grant not found: id={grant_id}, ip={client_ip}")
            return jsonify({'error': 'Grant not found'}), 404
        
        logger.info(f"Grant details accessed: id={grant_id}, type={grant.get('inferred_type', 'unknown')}, ip={client_ip}")
        return jsonify(grant)
        
    except Exception as e:
        logger.error(f"Grant details error: id={grant_id}, ip={client_ip}, error={e}")
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/api/stats', methods=['GET'])
@limiter.limit("60 per hour;10 per minute")  # Increased from 20 per hour;2 per minute
def get_stats():
    """Get enhanced database statistics with data type breakdown"""
    try:
        stats = grant_matcher.get_database_stats()
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return jsonify({
            'error': 'Internal server error',
            'total_grants': 0,
            'awards_count': 0,
            'solicitations_count': 0,
            'companies_count': 0,
            'recent_grants': 0,
            'open_solicitations': 0,
            'agencies': [],
            'last_updated': datetime.now().isoformat()
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
        
        sanitized_data = validate_input(
            data,
            required_fields=['grant_id', 'feedback_type'],
            max_lengths={'notes': 500, 'search_query': 200}
        )
        
        valid_types = ['helpful', 'not_helpful', 'applied', 'bookmarked']
        if sanitized_data['feedback_type'] not in valid_types:
            return jsonify({'error': 'Invalid feedback type'}), 400
        
        grant_id = sanitized_data['grant_id']
        if not isinstance(grant_id, int) or grant_id <= 0:
            return jsonify({'error': 'Invalid grant ID'}), 400
        
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
        logger.info("Enhanced Grant Matcher with Data Type Support initialized successfully!")
        logger.info(f"IDF cache contains {len(grant_matcher.idf_cache)} terms")
        
        # Log initial stats
        stats = grant_matcher.get_database_stats()
        logger.info(f"Database contains: {stats['awards_count']} awards, {stats['solicitations_count']} solicitations, {stats['companies_count']} companies")
    
    app.run(debug=False, host='0.0.0.0', port=5000)