from typing import List, Dict, Any
from extractors.base_extractor import BaseExtractor
from config.neo4j_schema import DEAL_PROPERTIES

class DealsExtractor(BaseExtractor):
    """Extract all deals from HubSpot"""
    
    def get_properties_list(self) -> List[str]:
        return DEAL_PROPERTIES
    
    def extract_all(self) -> List[Dict[str, Any]]:
        """Extract all deals with their properties and associations"""
        self.logger.info("Starting deals extraction")
        
        self.data = self.extract_with_pagination(
            self.client.crm.deals.basic_api.get_page,
            "deals",
            self.get_properties_list()
        )
        
        # Get associations for each deal
        self.logger.info("Fetching deal associations")
        for deal in self.data:
            deal['associations'] = self._get_deal_associations(deal['id'])
        
        return self.data
    
    def _get_deal_associations(self, deal_id: str) -> Dict:
        """Get all associations for a deal"""
        associations = {}
        
        try:
            deal = self._make_api_call(
                self.client.crm.deals.basic_api.get_by_id,
                deal_id=deal_id,
                associations=['contacts', 'companies']
            )
            
            if hasattr(deal, 'associations'):
                associations = self._extract_associations(deal.associations)
                
        except Exception as e:
            self.logger.warning(f"Could not get associations for deal {deal_id}: {str(e)}")
        
        return associations
