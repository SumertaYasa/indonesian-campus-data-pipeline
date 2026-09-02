from typing import Tuple, Optional
from src.models.mapped_data import KampusMapped

class BaseImageEnricherStrategy:
    """Base strategy for external image enrichment."""
    
    def enrich(self, kampus: KampusMapped) -> Tuple[Optional[str], Optional[str]]:
        """
        Attempts to find a logo and banner for the campus.
        Returns a tuple: (logo_url, banner_url).
        If an image is not found, its respective position in the tuple should be None.
        """
        raise NotImplementedError
