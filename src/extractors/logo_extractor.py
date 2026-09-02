import re
import ssl
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

class CampusLogoExtractor:
    """
    Extracts official campus logo URLs directly from official campus websites.
    Resolves favicons, apple-touch-icons, header logo <img> elements, and Open Graph assets.
    """

    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "id,en-US;q=0.9,en;q=0.8"
    }

    def __init__(self, logger: Optional[logging.Logger] = None, timeout: int = 6):
        self.logger = logger or logging.getLogger("CampusLogoExtractor")
        self.timeout = timeout
        # Create unverified SSL context for universities with self-signed/expired SSL certs
        self.ssl_context = ssl._create_unverified_context()

    def _normalize_url(self, url: str) -> Optional[str]:
        if not url or not isinstance(url, str):
            return None
        s = url.strip()
        if not s or s in ("-", "null", "None", "#"):
            return None
        if not (s.startswith("http://") or s.startswith("https://")):
            s = f"http://{s}"
        return s

    def extract_logo(self, website_url: str) -> str:
        """
        Attempts to find and extract the official logo URL from the given campus homepage.
        Returns an absolute URL string or empty string if not found.
        """
        clean_url = self._normalize_url(website_url)
        if not clean_url:
            return ""

        try:
            req = urllib.request.Request(clean_url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl_context) as resp:
                final_base_url = resp.geturl()
                content_type = resp.headers.get("Content-Type", "").lower()
                if "text/html" not in content_type and "application" not in content_type:
                    return ""
                html_bytes = resp.read(250000)  # Read first 250KB for fast head & header inspection
                html_text = html_bytes.decode("utf-8", errors="ignore")

            return self._parse_logo_from_html(html_text, final_base_url)
        except Exception as e:
            self.logger.debug(f"Logo extraction failed for {clean_url}: {e}")
            return ""

    def _parse_logo_from_html(self, html: str, base_url: str) -> str:
        """
        Parses HTML looking for high-resolution logos in order of fidelity:
        1. <link rel="apple-touch-icon"> (High resolution square icons)
        2. <img ...> with 'logo' in class/id/src/alt/title in header/navbar
        3. <link rel="icon"> / <link rel="shortcut icon">
        4. <meta property="og:image">
        """
        if not html:
            return ""

        if BeautifulSoup:
            soup = BeautifulSoup(html, "html.parser")

            # 1. Check apple-touch-icon (high-res official brand icons)
            for rel in ["apple-touch-icon", "apple-touch-icon-precomposed"]:
                link = soup.find("link", rel=lambda r: r and rel in (r if isinstance(r, list) else [r.lower()]))
                if link and link.get("href"):
                    href = link["href"].strip()
                    if href and not href.startswith("data:"):
                        return urllib.parse.urljoin(base_url, href)

            # 2. Check <img> tags with 'logo' keyword in header/nav or class/id
            imgs = soup.find_all("img")
            for img in imgs:
                src = img.get("src") or img.get("data-src")
                if not src or src.startswith("data:"):
                    continue
                
                # Check attributes for 'logo' indicator
                cls_id_alt = " ".join([
                    " ".join(img.get("class", [])) if isinstance(img.get("class"), list) else str(img.get("class", "")),
                    str(img.get("id", "")),
                    str(img.get("alt", "")),
                    str(src)
                ]).lower()

                if "logo" in cls_id_alt:
                    # Filter out common false positives (e.g. partner logos, kemdikbud logo, banner logos)
                    if any(bad in cls_id_alt for bad in ["kemdikbud", "tutwuri", "ristek", "kampusmerdeka", "partner", "sponsor"]):
                        continue
                    return urllib.parse.urljoin(base_url, src.strip())

            # 3. Check standard favicon / shortcut icon
            for rel in ["icon", "shortcut icon"]:
                link = soup.find("link", rel=lambda r: r and rel in (r if isinstance(r, list) else [r.lower()]))
                if link and link.get("href"):
                    href = link["href"].strip()
                    if href and not href.startswith("data:"):
                        return urllib.parse.urljoin(base_url, href)

            # 4. Check og:image
            og_meta = soup.find("meta", property=lambda p: p and p.lower() == "og:image")
            if og_meta and og_meta.get("content"):
                og_src = og_meta["content"].strip()
                if og_src and not og_src.startswith("data:"):
                    return urllib.parse.urljoin(base_url, og_src)

        else:
            # Fallback regex parser if BeautifulSoup is not installed
            # Look for apple-touch-icon
            m = re.search(r'<link[^>]+rel=["\'](?:apple-touch-icon|shortcut icon|icon)["\'][^>]+href=["\']([^"\']+)["\']', html, re.I)
            if not m:
                m = re.search(r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\'](?:apple-touch-icon|shortcut icon|icon)["\']', html, re.I)
            if m:
                return urllib.parse.urljoin(base_url, m.group(1).strip())

            # Look for img logo
            m = re.search(r'<img[^>]+src=["\']([^"\']*logo[^"\']*)["\']', html, re.I)
            if m:
                return urllib.parse.urljoin(base_url, m.group(1).strip())

        return ""
