"""
Temporal Query Examples for HubSpot Data

This script provides example queries for working with temporal data in Neo4j.
Use these queries to explore historical changes, track entity evolution, and
analyze data modifications over time.

Usage:
    python query_temporal.py
"""

from neo4j import GraphDatabase
from config.settings import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
from utils.logger import setup_logger
from datetime import datetime, timedelta


class TemporalQueries:
    """Example queries for temporal data"""
    
    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )
    
    def close(self):
        """Close Neo4j connection"""
        self.driver.close()
    
    def get_current_contacts(self, limit=10):
        """Get current (active) contacts"""
        query = """
        MATCH (c:HUBSPOT_Contact)
        WHERE c.is_current = true AND (c.is_deleted IS NULL OR c.is_deleted = false)
        RETURN c.hubspot_id as id, c.email as email, 
               c.first_name as first_name, c.last_name as last_name,
               c.valid_from as valid_from
        ORDER BY c.valid_from DESC
        LIMIT $limit
        """
        
        with self.driver.session() as session:
            result = session.run(query, limit=limit)
            contacts = [dict(record) for record in result]
            
        self.logger.info(f"Found {len(contacts)} current contacts")
        return contacts
    
    def get_contact_history(self, contact_id):
        """Get full history for a specific contact"""
        query = """
        MATCH (c:HUBSPOT_Contact {hubspot_id: $contact_id})
        OPTIONAL MATCH (c)-[:HAS_HISTORY]->(h:HUBSPOT_Contact_HISTORY)
        RETURN c as current, collect(h) as history
        """
        
        with self.driver.session() as session:
            result = session.run(query, contact_id=contact_id)
            record = result.single()
            
        if record:
            current = dict(record['current'])
            history = [dict(h) for h in record['history']]
            self.logger.info(f"Contact {contact_id}: 1 current + {len(history)} historical versions")
            return {'current': current, 'history': history}
        else:
            self.logger.info(f"Contact {contact_id} not found")
            return None
    
    def get_deleted_entities(self, entity_type='HUBSPOT_Contact', limit=10):
        """Get deleted entities"""
        query = f"""
        MATCH (n:{entity_type})
        WHERE n.is_deleted = true
        RETURN n.hubspot_id as id, n.valid_to as deleted_at,
               properties(n) as properties
        ORDER BY n.valid_to DESC
        LIMIT $limit
        """
        
        with self.driver.session() as session:
            result = session.run(query, limit=limit)
            deleted = [dict(record) for record in result]
        
        self.logger.info(f"Found {len(deleted)} deleted {entity_type} entities")
        return deleted
    
    def get_recent_changes(self, hours=24, limit=50):
        """Get entities changed in the last N hours"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        query = """
        MATCH (n)
        WHERE n.valid_from IS NOT NULL
          AND n.valid_from > $cutoff_time
          AND (n.is_current = true OR n.is_current IS NULL)
        RETURN labels(n)[0] as entity_type, n.hubspot_id as id,
               n.valid_from as changed_at,
               n.is_deleted as is_deleted
        ORDER BY n.valid_from DESC
        LIMIT $limit
        """
        
        with self.driver.session() as session:
            result = session.run(query, cutoff_time=cutoff_time, limit=limit)
            changes = [dict(record) for record in result]
        
        self.logger.info(f"Found {len(changes)} changes in the last {hours} hours")
        return changes
    
    def get_relationship_changes(self, limit=20):
        """Get recent relationship changes with properties"""
        query = """
        MATCH (rc:HUBSPOT_RelationshipChange)
        RETURN rc.change_type as change_type,
               rc.from_entity_type as from_type,
               rc.from_entity_id as from_id,
               rc.relationship_type as rel_type,
               rc.to_entity_type as to_type,
               rc.to_entity_id as to_id,
               rc.relationship_properties as properties,
               rc.changed_at as changed_at
        ORDER BY rc.changed_at DESC
        LIMIT $limit
        """
        
        with self.driver.session() as session:
            result = session.run(query, limit=limit)
            changes = [dict(record) for record in result]
        
        self.logger.info(f"Found {len(changes)} relationship changes")
        return changes
    
    def get_entity_relationship_history(self, entity_type, entity_id):
        """Get complete relationship change history for a specific entity"""
        query = """
        MATCH (rc:HUBSPOT_RelationshipChange)
        WHERE (rc.from_entity_type = $entity_type AND rc.from_entity_id = $entity_id)
           OR (rc.to_entity_type = $entity_type AND rc.to_entity_id = $entity_id)
        RETURN rc.change_type as change_type,
               rc.from_entity_type as from_type,
               rc.from_entity_id as from_id,
               rc.relationship_type as rel_type,
               rc.to_entity_type as to_type,
               rc.to_entity_id as to_id,
               rc.relationship_properties as properties,
               rc.changed_at as changed_at
        ORDER BY rc.changed_at ASC
        """
        
        with self.driver.session() as session:
            result = session.run(query, entity_type=entity_type, entity_id=entity_id)
            changes = [dict(record) for record in result]
        
        self.logger.info(f"Found {len(changes)} relationship changes for {entity_type} {entity_id}")
        return changes
    
    def get_ownership_changes(self, entity_type, entity_id=None):
        """Track ownership changes (OWNED_BY relationships)"""
        query = """
        MATCH (rc:HUBSPOT_RelationshipChange)
        WHERE rc.relationship_type = 'OWNED_BY'
          AND rc.from_entity_type = $entity_type
        """
        
        params = {'entity_type': entity_type}
        
        if entity_id:
            query += " AND rc.from_entity_id = $entity_id"
            params['entity_id'] = entity_id
        
        query += """
        RETURN rc.from_entity_id as entity_id,
               rc.change_type as change_type,
               rc.to_entity_id as owner_id,
               rc.changed_at as changed_at
        ORDER BY rc.changed_at ASC
        """
        
        with self.driver.session() as session:
            result = session.run(query, **params)
            changes = [dict(record) for record in result]
        
        if entity_id:
            self.logger.info(f"Found {len(changes)} ownership changes for {entity_type} {entity_id}")
        else:
            self.logger.info(f"Found {len(changes)} ownership changes for {entity_type}")
        return changes
    
    def get_relationship_change_statistics(self):
        """Get statistics about relationship changes"""
        query = """
        MATCH (rc:HUBSPOT_RelationshipChange)
        RETURN rc.relationship_type as rel_type,
               rc.change_type as change_type,
               count(*) as count
        ORDER BY count DESC
        """
        
        with self.driver.session() as session:
            result = session.run(query)
            stats = [dict(record) for record in result]
        
        self.logger.info(f"Retrieved relationship change statistics")
        return stats
    
    def compare_entity_versions(self, entity_type, entity_id):
        """Compare current version with most recent historical version"""
        query = f"""
        MATCH (n:{entity_type} {{hubspot_id: $entity_id}})
        OPTIONAL MATCH (n)-[:HAS_HISTORY]->(h:{entity_type}_HISTORY)
        WITH n, h
        ORDER BY h.valid_to DESC
        RETURN n as current, collect(h)[0] as previous
        """
        
        with self.driver.session() as session:
            result = session.run(query, entity_id=entity_id)
            record = result.single()
        
        if not record:
            self.logger.info(f"Entity {entity_type} {entity_id} not found")
            return None
        
        current = dict(record['current']) if record['current'] else None
        previous = dict(record['previous']) if record['previous'] else None
        
        if current and previous:
            # Find changed fields
            changed_fields = []
            for key in current.keys():
                if key not in ['valid_from', 'valid_to', 'snapshot_hash']:
                    if key not in previous or current[key] != previous[key]:
                        changed_fields.append({
                            'field': key,
                            'old_value': previous.get(key),
                            'new_value': current.get(key)
                        })
            
            self.logger.info(f"Found {len(changed_fields)} changed fields")
            return {
                'current': current,
                'previous': previous,
                'changed_fields': changed_fields
            }
        else:
            self.logger.info("No previous version found for comparison")
            return {'current': current, 'previous': None, 'changed_fields': []}
    
    def get_entity_lifecycle(self, entity_type, entity_id):
        """Get complete lifecycle timeline for an entity"""
        query = f"""
        MATCH (n:{entity_type} {{hubspot_id: $entity_id}})
        OPTIONAL MATCH (n)-[:HAS_HISTORY]->(h:{entity_type}_HISTORY)
        WITH n, collect(h) as history
        RETURN {{
            current: n,
            history: history,
            version_count: size(history) + 1,
            created_at: n.created_date,
            first_tracked: n.valid_from,
            is_deleted: coalesce(n.is_deleted, false)
        }} as lifecycle
        """
        
        with self.driver.session() as session:
            result = session.run(query, entity_id=entity_id)
            record = result.single()
        
        if record:
            lifecycle = record['lifecycle']
            self.logger.info(
                f"Entity lifecycle: {lifecycle['version_count']} versions, "
                f"deleted: {lifecycle['is_deleted']}"
            )
            return lifecycle
        else:
            self.logger.info(f"Entity {entity_type} {entity_id} not found")
            return None
    
    def get_temporal_statistics(self):
        """Get statistics about temporal data"""
        stats = {}
        
        entity_types = [
            'HUBSPOT_Contact', 'HUBSPOT_Company', 'HUBSPOT_Deal',
            'HUBSPOT_Activity', 'HUBSPOT_User'
        ]
        
        with self.driver.session() as session:
            for entity_type in entity_types:
                # Current entities
                result = session.run(
                    f"MATCH (n:{entity_type}) WHERE n.is_current = true RETURN count(n) as count"
                )
                current = result.single()['count']
                
                # Historical versions
                result = session.run(
                    f"MATCH (h:{entity_type}_HISTORY) RETURN count(h) as count"
                )
                history = result.single()['count']
                
                # Deleted
                result = session.run(
                    f"MATCH (n:{entity_type}) WHERE n.is_deleted = true RETURN count(n) as count"
                )
                deleted = result.single()['count']
                
                stats[entity_type] = {
                    'current': current,
                    'historical_versions': history,
                    'deleted': deleted,
                    'total_versions': current + history
                }
            
            # Relationship changes
            result = session.run(
                "MATCH (rc:HUBSPOT_RelationshipChange) RETURN count(rc) as count"
            )
            stats['relationship_changes'] = result.single()['count']
        
        self.logger.info("Temporal statistics retrieved")
        return stats


def main():
    """Main entry point for example usage"""
    print("=" * 70)
    print("TEMPORAL QUERY EXAMPLES")
    print("=" * 70)
    print()
    
    queries = TemporalQueries()
    
    try:
        # Example 1: Get current contacts
        print("\n1. Current Contacts (last 5):")
        print("-" * 70)
        contacts = queries.get_current_contacts(limit=5)
        for contact in contacts:
            print(f"  {contact['id']}: {contact['first_name']} {contact['last_name']} ({contact['email']})")
            print(f"    Valid from: {contact['valid_from']}")
        
        # Example 2: Get temporal statistics
        print("\n2. Temporal Statistics:")
        print("-" * 70)
        stats = queries.get_temporal_statistics()
        for entity_type, entity_stats in stats.items():
            if entity_type != 'relationship_changes':
                print(f"\n  {entity_type}:")
                print(f"    Current: {entity_stats['current']}")
                print(f"    Historical versions: {entity_stats['historical_versions']}")
                print(f"    Deleted: {entity_stats['deleted']}")
        print(f"\n  Relationship changes tracked: {stats['relationship_changes']}")
        
        # Example 3: Recent changes
        print("\n3. Recent Changes (last 24 hours):")
        print("-" * 70)
        changes = queries.get_recent_changes(hours=24, limit=10)
        if changes:
            for change in changes:
                status = "DELETED" if change.get('is_deleted') else "UPDATED/NEW"
                print(f"  {change['entity_type']} {change['id']}: {status} at {change['changed_at']}")
        else:
            print("  No recent changes")
        
        # Example 4: Deleted entities
        print("\n4. Recently Deleted Contacts:")
        print("-" * 70)
        deleted = queries.get_deleted_entities('HUBSPOT_Contact', limit=5)
        if deleted:
            for entity in deleted:
                print(f"  {entity['id']}: Deleted at {entity['deleted_at']}")
        else:
            print("  No deleted contacts")
        
        # Example 5: Relationship changes
        print("\n5. Recent Relationship Changes:")
        print("-" * 70)
        rel_changes = queries.get_relationship_changes(limit=5)
        if rel_changes:
            for change in rel_changes:
                props_str = ""
                if change.get('properties') and change['properties']:
                    props_str = f" (props: {change['properties']})"
                print(f"  {change['change_type'].upper()}: "
                      f"{change['from_type']}({change['from_id']}) "
                      f"-[{change['rel_type']}]-> "
                      f"{change['to_type']}({change['to_id']}){props_str} "
                      f"at {change['changed_at']}")
        else:
            print("  No relationship changes")
        
        # Example 6: Relationship change statistics
        print("\n6. Relationship Change Statistics:")
        print("-" * 70)
        rel_stats = queries.get_relationship_change_statistics()
        if rel_stats:
            for stat in rel_stats[:10]:  # Top 10
                print(f"  {stat['rel_type']} ({stat['change_type']}): {stat['count']} changes")
        else:
            print("  No relationship changes tracked yet")
        
        print("\n" + "=" * 70)
        print("Query examples complete!")
        print("=" * 70)
        print("\nTip: Use these query methods in your own scripts for custom analysis")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        queries.close()


if __name__ == "__main__":
    main()


