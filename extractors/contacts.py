from typing import List, Dict, Any
from extractors.base_extractor import BaseExtractor
from config.neo4j_schema import CONTACT_PROPERTIES
from config.settings import BATCH_SIZE, USE_BASIC_API_FOR_CONTACTS
from hubspot.crm.contacts import PublicObjectSearchRequest
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
from collections import deque

class ContactsExtractor(BaseExtractor):
    """Extract all contacts from HubSpot"""
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        # Rate limiting for Enterprise tier: 190 requests per 10 seconds
        self.max_requests_per_10s = 180  # Leave some buffer
        self.request_times = deque()
        self.rate_limit_lock = threading.Lock()
    
    def _wait_for_rate_limit(self):
        """Ensure we don't exceed rate limits"""
        with self.rate_limit_lock:
            now = time.time()
            # Remove timestamps older than 10 seconds
            while self.request_times and self.request_times[0] < now - 10:
                self.request_times.popleft()
            
            # If we've hit the limit, wait
            if len(self.request_times) >= self.max_requests_per_10s:
                sleep_time = 10 - (now - self.request_times[0]) + 0.1
                if sleep_time > 0:
                    time.sleep(sleep_time)
            
            # Record this request
            self.request_times.append(now)
    
    def get_properties_list(self) -> List[str]:
        return [
            'firstname', 'lastname', 'email', 'phone', 'company',
            'associatedcompanyid',  # This contains the actual company ID!
            'hubspot_owner_id',  # Owner ID for OWNED_BY relationships
            'jobtitle', 'lifecyclestage', 'hs_lead_status',
            'createdate', 'lastmodifieddate', 'hs_email_domain',
            'website', 'address', 'city', 'state', 'zip', 'country',
            'industry', 'numberofemployees', 'annualrevenue',
            'hs_analytics_source', 'hs_latest_source',
            # Email engagement metrics
            'hs_email_open', 'hs_email_click', 'hs_email_bounce',
            'hs_email_last_open_date', 'hs_email_last_click_date',
            'hs_email_last_send_date', 'hs_email_sends_since_last_engagement',
            # Additional analytics
            'hs_analytics_num_visits', 'hs_analytics_num_page_views',
            'hs_analytics_first_url', 'hs_analytics_last_url'
        ]
    
    def extract_all(self) -> List[Dict[str, Any]]:
        """Extract all contacts with their properties"""
        self.logger.info("Starting contacts extraction")
        
        if USE_BASIC_API_FOR_CONTACTS:
            # Use basic_api.get_page to avoid Search API 10k cap
            self.data = self.extract_with_pagination(
                self.client.crm.contacts.basic_api.get_page,
                "contacts",
                self.get_properties_list()
            )
        else:
            # Fallback: use search API (subject to 10k cap). Useful for quick rollback/testing.
            self.data = self.extract_with_pagination(
                self.client.crm.contacts.search_api.do_search,
                "contacts",
                self.get_properties_list()
            )
        
        # TEMPORARILY SKIP ASSOCIATIONS - we'll use associatedcompanyid property instead
        self.logger.info(f"Extracted {len(self.data)} contacts")
        self.logger.info("Using 'associatedcompanyid' property for company relationships")
        
        # Log some stats about company associations
        contacts_with_company_id = sum(1 for c in self.data if c.get('properties', {}).get('associatedcompanyid'))
        self.logger.info(f"Contacts with associatedcompanyid: {contacts_with_company_id}/{len(self.data)}")
        
        return self.data
    
    def _get_contact_associations_with_rate_limit(self, contact_id: str) -> Dict:
        """Get associations for a contact with rate limiting"""
        self._wait_for_rate_limit()
        return self._get_contact_associations(contact_id)
    
    def _get_contact_associations(self, contact_id: str) -> Dict:
        """Get all associations for a contact"""
        try:
            # Get the contact with associations
            contact = self._make_api_call(
                self.client.crm.contacts.basic_api.get_by_id,
                contact_id=contact_id,
                associations=['companies', 'deals', 'engagements']
            )
            
            associations = {}
            if hasattr(contact, 'associations'):
                associations = self._extract_associations(contact.associations)
                
            return associations
        except Exception as e:
            self.logger.warning(f"Could not get associations for contact {contact_id}: {str(e)}")
            return {}
