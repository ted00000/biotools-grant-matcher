#!/usr/bin/env python3
"""
Comprehensive Life Science Tools and Technology Scraper
Searches for the full spectrum of biotools/life science tools
"""

import requests
import sqlite3
from datetime import datetime
import time
import os

class ComprehensiveBiotoolsScraper:
    def __init__(self, db_path="data/grants.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.setup_database()
        
        # Comprehensive life science tool categories
        self.biotools_categories = {
            'instrumentation': [
                'microscopy', 'spectrometry', 'mass spectrometer', 'flow cytometer', 
                'DNA sequencer', 'protein analyzer', 'cell counter', 'plate reader',
                'fluorescence imaging', 'confocal microscope', 'electron microscope'
            ],
            'laboratory_equipment': [
                'centrifuge', 'incubator', 'thermal cycler', 'PCR machine', 
                'electrophoresis', 'chromatography', 'liquid handler', 'pipette',
                'biosafety cabinet', 'autoclave', 'pH meter', 'balance'
            ],
            'molecular_biology': [
                'PCR', 'qPCR', 'DNA extraction', 'RNA extraction', 'protein purification',
                'gel electrophoresis', 'western blot', 'ELISA', 'immunoassay',
                'cloning', 'transfection', 'cell culture', 'tissue culture'
            ],
            'analytical_tools': [
                'HPLC', 'LCMS', 'NMR', 'X-ray crystallography', 'surface plasmon resonance',
                'dynamic light scattering', 'circular dichroism', 'UV-Vis spectroscopy',
                'infrared spectroscopy', 'atomic force microscopy'
            ],
            'genomics': [
                'genome sequencing', 'RNA sequencing', 'ChIP-seq', 'CRISPR', 
                'gene editing', 'SNP analysis', 'microarray', 'genotyping',
                'next generation sequencing', 'single cell sequencing'
            ],
            'proteomics': [
                'protein analysis', 'mass spectrometry proteomics', 'protein folding',
                'protein interaction', 'enzyme assay', 'protein crystallization',
                'peptide synthesis', 'amino acid analysis'
            ],
            'cell_biology': [
                'cell imaging', 'live cell imaging', 'cell sorting', 'cell counting',
                'cell viability', 'apoptosis assay', 'cell cycle analysis',
                'calcium imaging', 'patch clamp', 'electrophysiology'
            ],
            'bioinformatics': [
                'sequence analysis', 'phylogenetic analysis', 'molecular modeling',
                'protein structure prediction', 'drug discovery software',
                'database management', 'statistical analysis', 'data mining'
            ],
            'automation': [
                'laboratory automation', 'robotic liquid handling', 'automated imaging',
                'high throughput screening', 'laboratory information management',
                'workflow automation', 'sample tracking'
            ],
            'diagnostics': [
                'point of care testing', 'immunodiagnostics', 'molecular diagnostics',
                'biosensor', 'biomarker discovery', 'clinical chemistry analyzer',
                'rapid testing', 'multiplex assay'
            ]
        }
    
    def setup_database(self):
        """Create database tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS grants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                funding_opportunity_number TEXT UNIQUE,
                title TEXT NOT NULL,
                agency TEXT,
                deadline DATE,
                amount_min INTEGER,
                amount_max INTEGER,
                description TEXT,
                keywords TEXT,
                eligibility TEXT,
                url TEXT,
                biotools_category TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def get_search_terms(self):
        """Generate comprehensive search terms for life science tools"""
        # Primary broad terms
        primary_terms = [
            'laboratory instrumentation', 'research instrumentation', 
            'analytical instrumentation', 'life science tools',
            'biotechnology tools', 'research equipment',
            'scientific instrumentation', 'laboratory technology'
        ]
        
        # Category-specific terms
        category_terms = []
        for category, terms in self.biotools_categories.items():
            category_terms.extend(terms[:5])  # Top 5 terms per category
        
        # Combine and return unique terms
        all_terms = primary_terms + category_terms
        return list(set(all_terms))
    
    def fetch_nsf_grants(self):
        """Fetch NSF grants with comprehensive biotools search"""
        print("🔬 Fetching NSF grants for life science tools...")
        
        grants = []
        search_terms = self.get_search_terms()
        
        print(f"  Using {len(search_terms)} search terms covering:")
        for category in self.biotools_categories.keys():
            print(f"    • {category.replace('_', ' ').title()}")
        
        # Search in batches to avoid overwhelming the API
        for i, term in enumerate(search_terms[:20]):  # Limit to avoid too many requests
            try:
                url = "https://api.nsf.gov/services/v1/awards.json"
                params = {
                    'keyword': term,
                    'rpp': '15',  # Fewer per term, but more terms
                    'printFields': 'id,title,fundsObligatedAmt,abstractText,awardee,program'
                }
                
                print(f"  [{i+1:2d}/{len(search_terms[:20])}] Searching: '{term}'...")
                response = requests.get(url, params=params, timeout=20)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    awards = []
                    if isinstance(data, dict) and 'response' in data:
                        response_data = data['response']
                        if isinstance(response_data, dict) and 'award' in response_data:
                            awards_data = response_data['award']
                            if isinstance(awards_data, list):
                                awards = awards_data
                            elif isinstance(awards_data, dict):
                                awards = [awards_data]
                    
                    relevant_count = 0
                    for award in awards:
                        if isinstance(award, dict):
                            title = award.get('title', '')
                            abstract = award.get('abstractText', '')
                            
                            if self.is_biotools_relevant(title, abstract):
                                category = self.categorize_biotools(title + ' ' + abstract)
                                grant = self.parse_nsf_award(award, category)
                                if grant:
                                    grants.append(grant)
                                    relevant_count += 1
                    
                    print(f"      Found {relevant_count} relevant grants")
                
                else:
                    print(f"      API error: {response.status_code}")
                
                time.sleep(1.5)  # Rate limiting
                
            except Exception as e:
                print(f"      Error: {e}")
                continue
        
        print(f"✅ Collected {len(grants)} NSF life science tool grants")
        return grants
    
    def fetch_nih_grants(self):
        """Fetch NIH grants with comprehensive biotools search"""
        print("🧬 Fetching NIH grants for life science tools...")
        
        grants = []
        
        # NIH search with broader life science tool terms
        search_queries = [
            "laboratory instrumentation OR research instrumentation OR analytical instrumentation",
            "microscopy OR spectrometry OR chromatography OR electrophoresis",
            "PCR OR sequencing OR protein analysis OR cell analysis",
            "bioengineering OR biotechnology OR life science technology",
            "laboratory automation OR high throughput screening OR robotics",
            "bioinformatics OR computational biology OR data analysis tools"
        ]
        
        for i, search_text in enumerate(search_queries):
            try:
                url = "https://api.reporter.nih.gov/v2/projects/search"
                
                payload = {
                    "criteria": {
                        "advanced_text_search": {
                            "operator": "and",
                            "search_field": "projecttitle,terms,abstracttext",
                            "search_text": search_text
                        },
                        "fiscal_years": [2022, 2023, 2024, 2025]
                    },
                    "include_fields": [
                        "ProjectTitle", "AbstractText", "AgencyCode", 
                        "TotalCostAmount", "Organization", "ApplId", "Terms"
                    ],
                    "limit": 50
                }
                
                print(f"  [{i+1}/{len(search_queries)}] NIH search: {search_text[:50]}...")
                response = requests.post(url, json=payload, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if 'results' in data:
                        projects = data['results']
                        relevant_count = 0
                        
                        for project in projects:
                            title = project.get('project_title', '')
                            abstract = project.get('abstract_text', '')
                            
                            if self.is_biotools_relevant(title, abstract):
                                category = self.categorize_biotools(title + ' ' + abstract)
                                grant = self.parse_nih_project(project, category)
                                if grant:
                                    grants.append(grant)
                                    relevant_count += 1
                        
                        print(f"      Found {relevant_count} relevant grants")
                    else:
                        print("      No results")
                        
                else:
                    print(f"      API error: {response.status_code}")
                
                time.sleep(2)  # Rate limiting
                
            except Exception as e:
                print(f"      Error: {e}")
                continue
        
        print(f"✅ Collected {len(grants)} NIH life science tool grants")
        return grants
    
    def is_biotools_relevant(self, title, abstract):
        """Enhanced relevance checking for life science tools"""
        text = (title + ' ' + abstract).lower()
        
        # Must contain at least one term from any category
        for category, terms in self.biotools_categories.items():
            if any(term.lower() in text for term in terms):
                return True
        
        # Additional broad life science tool indicators
        broad_indicators = [
            'laboratory', 'research tool', 'scientific instrument', 
            'analytical method', 'measurement technique', 'experimental method',
            'assay development', 'protocol development', 'technology development'
        ]
        
        return any(indicator in text for indicator in broad_indicators)
    
    def categorize_biotools(self, text):
        """Categorize the biotools grant by type"""
        text_lower = text.lower()
        
        # Score each category
        category_scores = {}
        for category, terms in self.biotools_categories.items():
            score = sum(1 for term in terms if term.lower() in text_lower)
            if score > 0:
                category_scores[category] = score
        
        # Return the highest scoring category
        if category_scores:
            return max(category_scores, key=category_scores.get)
        
        return 'general_life_science'
    
    def parse_nsf_award(self, award, category):
        """Parse NSF award with category information"""
        try:
            award_id = award.get('id', '')
            title = award.get('title', '')
            abstract = award.get('abstractText', '')
            
            amount = 0
            if 'fundsObligatedAmt' in award:
                try:
                    amount = int(float(str(award['fundsObligatedAmt'])))
                except (ValueError, TypeError):
                    amount = 0
            
            org = "Research Institution"
            if 'awardee' in award and isinstance(award['awardee'], dict):
                org_name = award['awardee'].get('name', '')
                if org_name:
                    org = org_name[:200]
            
            return {
                'funding_opportunity_number': f"NSF-{award_id}",
                'title': title[:250] if title else f"NSF Award {award_id}",
                'agency': 'NSF',
                'description': abstract[:1000] if abstract else 'NSF funded research project',
                'amount_min': 0,
                'amount_max': amount,
                'keywords': self.extract_keywords(title + ' ' + abstract),
                'eligibility': org,
                'url': f"https://www.nsf.gov/awardsearch/showAward?AWD_ID={award_id}",
                'biotools_category': category,
                'deadline': None
            }
            
        except Exception as e:
            print(f"    Parse error: {e}")
            return None
    
    def parse_nih_project(self, project, category):
        """Parse NIH project with category information"""
        try:
            appl_id = project.get('appl_id', '')
            title = project.get('project_title', '')
            abstract = project.get('abstract_text', '')
            
            amount = 0
            if 'total_cost_amount' in project:
                try:
                    amount = int(project['total_cost_amount'])
                except (ValueError, TypeError):
                    amount = 0
            
            org = "Research Institution"
            if 'organization' in project and isinstance(project['organization'], dict):
                org_name = project['organization'].get('org_name', '')
                if org_name:
                    org = org_name[:200]
            
            return {
                'funding_opportunity_number': f"NIH-{appl_id}",
                'title': title[:250] if title else f"NIH Project {appl_id}",
                'agency': 'NIH',
                'description': abstract[:1000] if abstract else 'NIH funded research project',
                'amount_min': 0,
                'amount_max': amount,
                'keywords': self.extract_keywords(title + ' ' + abstract),
                'eligibility': org,
                'url': f"https://reporter.nih.gov/project-details/{appl_id}",
                'biotools_category': category,
                'deadline': None
            }
            
        except Exception as e:
            print(f"    Parse error: {e}")
            return None
    
    def extract_keywords(self, text):
        """Extract life science tool keywords"""
        if not text:
            return ''
        
        # Comprehensive keyword list
        all_keywords = []
        for terms in self.biotools_categories.values():
            all_keywords.extend(terms)
        
        # Find matching keywords
        found = []
        text_lower = text.lower()
        for keyword in all_keywords:
            if keyword.lower() in text_lower and keyword not in found:
                found.append(keyword)
        
        return ', '.join(found[:10])  # Top 10 keywords
    
    def save_grants(self, grants, source_name):
        """Save grants to database with category information"""
        if not grants:
            print(f"⚠️ No {source_name} grants to save")
            return 0
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Add category column if it doesn't exist
        try:
            cursor.execute("ALTER TABLE grants ADD COLUMN biotools_category TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        saved_count = 0
        duplicate_count = 0
        current_time = datetime.now().isoformat()
        
        for grant in grants:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO grants 
                    (funding_opportunity_number, title, agency, description, 
                     amount_min, amount_max, keywords, eligibility, url, 
                     biotools_category, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    grant['funding_opportunity_number'],
                    grant['title'],
                    grant['agency'],
                    grant['description'],
                    grant['amount_min'],
                    grant['amount_max'],
                    grant['keywords'],
                    grant['eligibility'],
                    grant['url'],
                    grant['biotools_category'],
                    current_time
                ))
                
                if cursor.rowcount > 0:
                    saved_count += 1
                else:
                    duplicate_count += 1
                    
            except sqlite3.Error as e:
                print(f"Database error: {e}")
        
        conn.commit()
        conn.close()
        
        print(f"✅ Saved {saved_count} new {source_name} grants")
        if duplicate_count > 0:
            print(f"📝 Skipped {duplicate_count} {source_name} duplicates")
        
        return saved_count
    
    def get_stats(self):
        """Get comprehensive database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM grants")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT agency, COUNT(*) FROM grants GROUP BY agency ORDER BY COUNT(*) DESC")
        by_agency = cursor.fetchall()
        
        # Get category breakdown
        try:
            cursor.execute("SELECT biotools_category, COUNT(*) FROM grants WHERE biotools_category IS NOT NULL GROUP BY biotools_category ORDER BY COUNT(*) DESC")
            by_category = cursor.fetchall()
        except sqlite3.OperationalError:
            by_category = []
        
        conn.close()
        return total, by_agency, by_category
    
    def run_scraper(self):
        """Run comprehensive life science tools scraper"""
        print("🧬 Starting Comprehensive Life Science Tools Scraper")
        print("=" * 60)
        print("🎯 Searching for ALL types of biotools:")
        for category in self.biotools_categories.keys():
            print(f"   • {category.replace('_', ' ').title()}")
        print("=" * 60)
        
        before_total, _, _ = self.get_stats()
        print(f"📊 Current database: {before_total} grants")
        
        total_added = 0
        
        # Fetch NSF grants
        print("\n" + "="*40)
        try:
            nsf_grants = self.fetch_nsf_grants()
            total_added += self.save_grants(nsf_grants, "NSF")
        except Exception as e:
            print(f"❌ NSF scraping failed: {e}")
        
        # Fetch NIH grants
        print("\n" + "="*40)
        try:
            nih_grants = self.fetch_nih_grants()
            total_added += self.save_grants(nih_grants, "NIH")
        except Exception as e:
            print(f"❌ NIH scraping failed: {e}")
        
        # Final results
        print("\n" + "="*60)
        after_total, by_agency, by_category = self.get_stats()
        
        print(f"📈 Final database: {after_total} grants (+{after_total - before_total})")
        
        print("\n📊 Grants by agency:")
        for agency, count in by_agency:
            print(f"   {agency}: {count}")
        
        if by_category:
            print("\n🔬 Grants by biotools category:")
            for category, count in by_category:
                print(f"   {category.replace('_', ' ').title()}: {count}")
        
        print(f"\n✅ Added {total_added} new life science tool grants")
        
        return total_added

def main():
    scraper = ComprehensiveBiotoolsScraper()
    scraper.run_scraper()

if __name__ == "__main__":
    main()