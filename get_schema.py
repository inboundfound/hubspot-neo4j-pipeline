#!/usr/bin/env python3
"""Extract complete Neo4j schema for analysis"""

from neo4j import GraphDatabase
from config.settings import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
import json

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

schema = {
    "node_labels": {},
    "relationship_types": {},
    "constraints": [],
    "indexes": [],
    "sample_nodes": {},
    "sample_relationships": {}
}

with driver.session() as session:
    # Get all node labels with counts and sample properties
    print("Extracting node labels...")
    result = session.run('CALL db.labels()')
    labels = [record['label'] for record in result]

    for label in labels:
        result = session.run(f'MATCH (n:`{label}`) RETURN count(n) as count')
        count = next(result)['count']

        # Get sample properties
        result = session.run(f'MATCH (n:`{label}`) RETURN n LIMIT 1')
        sample = next(result, None)
        props = list(sample['n'].keys()) if sample else []

        schema["node_labels"][label] = {
            "count": count,
            "properties": props
        }

        # Get a full sample node
        if sample:
            schema["sample_nodes"][label] = dict(sample['n'])

    # Get all relationship types with counts
    print("Extracting relationship types...")
    result = session.run('CALL db.relationshipTypes()')
    rel_types = [record['relationshipType'] for record in result]

    for rel_type in rel_types:
        result = session.run(f'MATCH ()-[r:`{rel_type}`]->() RETURN count(r) as count')
        count = next(result)['count']

        # Get sample with start/end node labels
        result = session.run(f'''
            MATCH (a)-[r:`{rel_type}`]->(b)
            RETURN labels(a) as from_labels, labels(b) as to_labels, r
            LIMIT 1
        ''')
        sample = next(result, None)

        schema["relationship_types"][rel_type] = {
            "count": count,
            "from_labels": sample['from_labels'] if sample else [],
            "to_labels": sample['to_labels'] if sample else [],
            "properties": list(sample['r'].keys()) if sample else []
        }

        if sample:
            schema["sample_relationships"][rel_type] = {
                "from_labels": sample['from_labels'],
                "to_labels": sample['to_labels'],
                "properties": dict(sample['r'])
            }

    # Get constraints
    print("Extracting constraints...")
    result = session.run('SHOW CONSTRAINTS')
    for record in result:
        schema["constraints"].append({
            "name": record.get('name'),
            "type": record.get('type'),
            "entityType": record.get('entityType'),
            "labelsOrTypes": record.get('labelsOrTypes'),
            "properties": record.get('properties')
        })

    # Get indexes
    print("Extracting indexes...")
    result = session.run('SHOW INDEXES')
    for record in result:
        schema["indexes"].append({
            "name": record.get('name'),
            "type": record.get('type'),
            "entityType": record.get('entityType'),
            "labelsOrTypes": record.get('labelsOrTypes'),
            "properties": record.get('properties')
        })

driver.close()

# Print formatted output
print("\n" + "="*80)
print("NEO4J SCHEMA ANALYSIS")
print("="*80)

print("\n📊 NODE LABELS:")
print("-"*80)
for label, info in sorted(schema["node_labels"].items()):
    print(f"\n{label}: {info['count']:,} nodes")
    print(f"  Properties: {', '.join(info['properties'][:10])}")
    if len(info['properties']) > 10:
        print(f"  ... and {len(info['properties']) - 10} more")

print("\n\n🔗 RELATIONSHIP TYPES:")
print("-"*80)
for rel_type, info in sorted(schema["relationship_types"].items()):
    from_label = '+'.join(info['from_labels']) if info['from_labels'] else '?'
    to_label = '+'.join(info['to_labels']) if info['to_labels'] else '?'
    print(f"\n({from_label})-[:{rel_type}]->({to_label}): {info['count']:,}")
    if info['properties']:
        print(f"  Properties: {', '.join(info['properties'])}")

print("\n\n🔒 CONSTRAINTS:")
print("-"*80)
for constraint in schema["constraints"]:
    labels = '+'.join(constraint['labelsOrTypes']) if constraint['labelsOrTypes'] else '?'
    props = ', '.join(constraint['properties']) if constraint['properties'] else '?'
    print(f"{constraint['type']}: {labels}({props})")

print("\n\n📇 INDEXES:")
print("-"*80)
for index in schema["indexes"]:
    if index['type'] != 'LOOKUP':  # Skip default lookup indexes
        labels = '+'.join(index['labelsOrTypes']) if index['labelsOrTypes'] else '?'
        props = ', '.join(index['properties']) if index['properties'] else '?'
        print(f"{index['type']}: {labels}({props})")

print("\n\n💾 SAMPLE NODES:")
print("-"*80)
for label, sample in list(schema["sample_nodes"].items())[:3]:
    print(f"\n{label}:")
    for key, value in list(sample.items())[:5]:
        val_str = str(value)[:60] + '...' if len(str(value)) > 60 else str(value)
        print(f"  {key}: {val_str}")

# Save to file
with open('schema_export.json', 'w') as f:
    json.dump(schema, f, indent=2, default=str)

print("\n\n✅ Full schema saved to schema_export.json")
