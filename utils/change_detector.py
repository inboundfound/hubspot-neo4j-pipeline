import hashlib
import json
from typing import Dict, List, Set, Tuple, Any
from neo4j import GraphDatabase
from config.settings import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, IMMUTABLE_EVENT_RELATIONSHIPS
from utils.logger import setup_logger


class ChangeDetector:
    """Detect changes between HubSpot data and existing Neo4j data"""
    
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )
    
    def close(self):
        """Close Neo4j connection"""
        self.driver.close()
    
    def generate_property_hash(self, properties: Dict[str, Any]) -> str:
        """
        Generate hash from node properties for change detection.
        Excludes temporal fields to avoid false positives.
        """
        # Exclude temporal and metadata fields
        excluded_fields = {
            'valid_from', 'valid_to', 'is_current', 'is_deleted', 
            'snapshot_hash', 'last_modified'
        }
        
        # Create stable representation
        filtered_props = {
            k: v for k, v in sorted(properties.items()) 
            if k not in excluded_fields and v is not None
        }
        
        # Convert to JSON and hash
        props_str = json.dumps(filtered_props, sort_keys=True, default=str)
        return hashlib.sha256(props_str.encode()).hexdigest()
    
    def fetch_existing_data(self, node_type: str) -> Dict[str, Dict]:
        """
        Fetch all current nodes of a specific type from Neo4j.
        Returns dict mapping hubspot_id -> node properties.
        """
        self.logger.info(f"Fetching existing {node_type} nodes from Neo4j")
        
        query = f"""
        MATCH (n:{node_type})
        WHERE n.is_current = true OR n.is_current IS NULL
        RETURN n.hubspot_id as id, properties(n) as props
        """
        
        existing_data = {}
        with self.driver.session() as session:
            result = session.run(query)
            for record in result:
                existing_data[record['id']] = record['props']
        
        self.logger.info(f"Found {len(existing_data)} existing {node_type} nodes")
        return existing_data
    
    def compare_records(
        self, 
        node_type: str,
        new_data: List[Dict], 
        existing_data: Dict[str, Dict]
    ) -> Dict[str, List]:
        """
        Compare new HubSpot data with existing Neo4j data.
        Returns dict with 'new', 'updated', 'unchanged', and 'deleted' records.
        """
        self.logger.info(f"Comparing {len(new_data)} new records with {len(existing_data)} existing records")
        
        changes = {
            'new': [],
            'updated': [],
            'unchanged': [],
            'deleted': []
        }
        
        new_ids = set()
        
        for record in new_data:
            record_id = str(record['hubspot_id'])
            new_ids.add(record_id)
            
            if record_id not in existing_data:
                # New record
                changes['new'].append(record)
            else:
                # Compare hashes
                new_hash = record.get('snapshot_hash', self.generate_property_hash(record))
                existing_hash = existing_data[record_id].get('snapshot_hash')
                
                # If existing node doesn't have a hash, compute one from its properties
                if not existing_hash:
                    existing_hash = self.generate_property_hash(existing_data[record_id])
                
                if new_hash != existing_hash:
                    changes['updated'].append({
                        'new': record,
                        'old': existing_data[record_id]
                    })
                else:
                    changes['unchanged'].append(record)
        
        # Find deleted records (in Neo4j but not in new data)
        existing_ids = set(existing_data.keys())
        deleted_ids = existing_ids - new_ids
        
        for deleted_id in deleted_ids:
            changes['deleted'].append({
                'hubspot_id': deleted_id,
                'old': existing_data[deleted_id]
            })
        
        self.logger.info(
            f"Changes for {node_type}: "
            f"{len(changes['new'])} new, "
            f"{len(changes['updated'])} updated, "
            f"{len(changes['unchanged'])} unchanged, "
            f"{len(changes['deleted'])} deleted"
        )
        
        return changes
    
    def fetch_existing_relationships(self, rel_type: str) -> Set[Tuple[str, str, str]]:
        """
        Fetch existing relationships from Neo4j.
        Returns set of (from_id, rel_type, to_id) tuples.
        """
        query = f"""
        MATCH (a)-[r:{rel_type}]->(b)
        WHERE a.hubspot_id IS NOT NULL AND b.hubspot_id IS NOT NULL
        RETURN a.hubspot_id as from_id, type(r) as rel_type, b.hubspot_id as to_id
        """
        
        relationships = set()
        with self.driver.session() as session:
            result = session.run(query)
            for record in result:
                relationships.add((
                    str(record['from_id']),
                    record['rel_type'],
                    str(record['to_id'])
                ))
        
        return relationships
    
    def detect_relationship_changes(
        self,
        new_relationships: List[Dict],
        existing_relationships: Set[Tuple[str, str, str]] = None
    ) -> Dict[str, List]:
        """
        Compare new relationships with existing ones.
        Returns dict with 'added' and 'removed' relationships.
        
        Only tracks mutable entity relationships (those with HubSpot IDs).
        Excludes immutable event relationships (those using email matching).
        """
        self.logger.info(f"Detecting relationship changes")
        
        # Filter to only trackable relationships (exclude immutable events)
        trackable_relationships = [
            rel for rel in new_relationships 
            if rel['type'] not in IMMUTABLE_EVENT_RELATIONSHIPS 
            and 'from_email' not in rel
        ]
        
        immutable_count = len(new_relationships) - len(trackable_relationships)
        if immutable_count > 0:
            self.logger.info(f"Skipping {immutable_count} immutable event relationships from change detection")
        
        # Convert trackable relationships to tuple format
        new_rel_set = set()
        for rel in trackable_relationships:
            from_id = rel.get('from_id')
            to_id = rel.get('to_id')
            
            if from_id and to_id:
                new_rel_set.add((
                    str(from_id),
                    rel['type'],
                    str(to_id)
                ))
            else:
                # Skip relationships without proper identifiers
                self.logger.debug(f"Skipping relationship without proper identifiers: {rel}")
        
        # If no existing relationships provided, fetch all trackable ones
        if existing_relationships is None:
            existing_relationships = set()
            # Build list for WHERE clause to exclude immutable types
            immutable_types_list = ', '.join([f"'{t}'" for t in IMMUTABLE_EVENT_RELATIONSHIPS])
            
            # Fetch only trackable relationship types (exclude immutable events)
            with self.driver.session() as session:
                result = session.run(f"""
                    MATCH (a)-[r]->(b)
                    WHERE a.hubspot_id IS NOT NULL 
                      AND b.hubspot_id IS NOT NULL
                      AND NOT type(r) IN [{immutable_types_list}]
                    RETURN a.hubspot_id as from_id, type(r) as rel_type, b.hubspot_id as to_id
                """)
                for record in result:
                    existing_relationships.add((
                        str(record['from_id']),
                        record['rel_type'],
                        str(record['to_id'])
                    ))
        
        changes = {
            'added': [],
            'removed': []
        }
        
        # Find added relationships
        added = new_rel_set - existing_relationships
        for rel_tuple in added:
            changes['added'].append({
                'from_id': rel_tuple[0],
                'type': rel_tuple[1],
                'to_id': rel_tuple[2]
            })
        
        # Find removed relationships
        removed = existing_relationships - new_rel_set
        for rel_tuple in removed:
            changes['removed'].append({
                'from_id': rel_tuple[0],
                'type': rel_tuple[1],
                'to_id': rel_tuple[2]
            })
        
        self.logger.info(
            f"Relationship changes: {len(changes['added'])} added, "
            f"{len(changes['removed'])} removed"
        )
        
        return changes
    
    def detect_all_changes(
        self, 
        nodes: Dict[str, List[Dict]], 
        relationships: List[Dict]
    ) -> Dict:
        """
        Detect all changes for nodes and relationships.
        Main orchestrator method.
        """
        self.logger.info("Starting comprehensive change detection")
        
        all_changes = {
            'nodes': {},
            'relationships': {}
        }
        
        # Process each node type
        for node_type, node_list in nodes.items():
            if node_list:
                existing_data = self.fetch_existing_data(node_type)
                changes = self.compare_records(node_type, node_list, existing_data)
                all_changes['nodes'][node_type] = changes
        
        # Process relationships
        all_changes['relationships'] = self.detect_relationship_changes(relationships)
        
        # Summary
        total_new = sum(len(c['new']) for c in all_changes['nodes'].values())
        total_updated = sum(len(c['updated']) for c in all_changes['nodes'].values())
        total_deleted = sum(len(c['deleted']) for c in all_changes['nodes'].values())
        
        self.logger.info(
            f"Change detection complete: "
            f"{total_new} new nodes, "
            f"{total_updated} updated nodes, "
            f"{total_deleted} deleted nodes, "
            f"{len(all_changes['relationships']['added'])} relationships added, "
            f"{len(all_changes['relationships']['removed'])} relationships removed"
        )
        
        return all_changes

