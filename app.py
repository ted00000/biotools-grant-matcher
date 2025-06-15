#!/usr/bin/env python3
"""
Flask API Backend for Grant Matching Service
Handles grant search requests and interfaces with DigitalOcean agents
"""

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3
import json
import re
from datetime import datetime
import requests
import os
from typing import List, Dict, Any

app = Flask(__name__)
CORS(app)

# Configuration
DATABASE_PATH = "data/grants.db"
DIGITALOCEAN_AGENT_API_KEY = os.getenv('DO_AGENT_API_KEY', '')
DIGITALOCEAN_AGENT_URL = os.getenv('DO_AGENT_URL', '')

class GrantMatcher:
    def __init__(self, db_path=DATABASE_PATH):
        self.db_path = db_path
    
    def search_grants(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search grants based on query string"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # This allows column access by name
        cursor = conn.cursor()
        
        # Simple keyword search across title, description, and keywords
        search_terms = query.lower().split()
        
        # Build dynamic SQL query for keyword matching
        sql_conditions = []
        params = []
        
        for term in search_terms:
            condition = "(LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR LOWER(keywords) LIKE ?)"
            sql_conditions.append(condition)
            params.extend([f"%{term}%", f"%{term}%", f"%{term}%"])
        
        if sql_conditions:
            where_clause = " AND ".join(sql_conditions)
            sql = f"""
                SELECT * FROM grants 
                WHERE {where_clause}
                ORDER BY updated_at DESC 
                LIMIT ?
            """
            params.append(limit)
        else:
            sql = "SELECT * FROM grants ORDER BY updated_at DESC LIMIT ?"
            params = [limit]
        
        cursor.execute(sql, params)
        results = cursor.fetchall()
        conn.close()
        
        # Convert to list of dictionaries
        grants = []
        for row in results:
            grant = dict(row)
            # Calculate relevance score (simple implementation)
            grant['relevance_score'] = self.calculate_relevance(query, grant)
            grants.append(grant)
        
        # Sort by relevance score
        grants.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return grants
    
    def calculate_relevance(self, query: str, grant: Dict[str, Any]) -> float:
        """Calculate relevance score for a grant based on query"""
        score = 0.0
        query_lower = query.lower()
        
        # Title matches get highest score
        if grant['title'] and query_lower in grant['title'].lower():
            score += 10.0
        
        # Keyword matches get medium score
        if grant['keywords']:
            keywords_lower = grant['keywords'].lower()
            for word in query_lower.split():
                if word in keywords_lower:
                    score += 5.0
        
        # Description matches get lower score
        if grant['description'] and query_lower in grant['description'].lower():
            score += 2.0
        
        # Recent grants get slight boost
        if grant['updated_at']:
            try:
                updated = datetime.fromisoformat(grant['updated_at'].replace('Z', '+00:00'))
                days_old = (datetime.now() - updated).days
                if days_old < 30:
                    score += 1.0
            except:
                pass
        
        return score
    
    def get_grant_by_id(self, grant_id: int) -> Dict[str, Any]:
        """Get specific grant by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM grants WHERE id = ?", (grant_id,))
        result = cursor.fetchone()
        conn.close()
        
        return dict(result) if result else None

# Initialize grant matcher
grant_matcher = GrantMatcher()

@app.route('/')
def index():
    """Serve the main application page"""
    return render_template('index.html')

@app.route('/api/search', methods=['POST'])
def search_grants():
    """Search for grants based on research query"""
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        limit = data.get('limit', 20)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Search grants
        grants = grant_matcher.search_grants(query, limit)
        
        # Use DigitalOcean agent to enhance results (if configured)
        if DIGITALOCEAN_AGENT_API_KEY and DIGITALOCEAN_AGENT_URL:
            enhanced_grants = enhance_with_agent(query, grants)
            grants = enhanced_grants if enhanced_grants else grants
        
        return jsonify({
            'query': query,
            'results': grants,
            'total_found': len(grants),
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
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
        
        cursor.execute("SELECT agency, COUNT(*) FROM grants GROUP BY agency ORDER BY COUNT(*) DESC")
        agencies = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            'total_grants': total_grants,
            'recent_grants': recent_grants,
            'agencies': [{'name': agency[0], 'count': agency[1]} for agency in agencies],
            'last_updated': datetime.now().isoformat()
        })
        
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

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    """Submit user feedback on grant recommendations"""
    try:
        data = request.get_json()
        # For MVP, just log feedback - later integrate with agent learning
        print(f"Feedback received: {data}")
        
        return jsonify({'status': 'success', 'message': 'Feedback recorded'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
    
    # Run Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)