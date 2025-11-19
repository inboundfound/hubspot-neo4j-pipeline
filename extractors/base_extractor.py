import json
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import hubspot
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from tqdm import tqdm

from config.settings import (
    HUBSPOT_ACCESS_TOKEN,
    BATCH_SIZE,
    MAX_RETRIES,
    USE_BASIC_API_FOR_CONTACTS,
    CONTACTS_PAGE_LOG_INTERVAL,
    HUBSPOT_MAX_REQUESTS_PER_10S,
)
from utils.logger import setup_logger
from utils.parallel_processor import ParallelProcessor

class BaseExtractor(ABC):
    """Base class for all HubSpot data extractors"""
    
    def __init__(self):
        self.client = hubspot.Client.create(access_token=HUBSPOT_ACCESS_TOKEN)
        self.logger = setup_logger(self.__class__.__name__)
        self.data = []
        
        # Initialize parallel processor with rate limiting
        self.processor = ParallelProcessor(max_requests_per_10s=HUBSPOT_MAX_REQUESTS_PER_10S)
        
    @abstractmethod
    def extract_all(self) -> List[Dict[str, Any]]:
        """Extract all records - must be implemented by subclasses"""
        pass
    
    @abstractmethod
    def get_properties_list(self) -> List[str]:
        """Return list of properties to fetch"""
        pass
    
    def _is_retryable_error(exception):
        """Check if an exception is a retryable server error (502, 500, 503, 429)"""
        error_str = str(exception)
        return ('502' in error_str or '500' in error_str or 
                '503' in error_str or '429' in error_str or
                'Bad Gateway' in error_str or 'Internal Server Error' in error_str or
                'Service Unavailable' in error_str or 'Too Many Requests' in error_str)
    
    @retry(
        stop=stop_after_attempt(MAX_RETRIES), 
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception(_is_retryable_error)
    )
    def _make_api_call(self, api_method, **kwargs):
        """
        Make an API call with retry logic for server errors.
        Automatically retries on 502, 500, 503, 429 with exponential backoff.
        """
        try:
            return api_method(**kwargs)
        except Exception as e:
            error_str = str(e)
            if '502' in error_str or '500' in error_str or '503' in error_str:
                self.logger.warning(f"Server error (will retry with backoff): {error_str[:200]}")
            elif '429' in error_str:
                self.logger.warning(f"Rate limit error (will retry with backoff): {error_str[:200]}")
            else:
                self.logger.error(f"API call failed: {error_str[:200]}")
            raise
    
    def _make_api_call_with_rate_limit(self, api_method, **kwargs):
        """
        Make a rate-limited API call.
        Use this when calling APIs outside of parallel processing.
        """
        self.processor._wait_for_rate_limit()
        return self._make_api_call(api_method, **kwargs)
    
    def save_to_json(self, filename: str):
        """Save extracted data to JSON file for debugging"""
        self.logger.info(f"Saving {len(self.data)} records to {filename}")
        with open(filename, 'w') as f:
            json.dump(self.data, f, indent=2, default=str)
    
    def extract_with_search_filter(self, search_method, object_type: str, properties: List[str], 
                                   filter_groups: List[Dict] = None) -> List[Dict]:
        """
        Extract data using search API with optional filters.
        Specifically for engagements that need filter_groups.
        """
        all_records = []
        after = None
        total_count = 0
        
        from hubspot.crm.objects import PublicObjectSearchRequest as ObjectSearchRequest
        
        with tqdm(desc=f"Extracting {object_type}") as pbar:
            while True:
                try:
                    # Build search request with filters
                    search_params = {
                        'properties': properties,
                        'limit': BATCH_SIZE,
                        'after': after
                    }
                    if filter_groups:
                        search_params['filter_groups'] = filter_groups
                    
                    search_request = ObjectSearchRequest(**search_params)
                    
                    results = self._make_api_call_with_rate_limit(
                        search_method,
                        object_type=object_type,
                        public_object_search_request=search_request
                    )
                    
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
                        results = self._make_api_call_with_rate_limit(
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
                        results = self._make_api_call_with_rate_limit(search_method, **kwargs)
                    
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