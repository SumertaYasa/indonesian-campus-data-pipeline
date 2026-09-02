import re
import json
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, Dict, Any

class WikipediaEnricher:
    """
    Client for Indonesian Wikipedia & Wikimedia Commons API with strict educational entity guardrails.
    Guarantees:
    - Only accepts genuine higher education institution articles (rejects biographies/politicians/places).
    - Retrieves official high-resolution institutional logos (PNG/SVG) while rejecting personal photos.
    - Retrieves comprehensive narrative history & institutional profile.
    """

    REST_SUMMARY_URL = "https://id.wikipedia.org/api/rest_v1/page/summary/"
    ACTION_API_URL = "https://id.wikipedia.org/w/api.php"

    HEADERS = {
        "User-Agent": "IndonesianCampusEnricher/2.0 (https://github.com/campus-data; data-extractor@campus.id)",
        "Accept": "application/json"
    }

    # Mandatory keywords indicating an educational entity
    REQUIRED_CAMPUS_KEYWORDS = [
        "perguruan tinggi", "universitas", "institut", "sekolah tinggi",
        "akademi", "politeknik", "kampus", "fakultas", "pendidikan tinggi",
        "akademik", "program studi", "jurusan"
    ]

    # Reject signals for personal biographies/politicians/non-campus articles
    BIOGRAPHY_REJECT_KEYWORDS = [
        "politisi", "gubernur", "anggota dpr", "partai", "kelahiran",
        "meninggal dunia", "atlet", "penyanyi", "aktor", "aktris",
        "bupati", "walikota", "menteri", "wakil ketua dprd", "fraksi"
    ]

    # Image keywords indicating person portraits rather than logos
    INVALID_IMAGE_KEYWORDS = [
        "kpu_", "portrait", "potret", "foto_", "face", "headshot",
        "official_portrait", "dpr", "gubernur", "walikota", "bupati",
        "presiden", "flag_of", "bendera", "peta", "map", "stub",
        "question", "icon", "blank", "lambang_negara", "garuda"
    ]

    def __init__(self, logger: Optional[logging.Logger] = None, timeout: int = 5):
        self.logger = logger or logging.getLogger("WikipediaEnricher")
        self.timeout = timeout

    def search_campus(self, campus_name: str, location_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Looks up the campus in Indonesian Wikipedia with strict entity verification.
        Returns validated {description, logo_url, wiki_url} or None.
        """
        clean_name = campus_name.strip()
        if not clean_name:
            return None

        # 1. Try direct title lookup
        result = self._get_verified_summary(clean_name, clean_name)
        if result:
            return result

        # 2. Try Wikipedia Search API
        search_query = clean_name
        if location_hint and location_hint.strip():
            search_query = f"{clean_name} {location_hint.strip()}"

        candidate_title = self._search_page_title(search_query)
        if candidate_title and candidate_title.lower() != clean_name.lower():
            result = self._get_verified_summary(candidate_title, clean_name)
            if result:
                return result

        return None

    def _get_verified_summary(self, page_title: str, original_campus_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves Wikipedia page summary and validates it against educational guardrails.
        """
        encoded_title = urllib.parse.quote(page_title.replace(" ", "_"))
        url = f"{self.REST_SUMMARY_URL}{encoded_title}"

        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            page_type = data.get("type", "")
            if page_type == "disambiguation":
                return None

            extract = data.get("extract", "").strip()
            title = data.get("title", page_title).strip()
            if not extract:
                return None

            # GUARDRAIL 1: Entity Context Verification (Must be an educational institution)
            if not self._is_valid_campus_entity(extract, title, original_campus_name):
                self.logger.debug(f"Wikipedia rejected non-campus article '{title}' for '{original_campus_name}'")
                return None

            # GUARDRAIL 2: Extract & Verify Logo Image
            logo_url = ""
            orig_img = data.get("originalimage", {})
            if orig_img and orig_img.get("source"):
                logo_url = orig_img["source"]
            elif data.get("thumbnail", {}).get("source"):
                logo_url = data["thumbnail"]["source"]

            if logo_url and not self._is_valid_logo_image(logo_url):
                self.logger.debug(f"Wikipedia rejected personal/non-logo image '{logo_url}' for '{title}'")
                logo_url = ""

            return {
                "title": title,
                "description": extract,
                "logo_url": logo_url,
                "wiki_url": data.get("content_urls", {}).get("desktop", {}).get("page", "")
            }
        except urllib.error.HTTPError as e:
            if e.code != 404:
                self.logger.debug(f"Wikipedia REST API HTTPError {e.code} for '{page_title}'")
            return None
        except Exception as e:
            self.logger.debug(f"Wikipedia REST API error for '{page_title}': {e}")
            return None

    def _is_valid_campus_entity(self, extract: str, wiki_title: str, original_name: str) -> bool:
        """
        Ensures the article is specifically about a higher education institution
        and not a person, politician, geographical location, or unrelated topic.
        """
        extract_lower = extract.lower()
        title_lower = wiki_title.lower()
        orig_lower = original_name.lower()

        # 1. Must contain at least one educational institution keyword
        has_campus_keyword = any(kw in extract_lower or kw in title_lower for kw in self.REQUIRED_CAMPUS_KEYWORDS)
        if not has_campus_keyword:
            return False

        # 2. Reject if strongly matches biography markers without clear institutional subject
        biography_count = sum(1 for kw in self.BIOGRAPHY_REJECT_KEYWORDS if kw in extract_lower)
        if biography_count >= 2:
            # If it talks heavily about politics/biography and is not explicitly "universitas/sekolah tinggi", reject!
            if not any(f"adalah {kw}" in extract_lower or f"merupakan {kw}" in extract_lower for kw in self.REQUIRED_CAMPUS_KEYWORDS):
                return False

        # 3. Keyword Overlap Check between Original Name and Wikipedia Title
        # Extract meaningful words (min 3 chars, skip generic stop words)
        orig_words = set(re.findall(r'[a-zA-Z0-9]{3,}', orig_lower))
        stop_words = {"dan", "yang", "dari", "untuk", "pada", "oleh", "stia", "stai", "stie", "stmi", "stik", "stt"}
        meaningful_orig_words = {w for w in orig_words if w not in stop_words}

        if meaningful_orig_words:
            matched_words = {w for w in meaningful_orig_words if w in title_lower or w in extract_lower[:200]}
            if not matched_words:
                return False

        return True

    def _is_valid_logo_image(self, image_url: str) -> bool:
        """
        Validates that the image is an institutional logo/crest/emblem
        and not a photo of a human being, politician, building snapshot, or flag.
        """
        if not image_url or not isinstance(image_url, str):
            return False

        url_lower = image_url.lower()

        # Check against blacklist of non-logo keywords
        if any(bad in url_lower for bad in self.INVALID_IMAGE_KEYWORDS):
            return False

        # Positive indicator: usually .svg, .png, or contains 'logo' or 'lambang'
        if any(good in url_lower for good in [".png", ".svg", "logo", "lambang", "emblem", "seal"]):
            return True

        # Accept if standard jpg without bad markers
        return True

    def _search_page_title(self, query: str) -> Optional[str]:
        params = urllib.parse.urlencode({
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": 1,
            "format": "json"
        })
        url = f"{self.ACTION_API_URL}?{params}"

        try:
            req = urllib.request.Request(url, headers=self.HEADERS)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            search_results = data.get("query", {}).get("search", [])
            if search_results and isinstance(search_results, list):
                top_hit = search_results[0].get("title")
                return top_hit
            return None
        except Exception as e:
            self.logger.debug(f"Wikipedia Search API error for '{query}': {e}")
            return None
