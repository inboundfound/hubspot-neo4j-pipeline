# Temporal Data Tracking

## Overview

The HubSpot Neo4j pipeline now includes comprehensive temporal data tracking. This system maintains a complete audit trail of all changes to HubSpot data, including property updates, deletions, and relationship modifications.

## Architecture

### Audit Log Pattern

- **Current State**: Main entity nodes (e.g., `HUBSPOT_Contact`) store the current/active version
- **Historical State**: Separate history nodes (e.g., `HUBSPOT_Contact_HISTORY`) store full snapshots of previous versions
- **Change Tracking**: `HUBSPOT_RelationshipChange` nodes track association additions and removals

### Temporal Fields

All entity nodes include:
- `valid_from`: Timestamp when this version became active
- `valid_to`: Timestamp when superseded (null for current)
- `is_current`: Boolean flag for active version
- `is_deleted`: Boolean flag for soft-deleted records
- `snapshot_hash`: Hash of properties for change detection

## Components

### 1. Change Detector (`utils/change_detector.py`)

Compares HubSpot data with existing Neo4j state to identify:
- New records
- Updated records (property changes)
- Deleted records
- Relationship changes

### 2. Graph Transformer (`transformers/graph_transformer.py`)

Enhanced to automatically add temporal fields to all transformed nodes.

### 3. Temporal Loader (`loaders/temporal_loader.py`)

Replaces the standard Neo4j loader with temporal-aware loading:
- Creates history snapshots before updates
- Soft-deletes missing records
- Tracks relationship changes

### 4. Schema Updates (`config/neo4j_schema.py`)

Added:
- Temporal field indexes for efficient querying
- History node constraints
- Composite unique constraints on `(hubspot_id, valid_from)`

## Usage

### First-Time Setup

Before using temporal tracking for the first time, initialize existing data:

```bash
python scripts/initialize_temporal_data.py
```

This one-time script adds temporal fields to all existing nodes in Neo4j.

### Running the Pipeline

The main pipeline now uses temporal tracking automatically:

```bash
python main.py
```

On subsequent runs, the system will:
1. Detect changes since last run
2. Create history snapshots for modified records
3. Update current state
4. Mark deleted records (soft delete)
5. Track relationship changes

### Querying Temporal Data

Use the query helper script for examples:

```bash
python query_temporal.py
```

#### Get Current State

```cypher
MATCH (n:HUBSPOT_Contact)
WHERE n.is_current = true AND (n.is_deleted IS NULL OR n.is_deleted = false)
RETURN n
```

#### Get Entity History

```cypher
MATCH (c:HUBSPOT_Contact {hubspot_id: "12345"})
OPTIONAL MATCH (c)-[:HAS_HISTORY]->(h:HUBSPOT_Contact_HISTORY)
RETURN c as current, collect(h) as history
ORDER BY h.valid_from DESC
```

#### Find Deleted Entities

```cypher
MATCH (n:HUBSPOT_Contact)
WHERE n.is_deleted = true
RETURN n.hubspot_id, n.valid_to as deleted_at
ORDER BY n.valid_to DESC
```

#### Track Recent Changes

```cypher
MATCH (n)
WHERE n.valid_from > datetime() - duration('P1D')
AND n.is_current = true
RETURN labels(n)[0] as type, n.hubspot_id as id, n.valid_from
ORDER BY n.valid_from DESC
```

#### View Relationship Changes

```cypher
MATCH (rc:HUBSPOT_RelationshipChange)
WHERE rc.changed_at > datetime() - duration('P7D')
RETURN rc.change_type, rc.from_entity_type, rc.relationship_type, 
       rc.to_entity_type, rc.changed_at
ORDER BY rc.changed_at DESC
```

#### Compare Versions

```cypher
MATCH (c:HUBSPOT_Contact {hubspot_id: "12345"})
OPTIONAL MATCH (c)-[:HAS_HISTORY]->(h:HUBSPOT_Contact_HISTORY)
WITH c, h
ORDER BY h.valid_to DESC
RETURN c as current, collect(h)[0] as previous
```

