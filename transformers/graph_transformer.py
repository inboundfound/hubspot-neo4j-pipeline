from typing import Dict, List, Any, Tuple
from datetime import datetime
from urllib.parse import urlparse
from utils.logger import setup_logger

class GraphTransformer:
    """Transform HubSpot data into Neo4j nodes and relationships"""
    
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.nodes = {
            'Contact': [],
            'Company': [],
            'Deal': [],
            'Activity': [],
            'EmailCampaign': [],
            'WebPage': []
        }
        self.relationships = []
        self.processed_urls = set()
        self.processed_campaigns = set()
    
    def transform_all(self, data: Dict[str, List[Dict]]) -> Tuple[Dict, List]:
        """Transform all extracted data into nodes and relationships"""
        self.logger.info("Starting data transformation")
        
        # Transform entities
        if 'contacts' in data:
            self._transform_contacts(data['contacts'])
        
        if 'companies' in data:
            self._transform_companies(data['companies'])
        
        if 'deals' in data:
            self._transform_deals(data['deals'])
        
        if 'engagements' in data:
            self._transform_engagements(data['engagements'])
        
        if 'email_events' in data:
            self._transform_email_events(data['email_events'])
        
        self.logger.info(f"Transformation complete. Nodes: {sum(len(n) for n in self.nodes.values())}, "
                        f"Relationships: {len(self.relationships)}")
        
        return self.nodes, self.relationships
    
    def _transform_contacts(self, contacts: List[Dict]):
        """Transform contact data"""
        for contact in contacts:
            props = contact.get('properties', {})
            
            node = {
                'hubspot_id': str(contact['id']),
                'email': self._clean_email(props.get('email')),
                'first_name': props.get('firstname', ''),
                'last_name': props.get('lastname', ''),
                'job_title': props.get('jobtitle', ''),
                'lifecycle_stage': props.get('lifecyclestage', ''),
                'created_date': self._parse_date(props.get('createdate')),
                'last_modified': self._parse_date(props.get('lastmodifieddate')),
                'total_email_opens': self._safe_int(props.get('hs_email_open')),
                'total_email_clicks': self._safe_int(props.get('hs_email_click')),
                'total_page_views': self._safe_int(props.get('hs_analytics_num_visits')),
                'source': props.get('hs_analytics_source', ''),
                'first_page_seen': props.get('hs_analytics_first_url', ''),
                'country': props.get('country', ''),
                'city': props.get('city', ''),
                'state': props.get('state', '')
            }
            
            self.nodes['Contact'].append(node)
            
            # Create Contact->Company relationships using associatedcompanyid property
            company_id = props.get('associatedcompanyid')
            if company_id:
                self.relationships.append({
                    'type': 'WORKS_AT',
                    'from_type': 'Contact',
                    'from_id': str(contact['id']),
                    'to_type': 'Company',
                    'to_id': str(company_id),
                    'properties': {}
                })
            
            # Create relationships
            assoc = contact.get('associations', {})
            
            # Contact -> Deal relationships
            if 'deals' in assoc:
                for deal in assoc['deals']:
                    self.relationships.append({
                        'type': 'ASSOCIATED_WITH',
                        'from_type': 'Contact',
                        'from_id': str(contact['id']),
                        'to_type': 'Deal',
                        'to_id': str(deal['id']),
                        'properties': {}
                    })
            
            # Create WebPage nodes from URLs
            if props.get('hs_analytics_last_url'):
                self._create_webpage_node(props['hs_analytics_last_url'])
                self.relationships.append({
                    'type': 'VISITED',
                    'from_type': 'Contact',
                    'from_id': str(contact['id']),
                    'to_type': 'WebPage',
                    'to_id': props['hs_analytics_last_url'],
                    'properties': {
                        'timestamp': self._parse_date(props.get('hs_analytics_last_visit_timestamp')),
                        'source': props.get('hs_analytics_source', 'direct')
                    }
                })
    
    def _transform_companies(self, companies: List[Dict]):
        """Transform company data"""
        for company in companies:
            props = company.get('properties', {})
            
            node = {
                'hubspot_id': str(company['id']),
                'name': props.get('name', ''),
                'domain': self._clean_domain(props.get('domain')),
                'industry': props.get('industry', ''),
                'employee_count': self._safe_int(props.get('numberofemployees')),
                'annual_revenue': self._safe_float(props.get('annualrevenue')),
                'description': props.get('description', ''),
                'created_date': self._parse_date(props.get('createdate')),
                'last_modified': self._parse_date(props.get('hs_lastmodifieddate')),
                'country': props.get('country', ''),
                'city': props.get('city', ''),
                'state': props.get('state', '')
            }
            
            self.nodes['Company'].append(node)
    
    def _transform_deals(self, deals: List[Dict]):
        """Transform deal data"""
        for deal in deals:
            props = deal.get('properties', {})
            
            node = {
                'hubspot_id': str(deal['id']),
                'name': props.get('dealname', ''),
                'amount': self._safe_float(props.get('amount')),
                'stage': props.get('dealstage', ''),
                'pipeline': props.get('pipeline', 'default'),
                'close_date': self._parse_date(props.get('closedate')),
                'created_date': self._parse_date(props.get('createdate')),
                'last_modified': self._parse_date(props.get('hs_lastmodifieddate')),
                'is_won': props.get('hs_is_closed_won', 'false').lower() == 'true',
                'probability': self._safe_float(props.get('hs_forecast_probability'))
            }
            
            self.nodes['Deal'].append(node)
            
            # Create Deal -> Company relationships
            assoc = deal.get('associations', {})
            if 'companies' in assoc:
                for company in assoc['companies']:
                    self.relationships.append({
                        'type': 'BELONGS_TO',
                        'from_type': 'Deal',
                        'from_id': str(deal['id']),
                        'to_type': 'Company',
                        'to_id': str(company['id']),
                        'properties': {}
                    })
            # Also create Contact->Deal relationships (reverse direction)
            if 'contacts' in assoc:
                for contact in assoc['contacts']:
                    self.relationships.append({
                        'type': 'ASSOCIATED_WITH',
                        'from_type': 'Contact',
                        'from_id': str(contact['id']),
                        'to_type': 'Deal', 
                        'to_id': str(deal['id']),
                        'properties': {}
                    })
    
    def _transform_engagements(self, engagements: List[Dict]):
        """Transform engagement data"""
        for eng in engagements:
            props = eng.get('properties', {})
            eng_type = props.get('hs_engagement_type', eng.get('engagement_type', 'UNKNOWN'))
            
            # Create activity node
            node = {
                'hubspot_id': str(eng['id']),
                'type': eng_type,
                'timestamp': self._parse_date(props.get('hs_timestamp') or props.get('hs_createdate')),
                'created_date': self._parse_date(props.get('hs_createdate')),
                'details': ''
            }
            
            # Add type-specific details
            if eng_type == 'MEETING':
                node['details'] = props.get('hs_meeting_title', '')
                node['body'] = props.get('hs_meeting_body', '')
                node['start_time'] = self._parse_date(props.get('hs_meeting_start_time'))
                node['end_time'] = self._parse_date(props.get('hs_meeting_end_time'))
            elif eng_type == 'CALL':
                node['details'] = props.get('hs_call_title', '')
                node['body'] = props.get('hs_call_body', '')
                node['duration'] = self._safe_int(props.get('hs_call_duration'))
            elif eng_type == 'NOTE':
                node['details'] = props.get('hs_note_body', '')[:200]  # First 200 chars
                node['body'] = props.get('hs_note_body', '')
            elif eng_type == 'TASK':
                node['details'] = props.get('hs_task_subject', '')
                node['body'] = props.get('hs_task_body', '')
                node['status'] = props.get('hs_task_status', '')
            
            self.nodes['Activity'].append(node)
            
            # Create relationships
            assoc = eng.get('associations', {})
            
            # Activity -> Contact relationships
            if 'contacts' in assoc:
                for contact in assoc['contacts']:
                    self.relationships.append({
                        'type': 'INVOLVES',
                        'from_type': 'Activity',
                        'from_id': str(eng['id']),
                        'to_type': 'Contact',
                        'to_id': str(contact['id']),
                        'properties': {}
                    })
            
            # Activity -> Deal relationships
            if 'deals' in assoc:
                for deal in assoc['deals']:
                    self.relationships.append({
                        'type': 'RELATED_TO',
                        'from_type': 'Activity',
                        'from_id': str(eng['id']),
                        'to_type': 'Deal',
                        'to_id': str(deal['id']),
                        'properties': {}
                    })
    
    def _transform_email_events(self, events: List[Dict]):
        """Transform email event data"""
        for event in events:
            # Create email campaign nodes
            campaign_id = str(event.get('emailCampaignId', 'unknown'))
            if campaign_id != 'unknown' and campaign_id not in self.processed_campaigns:
                self.processed_campaigns.add(campaign_id)
                campaign_node = {
                    'hubspot_id': campaign_id,
                    'name': event.get('emailCampaignName', f'Campaign {campaign_id}'),
                    'subject': event.get('subject', ''),
                    'sent_date': self._parse_date(event.get('created'))
                }
                self.nodes['EmailCampaign'].append(campaign_node)
            
            # Create relationships based on event type
            event_type = event.get('event_type', event.get('type', 'UNKNOWN'))
            recipient = event.get('recipient')
            
            if recipient and event_type in ['OPEN', 'CLICK']:
                # We need to match by email - this will be done in the loader
                rel = {
                    'type': 'OPENED' if event_type == 'OPEN' else 'CLICKED',
                    'from_type': 'Contact',
                    'from_email': self._clean_email(recipient),  # Special case - match by email
                    'to_type': 'EmailCampaign',
                    'to_id': campaign_id,
                    'properties': {
                        'timestamp': self._parse_date(event.get('created')),
                        'device_type': event.get('deviceType', ''),
                        'location': event.get('location', {}).get('city', '')
                    }
                }
                
                if event_type == 'CLICK':
                    rel['properties']['url'] = event.get('url', '')
                    # Create webpage node for clicked URL
                    if event.get('url'):
                        self._create_webpage_node(event['url'])
                
                self.relationships.append(rel)
    
    def _create_webpage_node(self, url: str):
        """Create a webpage node from URL"""
        if not url or url in self.processed_urls:
            return
        
        self.processed_urls.add(url)
        parsed = urlparse(url)
        
        node = {
            'hubspot_id': url,  # Use URL as the ID for consistency
            'url': url,
            'domain': parsed.netloc,
            'path': parsed.path,
            'title': ''  # Would need to fetch or get from another source
        }
        
        self.nodes['WebPage'].append(node)
    
    # Helper methods
    def _clean_email(self, email: str) -> str:
        """Clean and normalize email address"""
        if not email:
            return ''
        return email.lower().strip()
    
    def _clean_domain(self, domain: str) -> str:
        """Clean and normalize domain"""
        if not domain:
            return ''
        domain = domain.lower().strip()
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    
    def _parse_date(self, date_str: str) -> str:
        """Parse date string to ISO format"""
        if not date_str:
            return ''
        
        try:
            # Handle Unix timestamp
            if isinstance(date_str, (int, float)):
                return datetime.fromtimestamp(date_str / 1000).isoformat()
            
            # Handle ISO format
            if 'T' in str(date_str):
                return date_str
            
            # Try to parse other formats
            return datetime.fromisoformat(date_str.replace('Z', '+00:00')).isoformat()
        except:
            return str(date_str)
    
    def _safe_int(self, value: Any) -> int:
        """Safely convert to integer"""
        if not value:
            return 0
        try:
            return int(value)
        except:
            return 0
    
    def _safe_float(self, value: Any) -> float:
        """Safely convert to float"""
        if not value:
            return 0.0
        try:
            return float(value)
        except:
            return 0.0
