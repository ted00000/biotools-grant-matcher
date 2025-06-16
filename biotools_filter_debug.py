#!/usr/bin/env python3
"""
Debug script to test biotools filtering on actual SBIR data
"""

import requests
import json

def test_biotools_filtering():
    """Test biotools filtering on real SBIR data"""
    
    biotools_keywords = [
        'diagnostic', 'biomarker', 'assay', 'test', 'detection', 'screening',
        'laboratory', 'instrumentation', 'microscopy', 'spectrometry', 'imaging',
        'biotechnology', 'bioengineering', 'medical device', 'biosensor',
        'microfluidics', 'lab-on-chip', 'point-of-care', 'automation',
        'genomics', 'proteomics', 'molecular', 'analytical', 'chromatography',
        'electrophoresis', 'mass spectrometry', 'sequencing', 'pcr',
        'cell analysis', 'protein analysis', 'dna analysis', 'rna analysis',
        'bioinformatics', 'computational biology', 'machine learning',
        'artificial intelligence', 'high throughput', 'drug discovery',
        'pharmaceutical', 'therapeutics', 'clinical', 'biomedical',
        'sensor', 'monitor', 'measurement', 'analysis', 'research tool',
        'scientific instrument', 'clinical trial', 'medical', 'healthcare',
        'biological', 'biochemical', 'biomolecular', 'therapeutic'
    ]
    
    def is_biotools_relevant(text):
        if not text:
            return False
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in biotools_keywords)
    
    def calculate_biotools_relevance_score(title, description, keywords=""):
        score = 0.0
        combined_text = f"{title} {description} {keywords}".lower()
        
        high_value_terms = [
            'diagnostic', 'biomarker', 'medical device', 'biosensor', 'microfluidics',
            'lab-on-chip', 'point-of-care', 'sequencing', 'genomics', 'proteomics'
        ]
        
        medium_value_terms = [
            'laboratory', 'instrumentation', 'microscopy', 'biotechnology',
            'analytical', 'automation', 'imaging', 'molecular'
        ]
        
        for term in high_value_terms:
            if term in combined_text:
                score += 3.0
        
        for term in medium_value_terms:
            if term in combined_text:
                score += 1.5
        
        for keyword in biotools_keywords:
            if keyword in combined_text:
                score += 1.0
        
        return min(score, 10.0)
    
    print("🧪 Testing Biotools Filtering on Real SBIR Data")
    print("=" * 60)
    
    # Test HHS 2024 awards
    url = "https://api.www.sbir.gov/public/api/awards?agency=HHS&year=2024&rows=20"
    
    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            awards = response.json()
            
            print(f"📊 Analyzing {len(awards)} HHS 2024 awards...")
            print()
            
            biotools_count = 0
            non_biotools_count = 0
            
            for i, award in enumerate(awards):
                title = award.get('award_title', '')
                abstract = award.get('abstract', '')
                keywords = award.get('research_area_keywords', '') or ''
                
                combined_text = f"{title} {abstract} {keywords}"
                
                is_relevant = is_biotools_relevant(combined_text)
                score = calculate_biotools_relevance_score(title, abstract, keywords)
                
                if is_relevant:
                    biotools_count += 1
                    print(f"✅ BIOTOOLS RELEVANT (Score: {score:.1f})")
                    print(f"   Title: {title[:80]}...")
                    print(f"   Company: {award.get('firm', 'Unknown')}")
                    
                    # Show which keywords matched
                    matched_keywords = []
                    text_lower = combined_text.lower()
                    for keyword in biotools_keywords:
                        if keyword in text_lower:
                            matched_keywords.append(keyword)
                    print(f"   Matched: {', '.join(matched_keywords[:5])}")
                    print()
                else:
                    non_biotools_count += 1
                    if i < 5:  # Show first few non-matches for comparison
                        print(f"❌ NOT BIOTOOLS RELEVANT (Score: {score:.1f})")
                        print(f"   Title: {title[:80]}...")
                        print(f"   Company: {award.get('firm', 'Unknown')}")
                        print()
            
            print(f"📈 RESULTS:")
            print(f"   Biotools Relevant: {biotools_count}")
            print(f"   Not Relevant: {non_biotools_count}")
            print(f"   Relevance Rate: {biotools_count/len(awards)*100:.1f}%")
            
            if biotools_count == 0:
                print("\n🔍 DIAGNOSTIC: No biotools matches found!")
                print("Let's check some sample titles and abstracts:")
                
                for i, award in enumerate(awards[:3]):
                    print(f"\nSample {i+1}:")
                    print(f"Title: {award.get('award_title', '')}")
                    print(f"Abstract: {award.get('abstract', '')[:200]}...")
                    print(f"Keywords: {award.get('research_area_keywords', 'None')}")
        
        else:
            print(f"API Error: {response.status_code}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_biotools_filtering()