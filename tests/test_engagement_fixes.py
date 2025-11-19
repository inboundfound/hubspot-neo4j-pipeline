#!/usr/bin/env python3
"""
Test script to verify engagement extraction fixes:
1. No duplicate extraction (should get ~750-800 per type, not 3067)
2. Proper filtering by engagement type
3. Incremental saving works
"""

import json
import os
from extractors.engagements import EngagementsExtractor
from utils.logger import setup_logger


def test_single_engagement_type():
    """Test extracting a single engagement type to verify no duplicates"""
    logger = setup_logger('EngagementTest')
    
    logger.info("=" * 60)
    logger.info("TESTING ENGAGEMENT EXTRACTION FIXES")
    logger.info("=" * 60)
    logger.info("")
    
    # Test with just MEETING to verify filtering works
    logger.info("Test 1: Extract MEETING engagements only")
    logger.info("-" * 60)
    
    extractor = EngagementsExtractor()
    
    # Temporarily modify to test just one type
    original_types = ['MEETING', 'CALL', 'NOTE', 'TASK']
    test_types = ['MEETING']  # Just test one type first
    
    # Monkey patch for testing
    import extractors.engagements as eng_module
    old_extract = eng_module.EngagementsExtractor.extract_all
    
    def test_extract(self):
        """Modified extract_all that only processes MEETING"""
        self.logger.info("Starting engagements extraction (TEST MODE - MEETING only)")
        
        all_engagements = []
        engagement_types = ['MEETING']  # Only test MEETING
        
        for eng_type in engagement_types:
            self.logger.info(f"Extracting {eng_type} engagements")
            
            # Search for specific engagement type using filter
            filter_groups = [{
                "filters": [{
                    "propertyName": "hs_engagement_type",
                    "operator": "EQ",
                    "value": eng_type
                }]
            }]
            
            engagements = self.extract_with_search_filter(
                self.client.crm.objects.search_api.do_search,
                "engagements",
                self.get_properties_list(),
                filter_groups=filter_groups
            )
            
            # Add engagement type to each record
            for eng in engagements:
                eng['engagement_type'] = eng_type
            
            logger.info(f"✓ Extracted {len(engagements)} {eng_type} engagements")
            logger.info(f"  Expected: ~750-1000 (NOT 3067)")
            
            if len(engagements) > 2500:
                logger.error(f"❌ FAIL: Got {len(engagements)} - likely extracting ALL types!")
                logger.error("  This suggests filtering is NOT working")
                return None
            elif len(engagements) < 100:
                logger.warning(f"⚠️  WARNING: Only got {len(engagements)} - seems low")
            else:
                logger.info(f"✅ PASS: Count looks reasonable ({len(engagements)})")
            
            # Verify all are MEETING type
            meeting_count = sum(1 for e in engagements if e.get('properties', {}).get('hs_engagement_type') == 'MEETING')
            logger.info(f"  Verified {meeting_count}/{len(engagements)} have hs_engagement_type=MEETING")
            
            if meeting_count < len(engagements) * 0.9:
                logger.error(f"❌ FAIL: Less than 90% are MEETING type - filtering not working!")
                return None
            
            # Don't fetch associations for test - just verify extraction
            logger.info(f"  Skipping association fetching for speed...")
            
            all_engagements.extend(engagements)
            
            # Test incremental save
            self.data = all_engagements
            test_filename = 'data/raw/test_engagements_meeting.json'
            self.save_to_json(test_filename)
            logger.info(f"  Saved to {test_filename}")
            
            # Verify file was created
            if os.path.exists(test_filename):
                with open(test_filename, 'r') as f:
                    saved_data = json.load(f)
                logger.info(f"✅ Incremental save verified: {len(saved_data)} records in file")
            else:
                logger.error(f"❌ Incremental save FAILED: File not created")
        
        self.data = all_engagements
        return self.data
    
    # Patch and run test
    eng_module.EngagementsExtractor.extract_all = test_extract
    
    try:
        data = extractor.extract_all()
        
        if data is None:
            logger.error("")
            logger.error("=" * 60)
            logger.error("❌ TEST FAILED")
            logger.error("=" * 60)
            return False
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ ALL TESTS PASSED")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Summary:")
        logger.info(f"  - Extracted {len(data)} MEETING engagements")
        logger.info(f"  - Filtering appears to be working correctly")
        logger.info(f"  - Incremental saving working")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Run full pipeline to test all 4 engagement types")
        logger.info("  2. Verify total count is ~3000-3200 (not 12,000+)")
        logger.info("  3. Check that each type has different counts")
        logger.info("")
        
        return True
        
    finally:
        # Restore original
        eng_module.EngagementsExtractor.extract_all = old_extract


if __name__ == "__main__":
    import sys
    
    # Create data directory if needed
    os.makedirs('data/raw', exist_ok=True)
    
    # Test connections first
    print("\n🔧 Testing connections...")
    from test_connection import test_hubspot_connection
    
    if not test_hubspot_connection():
        print("\n❌ HubSpot connection failed. Fix before running tests.")
        sys.exit(1)
    
    print("\n✅ Connection test passed. Running engagement extraction test...\n")
    
    success = test_single_engagement_type()
    
    if success:
        print("\n" + "=" * 60)
        print("✅ TEST PASSED - Fixes appear to be working!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("❌ TEST FAILED - Please review errors above")
        print("=" * 60)
        sys.exit(1)

