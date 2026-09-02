import logging
from typing import List
from src.models.mapped_data import KampusMapped
from src.enrichers.strategies.base_strategy import BaseImageEnricherStrategy
from src.enrichers.strategies.official_website import OfficialWebsiteStrategy

class ExternalImageEnricher:
    """Manager for external image enrichment, executes strategies in order."""
    
    def __init__(self):
        self.logger = logging.getLogger("quipper_scraper")
        # In the MVP, we only have one strategy: Official Website
        self.strategies: List[BaseImageEnricherStrategy] = [
            OfficialWebsiteStrategy()
        ]
        
    def enrich(self, kampus: KampusMapped) -> str:
        """
        Runs the enrichment strategies.
        Returns the status: 'SUCCESS', 'WARNING', 'ERROR'.
        """
        try:
            logo_url = None
            banner_url = None
            
            for strategy in self.strategies:
                strat_name = strategy.__class__.__name__
                try:
                    # Only look for images we haven't found yet
                    curr_logo, curr_banner = strategy.enrich(kampus)
                    
                    if curr_logo and not logo_url:
                        logo_url = curr_logo
                        
                    if curr_banner and not banner_url:
                        banner_url = curr_banner
                        
                    # If both found, we can break early
                    if logo_url and banner_url:
                        break
                        
                except Exception as strat_e:
                    self.logger.warning(f"IMAGE_ENRICHMENT_FAILED | {kampus.nama} | {strat_name} | {strat_e}")
                    # Keep trying the next strategy
                    continue
                    
            kampus.logo_url = logo_url
            kampus.banner_url = banner_url
            
            if kampus.logo_url and kampus.banner_url:
                return 'SUCCESS'
            else:
                return 'WARNING'
                
        except Exception as e:
            self.logger.warning(f"IMAGE_ENRICHMENT_FAILED | {kampus.nama} | ExternalImageEnricher | {e}")
            kampus.logo_url = None
            kampus.banner_url = None
            return 'ERROR'
