import sys
sys.path.append('app')

try:
    from scraper import CompleteBiotoolsScraper
    print("✅ Scraper imports successfully")
    
    scraper = CompleteBiotoolsScraper()
    print("✅ Scraper initializes successfully")
    
except SyntaxError as e:
    print(f"❌ Syntax error: {e}")
except Exception as e:
    print(f"❌ Other error: {e}")
