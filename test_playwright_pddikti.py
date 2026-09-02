import urllib.request
import urllib.error
import json
import logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("pddikti_test")

API_URL = "https://pddikti.kemdiktisaintek.go.id/api/v2/pt/search/filter?limit=10&page=1"
DOMAIN_URL = "https://pddikti.kemdiktisaintek.go.id/"

def test_direct_http():
    logger.info("=========================================")
    logger.info("DIRECT_HTTP")
    logger.info("=========================================")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json'
    }
    req = urllib.request.Request(API_URL, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            status = response.status
            content_type = response.headers.get('Content-Type', '')
            content = response.read().decode('utf-8', errors='ignore')
    except urllib.error.HTTPError as e:
        status = e.code
        content_type = e.headers.get('Content-Type', '')
        content = e.read().decode('utf-8', errors='ignore')
    except Exception as e:
        logger.info(f"→ Exception: {e}")
        return
        
    logger.info(f"→ HTTP {status}")
    logger.info(f"→ Content-Type: {content_type}")
    
    try:
        data = json.loads(content)
        logger.info(f"→ JSON Parsable: YES")
        if isinstance(data, dict) and 'status' in data:
            logger.info(f"→ JSON 'status': {data.get('status')}")
    except json.JSONDecodeError:
        logger.info(f"→ JSON Parsable: NO")

def test_playwright_context():
    logger.info("\n=========================================")
    logger.info("PLAYWRIGHT_CONTEXT")
    logger.info("=========================================")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            page = context.new_page()
            
            # Establish session by visiting domain first
            logger.info(f"Visiting domain: {DOMAIN_URL} to establish session...")
            try:
                page.goto(DOMAIN_URL, wait_until="commit", timeout=15000)
                # Small wait to let cookies set
                page.wait_for_timeout(2000)
            except Exception as e:
                logger.info(f"Warning: Failed to load domain: {e}")
                
            logger.info(f"Requesting API via context.request...")
            # Use context.request to hit API
            response = context.request.get(API_URL)
            
            status = response.status
            content_type = response.headers.get('content-type', '')
            
            logger.info(f"→ HTTP {status}")
            logger.info(f"→ Content-Type: {content_type}")
            
            try:
                data = response.json()
                logger.info(f"→ JSON Parsable: YES")
                if isinstance(data, dict) and 'status' in data:
                    logger.info(f"→ JSON 'status': {data.get('status')}")
            except Exception:
                logger.info(f"→ JSON Parsable: NO")
                
            browser.close()
    except Exception as e:
        logger.info(f"→ Playwright Exception: {e}")

if __name__ == "__main__":
    test_direct_http()
    test_playwright_context()
