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
        
        # Step 1: Fetch ALL engagements in ONE API call (no filter)
        # Note: Search API includes associations by default
        self.logger.info("Fetching all engagements (no type filter)...")
        all_raw_engagements = self.extract_with_search_filter(
            self.client.crm.objects.search_api.do_search,
            "engagements",
            self.get_properties_list(),
            filter_groups=None  # No filter = all types
        )
        
        self.logger.info(f"Fetched {len(all_raw_engagements)} total engagements")
        
        # Step 2: Process by type for incremental saving and progress tracking
        all_processed = []
        main_types = ['MEETING', 'CALL', 'NOTE', 'TASK']
        
        # Group engagements by type
        engagements_by_type = {}
        for eng in all_raw_engagements:
            eng_type = eng.get('properties', {}).get('hs_engagement_type', 'UNKNOWN')
            if eng_type not in engagements_by_type:
                engagements_by_type[eng_type] = []
            engagements_by_type[eng_type].append(eng)
        
        self.logger.info(f"Found types: {list(engagements_by_type.keys())}")
        
        # Process main types first
        for eng_type in main_types:
            engagements = engagements_by_type.get(eng_type, [])
            
            if not engagements:
                self.logger.info(f"No {eng_type} engagements found")
                continue
            
            self.logger.info(f"Processing {len(engagements)} {eng_type} engagements")
            
            # Associations already included in search results!
            # Only fetch for engagements without associations
            need_associations = [e for e in engagements if not e.get('associations')]
            
            if need_associations:
                self.logger.info(f"Fetching missing associations for {len(need_associations)}/{len(engagements)} {eng_type} engagements...")
                
                associations_list = self.processor.process_batch(
                    items=need_associations,
                    func=lambda eng: self._get_engagement_associations(eng['id']),
                    desc=f"Fetching missing {eng_type} associations"
                )
                
                # Assign associations
                for eng, associations in zip(need_associations, associations_list):
                    eng['associations'] = associations
            
            # Count results
            with_assoc = sum(1 for e in engagements if e.get('associations'))
            self.logger.info(f"Completed {eng_type} - With associations: {with_assoc}/{len(engagements)}")
            all_processed.extend(engagements)
            
            # Save incrementally after each engagement type
            self.data = all_processed
            partial_filename = f'data/raw/engagements_{eng_type.lower()}_partial.json'
            self.save_to_json(partial_filename)
            self.logger.info(f"Saved {len(all_processed)} engagements to {partial_filename} (cumulative)")
        
        # Process any OTHER types (EMAIL, INCOMING_EMAIL, etc.)
        other_types = [t for t in engagements_by_type.keys() if t not in main_types]
        if other_types:
            for eng_type in other_types:
                engagements = engagements_by_type[eng_type]
                self.logger.info(f"Processing {len(engagements)} {eng_type} engagements")
                
                # Only fetch missing associations
                need_associations = [e for e in engagements if not e.get('associations')]
                if need_associations:
                    self.logger.info(f"Fetching missing associations for {len(need_associations)} {eng_type}...")
                    associations_list = self.processor.process_batch(
                        items=need_associations,
                        func=lambda eng: self._get_engagement_associations(eng['id']),
                        desc=f"Fetching missing {eng_type} associations"
                    )
                    for eng, associations in zip(need_associations, associations_list):
                        eng['associations'] = associations
                
                all_processed.extend(engagements)
                with_assoc = sum(1 for e in engagements if e.get('associations'))
                self.logger.info(f"Completed {eng_type} - With associations: {with_assoc}/{len(engagements)}")
        
        self.data = all_processed
        self.logger.info(f"Total engagements processed: {len(all_processed)}")
        return self.data
    
    def _get_engagement_associations(self, engagement_id: str) -> Dict:
        """
        Get associations for an engagement.
        Let @retry decorator handle retries - no exception swallowing.
        """
        engagement = self._make_api_call(
            self.client.crm.objects.basic_api.get_by_id,
            object_type="engagements",
            object_id=engagement_id,
            associations=['contacts', 'companies', 'deals']
        )
        
        if hasattr(engagement, 'associations'):
            return self._extract_associations(engagement.associations)
        
        return {}
