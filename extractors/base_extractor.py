import json
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import hubspot
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm

from config.settings import (
    HUBSPOT_ACCESS_TOKEN,
    BATCH_SIZE,
    MAX_RETRIES,
    RATE_LIMIT_DELAY,
    USE_BASIC_API_FOR_CONTACTS,
    CONTACTS_PAGE_LOG_INTERVAL,
)
from utils.logger import setup_logger

class BaseExtractor(ABC):
    """Base class for all HubSpot data extractors"""
    
    def __init__(self):
        self.client = hubspot.Client.create(access_token=HUBSPOT_ACCESS_TOKEN)
        self.logger = setup_logger(self.__class__.__name__)
        self.data = []
        
    @abstractmethod
    def extract_all(self) -> List[Dict[str, Any]]:
        """Extract all records - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def get_properties_list(self) -> List[str]:
        """Return list of properties to fetch"""
        pass
    
    @retry(stop=stop_after_attempt(MAX_RETRIES), wait=wait_exponential(min=1, max=10))
    def _make_api_call(self, api_method, **kwargs):
        """Make an API call with retry logic"""
        try:
            time.sleep(RATE_LIMIT_DELAY)  # Rate limiting
            return api_method(**kwargs)
        except Exception as e:
            self.logger.error(f"API call failed: {str(e)}")
            raise
    
    def save_to_json(self, filename: str):
        """Save extracted data to JSON file for debugging"""
        self.logger.info(f"Saving {len(self.data)} records to {filename}")
        with open(filename, 'w') as f:
            json.dump(self.data, f, indent=2, default=str)
    
    def extract_with_pagination(self, search_method, object_type: str, properties: List[str]) -> List[Dict]:
        """Generic pagination handler for HubSpot API"""
        all_records = []
        after = None
        total_count = 0
        
        with tqdm(desc=f"Extracting {object_type}") as pbar:
            while True:
                try:
                    if object_type == "engagements":
                        # Engagements MUST include object_type in search
                        from hubspot.crm.objects import PublicObjectSearchRequest as ObjectSearchRequest
                        search_request = ObjectSearchRequest(
                            properties=properties,
                            limit=BATCH_SIZE,
                            after=after
                        )
                        results = self._make_api_call(
                            search_method,
                            object_type=object_type,
                            public_object_search_request=search_request
                        )
                    else:
                        # Use basic_api.get_page for all non-engagements (including contacts if flag is set)
                        kwargs = {
                            'properties': properties,
                            'limit': BATCH_SIZE
                        }
                        if after:
                            kwargs['after'] = after
                        results = self._make_api_call(search_method, **kwargs)
                    
                    # Process results
                    if hasattr(results, 'results'):
                        batch = results.results
                        for record in batch:
                            record_dict = {
                                'id': record.id,
                                'properties': record.properties if isinstance(record.properties, dict) else {},
                                'created_at': str(record.created_at) if hasattr(record, 'created_at') else None,
                                'updated_at': str(record.updated_at) if hasattr(record, 'updated_at') else None
                            }
                            
                            # Add associations if available
                            if hasattr(record, 'associations'):
                                record_dict['associations'] = self._extract_associations(record.associations)
                            
                            all_records.append(record_dict)
                            total_count += 1
                        
                        pbar.update(len(batch))
                        # Progress logging for large collections (e.g., contacts)
                        if object_type == "contacts" and total_count % max(CONTACTS_PAGE_LOG_INTERVAL, 1) == 0:
                            self.logger.info(f"Contacts extracted so far: {total_count}")
                        
                        # Check for more pages
                        if hasattr(results, 'paging') and results.paging and hasattr(results.paging, 'next'):
                            after = results.paging.next.after
                        else:
                            break
                    else:
                        self.logger.warning(f"No results found for {object_type}")
                        break
                        
                except Exception as e:
                    self.logger.error(f"Error extracting {object_type}: {str(e)}")
                    break
        
        self.logger.info(f"Extracted {len(all_records)} {object_type}")
        return all_records

    def _extract_associations(self, associations) -> Dict:
        """Extract association data from API response"""
        assoc_dict = {}
        
        if not associations:
            return assoc_dict
        
        # Check if associations is a dictionary (batch API format)
        if isinstance(associations, dict):
            for assoc_type in ['contacts', 'companies', 'deals', 'tickets', 'engagements']:
                if assoc_type in associations:
                    assoc_data = associations[assoc_type]
                    
                    # Handle HubSpot CollectionResponse objects
                    if hasattr(assoc_data, 'results'):
                        assoc_dict[assoc_type] = [
                            {'id': str(item.id if hasattr(item, 'id') else item.get('id', item))} 
                            for item in assoc_data.results
                        ]
                    # Handle plain dict format
                    elif isinstance(assoc_data, dict) and 'results' in assoc_data:
                        assoc_dict[assoc_type] = [
                            {'id': str(item.get('id') if isinstance(item, dict) else item)} 
                            for item in assoc_data['results']
                        ]
            return assoc_dict
        
        # Handle object-based associations (individual API format)
        for assoc_type in ['contacts', 'companies', 'deals', 'tickets', 'engagements']:
            if hasattr(associations, assoc_type):
                assoc_data = getattr(associations, assoc_type)
                if hasattr(assoc_data, 'results'):
                    assoc_dict[assoc_type] = [
                        {'id': str(item.id if hasattr(item, 'id') else item)} 
                        for item in assoc_data.results
                    ]
        
        return assoc_dict