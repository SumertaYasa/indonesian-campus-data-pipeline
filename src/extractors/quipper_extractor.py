import re
import json
from typing import Optional, Tuple

def extract_siteroot_json(html: str) -> Tuple[Optional[dict], Optional[str]]:
    """
    Extracts the JSON from the SiteRoot script tag in the HTML.
    Returns a tuple of (json_data, error_message).
    """
    # Look for <script type="application/json" data-hypernova-key="SiteRoot" ...> ... </script>
    # The JSON payload is often wrapped in <!-- -->
    match = re.search(r'<script\s+[^>]*data-hypernova-key="SiteRoot"[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
    
    if not match:
        return None, "SITEROOT_SCRIPT_NOT_FOUND"
    
    script_content = match.group(1).strip()
    
    # Handle HTML comment wrappers if present <!-- ... -->
    if script_content.startswith('<!--') and script_content.endswith('-->'):
        # Extract everything between <!-- and -->
        script_content = script_content[4:-3].strip()
        
    try:
        data = json.loads(script_content)
        return data, None
    except json.JSONDecodeError as e:
        return None, f"INVALID_QUIPPER_JSON: {str(e)}"

def extract_quipper_data(siteroot_data: dict) -> Tuple[Optional[dict], Optional[str]]:
    """
    Extracts the raw campus data from the parsed SiteRoot JSON.
    Returns (raw_data, error_message)
    """
    if not isinstance(siteroot_data, dict):
        return None, "INVALID_QUIPPER_STRUCTURE: Root is not an object"
        
    school = siteroot_data.get('school')
    if not school:
        return None, "INVALID_QUIPPER_STRUCTURE: 'school' key not found"
        
    return school, None
