from typing import Dict, List, Any
from datetime import datetime
from neo4j import GraphDatabase
from tqdm import tqdm
from config.settings import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, BATCH_SIZE, IMMUTABLE_EVENT_RELATIONSHIPS
from config.neo4j_schema import CONSTRAINTS, INDEXES
from utils.logger import setup_logger
from utils.change_detector import ChangeDetector


class TemporalLoader:
    """
    Load transformed data into Neo4j with temporal tracking.
    Maintains current state in main nodes and stores full history in HISTORY nodes.
    """
    
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )
        self.change_detector = ChangeDetector()
        self.current_timestamp = datetime.now()
    
    def close(self):
        """Close Neo4j and ChangeDetector connections"""
        self.driver.close()
        self.change_detector.close()
    
    def setup_schema(self):
        """Create constraints and indexes"""
        self.logger.info("Setting up Neo4j schema")
        
        with self.driver.session() as session:
            # Create constraints
            for constraint in CONSTRAINTS:
                try:
                    session.run(constraint)
                    self.logger.info(f"Created constraint: {constraint[:60]}...")
                except Exception as e:
                    if "already exists" not in str(e):
                        self.logger.error(f"Failed to create constraint: {e}")
            
            # Create indexes
            for index in INDEXES:
                try:
                    session.run(index)
                    self.logger.info(f"Created index: {index[:60]}...")
                except Exception as e:
                    if "already exists" not in str(e):
                        self.logger.error(f"Failed to create index: {e}")
    
    def load_with_history(
        self, 
        nodes: Dict[str, List[Dict]], 
        relationships: List[Dict]
    ):
        """
        Main orchestrator for temporal data loading.
        Detects changes and manages history.
        """
        self.logger.info("Starting temporal data load to Neo4j")
        
        # Setup schema first
        self.setup_schema()
        
        # Process each node type with change detection
        for node_type, node_list in nodes.items():
            if node_list:
                self.logger.info(f"Processing {len(node_list)} {node_type} nodes")
                
                # Fetch existing data
                existing_data = self.change_detector.fetch_existing_data(node_type)
                
                # Compare and detect changes
                changes = self.change_detector.compare_records(
                    node_type, node_list, existing_data
                )
                
                # Process changes
                self._process_node_changes(node_type, changes)
        
        # Separate relationships into trackable and immutable
        trackable_rels = []
        immutable_rels = []
        
        for rel in relationships:
            if rel['type'] in IMMUTABLE_EVENT_RELATIONSHIPS or 'from_email' in rel:
                immutable_rels.append(rel)
            else:
                trackable_rels.append(rel)
        
        # Load immutable relationships without change tracking
        if immutable_rels:
            self.logger.info(f"Loading {len(immutable_rels)} immutable event relationships (no change tracking)")
            self._load_relationships(immutable_rels)
        
        # Process trackable relationships with change detection
        if trackable_rels:
            self._process_relationship_changes(trackable_rels)
        
        self.logger.info("Temporal data load complete")
    
    def _process_node_changes(self, node_type: str, changes: Dict[str, List]):
        """
        Process node changes: new, updated, deleted.
        Creates history snapshots for changes.
        """
        # Load new nodes
        if changes['new']:
            self.logger.info(f"Loading {len(changes['new'])} new {node_type} nodes")
            self._load_new_nodes(node_type, changes['new'])
        
        # Update changed nodes (create history + update current)
        if changes['updated']:
            self.logger.info(f"Updating {len(changes['updated'])} {node_type} nodes")
            self._update_nodes_with_history(node_type, changes['updated'])
        
        # Mark deleted nodes
        if changes['deleted']:
            self.logger.info(f"Marking {len(changes['deleted'])} {node_type} nodes as deleted")
            self._mark_nodes_deleted(node_type, changes['deleted'])
        
        # Log unchanged
        if changes['unchanged']:
            self.logger.info(f"Skipping {len(changes['unchanged'])} unchanged {node_type} nodes")
    
    def _load_new_nodes(self, node_type: str, nodes: List[Dict]):
        """Load brand new nodes that don't exist in Neo4j"""
        with self.driver.session() as session:
            for i in tqdm(range(0, len(nodes), BATCH_SIZE), desc=f"Loading new {node_type}"):
                batch = nodes[i:i + BATCH_SIZE]
                
                # Special handling for users to add Archived label
                if node_type == 'HUBSPOT_User':
                    query = f"""
                    UNWIND $nodes AS node
                    MERGE (n:{node_type} {{hubspot_id: node.hubspot_id}})
                    SET n = node
                    WITH n, node
                    FOREACH (_ IN CASE WHEN node.archived = true THEN [1] ELSE [] END |
                        SET n:Archived
                    )
                    """
                else:
                    query = f"""
                    UNWIND $nodes AS node
                    MERGE (n:{node_type} {{hubspot_id: node.hubspot_id}})
                    SET n = node
                    """
                
                try:
                    session.run(query, nodes=batch)
                except Exception as e:
                    self.logger.error(f"Failed to load new {node_type} batch: {e}")
    
    def _update_nodes_with_history(self, node_type: str, updates: List[Dict]):
        """
        Update nodes that have changed.
        Creates history snapshot of old state, then updates current node.
        """
        history_label = f"{node_type}_HISTORY"
        
        with self.driver.session() as session:
            for i in tqdm(range(0, len(updates), BATCH_SIZE), desc=f"Updating {node_type}"):
                batch = updates[i:i + BATCH_SIZE]
                
                # Create history snapshots and update main nodes
                for update in batch:
                    old_data = update['old']
                    new_data = update['new']
                    hubspot_id = new_data['hubspot_id']
                    
                    try:
                        # Step 1: Create history snapshot of old state
                        history_query = f"""
                        MATCH (n:{node_type} {{hubspot_id: $hubspot_id}})
                        CREATE (h:{history_label})
                        SET h = properties(n),
                            h.valid_to = $valid_to
                        CREATE (n)-[:HAS_HISTORY]->(h)
                        """
                        
                        session.run(
                            history_query,
                            hubspot_id=hubspot_id,
                            valid_to=self.current_timestamp
                        )
                        
                        # Step 2: Update main node with new data
                        if node_type == 'HUBSPOT_User':
                            # Handle Archived label for users
                            update_query = f"""
                            MATCH (n:{node_type} {{hubspot_id: $hubspot_id}})
                            SET n = $new_data
                            WITH n
                            FOREACH (_ IN CASE WHEN $archived = true THEN [1] ELSE [] END |
                                SET n:Archived
                            )
                            FOREACH (_ IN CASE WHEN $archived = false THEN [1] ELSE [] END |
                                REMOVE n:Archived
                            )
                            """
                            session.run(
                                update_query,
                                hubspot_id=hubspot_id,
                                new_data=new_data,
                                archived=new_data.get('archived', False)
                            )
                        else:
                            update_query = f"""
                            MATCH (n:{node_type} {{hubspot_id: $hubspot_id}})
                            SET n = $new_data
                            """
                            session.run(
                                update_query,
                                hubspot_id=hubspot_id,
                                new_data=new_data
                            )
                        
                    except Exception as e:
                        self.logger.error(
                            f"Failed to update {node_type} {hubspot_id}: {e}"
                        )
    
    def _mark_nodes_deleted(self, node_type: str, deleted: List[Dict]):
        """
        Mark nodes as deleted (don't actually delete them).
        Creates history snapshot, then marks is_deleted=True.
        """
        history_label = f"{node_type}_HISTORY"
        
        with self.driver.session() as session:
            for i in tqdm(range(0, len(deleted), BATCH_SIZE), desc=f"Marking {node_type} deleted"):
                batch = deleted[i:i + BATCH_SIZE]
                
                for item in batch:
                    hubspot_id = item['hubspot_id']
                    
                    try:
                        # Create history snapshot before marking deleted
                        query = f"""
                        MATCH (n:{node_type} {{hubspot_id: $hubspot_id}})
                        WHERE n.is_deleted IS NULL OR n.is_deleted = false
                        CREATE (h:{history_label})
                        SET h = properties(n),
                            h.valid_to = $valid_to
                        CREATE (n)-[:HAS_HISTORY]->(h)
                        WITH n
                        SET n.is_deleted = true,
                            n.valid_to = $valid_to,
                            n.is_current = false
                        """
                        
                        session.run(
                            query,
                            hubspot_id=hubspot_id,
                            valid_to=self.current_timestamp
                        )
                        
                    except Exception as e:
                        self.logger.error(
                            f"Failed to mark {node_type} {hubspot_id} as deleted: {e}"
                        )
    
    def _filter_valid_relationships(self, relationships: List[Dict]) -> List[Dict]:
        """
        Filter relationships to only include those where both nodes exist.
        This prevents tracking relationships that can't be created due to missing nodes.
        """
        if not relationships:
            return []
        
        self.logger.info(f"Validating {len(relationships)} relationships for node existence")
        
        # Collect all unique node IDs
        all_node_ids = set()
        for rel in relationships:
            all_node_ids.add(str(rel['from_id']))
            all_node_ids.add(str(rel['to_id']))
        
        # Query which nodes exist in bulk
        existing_nodes = set()
        with self.driver.session() as session:
            result = session.run("""
                MATCH (n)
                WHERE n.hubspot_id IN $node_ids
                RETURN DISTINCT n.hubspot_id as id
            """, node_ids=list(all_node_ids))
            
            for record in result:
                existing_nodes.add(str(record['id']))
        
        # Filter relationships where both nodes exist
        valid_relationships = []
        for rel in relationships:
            from_id = str(rel['from_id'])
            to_id = str(rel['to_id'])
            if from_id in existing_nodes and to_id in existing_nodes:
                valid_relationships.append(rel)
        
        invalid_count = len(relationships) - len(valid_relationships)
        if invalid_count > 0:
            self.logger.warning(
                f"Filtered out {invalid_count} relationships with missing nodes "
                f"(kept {len(valid_relationships)} valid relationships)"
            )
        
        return valid_relationships
    
    def _process_relationship_changes(self, new_relationships: List[Dict]):
        """
        Process relationship changes.
        Tracks added and removed relationships in HUBSPOT_RelationshipChange nodes.
        Only tracks relationships where both nodes exist to avoid false positives.
        """
        self.logger.info(f"Processing {len(new_relationships)} relationships")
        
        # Filter to only relationships where both nodes exist
        valid_relationships = self._filter_valid_relationships(new_relationships)
        
        # Detect changes (only for valid relationships)
        rel_changes = self.change_detector.detect_relationship_changes(valid_relationships)
        
        # Load new/added relationships (try to load all, but only valid ones will succeed)
        if new_relationships:
            self._load_relationships(new_relationships)
        
        # Track removed relationships
        if rel_changes['removed']:
            self._track_removed_relationships(rel_changes['removed'])
        
        # Track added relationships (only valid ones)
        if rel_changes['added']:
            self._track_added_relationships(rel_changes['added'])
    
    def _load_relationships(self, relationships: List[Dict]):
        """Load all current relationships (new + existing)"""
        # Group by type
        rel_groups = {}
        for rel in relationships:
            key = f"{rel['from_type']}_{rel['type']}_{rel['to_type']}"
            if key not in rel_groups:
                rel_groups[key] = []
            rel_groups[key].append(rel)
        
        with self.driver.session() as session:
            for rel_key, rels in rel_groups.items():
                # Handle special case for email relationships
                if rels and "from_email" in rels[0]:
                    self._load_email_relationships(session, rels)
                else:
                    self._load_standard_relationships(session, rels)
    
    def _load_standard_relationships(self, session, relationships: List[Dict]):
        """Load standard relationships (matched by hubspot_id)"""
        for i in tqdm(range(0, len(relationships), BATCH_SIZE), desc="Loading relationships"):
            batch = relationships[i:i + BATCH_SIZE]
            if not batch:
                continue
                
            rel = batch[0]
            
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
        for i in tqdm(range(0, len(relationships), BATCH_SIZE), desc="Loading email relationships"):
            batch = relationships[i:i + BATCH_SIZE]
            if not batch:
                continue
                
            rel = batch[0]
            
            query = f"""
            UNWIND $rels AS rel
            MATCH (a:HUBSPOT_Contact {{email: rel.from_email}})
            MATCH (b:{rel['to_type']} {{hubspot_id: rel.to_id}})
            MERGE (a)-[r:{rel['type']}]->(b)
            SET r = rel.properties
            """
            
            try:
                session.run(query, rels=batch)
            except Exception as e:
                self.logger.error(f"Failed to load email relationship batch: {e}")
    
    def _track_removed_relationships(self, removed: List[Dict]):
        """Track removed relationships as change events with properties"""
        self.logger.info(f"Tracking {len(removed)} removed relationships")
        
        with self.driver.session() as session:
            for i in tqdm(range(0, len(removed), BATCH_SIZE), desc="Tracking removed relationships"):
                batch = removed[i:i + BATCH_SIZE]
                
                query = """
                UNWIND $changes AS change
                CREATE (rc:HUBSPOT_RelationshipChange {
                    change_type: 'removed',
                    from_entity_type: change.from_type,
                    from_entity_id: change.from_id,
                    to_entity_type: change.to_type,
                    to_entity_id: change.to_id,
                    relationship_type: change.type,
                    relationship_properties: change.properties,
                    changed_at: $timestamp
                })
                """
                
                # Also delete the actual relationship
                delete_query = """
                UNWIND $changes AS change
                MATCH (a {hubspot_id: change.from_id})-[r]->(b {hubspot_id: change.to_id})
                WHERE type(r) = change.type
                DELETE r
                """
                
                try:
                    session.run(query, changes=batch, timestamp=self.current_timestamp)
                    session.run(delete_query, changes=batch)
                except Exception as e:
                    self.logger.error(f"Failed to track removed relationships: {e}")
    
    def _track_added_relationships(self, added: List[Dict]):
        """Track newly added relationships as change events with properties"""
        self.logger.info(f"Tracking {len(added)} added relationships")
        
        with self.driver.session() as session:
            for i in tqdm(range(0, len(added), BATCH_SIZE), desc="Tracking added relationships"):
                batch = added[i:i + BATCH_SIZE]
                
                query = """
                UNWIND $changes AS change
                CREATE (rc:HUBSPOT_RelationshipChange {
                    change_type: 'added',
                    from_entity_type: change.from_type,
                    from_entity_id: change.from_id,
                    to_entity_type: change.to_type,
                    to_entity_id: change.to_id,
                    relationship_type: change.type,
                    relationship_properties: change.properties,
                    changed_at: $timestamp
                })
                """
                
                try:
                    session.run(query, changes=batch, timestamp=self.current_timestamp)
                except Exception as e:
                    self.logger.error(f"Failed to track added relationships: {e}")
    
    def verify_load(self) -> Dict[str, int]:
        """Verify the data load by counting nodes and relationships"""
        self.logger.info("Verifying data load")
        
        counts = {}
        with self.driver.session() as session:
            # Count current nodes by type
            node_types = [
                'HUBSPOT_Contact', 'HUBSPOT_Company', 'HUBSPOT_Deal',
                'HUBSPOT_Activity', 'HUBSPOT_User', 'HUBSPOT_EmailCampaign',
                'HUBSPOT_WebPage', 'HUBSPOT_EmailOpenEvent', 'HUBSPOT_EmailClickEvent',
                'HUBSPOT_FormSubmission', 'HUBSPOT_PageVisit'
            ]
            
            for node_type in node_types:
                result = session.run(
                    f"MATCH (n:{node_type}) WHERE n.is_current = true OR n.is_current IS NULL RETURN count(n) as count"
                )
                record = result.single()
                counts[node_type] = record['count'] if record else 0
            
            # Count history nodes
            history_types = [
                'HUBSPOT_Contact_HISTORY', 'HUBSPOT_Company_HISTORY',
                'HUBSPOT_Deal_HISTORY', 'HUBSPOT_Activity_HISTORY', 
                'HUBSPOT_User_HISTORY'
            ]
            
            for history_type in history_types:
                result = session.run(f"MATCH (h:{history_type}) RETURN count(h) as count")
                record = result.single()
                counts[history_type] = record['count'] if record else 0
            
            # Count relationships
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            record = result.single()
            counts['relationships'] = record['count'] if record else 0
            
            # Count relationship changes
            result = session.run("MATCH (rc:HUBSPOT_RelationshipChange) RETURN count(rc) as count")
            record = result.single()
            counts['relationship_changes'] = record['count'] if record else 0
            
            # Count deleted nodes
            result = session.run(
                "MATCH (n) WHERE n.is_deleted = true RETURN count(n) as count"
            )
            record = result.single()
            counts['deleted_nodes'] = record['count'] if record else 0
        
        self.logger.info(f"Verification complete: {counts}")
        return counts


