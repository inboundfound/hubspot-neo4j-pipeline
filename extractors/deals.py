# extractors/deals.py - COMPLETE REPLACEMENT

from typing import List, Dict, Any
from extractors.base_extractor import BaseExtractor
from config.neo4j_schema import DEAL_PROPERTIES
from config.settings import BATCH_SIZE

class DealsExtractor(BaseExtractor):
    """Extract all deals from HubSpot"""
    
    def get_properties_list(self) -> List[str]:
        return DEAL_PROPERTIES
    
    def extract_all(self) -> List[Dict[str, Any]]:
        """Extract all deals with their properties and associations"""
        self.logger.info("Starting deals extraction WITH associations")
        
        self.data = []
        after = None
        
        from tqdm import tqdm
        with tqdm(desc="Extracting deals with associations") as pbar:
            while True:
                try:
                    # Get deals WITH associations in the same call
                    kwargs = {
                        'properties': self.get_properties_list(),
                        'associations': ['contacts', 'companies'],  # ← KEY CHANGE
                        'limit': BATCH_SIZE
                    }
                    if after:
                        kwargs['after'] = after
                    
                    results = self._make_api_call(
                        self.client.crm.deals.basic_api.get_page,
                        **kwargs
                    )
                    
                    if hasattr(results, 'results'):
                        for deal in results.results:
                            record_dict = {
                                'id': deal.id,
                                'properties': deal.properties,
                                'created_at': str(deal.created_at) if hasattr(deal, 'created_at') else None,
                                'updated_at': str(deal.updated_at) if hasattr(deal, 'updated_at') else None
                            }
                            
                            # Extract associations directly
                            if hasattr(deal, 'associations'):
                                record_dict['associations'] = self._extract_associations(deal.associations)
                            else:
                                record_dict['associations'] = {}
                            
                            self.data.append(record_dict)
                        
                        pbar.update(len(results.results))
                        
                        # Pagination
                        if hasattr(results, 'paging') and results.paging and hasattr(results.paging, 'next'):
                            after = results.paging.next.after
                        else:
                            break
                    else:
                        break
                        
                except Exception as e:
                    self.logger.error(f"Error extracting deals: {str(e)}")
                    break
        
        self.logger.info(f"Extracted {len(self.data)} deals with associations")
        return self.data