## Data Model

### Entity Nodes (Current State)

```
(:HUBSPOT_Contact {
  hubspot_id: "12345",
  email: "john@example.com",
  first_name: "John",
  last_name: "Doe",
  // ... other properties ...
  valid_from: datetime("2025-11-18T10:00:00Z"),
  valid_to: null,
  is_current: true,
  is_deleted: false,
  snapshot_hash: "abc123..."
})
```

### History Nodes

```
(:HUBSPOT_Contact_HISTORY {
  hubspot_id: "12345",
  email: "john@oldexample.com",  // Old value
  first_name: "John",
  // ... snapshot of all properties at this point in time ...
  valid_from: datetime("2025-11-01T10:00:00Z"),
  valid_to: datetime("2025-11-18T10:00:00Z"),
  snapshot_hash: "xyz789..."
})
```

### Relationship Changes

```
(:HUBSPOT_RelationshipChange {
  change_type: "added",  // or "removed"
  from_entity_type: "HUBSPOT_Contact",
  from_entity_id: "12345",
  relationship_type: "OWNED_BY",
  to_entity_type: "HUBSPOT_User",
  to_entity_id: "67890",
  changed_at: datetime("2025-11-18T10:00:00Z")
})
```

### History Relationships

```
(current:HUBSPOT_Contact)-[:HAS_HISTORY]->(history:HUBSPOT_Contact_HISTORY)
```

## Benefits

1. **Audit Trail**: Complete record of all changes for compliance and debugging
2. **Point-in-Time Queries**: Query data as it existed at any point in time
3. **Change Analysis**: Track how entities evolve over time
4. **Soft Deletes**: Deleted records remain queryable with full history
5. **Relationship Tracking**: Know when associations were created or removed
6. **Data Recovery**: Restore previous versions if needed

## Performance Considerations

- History nodes accumulate over time (plan for growth)
- Temporal indexes optimize query performance
- First load initializes all nodes (one-time overhead)
- Subsequent loads only process changes (incremental)
- Batch processing minimizes transaction overhead

## Best Practices

1. **Run initialization once** before enabling temporal tracking
2. **Regular backups** of Neo4j database (history is valuable)
3. **Monitor history node growth** and plan archival strategy
4. **Use temporal queries** to understand data evolution
5. **Leverage soft deletes** instead of purging data
6. **Index temporal fields** for query performance

## Troubleshooting

### Issue: "No temporal fields on existing nodes"
**Solution**: Run `python scripts/initialize_temporal_data.py`

### Issue: "History not being created"
**Solution**: Verify TemporalLoader is being used in main.py

### Issue: "Slow temporal queries"
**Solution**: Ensure temporal indexes are created (check neo4j_schema.py)

### Issue: "Duplicate history entries"
**Solution**: Check that initialization was only run once

## Future Enhancements

Potential additions:
- Automatic history archival (move old versions to cold storage)
- Time-travel queries (query state at specific timestamp)
- Change notifications (alert on specific entity changes)
- History compression (reduce storage for old versions)
- Differential snapshots (store only changed fields)

## Files Modified/Created

### Created
- `utils/change_detector.py` - Change detection logic
- `loaders/temporal_loader.py` - Temporal-aware data loading
- `scripts/initialize_temporal_data.py` - One-time initialization
- `query_temporal.py` - Example temporal queries
- `docs/TEMPORAL_DATA_TRACKING.md` - This documentation

### Modified
- `transformers/graph_transformer.py` - Added temporal fields to all entities
- `config/neo4j_schema.py` - Added temporal indexes and constraints
- `main.py` - Integrated TemporalLoader

## Support

For issues or questions:
1. Check this documentation
2. Review example queries in `query_temporal.py`
3. Examine logs for error details
4. Verify schema setup in Neo4j Browser


