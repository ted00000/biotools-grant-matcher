#!/usr/bin/env python3
"""
Enhanced BioTools Scraper with Advanced TABA Detection and Tracking - FIXED
Identifies TABA funding in SBIR/STTR awards and tracks amounts/status
"""

# ... [Previous imports remain the same] ...
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
    """Enhanced grant matcher with comprehensive TABA tracking and contact information"""
    
    def __init__(self, db_path="data/grants.db"):
        self.db_path = db_path
        
        # ... [Previous initialization code remains the same] ...
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
        
        # ... [Previous TABA keywords and agency definitions remain the same] ...
        
        self.init_enhanced_database()
        self.company_cache = {}
    
    # ... [Previous methods remain the same until save_enhanced_awards_with_taba] ...
    
    def save_enhanced_awards_with_taba(self, awards: List[Dict]) -> int:
        """Save enhanced awards with comprehensive TABA detection and tracking - FIXED"""
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
                    
                    # FIXED: Insert with all 49 columns including the missing ones
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
                                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    # ... [All other methods remain the same] ...

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
        
        # ... [Rest of the TABA detection logic remains the same] ...
        
        return has_taba, taba_amount, taba_type, matched_keywords, confidence_score

    # ... [All other methods remain exactly the same] ...

# ... [Rest of the file remains the same] ...

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