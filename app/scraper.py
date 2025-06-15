#!/usr/bin/env python3
"""
Simplified NIH Grant Data Scraper with Sample Data
Creates a working database for testing the application
"""

import sqlite3
from datetime import datetime
import os

class SimpleGrantScraper:
    def __init__(self, db_path="data/grants.db"):
        self.db_path = db_path
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.setup_database()
    
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Database setup complete")
    
    def create_sample_data(self):
        """Create sample grant data for testing"""
        sample_grants = [
            {
                'funding_opportunity_number': 'R01-CA-25-001',
                'title': 'Novel Biomarker Discovery for Early Cancer Detection',
                'agency': 'NIH/NCI',
                'description': 'This program supports innovative research to identify and validate novel biomarkers for early detection of cancer. Projects should focus on developing diagnostic tools that can be translated to clinical practice. Special emphasis on liquid biopsies, circulating tumor DNA, and point-of-care devices.',
                'amount_min': 250000,
                'amount_max': 500000,
                'keywords': 'biomarker, cancer, diagnostic, liquid biopsy, circulating tumor DNA, point-of-care',
                'eligibility': 'Universities, medical centers, research institutions',
                'url': 'https://grants.nih.gov/grants/guide/rfa/CA-25-001.html'
            },
            {
                'funding_opportunity_number': 'R43-EB-25-002',
                'title': 'SBIR: Microfluidic Devices for Point-of-Care Diagnostics',
                'agency': 'NIH/NIBIB',
                'description': 'Small Business Innovation Research program supporting development of microfluidic technologies for point-of-care diagnostic applications. Focus on lab-on-chip devices, portable analyzers, and rapid diagnostic tests for infectious diseases and chronic conditions.',
                'amount_min': 150000,
                'amount_max': 300000,
                'keywords': 'microfluidics, point-of-care, lab-on-chip, diagnostic device, SBIR',
                'eligibility': 'Small businesses, startups',
                'url': 'https://grants.nih.gov/grants/guide/rfa/EB-25-002.html'
            },
            {
                'funding_opportunity_number': 'R01-AI-25-003',
                'title': 'AI-Powered Medical Imaging for Infectious Disease Diagnosis',
                'agency': 'NIH/NIAID',
                'description': 'Research program to develop artificial intelligence and machine learning approaches for medical imaging in infectious disease diagnosis. Projects should integrate AI algorithms with existing imaging modalities to improve diagnostic accuracy and speed.',
                'amount_min': 300000,
                'amount_max': 750000,
                'keywords': 'artificial intelligence, medical imaging, machine learning, infectious disease, AI',
                'eligibility': 'Universities, research hospitals',
                'url': 'https://grants.nih.gov/grants/guide/rfa/AI-25-003.html'
            },
            {
                'funding_opportunity_number': 'R21-HG-25-004',
                'title': 'Next-Generation Genomic Sequencing Tools',
                'agency': 'NIH/NHGRI',
                'description': 'Exploratory research program for developing innovative genomic sequencing technologies. Focus on portable sequencers, single-cell analysis tools, and real-time genomic analysis platforms. Applications should demonstrate potential for clinical translation.',
                'amount_min': 200000,
                'amount_max': 400000,
                'keywords': 'genomic sequencing, DNA sequencing, single-cell, portable sequencer, genomics',
                'eligibility': 'Academic institutions, biotechnology companies',
                'url': 'https://grants.nih.gov/grants/guide/rfa/HG-25-004.html'
            },
            {
                'funding_opportunity_number': 'R44-MD-25-005',
                'title': 'STTR: Wearable Health Monitoring Devices',
                'agency': 'NIH/NIMHD',
                'description': 'Small Business Technology Transfer program supporting development of wearable devices for continuous health monitoring. Emphasis on devices that can detect early signs of disease, monitor chronic conditions, and provide real-time health data to patients and providers.',
                'amount_min': 500000,
                'amount_max': 1000000,
                'keywords': 'wearable device, health monitoring, biosensor, continuous monitoring, STTR',
                'eligibility': 'Small businesses with academic partnerships',
                'url': 'https://grants.nih.gov/grants/guide/rfa/MD-25-005.html'
            },
            {
                'funding_opportunity_number': 'R01-GM-25-006',
                'title': 'Automated Laboratory Instrumentation for Drug Discovery',
                'agency': 'NIH/NIGMS',
                'description': 'Program supporting development of automated laboratory systems for high-throughput drug discovery and screening. Projects should focus on robotics, automated sample handling, and integrated analysis platforms that can accelerate pharmaceutical research.',
                'amount_min': 400000,
                'amount_max': 800000,
                'keywords': 'laboratory automation, drug discovery, high-throughput screening, robotics, pharmaceutical',
                'eligibility': 'Universities, pharmaceutical companies, research institutes',
                'url': 'https://grants.nih.gov/grants/guide/rfa/GM-25-006.html'
            },
            {
                'funding_opportunity_number': 'R21-NS-25-007',
                'title': 'Brain-Computer Interface Technologies',
                'agency': 'NIH/NINDS',
                'description': 'Exploratory research for developing brain-computer interface technologies for neurological applications. Focus on neural prosthetics, brain stimulation devices, and neurofeedback systems. Projects should address both technical development and clinical translation.',
                'amount_min': 300000,
                'amount_max': 600000,
                'keywords': 'brain-computer interface, neural prosthetics, neurotechnology, brain stimulation',
                'eligibility': 'Research universities, medical centers',
                'url': 'https://grants.nih.gov/grants/guide/rfa/NS-25-007.html'
            },
            {
                'funding_opportunity_number': 'R01-DK-25-008',
                'title': 'Biosensors for Diabetes Management',
                'agency': 'NIH/NIDDK',
                'description': 'Research program for developing advanced biosensor technologies for diabetes monitoring and management. Focus on continuous glucose monitors, insulin delivery systems, and integrated diabetes management platforms. Emphasis on improving patient outcomes and quality of life.',
                'amount_min': 350000,
                'amount_max': 700000,
                'keywords': 'biosensor, diabetes, glucose monitoring, insulin delivery, continuous monitoring',
                'eligibility': 'Academic medical centers, biotechnology companies',
                'url': 'https://grants.nih.gov/grants/guide/rfa/DK-25-008.html'
            },
            {
                'funding_opportunity_number': 'R43-HL-25-009',
                'title': 'SBIR: Cardiovascular Diagnostic Devices',
                'agency': 'NIH/NHLBI',
                'description': 'Small Business Innovation Research program for cardiovascular diagnostic technologies. Support for development of portable ECG devices, cardiac biomarker tests, and imaging technologies for heart disease detection. Focus on point-of-care and home-use applications.',
                'amount_min': 200000,
                'amount_max': 350000,
                'keywords': 'cardiovascular, diagnostic device, ECG, cardiac biomarker, heart disease',
                'eligibility': 'Small businesses, medical device startups',
                'url': 'https://grants.nih.gov/grants/guide/rfa/HL-25-009.html'
            },
            {
                'funding_opportunity_number': 'R01-CA-25-010',
                'title': 'Immunotherapy Biomarker Development',
                'agency': 'NIH/NCI',
                'description': 'Research program supporting development of biomarkers to predict and monitor immunotherapy response in cancer patients. Focus on developing companion diagnostic tests, predictive algorithms, and personalized medicine approaches for cancer immunotherapy.',
                'amount_min': 400000,
                'amount_max': 900000,
                'keywords': 'immunotherapy, cancer biomarker, companion diagnostic, personalized medicine, oncology',
                'eligibility': 'Cancer centers, research universities',
                'url': 'https://grants.nih.gov/grants/guide/rfa/CA-25-010.html'
            }
        ]
        
        return sample_grants
    
    def save_grants(self, grants):
        """Save grants to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        saved_count = 0
        for grant in grants:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO grants 
                    (funding_opportunity_number, title, agency, description, 
                     amount_min, amount_max, keywords, eligibility, url, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    datetime.now()
                ))
                saved_count += 1
            except sqlite3.Error as e:
                print(f"Error saving grant {grant.get('title', 'Unknown')}: {e}")
        
        conn.commit()
        conn.close()
        
        print(f"✅ Saved {saved_count} grants to database")
        return saved_count
    
    def run_scraper(self):
        """Run the complete scraping process with sample data"""
        print("🔬 Starting BioTools Grant Matcher - Sample Data Setup...")
        
        # Create sample grants
        sample_grants = self.create_sample_data()
        
        # Save to database
        saved_count = self.save_grants(sample_grants)
        
        if saved_count > 0:
            print(f"✅ Setup complete! Created database with {saved_count} sample grants.")
            print(f"📍 Database location: {self.db_path}")
            print("\n🚀 You can now run: python app.py")
        else:
            print("❌ No grants were saved.")
        
        return saved_count

def main():
    scraper = SimpleGrantScraper()
    scraper.run_scraper()

if __name__ == "__main__":
    main()