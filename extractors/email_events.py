from typing import List, Dict, Any
import requests
from datetime import datetime, timedelta
from extractors.base_extractor import BaseExtractor
from config.settings import HUBSPOT_ACCESS_TOKEN, USE_EMAIL_EVENTS_OFFSET_PAGINATION

class EmailEventsExtractor(BaseExtractor):
    """Extract email events (opens, clicks, etc.) from HubSpot"""
    
    def get_properties_list(self) -> List[str]:
        # Email events use different API, properties not applicable
        return []
    
    def extract_all(self) -> List[Dict[str, Any]]:
        """Extract all email events from the last 90 days"""
        self.logger.info("Starting email events extraction")
        
        headers = {
            "Authorization": f"Bearer {HUBSPOT_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        
        all_events = []
        event_types = ['SENT', 'OPEN', 'CLICK', 'BOUNCE', 'DEFERRED', 'DROPPED']
        
        # Get events from last 90 days
        start_timestamp = int((datetime.now() - timedelta(days=90)).timestamp() * 1000)
        
        for event_type in event_types:
            self.logger.info(f"Extracting {event_type} events")
            
            try:
                base_url = "https://api.hubapi.com/email/public/v1/events"
                params = {
                    'eventType': event_type,
                    'startTimestamp': start_timestamp,
                    'limit': 1000
                }
                url = base_url

                while True:
                    response = requests.get(url, headers=headers, params=params)

                    if response.status_code == 200:
                        data = response.json()
                        events = data.get('events', [])
                        
                        for event in events:
                            event['event_type'] = event_type
                            all_events.append(event)
                        
                        # Check for next page
                        if data.get('hasMore') and 'offset' in data:
                            if USE_EMAIL_EVENTS_OFFSET_PAGINATION:
                                # Keep URL constant, pass offset as a param
                                params['offset'] = data['offset']
                                url = base_url
                            else:
                                # Fallback (not recommended): some clients treat offset as full URL
                                url = data['offset']
                                params = {}
                        else:
                            break
                    else:
                        self.logger.error(f"Failed to get {event_type} events: {response.status_code}")
                        break
                        
            except Exception as e:
                self.logger.error(f"Error extracting {event_type} events: {str(e)}")
        
        self.data = all_events
        self.logger.info(f"Extracted {len(all_events)} email events")
        return self.data
