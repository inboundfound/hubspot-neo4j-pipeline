from typing import Dict, List, Any, Tuple
from datetime import datetime
from urllib.parse import urlparse
from utils.logger import setup_logger
from utils.change_detector import ChangeDetector

class GraphTransformer:
    """Transform HubSpot data into Neo4j nodes and relationships"""
    
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.change_detector = ChangeDetector()
        self.nodes = {
            'HUBSPOT_Contact': [],
            'HUBSPOT_Company': [],
            'HUBSPOT_Deal': [],
            'HUBSPOT_Activity': [],
            'HUBSPOT_EmailCampaign': [],
            'HUBSPOT_WebPage': [],
            'HUBSPOT_User': [],
            'HUBSPOT_EmailOpenEvent': [],
            'HUBSPOT_EmailClickEvent': [],
            'HUBSPOT_FormSubmission': [],
            'HUBSPOT_PageVisit': []
        }
        self.relationships = []
        self.processed_urls = set()
        self.processed_campaigns = set()
        self.event_id_counter = 0  # For generating unique event IDs
        self.current_timestamp = datetime.now()
    
    def transform_all(self, data: Dict[str, List[Dict]]) -> Tuple[Dict, List]:
        """Transform all extracted data into nodes and relationships"""
        self.logger.info("Starting data transformation")

        # Transform users first (needed for owner relationships)
        if 'users' in data:
            self._transform_users(data['users'])

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

        if 'form_submissions' in data:
            self._transform_form_submissions(data['form_submissions'])

        self.logger.info(f"Transformation complete. Nodes: {sum(len(n) for n in self.nodes.values())}, "
                        f"Relationships: {len(self.relationships)}")

        return self.nodes, self.relationships

    def _transform_users(self, users: List[Dict]):
        """Transform user/owner data, including both active and archived users"""
        for user in users:
            is_archived = user.get('archived', False)
            
            node = {
                'hubspot_id': str(user['id']),
                'email': self._clean_email(user.get('email', '')),
                'first_name': user.get('first_name', ''),
                'last_name': user.get('last_name', ''),
                'active': not is_archived,
                'archived': is_archived,  # Explicit archived flag for loader
                'created_date': self._parse_date(user.get('created_at')),
                'last_modified': self._parse_date(user.get('updated_at')),
                'user_id': str(user.get('user_id', '')) if user.get('user_id') else ''
            }

            # Add team information if available
            if user.get('teams'):
                node['teams'] = ', '.join([team.get('name', '') for team in user['teams']])

            # Add temporal fields
            node['valid_from'] = self.current_timestamp
            node['valid_to'] = None
            node['is_current'] = True
            node['is_deleted'] = False
            node['snapshot_hash'] = self.change_detector.generate_property_hash(node)

            self.nodes['HUBSPOT_User'].append(node)

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
                'owner_id': props.get('hubspot_owner_id', ''),
                'total_email_opens': self._safe_int(props.get('hs_email_open')),
                'total_email_clicks': self._safe_int(props.get('hs_email_click')),
                'total_page_views': self._safe_int(props.get('hs_analytics_num_visits')),
                'source': props.get('hs_analytics_source', ''),
                'first_page_seen': props.get('hs_analytics_first_url', ''),
                'country': props.get('country', ''),
                'city': props.get('city', ''),
                'state': props.get('state', '')
            }
            
            # Add temporal fields
            node['valid_from'] = self.current_timestamp
            node['valid_to'] = None
            node['is_current'] = True
            node['is_deleted'] = False
            node['snapshot_hash'] = self.change_detector.generate_property_hash(node)
            
            self.nodes['HUBSPOT_Contact'].append(node)

            # Create HUBSPOT_Contact->HUBSPOT_User ownership relationship
            owner_id = props.get('hubspot_owner_id')
            if owner_id:
                self.relationships.append({
                    'type': 'OWNED_BY',
                    'from_type': 'HUBSPOT_Contact',
                    'from_id': str(contact['id']),
                    'to_type': 'HUBSPOT_User',
                    'to_id': str(owner_id),
                    'properties': {}
                })

            # Create HUBSPOT_Contact->HUBSPOT_Company relationships using associatedcompanyid property
            company_id = props.get('associatedcompanyid')
            if company_id:
                self.relationships.append({
                    'type': 'WORKS_AT',
                    'from_type': 'HUBSPOT_Contact',
                    'from_id': str(contact['id']),
                    'to_type': 'HUBSPOT_Company',
                    'to_id': str(company_id),
                    'properties': {}
                })
            
            # Create relationships
            assoc = contact.get('associations', {})
            
            # HUBSPOT_Contact -> HUBSPOT_Deal relationships
            if 'deals' in assoc:
                for deal in assoc['deals']:
                    self.relationships.append({
                        'type': 'ASSOCIATED_WITH',
                        'from_type': 'HUBSPOT_Contact',
                        'from_id': str(contact['id']),
                        'to_type': 'HUBSPOT_Deal',
                        'to_id': str(deal['id']),
                        'properties': {}
                    })
            
            # Create HUBSPOT_WebPage nodes from URLs
            if props.get('hs_analytics_last_url'):
                self._create_webpage_node(props['hs_analytics_last_url'])
                self.relationships.append({
                    'type': 'VISITED',
                    'from_type': 'HUBSPOT_Contact',
                    'from_id': str(contact['id']),
                    'to_type': 'HUBSPOT_WebPage',
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
                'owner_id': props.get('hubspot_owner_id', ''),
                'country': props.get('country', ''),
                'city': props.get('city', ''),
                'state': props.get('state', '')
            }

            # Add temporal fields
            node['valid_from'] = self.current_timestamp
            node['valid_to'] = None
            node['is_current'] = True
            node['is_deleted'] = False
            node['snapshot_hash'] = self.change_detector.generate_property_hash(node)

            self.nodes['HUBSPOT_Company'].append(node)

            # Create HUBSPOT_Company->HUBSPOT_User ownership relationship
            owner_id = props.get('hubspot_owner_id')
            if owner_id:
                self.relationships.append({
                    'type': 'OWNED_BY',
                    'from_type': 'HUBSPOT_Company',
                    'from_id': str(company['id']),
                    'to_type': 'HUBSPOT_User',
                    'to_id': str(owner_id),
                    'properties': {}
                })

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
                'owner_id': props.get('hubspot_owner_id', ''),
                'is_won': props.get('hs_is_closed_won', 'false').lower() == 'true',
                'probability': self._safe_float(props.get('hs_forecast_probability'))
            }

            # Add temporal fields
            node['valid_from'] = self.current_timestamp
            node['valid_to'] = None
            node['is_current'] = True
            node['is_deleted'] = False
            node['snapshot_hash'] = self.change_detector.generate_property_hash(node)

            self.nodes['HUBSPOT_Deal'].append(node)

            # Create HUBSPOT_Deal->HUBSPOT_User ownership relationship
            owner_id = props.get('hubspot_owner_id')
            if owner_id:
                self.relationships.append({
                    'type': 'OWNED_BY',
                    'from_type': 'HUBSPOT_Deal',
                    'from_id': str(deal['id']),
                    'to_type': 'HUBSPOT_User',
                    'to_id': str(owner_id),
                    'properties': {}
                })

            # Create HUBSPOT_Deal -> HUBSPOT_Company relationships
            assoc = deal.get('associations', {})
            if 'companies' in assoc:
                for company in assoc['companies']:
                    self.relationships.append({
                        'type': 'BELONGS_TO',
                        'from_type': 'HUBSPOT_Deal',
                        'from_id': str(deal['id']),
                        'to_type': 'HUBSPOT_Company',
                        'to_id': str(company['id']),
                        'properties': {}
                    })
            # Also create HUBSPOT_Contact->HUBSPOT_Deal relationships (reverse direction)
            if 'contacts' in assoc:
                for contact in assoc['contacts']:
                    self.relationships.append({
                        'type': 'ASSOCIATED_WITH',
                        'from_type': 'HUBSPOT_Contact',
                        'from_id': str(contact['id']),
                        'to_type': 'HUBSPOT_Deal', 
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
                note_body = props.get('hs_note_body') or ''
                node['details'] = note_body[:200] # First 200 chars
                node['body'] = note_body
            elif eng_type == 'TASK':
                node['details'] = props.get('hs_task_subject', '')
                node['body'] = props.get('hs_task_body', '')
                node['status'] = props.get('hs_task_status', '')
            
            # Add temporal fields
            node['valid_from'] = self.current_timestamp
            node['valid_to'] = None
            node['is_current'] = True
            node['is_deleted'] = False
            node['snapshot_hash'] = self.change_detector.generate_property_hash(node)
            
            self.nodes['HUBSPOT_Activity'].append(node)
            
            # Create relationships
            assoc = eng.get('associations', {})
            
            # HUBSPOT_Activity -> HUBSPOT_Contact relationships
            if 'contacts' in assoc:
                for contact in assoc['contacts']:
                    self.relationships.append({
                        'type': 'INVOLVES',
                        'from_type': 'HUBSPOT_Activity',
                        'from_id': str(eng['id']),
                        'to_type': 'HUBSPOT_Contact',
                        'to_id': str(contact['id']),
                        'properties': {}
                    })
            
            # HUBSPOT_Activity -> HUBSPOT_Company relationships
            if 'companies' in assoc:
                for company in assoc['companies']:
                    self.relationships.append({
                        'type': 'INVOLVES',
                        'from_type': 'HUBSPOT_Activity',
                        'from_id': str(eng['id']),
                        'to_type': 'HUBSPOT_Company',
                        'to_id': str(company['id']),
                        'properties': {}
                    })
            
            # HUBSPOT_Activity -> HUBSPOT_Deal relationships
            if 'deals' in assoc:
                for deal in assoc['deals']:
                    self.relationships.append({
                        'type': 'RELATED_TO',
                        'from_type': 'HUBSPOT_Activity',
                        'from_id': str(eng['id']),
                        'to_type': 'HUBSPOT_Deal',
                        'to_id': str(deal['id']),
                        'properties': {}
                    })
    
    def _transform_email_events(self, events: List[Dict]):
        """
        Transform email event data into Event nodes (v2 refactor).
        Creates HUBSPOT_EmailOpenEvent and HUBSPOT_EmailClickEvent nodes with indexed timestamps.
        """
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
                self.nodes['HUBSPOT_EmailCampaign'].append(campaign_node)

            # Create EVENT NODES instead of relationship properties
            event_type = event.get('event_type', event.get('type', 'UNKNOWN'))
            recipient = event.get('recipient')

            if recipient and event_type in ['OPEN', 'CLICK']:
                # Generate unique event ID
                self.event_id_counter += 1
                event_id = f"email_{event_type.lower()}_{self.event_id_counter}"

                # Create event node with timestamp as indexed property
                if event_type == 'OPEN':
                    event_node = {
                        'hubspot_id': event_id,
                        'timestamp': self._parse_date(event.get('created')),
                        'campaign_id': campaign_id,
                        'recipient_email': self._clean_email(recipient),
                        'device_type': event.get('deviceType', ''),
                        'location': event.get('location', {}).get('city', ''),
                        'browser': event.get('userAgent', '')
                    }
                    self.nodes['HUBSPOT_EmailOpenEvent'].append(event_node)

                    # Contact -> PERFORMED -> EmailOpenEvent
                    self.relationships.append({
                        'type': 'PERFORMED',
                        'from_type': 'HUBSPOT_Contact',
                        'from_email': self._clean_email(recipient),
                        'to_type': 'HUBSPOT_EmailOpenEvent',
                        'to_id': event_id,
                        'properties': {}
                    })

                    # EmailOpenEvent -> FOR_CAMPAIGN -> EmailCampaign
                    self.relationships.append({
                        'type': 'FOR_CAMPAIGN',
                        'from_type': 'HUBSPOT_EmailOpenEvent',
                        'from_id': event_id,
                        'to_type': 'HUBSPOT_EmailCampaign',
                        'to_id': campaign_id,
                        'properties': {}
                    })

                elif event_type == 'CLICK':
                    clicked_url = event.get('url', '')
                    event_node = {
                        'hubspot_id': event_id,
                        'timestamp': self._parse_date(event.get('created')),
                        'campaign_id': campaign_id,
                        'recipient_email': self._clean_email(recipient),
                        'device_type': event.get('deviceType', ''),
                        'location': event.get('location', {}).get('city', ''),
                        'browser': event.get('userAgent', ''),
                        'clicked_url': clicked_url
                    }
                    self.nodes['HUBSPOT_EmailClickEvent'].append(event_node)

                    # Contact -> PERFORMED -> EmailClickEvent
                    self.relationships.append({
                        'type': 'PERFORMED',
                        'from_type': 'HUBSPOT_Contact',
                        'from_email': self._clean_email(recipient),
                        'to_type': 'HUBSPOT_EmailClickEvent',
                        'to_id': event_id,
                        'properties': {}
                    })

                    # EmailClickEvent -> FOR_CAMPAIGN -> EmailCampaign
                    self.relationships.append({
                        'type': 'FOR_CAMPAIGN',
                        'from_type': 'HUBSPOT_EmailClickEvent',
                        'from_id': event_id,
                        'to_type': 'HUBSPOT_EmailCampaign',
                        'to_id': campaign_id,
                        'properties': {}
                    })

                    # Create webpage node and relationship for clicked URL
                    if clicked_url:
                        self._create_webpage_node(clicked_url)
                        # EmailClickEvent -> CLICKED_URL -> WebPage
                        self.relationships.append({
                            'type': 'CLICKED_URL',
                            'from_type': 'HUBSPOT_EmailClickEvent',
                            'from_id': event_id,
                            'to_type': 'HUBSPOT_WebPage',
                            'to_id': clicked_url,
                            'properties': {}
                        })
    
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
        
        self.nodes['HUBSPOT_WebPage'].append(node)

    def _transform_form_submissions(self, submissions: List[Dict]):
        """
        Transform form submission data into FormSubmission event nodes.
        Creates HUBSPOT_FormSubmission nodes with indexed timestamps.
        Links to contacts via email address matching.
        """
        # Build email-to-contact-id lookup from existing contacts
        email_to_contact = {}
        for contact in self.nodes['HUBSPOT_Contact']:
            email = contact.get('email', '').lower().strip()
            if email:
                email_to_contact[email] = contact.get('hubspot_id')

        matched_count = 0
        unmatched_count = 0

        for submission in submissions:
            # Form submissions come directly from Forms API (flat structure)
            # Not from CRM objects, so no 'properties' wrapper

            # Generate unique submission ID
            self.event_id_counter += 1
            submission_id = f"form_submission_{self.event_id_counter}"

            # Parse timestamp from milliseconds
            submitted_at = submission.get('submitted_at')
            timestamp = None
            if submitted_at:
                try:
                    # submitted_at is in milliseconds since epoch
                    timestamp = datetime.fromtimestamp(int(submitted_at) / 1000.0).isoformat() + 'Z'
                except (ValueError, TypeError):
                    timestamp = None

            # Create form submission event node
            event_node = {
                'hubspot_id': submission_id,
                'timestamp': timestamp,
                'created_date': timestamp,  # Use submitted_at as created_date
                'form_guid': submission.get('form_guid', ''),
                'form_name': submission.get('form_name', ''),
                'page_url': submission.get('page_url', ''),
                'page_title': submission.get('page_title', ''),
                'ip_address': submission.get('ip_address', ''),
                'email': submission.get('email', '')  # Store email for reference
            }

            self.nodes['HUBSPOT_FormSubmission'].append(event_node)

            # Match to contact by email address
            submission_email = submission.get('email', '').lower().strip()
            if submission_email and submission_email in email_to_contact:
                contact_id = email_to_contact[submission_email]
                matched_count += 1

                # FormSubmission -> SUBMITTED_BY -> Contact
                self.relationships.append({
                    'type': 'SUBMITTED_BY',
                    'from_type': 'HUBSPOT_FormSubmission',
                    'from_id': submission_id,
                    'to_type': 'HUBSPOT_Contact',
                    'to_id': contact_id,
                    'properties': {}
                })
            else:
                unmatched_count += 1

            # Create WebPage node for the submission page
            page_url = submission.get('page_url')
            if page_url:
                self._create_webpage_node(page_url)
                # FormSubmission -> ON_PAGE -> WebPage
                self.relationships.append({
                    'type': 'ON_PAGE',
                    'from_type': 'HUBSPOT_FormSubmission',
                    'from_id': submission_id,
                    'to_type': 'HUBSPOT_WebPage',
                    'to_id': page_url,
                    'properties': {}
                })

        if matched_count > 0 or unmatched_count > 0:
            self.logger.info(f"Form submissions: {matched_count} matched to contacts, {unmatched_count} unmatched")

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
