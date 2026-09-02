import urllib.request
import urllib.parse
import re
import logging
from typing import Tuple, Optional, List, Dict
from src.models.mapped_data import KampusMapped
from src.enrichers.strategies.base_strategy import BaseImageEnricherStrategy

class OfficialWebsiteStrategy(BaseImageEnricherStrategy):
    """Strategy to fetch logo and banner from official campus website."""
    
    def __init__(self):
        self.logger = logging.getLogger("quipper_scraper")
        self.timeout = 10
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def enrich(self, kampus: KampusMapped) -> Tuple[Optional[str], Optional[str]]:
        if not kampus.website:
            return None, None
            
        base_url = kampus.website.strip()
        if not base_url.startswith('http'):
            base_url = 'https://' + base_url
            
        try:
            req = urllib.request.Request(base_url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                html_content = response.read().decode('utf-8', errors='ignore')
        except Exception as e:
            self.logger.warning(f"IMAGE_ENRICHMENT_FAILED | {kampus.nama} | OfficialWebsiteStrategy | {e}")
            return None, None
            
        logo_candidates = self._extract_logo_candidates(html_content, base_url)
        banner_candidates = self._extract_banner_candidates(html_content, base_url)
        
        logo_url = self._validate_candidates(logo_candidates, kampus.nama, "logo")
        banner_url = self._validate_candidates(banner_candidates, kampus.nama, "banner")
        
        return logo_url, banner_url

    def _extract_logo_candidates(self, html: str, base_url: str) -> List[Dict]:
        candidates = []
        
        # 1. <img> with logo in attributes
        img_tags = re.findall(r'<img\s+[^>]*>', html, re.IGNORECASE)
        for img in img_tags:
            src_match = re.search(r'src=["\']([^"\']+)["\']', img, re.IGNORECASE)
            if not src_match:
                continue
            src = src_match.group(1)
            
            alt_match = re.search(r'alt=["\']([^"\']*)["\']', img, re.IGNORECASE)
            class_match = re.search(r'class=["\']([^"\']*)["\']', img, re.IGNORECASE)
            id_match = re.search(r'id=["\']([^"\']*)["\']', img, re.IGNORECASE)
            
            combined_text = (
                (alt_match.group(1) if alt_match else "") + " " +
                (class_match.group(1) if class_match else "") + " " +
                (id_match.group(1) if id_match else "") + " " + src
            ).lower()
            
            if 'logo' in combined_text:
                candidates.append({'url': self._normalize_url(src, base_url), 'rank': 1, 'type': 'img_logo'})
                
        # 2. og:image
        og_match = re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\'][^>]*>', html, re.IGNORECASE)
        if not og_match:
            og_match = re.search(r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\'][^>]*>', html, re.IGNORECASE)
        if og_match:
            candidates.append({'url': self._normalize_url(og_match.group(1), base_url), 'rank': 2, 'type': 'og_image'})
            
        # 3. favicon / touch icon
        favicon_matches = re.findall(r'<link[^>]*rel=["\'](?:shortcut )?icon["\'][^>]*href=["\']([^"\']+)["\'][^>]*>', html, re.IGNORECASE)
        favicon_matches += re.findall(r'<link[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\'](?:shortcut )?icon["\'][^>]*>', html, re.IGNORECASE)
        favicon_matches += re.findall(r'<link[^>]*rel=["\']apple-touch-icon["\'][^>]*href=["\']([^"\']+)["\'][^>]*>', html, re.IGNORECASE)
        
        for fav in favicon_matches:
            candidates.append({'url': self._normalize_url(fav, base_url), 'rank': 3, 'type': 'favicon'})
            
        return candidates

    def _extract_banner_candidates(self, html: str, base_url: str) -> List[Dict]:
        candidates = []
        
        # 1. og:image
        og_match = re.search(r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\'][^>]*>', html, re.IGNORECASE)
        if not og_match: 
            og_match = re.search(r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*property=["\']og:image["\'][^>]*>', html, re.IGNORECASE)
        if og_match:
            candidates.append({'url': self._normalize_url(og_match.group(1), base_url), 'rank': 1, 'type': 'og_image'})
            
        # 2. <img> with hero/banner/cover/header
        img_tags = re.findall(r'<img\s+[^>]*>', html, re.IGNORECASE)
        for img in img_tags:
            src_match = re.search(r'src=["\']([^"\']+)["\']', img, re.IGNORECASE)
            if not src_match:
                continue
            src = src_match.group(1)
            
            alt_match = re.search(r'alt=["\']([^"\']*)["\']', img, re.IGNORECASE)
            class_match = re.search(r'class=["\']([^"\']*)["\']', img, re.IGNORECASE)
            id_match = re.search(r'id=["\']([^"\']*)["\']', img, re.IGNORECASE)
            
            combined_text = (
                (alt_match.group(1) if alt_match else "") + " " +
                (class_match.group(1) if class_match else "") + " " +
                (id_match.group(1) if id_match else "") + " " + src
            ).lower()
            
            if any(keyword in combined_text for keyword in ['hero', 'banner', 'cover', 'header']):
                candidates.append({'url': self._normalize_url(src, base_url), 'rank': 2, 'type': 'img_banner'})
                
        return candidates

    def _normalize_url(self, url: str, base_url: str) -> Optional[str]:
        url = url.strip()
        if not url:
            return None
            
        lower_url = url.lower()
        if lower_url.startswith('data:') or lower_url.startswith('blob:') or lower_url.startswith('file:'):
            return None
            
        if not lower_url.startswith('http'):
            try:
                url = urllib.parse.urljoin(base_url, url)
            except Exception:
                return None
                
        if not url.startswith('http://') and not url.startswith('https://'):
            return None
            
        return url

    def _validate_candidates(self, candidates: List[Dict], campus_name: str, img_type: str) -> Optional[str]:
        # Remove None and duplicates, preserving rank order
        valid_cands = []
        seen = set()
        # Sort by rank first
        candidates.sort(key=lambda x: x['rank'])
        
        for c in candidates:
            if c['url'] and c['url'] not in seen:
                seen.add(c['url'])
                valid_cands.append(c)
                
        # Validate at most 3 top candidates to avoid DDoS and save time
        for cand in valid_cands[:3]:
            url = cand['url']
            try:
                req = urllib.request.Request(url, headers=self.headers, method='HEAD')
                with urllib.request.urlopen(req, timeout=5) as response:
                    content_type = response.headers.get('Content-Type', '').lower()
                    if content_type.startswith('image/'):
                        if cand['type'] == 'favicon':
                            self.logger.debug(f"Favicon used as fallback for {img_type} at {campus_name}")
                        return url
            except urllib.error.HTTPError as e:
                # Some servers reject HEAD requests, we could try GET with Range, but for MVP we skip
                continue
            except Exception:
                continue
                
        return None
