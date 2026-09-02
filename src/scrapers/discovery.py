import urllib.request
import urllib.error
import re
import json
import logging
from typing import List, Dict, Any

class QuipperDiscovery:
    def __init__(self, base_url: str = "https://campus.quipper.com"):
        self.base_url = base_url
        self.directory_url = f"{self.base_url}/directory"
        self.logger = logging.getLogger("quipper_scraper")
        
    def discover_campuses(self) -> List[Dict[str, str]]:
        """
        Discovers all campuses from Quipper Campus Directory using pagination.
        Returns a list of dictionaries with 'nama_kampus', 'slug', and 'url'.
        """
        targets = []
        seen_slugs = set()
        page = 1
        max_errors = 3
        consecutive_errors = 0
        duplicates_skipped = 0
        total_discovered = 0
        
        self.logger.info("=" * 60)
        self.logger.info("CAMPUS DISCOVERY")
        self.logger.info("=" * 60)
        
        while True:
            url = f"{self.directory_url}?page={page}"
            self.logger.info(f"\nFetching directory page {page}...")
            
            try:
                req = urllib.request.Request(
                    url,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                )
                with urllib.request.urlopen(req, timeout=15) as response:
                    html = response.read().decode('utf-8')
                    consecutive_errors = 0 # reset on success
            except Exception as e:
                self.logger.error("DISCOVERY FAILED")
                self.logger.error(f"Page      : {page}")
                self.logger.error(f"URL       : {url}")
                self.logger.error(f"Reason    : {e}")
                consecutive_errors += 1
                if consecutive_errors >= max_errors:
                    self.logger.error("Max consecutive HTTP errors reached. Aborting discovery.")
                    break
                page += 1
                continue
                
            # Extract SiteRoot JSON
            match = re.search(r'<script\s+[^>]*data-hypernova-key="SiteRoot"[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
            if not match:
                self.logger.error("DISCOVERY FAILED")
                self.logger.error(f"Page      : {page}")
                self.logger.error(f"URL       : {url}")
                self.logger.error(f"Reason    : SiteRoot not found")
                break
                
            script_content = match.group(1).strip()
            if script_content.startswith('<!--') and script_content.endswith('-->'):
                script_content = script_content[4:-3].strip()
                
            try:
                data = json.loads(script_content)
            except json.JSONDecodeError as e:
                self.logger.error("DISCOVERY FAILED")
                self.logger.error(f"Page      : {page}")
                self.logger.error(f"URL       : {url}")
                self.logger.error(f"Reason    : Failed to parse SiteRoot JSON: {e}")
                break
                
            schools = data.get('schools', [])
            if not schools:
                self.logger.info(f"    Schools found : 0")
                self.logger.info(f"    Total found   : {len(targets)}")
                self.logger.info(f"    Last page     : true")
                break
                
            new_campuses_found = 0
            for school in schools:
                slug = school.get('slug')
                nama = school.get('name')
                
                if not slug or not nama:
                    continue
                    
                total_discovered += 1
                if slug not in seen_slugs:
                    seen_slugs.add(slug)
                    new_campuses_found += 1
                    targets.append({
                        'nama_kampus': nama,
                        'slug': slug,
                        'url': f"{self.base_url}/directory/{slug}"
                    })
                else:
                    duplicates_skipped += 1
                    
            last_page = data.get('lastPage', False)
            
            self.logger.info(f"    Schools found : {new_campuses_found}")
            self.logger.info(f"    Total found   : {len(targets)}")
            self.logger.info(f"    Last page     : {str(last_page).lower()}")
            
            # Safety check: if page yielded schools but none were new, it might be stuck in a loop
            if new_campuses_found == 0:
                self.logger.warning("    No new campuses found on this page. Assuming end of directory to prevent infinite loop.")
                break
                
            if last_page:
                break
                
            page += 1
            
        self.logger.info("\nDiscovery completed.")
        self.logger.info("-" * 60)
        self.logger.info(f"Total discovered : {total_discovered}")
        self.logger.info(f"Unique campuses  : {len(targets)}")
        self.logger.info(f"Duplicate skipped: {duplicates_skipped}")
        self.logger.info("-" * 60)
        
        return targets
