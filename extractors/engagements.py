from typing import List, Dict, Any
from extractors.base_extractor import BaseExtractor
from hubspot.crm.objects import PublicObjectSearchRequest
from config.settings import BATCH_SIZE

class EngagementsExtractor(BaseExtractor):
    """Extract all engagements (meetings, calls, notes, tasks) from HubSpot"""
    
    def get_properties_list(self) -> List[str]:
        return [
            'hs_engagement_type', 'hs_timestamp', 'hs_createdate', 
            'hs_lastmodifieddate', 'hs_meeting_title', 'hs_meeting_body',
            'hs_meeting_start_time', 'hs_meeting_end_time', 'hs_call_title',
            'hs_call_body', 'hs_call_duration', 'hs_note_body', 'hs_task_subject',
            'hs_task_body', 'hs_task_status', 'hs_task_completion_date'
        ]
    
    def extract_all(self) -> List[Dict[str, Any]]:
        """Extract all engagements"""
        self.logger.info("Starting engagements extraction")
        
        all_engagements = []
        
        # Extract each engagement type
        engagement_types = ['MEETING', 'CALL', 'NOTE', 'TASK']
        
        for eng_type in engagement_types:
            self.logger.info(f"Extracting {eng_type} engagements")
            
            # Search for specific engagement type
            search_request = PublicObjectSearchRequest(
                filter_groups=[{
                    "filters": [{
                        "propertyName": "hs_engagement_type",
                        "operator": "EQ",
                        "value": eng_type
                    }]
                }],
                properties=self.get_properties_list(),
                limit=BATCH_SIZE
            )
            
            engagements = self.extract_with_pagination(
                self.client.crm.objects.search_api.do_search,
                "engagements",
                self.get_properties_list()
            )
            
            # Add engagement type to each record
            for eng in engagements:
                eng['engagement_type'] = eng_type
                eng['associations'] = self._get_engagement_associations(eng['id'])
            
            all_engagements.extend(engagements)
        
        self.data = all_engagements
        return self.data
    
    def _get_engagement_associations(self, engagement_id: str) -> Dict:
        """Get associations for an engagement"""
        associations = {}
        
        try:
            engagement = self._make_api_call(
                self.client.crm.objects.basic_api.get_by_id,
                object_type="engagements",
                object_id=engagement_id,
                associations=['contacts', 'companies', 'deals']
            )
            
            if hasattr(engagement, 'associations'):
                associations = self._extract_associations(engagement.associations)
                
        except Exception as e:
            self.logger.warning(f"Could not get associations for engagement {engagement_id}: {str(e)}")
        
        return associations
