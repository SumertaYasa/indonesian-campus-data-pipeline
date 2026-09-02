import re

def generate_slug(campus_name: str) -> str:
    """
    Transforms a campus name into a slug format:
    - Lowercase
    - Replace spaces with hyphens '-'
    """
    if not campus_name:
        return ""
    
    # Lowercase the string
    slug = campus_name.lower()
    
    # Replace one or more whitespace characters with a single hyphen
    slug = re.sub(r'\s+', '-', slug)
    
    return slug.strip('-')
