from typing import Dict, List, Any
from neo4j import GraphDatabase
from tqdm import tqdm
from config.settings import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, BATCH_SIZE
from config.neo4j_schema import CONSTRAINTS, INDEXES
from utils.logger import setup_logger

class Neo4jLoader:
    """Load transformed data into Neo4j"""
    
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        
    def close(self):
        """Close the Neo4j driver"""
        self.driver.close()
    
    def setup_schema(self):
        """Create constraints and indexes"""
        self.logger.info("Setting up Neo4j schema")
        
        with self.driver.session() as session:
            # Create constraints
            for constraint in CONSTRAINTS:
                try:
                    session.run(constraint)
                    self.logger.info(f"Created constraint: {constraint[:50]}...")
                except Exception as e:
                    if "already exists" not in str(e):
                        self.logger.error(f"Failed to create constraint: {e}")
            
            # Create indexes
            for index in INDEXES:
                try:
                    session.run(index)
                    self.logger.info(f"Created index: {index[:50]}...")
                except Exception as e:
                    if "already exists" not in str(e):
                        self.logger.error(f"Failed to create index: {e}")
    
    def load_all(self, nodes: Dict[str, List], relationships: List[Dict]):
        """Load all nodes and relationships"""
        self.logger.info("Starting data load to Neo4j")
        
        # Setup schema first
        self.setup_schema()
        
        # Load nodes
        for node_type, node_list in nodes.items():
            if node_list:
                self._load_nodes(node_type, node_list)
        
        # Load relationships
        if relationships:
            self._load_relationships(relationships)
        
        self.logger.info("Data load complete")
    
    def _load_nodes(self, node_type: str, nodes: List[Dict]):
        """Load nodes of a specific type"""
        self.logger.info(f"Loading {len(nodes)} {node_type} nodes")
        
        with self.driver.session() as session:
            # Process in batches
            for i in tqdm(range(0, len(nodes), BATCH_SIZE), desc=f"Loading {node_type}"):
                batch = nodes[i:i + BATCH_SIZE]
                
                query = f"""
                UNWIND $nodes AS node
                MERGE (n:{node_type} {{hubspot_id: node.hubspot_id}})
                SET n = node
                """
                
                try:
                    session.run(query, nodes=batch)
                except Exception as e:
                    self.logger.error(f"Failed to load {node_type} batch: {e}")
    
    def _load_relationships(self, relationships: List[Dict]):
        """Load all relationships"""
        self.logger.info(f"Loading {len(relationships)} relationships")
        
        # Group relationships by type for efficiency
        rel_groups = {}
        for rel in relationships:
            key = f"{rel['from_type']}_{rel['type']}_{rel['to_type']}"
            if key not in rel_groups:
                rel_groups[key] = []
            rel_groups[key].append(rel)
        
        with self.driver.session() as session:
            for rel_key, rels in rel_groups.items():
                self.logger.info(f"Loading {len(rels)} {rel_key} relationships")
                
                # Handle special case for email relationships (match by email)
                if 'from_email' in rels[0]:
                    self._load_email_relationships(session, rels)
                else:
                    self._load_standard_relationships(session, rels)
    
    def _load_standard_relationships(self, session, relationships: List[Dict]):
        """Load standard relationships (matched by hubspot_id)"""
        for i in tqdm(range(0, len(relationships), BATCH_SIZE)):
            batch = relationships[i:i + BATCH_SIZE]
            rel = batch[0]  # Get relationship type info from first item
            
            query = f"""
            UNWIND $rels AS rel
            MATCH (a:{rel['from_type']} {{hubspot_id: rel.from_id}})
            MATCH (b:{rel['to_type']} {{hubspot_id: rel.to_id}})
            MERGE (a)-[r:{rel['type']}]->(b)
            SET r = rel.properties
            """
            
            try:
                session.run(query, rels=batch)
            except Exception as e:
                self.logger.error(f"Failed to load relationship batch: {e}")
    
    def _load_email_relationships(self, session, relationships: List[Dict]):
        """Load email relationships (matched by email address)"""
        for i in tqdm(range(0, len(relationships), BATCH_SIZE)):
            batch = relationships[i:i + BATCH_SIZE]
            rel = batch[0]
            
            query = f"""
            UNWIND $rels AS rel
            MATCH (a:Contact {{email: rel.from_email}})
            MATCH (b:{rel['to_type']} {{hubspot_id: rel.to_id}})
            MERGE (a)-[r:{rel['type']}]->(b)
            SET r = rel.properties
            """
            
            try:
                session.run(query, rels=batch)
            except Exception as e:
                self.logger.error(f"Failed to load email relationship batch: {e}")
    
    def verify_load(self) -> Dict[str, int]:
        """Verify the data load by counting nodes and relationships"""
        self.logger.info("Verifying data load")
        
        with self.driver.session() as session:
            # Count nodes
            node_counts = {}
            for label in ['Contact', 'Company', 'Deal', 'Activity', 'EmailCampaign', 'WebPage']:
                result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                node_counts[label] = result.single()['count']
            
            # Count relationships
            rel_counts = {}
            for rel_type in ['WORKS_AT', 'ASSOCIATED_WITH', 'BELONGS_TO', 'INVOLVES', 
                           'RELATED_TO', 'OPENED', 'CLICKED', 'VISITED']:
                result = session.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count")
                rel_counts[rel_type] = result.single()['count']
            
            self.logger.info(f"Node counts: {node_counts}")
            self.logger.info(f"Relationship counts: {rel_counts}")
            
            return {'nodes': node_counts, 'relationships': rel_counts}
