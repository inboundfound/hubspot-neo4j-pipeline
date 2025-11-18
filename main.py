#!/usr/bin/env python3
"""Main pipeline orchestrator"""

import json
import time
from datetime import datetime
import os

from extractors.contacts import ContactsExtractor
from extractors.companies import CompaniesExtractor
from extractors.deals import DealsExtractor
from extractors.engagements import EngagementsExtractor
from extractors.email_events import EmailEventsExtractor
from extractors.users import UsersExtractor
from extractors.form_submissions import FormSubmissionsExtractor
from transformers.graph_transformer import GraphTransformer
from loaders.neo4j_loader import Neo4jLoader
from utils.logger import setup_logger

def run_pipeline():
    """Run the complete HubSpot to Neo4j pipeline"""
    logger = setup_logger('Pipeline')
    logger.info("🚀 Starting HubSpot to Neo4j Pipeline")
    
    start_time = time.time()
    
    # Create output directory for raw data
    os.makedirs('data/raw', exist_ok=True)
    
    try:
        # Step 1: Extract data from HubSpot
        logger.info("\n" + "="*50)
        logger.info("STEP 1: EXTRACTING DATA FROM HUBSPOT")
        logger.info("="*50)
        
        all_data = {}
        # with open('data/raw/contacts.json', 'r') as f:
        #     all_data['contacts'] = json.load(f)
        # with open('data/raw/companies.json', 'r') as f:
        #     all_data['companies'] = json.load(f)
        # with open('data/raw/deals.json', 'r') as f:
        #     all_data['deals'] = json.load(f)
        # with open('data/raw/engagements.json', 'r') as f:
        #     all_data['engagements'] = json.load(f)
        # with open('data/raw/email_events.json', 'r') as f:
        #     all_data['email_events'] = json.load(f)
        # with open('data/raw/users.json', 'r') as f:
        #     all_data['users'] = json.load(f)
        # with open('data/raw/form_submissions.json', 'r') as f:
        #     all_data['form_submissions'] = json.load(f)
        
        # Extract contacts
        logger.info("\n📋 Extracting Contacts...")
        contacts_extractor = ContactsExtractor()
        all_data['contacts'] = contacts_extractor.extract_all()
        contacts_extractor.save_to_json('data/raw/contacts.json')
        
        # Extract companies
        logger.info("\n🏢 Extracting Companies...")
        companies_extractor = CompaniesExtractor()
        all_data['companies'] = companies_extractor.extract_all()
        companies_extractor.save_to_json('data/raw/companies.json')
        
        # Extract deals
        logger.info("\n💰 Extracting Deals...")
        deals_extractor = DealsExtractor()
        all_data['deals'] = deals_extractor.extract_all()
        deals_extractor.save_to_json('data/raw/deals.json')
        
        # Extract engagements
        logger.info("\n📅 Extracting Engagements...")
        engagements_extractor = EngagementsExtractor()
        all_data['engagements'] = engagements_extractor.extract_all()
        engagements_extractor.save_to_json('data/raw/engagements.json')
        
        # Extract email events
        logger.info("\n📧 Extracting Email Events...")
        email_events_extractor = EmailEventsExtractor()
        all_data['email_events'] = email_events_extractor.extract_all()
        email_events_extractor.save_to_json('data/raw/email_events.json')

        # Extract users/owners
        logger.info("\n👥 Extracting Users/Owners...")
        users_extractor = UsersExtractor()
        all_data['users'] = users_extractor.extract_all()
        users_extractor.save_to_json('data/raw/users.json')

        # Extract form submissions
        logger.info("\n📝 Extracting Form Submissions...")
        form_submissions_extractor = FormSubmissionsExtractor()
        all_data['form_submissions'] = form_submissions_extractor.extract_all()
        form_submissions_extractor.save_to_json('data/raw/form_submissions.json')

        # Step 2: Transform data
        logger.info("\n" + "="*50)
        logger.info("STEP 2: TRANSFORMING DATA")
        logger.info("="*50)
        
        transformer = GraphTransformer()
        nodes, relationships = transformer.transform_all(all_data)
        
        # Save transformed data
        os.makedirs('data/transformed', exist_ok=True)
        with open('data/transformed/nodes.json', 'w') as f:
            json.dump(nodes, f, indent=2, default=str)
        with open('data/transformed/relationships.json', 'w') as f:
            json.dump(relationships, f, indent=2, default=str)
        
        # Step 3: Load into Neo4j
        logger.info("\n" + "="*50)
        logger.info("STEP 3: LOADING INTO NEO4J")
        logger.info("="*50)
        
        loader = Neo4jLoader()
        loader.load_all(nodes, relationships)
        
        # Verify the load
        counts = loader.verify_load()
        
        # Clean up
        loader.close()
        
        # Summary
        elapsed_time = time.time() - start_time
        logger.info("\n" + "="*50)
        logger.info("✅ PIPELINE COMPLETE")
        logger.info("="*50)
        logger.info(f"\nExecution time: {elapsed_time:.2f} seconds")
        logger.info(f"Extraction summary:")
        for key, data in all_data.items():
            logger.info(f"  - {key}: {len(data)} records")
        logger.info(f"\nGraph summary:")
        logger.info(f"  - Nodes: {sum(len(n) for n in nodes.values())}")
        logger.info(f"  - Relationships: {len(relationships)}")
        logger.info(f"\nNeo4j summary:")
        logger.info(f"  - Node counts: {counts['nodes']}")
        logger.info(f"  - Relationship counts: {counts['relationships']}")
        
        # Example queries
        logger.info("\n" + "="*50)
        logger.info("EXAMPLE NEO4J QUERIES")
        logger.info("="*50)
        logger.info("""
1. Find contacts with the most email engagement:
   MATCH (c:Contact)
   WHERE c.total_email_opens > 0
   RETURN c.email, c.total_email_opens, c.total_email_clicks
   ORDER BY c.total_email_opens DESC
   LIMIT 10

2. Show deals by company:
   MATCH (d:Deal)-[:BELONGS_TO]->(c:Company)
   RETURN c.name, collect(d.name) as deals, sum(d.amount) as total_value

3. Find most active contacts by activity count:
   MATCH (c:Contact)<-[:INVOLVES]-(a:Activity)
   RETURN c.email, count(a) as activity_count
   ORDER BY activity_count DESC
   LIMIT 10

4. Email campaign effectiveness:
   MATCH (c:Contact)-[o:OPENED]->(e:EmailCampaign)
   WITH e, count(DISTINCT c) as opens
   MATCH (c:Contact)-[cl:CLICKED]->(e)
   WITH e, opens, count(DISTINCT c) as clicks
   RETURN e.name, opens, clicks, (clicks * 100.0 / opens) as click_rate
   ORDER BY opens DESC
        """)
        
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    # Test connections first
    print("\n🔧 Testing connections before running pipeline...")
    from test_connection import test_hubspot_connection, test_neo4j_connection
    
    if test_hubspot_connection() and test_neo4j_connection():
        print("\n✅ Connection tests passed. Starting pipeline...\n")
        time.sleep(2)
        run_pipeline()
    else:
        print("\n❌ Connection tests failed. Please fix configuration before running pipeline.")
