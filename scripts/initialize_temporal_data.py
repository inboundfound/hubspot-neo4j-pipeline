"""
Initialize temporal fields for existing HubSpot nodes in Neo4j.

This script should be run ONCE before starting to use the temporal loader.
It adds temporal tracking fields to all existing nodes.

Usage:
    python scripts/initialize_temporal_data.py
"""

import sys
from datetime import datetime
from neo4j import GraphDatabase
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
from utils.logger import setup_logger
from utils.change_detector import ChangeDetector


class TemporalInitializer:
    """Initialize temporal fields on existing Neo4j nodes"""
    
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )
        self.change_detector = ChangeDetector()
        self.initialization_timestamp = datetime.now()
    
    def close(self):
        """Close connections"""
        self.driver.close()
        self.change_detector.close()
    
    def initialize_all(self):
        """Initialize temporal fields for all HubSpot entity types"""
        self.logger.info("Starting temporal initialization")
        self.logger.info(f"Initialization timestamp: {self.initialization_timestamp}")
        
        # Entity types to initialize (all types with temporal tracking)
        entity_types = [
            'HUBSPOT_Contact',
            'HUBSPOT_Company',
            'HUBSPOT_Deal',
            'HUBSPOT_Activity',
            'HUBSPOT_User',
            'HUBSPOT_EmailCampaign',
            'HUBSPOT_WebPage',
            'HUBSPOT_EmailOpenEvent',
            'HUBSPOT_EmailClickEvent',
            'HUBSPOT_FormSubmission',
            'HUBSPOT_PageVisit'
        ]
        
        total_initialized = 0
        
        for entity_type in entity_types:
            count = self._initialize_entity_type(entity_type)
            total_initialized += count
        
        self.logger.info(f"Initialization complete. Total nodes initialized: {total_initialized}")
        
        # Verify initialization
        self._verify_initialization()
    
    def _initialize_entity_type(self, entity_type: str) -> int:
        """Initialize temporal fields for a specific entity type"""
        self.logger.info(f"Initializing {entity_type} nodes")
        
        with self.driver.session() as session:
            # First, check how many nodes need initialization
            count_query = f"""
            MATCH (n:{entity_type})
            WHERE n.valid_from IS NULL
            RETURN count(n) as count
            """
            
            result = session.run(count_query)
            record = result.single()
            count = record['count'] if record else 0
            
            if count == 0:
                self.logger.info(f"No {entity_type} nodes need initialization")
                return 0
            
            self.logger.info(f"Found {count} {entity_type} nodes to initialize")
            
            # Initialize temporal fields
            # Process in smaller batches to avoid memory issues
            batch_size = 100
            initialized = 0
            
            while initialized < count:
                init_query = f"""
                MATCH (n:{entity_type})
                WHERE n.valid_from IS NULL
                WITH n LIMIT {batch_size}
                SET n.valid_from = $timestamp,
                    n.valid_to = null,
                    n.is_current = true,
                    n.is_deleted = false
                WITH n, properties(n) as props
                SET n.snapshot_hash = $hash_prefix + toString(id(n))
                RETURN count(n) as updated
                """
                
                try:
                    result = session.run(
                        init_query,
                        timestamp=self.initialization_timestamp,
                        hash_prefix='init_'
                    )
                    record = result.single()
                    batch_count = record['updated'] if record else 0
                    initialized += batch_count
                    
                    self.logger.info(f"Initialized {initialized}/{count} {entity_type} nodes")
                    
                    if batch_count == 0:
                        break  # No more nodes to initialize
                        
                except Exception as e:
                    self.logger.error(f"Error initializing {entity_type}: {e}")
                    break
            
            # Now compute proper hashes for the initialized nodes
            self.logger.info(f"Computing snapshot hashes for {entity_type}")
            self._compute_hashes(entity_type, session)
            
            return initialized
    
    def _compute_hashes(self, entity_type: str, session):
        """Compute proper snapshot hashes for nodes"""
        # Fetch all nodes of this type
        query = f"""
        MATCH (n:{entity_type})
        WHERE n.snapshot_hash STARTS WITH 'init_'
        RETURN n.hubspot_id as id, properties(n) as props
        """
        
        result = session.run(query)
        
        # Compute hash for each node and update
        for record in result:
            node_id = record['id']
            props = record['props']
            
            # Generate hash
            proper_hash = self.change_detector.generate_property_hash(props)
            
            # Update node
            update_query = f"""
            MATCH (n:{entity_type} {{hubspot_id: $node_id}})
            SET n.snapshot_hash = $hash
            """
            
            try:
                session.run(update_query, node_id=node_id, hash=proper_hash)
            except Exception as e:
                self.logger.error(f"Error updating hash for {entity_type} {node_id}: {e}")
    
    def _verify_initialization(self):
        """Verify that all nodes have been initialized"""
        self.logger.info("Verifying initialization")
        
        entity_types = [
            'HUBSPOT_Contact', 'HUBSPOT_Company', 'HUBSPOT_Deal',
            'HUBSPOT_Activity', 'HUBSPOT_User', 'HUBSPOT_EmailCampaign',
            'HUBSPOT_WebPage', 'HUBSPOT_EmailOpenEvent', 'HUBSPOT_EmailClickEvent',
            'HUBSPOT_FormSubmission', 'HUBSPOT_PageVisit'
        ]
        
        with self.driver.session() as session:
            for entity_type in entity_types:
                # Count initialized nodes
                query = f"""
                MATCH (n:{entity_type})
                WHERE n.valid_from IS NOT NULL
                RETURN count(n) as initialized
                """
                result = session.run(query)
                record = result.single()
                initialized = record['initialized'] if record else 0
                
                # Count total nodes
                total_query = f"MATCH (n:{entity_type}) RETURN count(n) as total"
                result = session.run(total_query)
                record = result.single()
                total = record['total'] if record else 0
                
                if initialized == total:
                    self.logger.info(f"✓ {entity_type}: {initialized}/{total} initialized")
                else:
                    self.logger.warning(
                        f"✗ {entity_type}: Only {initialized}/{total} initialized"
                    )


def main():
    """Main entry point"""
    print("=" * 70)
    print("TEMPORAL DATA INITIALIZATION")
    print("=" * 70)
    print("\nThis script will add temporal tracking fields to existing nodes.")
    print("It should only be run ONCE before starting temporal tracking.\n")
    
    response = input("Continue? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("Initialization cancelled.")
        return
    
    initializer = TemporalInitializer()
    
    try:
        initializer.initialize_all()
        print("\n" + "=" * 70)
        print("INITIALIZATION COMPLETE")
        print("=" * 70)
        print("\nYou can now use the temporal loader for future data imports.")
        
    except Exception as e:
        print(f"\nError during initialization: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        initializer.close()


if __name__ == "__main__":
    main()


