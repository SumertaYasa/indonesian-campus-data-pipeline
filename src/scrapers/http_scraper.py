import urllib.request
import urllib.error
from typing import Optional, Tuple

def fetch_html(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetches the raw HTML from the given URL.
    Returns a tuple of (html_content, error_message).
    """
    req = urllib.request.Request(
        url,
        headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                html = response.read().decode('utf-8')
                return html, None
            else:
                return None, f"HTTP_ERROR: {response.status}"
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, "CAMPUS_NOT_FOUND"
        return None, f"HTTP_ERROR: {e.code}"
    except Exception as e:
        return None, f"HTTP_ERROR: {str(e)}"
