#!/usr/bin/env python3
"""Test pipeline with minimal dataset for debugging temporal tracking"""

import json
import time
import os
from datetime import datetime

from transformers.graph_transformer import GraphTransformer
from loaders.temporal_loader import TemporalLoader
from utils.logger import setup_logger

def run_test_pipeline():
    """Run the pipeline with test data"""
    logger = setup_logger('TestPipeline')
    logger.info("🧪 Starting TEST Pipeline with Minimal Dataset")
    
    start_time = time.time()
    
    try:
        # Step 1: Load test data
        logger.info("\n" + "="*50)
        logger.info("STEP 1: LOADING TEST DATA")
        logger.info("="*50)
        
        all_data = {}
        test_files = [
            'users', 'contacts', 'companies', 'deals', 
            'engagements', 'email_events', 'form_submissions'
        ]
        
        for data_type in test_files:
            filepath = f'data/test/{data_type}.json'
            with open(filepath, 'r') as f:
                all_data[data_type] = json.load(f)
            logger.info(f"✓ Loaded {data_type}: {len(all_data[data_type])} records")
        
        # Step 2: Transform data
        logger.info("\n" + "="*50)
        logger.info("STEP 2: TRANSFORMING DATA")
        logger.info("="*50)
        
        transformer = GraphTransformer()
        nodes, relationships = transformer.transform_all(all_data)
        
        logger.info(f"Transformed into:")
        for node_type, node_list in nodes.items():
            if node_list:
                logger.info(f"  - {node_type}: {len(node_list)} nodes")
        logger.info(f"  - Relationships: {len(relationships)}")
        
        # Save transformed data for inspection
        os.makedirs('data/test/transformed', exist_ok=True)
        with open('data/test/transformed/nodes.json', 'w') as f:
            json.dump(nodes, f, indent=2, default=str)
        with open('data/test/transformed/relationships.json', 'w') as f:
            json.dump(relationships, f, indent=2, default=str)
        logger.info(f"✓ Saved transformed data to data/test/transformed/")
        
        # Step 3: Load into Neo4j with temporal tracking
        logger.info("\n" + "="*50)
        logger.info("STEP 3: LOADING INTO NEO4J (WITH TEMPORAL TRACKING)")
        logger.info("="*50)
        
        loader = TemporalLoader()
        loader.load_with_history(nodes, relationships)
        
        # Verify the load
        logger.info("\n" + "="*50)
        logger.info("STEP 4: VERIFICATION")
        logger.info("="*50)
        
        counts = loader.verify_load()
        
        # Clean up
        loader.close()
        
        # Summary
        elapsed_time = time.time() - start_time
        logger.info("\n" + "="*50)
        logger.info("✅ TEST PIPELINE COMPLETE")
        logger.info("="*50)
        logger.info(f"\nExecution time: {elapsed_time:.2f} seconds")
        
        logger.info(f"\nInput summary:")
        for key, data in all_data.items():
            logger.info(f"  - {key}: {len(data)} records")
        
        logger.info(f"\nGraph summary:")
        logger.info(f"  - Total nodes: {sum(len(n) for n in nodes.values())}")
        logger.info(f"  - Total relationships: {len(relationships)}")
        
        logger.info(f"\nNeo4j summary (current state):")
        
        # Show entity counts
        entity_types = ['HUBSPOT_Contact', 'HUBSPOT_Company', 'HUBSPOT_Deal', 
                       'HUBSPOT_Activity', 'HUBSPOT_User', 'HUBSPOT_EmailCampaign',
                       'HUBSPOT_WebPage', 'HUBSPOT_EmailOpenEvent', 'HUBSPOT_EmailClickEvent',
                       'HUBSPOT_FormSubmission', 'HUBSPOT_PageVisit']
        
        for entity_type in entity_types:
            if entity_type in counts and counts[entity_type] > 0:
                logger.info(f"  - {entity_type}: {counts[entity_type]}")
        
        logger.info(f"  - Relationships: {counts.get('relationships', 0)}")
        logger.info(f"  - Relationship changes tracked: {counts.get('relationship_changes', 0)}")
        logger.info(f"  - Deleted nodes: {counts.get('deleted_nodes', 0)}")
        
        # Show history counts
        history_total = sum(counts.get(f'{et}_HISTORY', 0) for et in 
                           ['HUBSPOT_Contact', 'HUBSPOT_Company', 'HUBSPOT_Deal', 
                            'HUBSPOT_Activity', 'HUBSPOT_User'])
        if history_total > 0:
            logger.info(f"  - Historical versions: {history_total}")
        
        logger.info("\n" + "="*50)
        logger.info("NEXT STEPS")
        logger.info("="*50)
        logger.info("\n1. Run again to test change detection:")
        logger.info("   python run_test_pipeline.py")
        logger.info("\n2. Modify test data and run again:")
        logger.info("   - Edit data/test/*.json files")
        logger.info("   - Change values to test updates")
        logger.info("   - Remove records to test deletions")
        logger.info("\n3. Query temporal data:")
        logger.info("   python query_temporal.py")
        logger.info("\n4. Clear database to start fresh:")
        logger.info("   # In Neo4j Browser: MATCH (n) DETACH DELETE n")
        
    except Exception as e:
        logger.error(f"Test pipeline failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_test_pipeline()


