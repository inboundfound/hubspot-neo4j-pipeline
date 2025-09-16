from typing import List, Dict, Any
from extractors.base_extractor import BaseExtractor
from config.neo4j_schema import COMPANY_PROPERTIES

class CompaniesExtractor(BaseExtractor):
    """Extract all companies from HubSpot"""
    
    def get_properties_list(self) -> List[str]:
        return COMPANY_PROPERTIES
    
    def extract_all(self) -> List[Dict[str, Any]]:
        """Extract all companies with their properties"""
        self.logger.info("Starting companies extraction")
        
        self.data = self.extract_with_pagination(
            self.client.crm.companies.basic_api.get_page,
            "companies",
            self.get_properties_list()
        )
        
        return self.data
