# Relationship Temporal Tracking

## Overview

This document describes the **hybrid approach** to relationship temporal tracking in the HubSpot → Neo4j pipeline. This design maintains a clean, performant current-state graph while preserving complete historical information about relationship changes.

---

## Architecture Philosophy

### Why Hybrid Approach?

We evaluated three approaches and chose the hybrid model:

#### ❌ Approach 1: No History
- **Problem**: Lost visibility into relationship changes
- **Use Case**: Only works if you never need to know "what changed when"

#### ❌ Approach 2: Temporal Properties on Relationships
```cypher
(Contact)-[WORKS_AT {
  valid_from: '2024-01-01',
  valid_to: '2024-06-01',
  is_current: false
}]->(Company)
```
- **Problem**: Every query needs `WHERE r.is_current = true`
- **Problem**: Performance degradation on all traversals
- **Problem**: Deleted relationships clutter the graph

#### ✅ Approach 3: Hybrid - Separate Change Nodes (CHOSEN)
```cypher
// Current state (clean, fast queries)
(Contact)-[WORKS_AT]->(Company)

// Change history (separate audit trail)
(RelationshipChange {
  change_type: 'added',
  from_entity_type: 'HUBSPOT_Contact',
  from_entity_id: '12345',
  to_entity_type: 'HUBSPOT_Company',
  to_entity_id: '67890',
  relationship_type: 'WORKS_AT',
  relationship_properties: {...},
  changed_at: '2024-11-19T01:00:00Z'
})
```

**Benefits:**
- ✅ Current graph stays clean and fast (no filtering needed)
- ✅ Historical data preserved in separate nodes
- ✅ Relationship properties captured
- ✅ Consistent with node history pattern (`_HISTORY` nodes)
- ✅ Neo4j-optimized design

---

## Data Model

### Current State Graph

The operational graph contains only **current, active relationships**:

```cypher
// Example: Contact works at Company
(c:HUBSPOT_Contact {hubspot_id: "12345"})
  -[r:WORKS_AT]->
(co:HUBSPOT_Company {hubspot_id: "67890"})
```

**Key Properties:**
- No temporal filtering required
- Fast traversals
- Clean visualization
- Same structure as before temporal tracking

### Change History Nodes

All relationship changes are tracked in `HUBSPOT_RelationshipChange` nodes:

```cypher
(:HUBSPOT_RelationshipChange {
  change_type: 'added' | 'removed',
  from_entity_type: 'HUBSPOT_Contact',
  from_entity_id: '12345',
  to_entity_type: 'HUBSPOT_Company',
  to_entity_id: '67890',
  relationship_type: 'WORKS_AT',
  relationship_properties: {
    timestamp: '2024-01-15',
    source: 'direct'
  },
  changed_at: '2024-11-19T01:06:21.552Z'
})
```

**Node Properties:**

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `change_type` | String | `'added'` or `'removed'` | `'added'` |
| `from_entity_type` | String | Source node label | `'HUBSPOT_Contact'` |
| `from_entity_id` | String | Source HubSpot ID | `'12345'` |
| `to_entity_type` | String | Target node label | `'HUBSPOT_Company'` |
| `to_entity_id` | String | Target HubSpot ID | `'67890'` |
| `relationship_type` | String | Cypher relationship type | `'WORKS_AT'` |
| `relationship_properties` | Map | Original relationship properties | `{timestamp: '...'}` |
| `changed_at` | DateTime | When the change was detected | `'2024-11-19T01:06:21.552Z'` |

---

## Relationship Types and Tracking Status

### Tracked Relationships (Mutable Entity Relationships)

These relationships use **HubSpot IDs** and can change over time, making them suitable for temporal tracking:

**Contact Relationships:**
- `OWNED_BY` (Contact → User) - Ownership changes
- `WORKS_AT` (Contact → Company) - Employment changes  
- `ASSOCIATED_WITH` (Contact ↔ Deal) - Deal associations

**Company Relationships:**
- `OWNED_BY` (Company → User) - Ownership changes

**Deal Relationships:**
- `OWNED_BY` (Deal → User) - Ownership changes
- `BELONGS_TO` (Deal → Company) - Deal-company relationships
- `ASSOCIATED_WITH` (Deal ↔ Contact) - Contact associations

**Activity (Engagement) Relationships:**
- `INVOLVES` (Activity → Contact) - Engagement participants
- `INVOLVES` (Activity → Company) - Company involvement
- `RELATED_TO` (Activity → Deal) - Engagement-deal associations

**Change tracking:** ✅ Full temporal tracking with `HUBSPOT_RelationshipChange` nodes

---

### Not Tracked (Immutable Event Relationships)

These are **historical events that never change** once created. They use **email matching** instead of HubSpot IDs, making change detection unreliable and unnecessary:

**Email Event Relationships:**
- `PERFORMED` (Contact → EmailOpenEvent/EmailClickEvent) - Email interactions (email-based)
- `FOR_CAMPAIGN` (EmailEvent → EmailCampaign) - Campaign associations

**Form Submission Relationships:**
- `SUBMITTED_BY` (FormSubmission → Contact) - Form submissions (email-based)
- `ON_PAGE` (FormSubmission → WebPage) - Submission pages

**Web Activity:**
- `VISITED` (Contact → WebPage) - Page visits
- `CLICKED_URL` (EmailClickEvent → WebPage) - Clicked URLs

**Change tracking:** ❌ None - these are immutable events, not changeable relationships

**Why not tracked:**
1. **Immutable by nature** - Events are historical facts that don't change
2. **Email-based matching** - Uses email addresses, not HubSpot IDs (unreliable)
3. **No business value** - Tracking "changes" in historical events is conceptually incorrect
4. **Performance** - Eliminates 60,000+ false positive comparisons per sync

### Missing Node Handling

Relationships are only tracked if **both nodes exist** in the database. If a relationship references a missing node (e.g., a user that wasn't extracted or a deleted entity), it is:
- **Not loaded** into the graph (the Cypher MATCH fails)
- **Not tracked** as a change (filtered out before change detection)
- **Logged as a warning** for visibility

This prevents false positives from relationships that can't be created due to missing referenced entities.

### Archived User Handling

The pipeline extracts **both active and archived (deactivated) users** from HubSpot to maintain complete ownership history:

**Extraction:**
- **Active users**: Fetched with `archived=false`
- **Archived users**: Fetched with `archived=true` 
- **Combined**: Both sets are merged into the dataset

**Neo4j Representation:**
- **Labels**: Archived users have **both** `HUBSPOT_User` and `Archived` labels
- **Properties**: `archived=true` and `active=false` for archived users
- **Queries**: Easy to filter - `MATCH (u:HUBSPOT_User) WHERE NOT u:Archived` for active only

**Why include archived users?**
1. **Complete ownership history**: Entities retain owner references even after users are deactivated
2. **Historical accuracy**: Prevents broken `OWNED_BY` relationships
3. **Audit trail**: Shows who owned what, even if they no longer work there
4. **Clear distinction**: The `Archived` label makes it obvious these are former users

**Example query for active users only:**
```cypher
MATCH (c:HUBSPOT_Contact)-[:OWNED_BY]->(u:HUBSPOT_User)
WHERE NOT u:Archived
RETURN c, u
```

---

## Relationship Properties Preserved

Most tracked relationships have **empty properties** (`{}`). The hybrid approach captures any relationship properties in the `HUBSPOT_RelationshipChange` nodes when relationships are added or removed.

**Note:** Immutable event relationships (like `VISITED`, `PERFORMED`, etc.) are not tracked for changes, so their properties remain only on the relationships themselves, not in change history nodes.

### Future Considerations

The architecture supports adding properties to any relationship type:

```cypher
// Example: Deal stage when associated
{
  associated_stage: 'qualification',
  associated_date: '2024-01-15'
}
```

These properties will automatically be captured in change tracking.

---

## Change Detection Algorithm

### Process Flow

```
1. Extract current data from HubSpot
   ↓
2. Transform into nodes and relationships
   ↓
3. Compare with existing Neo4j data
   ↓
4. Detect changes:
   - New relationships (not in Neo4j)
   - Removed relationships (in Neo4j, not in HubSpot)
   ↓
5. Track changes:
   - Create HUBSPOT_RelationshipChange nodes
   - Add new relationships to graph
   - Remove deleted relationships from graph
```

### Comparison Logic

Relationships are considered **identical** if they match on:
- `from_id` (source entity HubSpot ID)
- `to_id` (target entity HubSpot ID)
- `type` (relationship type, e.g., `WORKS_AT`)

**Note:** Properties are NOT used for comparison. A relationship is either present or absent.

### Special Case: Email-Based Relationships

Email events use `from_email` instead of `from_id` for contact matching:

```python
{
  'type': 'PERFORMED',
  'from_type': 'HUBSPOT_Contact',
  'from_email': 'john@example.com',  # ← Email instead of ID
  'to_type': 'HUBSPOT_EmailOpenEvent',
  'to_id': 'event_123',
  'properties': {}
}
```

These are **excluded from change detection** because:
1. Email matching is probabilistic (contact might not exist yet)
2. Events are immutable (never updated after creation)
3. They represent historical actions, not current state

---

## Query Examples

### 1. Get All Relationship Changes

```cypher
MATCH (rc:HUBSPOT_RelationshipChange)
RETURN rc.change_type AS change,
       rc.from_entity_type AS from_type,
       rc.from_entity_id AS from_id,
       rc.to_entity_type AS to_type,
       rc.to_entity_id AS to_id,
       rc.relationship_type AS rel_type,
       rc.changed_at AS when
ORDER BY rc.changed_at DESC
LIMIT 100;
```

### 2. Track Ownership Changes for a Contact

```cypher
MATCH (rc:HUBSPOT_RelationshipChange)
WHERE rc.from_entity_type = 'HUBSPOT_Contact'
  AND rc.from_entity_id = '12345'
  AND rc.relationship_type = 'OWNED_BY'
RETURN rc.change_type AS change,
       rc.to_entity_id AS owner_id,
       rc.changed_at AS when
ORDER BY rc.changed_at;
```

**Sample Output:**
```
change  | owner_id | when
--------|----------|---------------------
'added' | 'user_1' | 2024-01-15T10:00:00Z
'removed'|'user_1' | 2024-06-01T14:30:00Z
'added' | 'user_2' | 2024-06-01T14:30:00Z
```

### 3. Find Recently Removed Relationships

```cypher
MATCH (rc:HUBSPOT_RelationshipChange)
WHERE rc.change_type = 'removed'
  AND rc.changed_at > datetime() - duration('P7D')  // Last 7 days
RETURN rc.from_entity_type AS from_type,
       rc.from_entity_id AS from_id,
       rc.relationship_type AS rel_type,
       rc.to_entity_type AS to_type,
       rc.to_entity_id AS to_id,
       rc.changed_at AS when
ORDER BY rc.changed_at DESC;
```

### 4. Audit Trail for a Deal's Company Associations

```cypher
MATCH (rc:HUBSPOT_RelationshipChange)
WHERE rc.from_entity_type = 'HUBSPOT_Deal'
  AND rc.from_entity_id = '54321'
  AND rc.relationship_type = 'BELONGS_TO'
  AND rc.to_entity_type = 'HUBSPOT_Company'
RETURN rc.change_type AS change,
       rc.to_entity_id AS company_id,
       rc.changed_at AS when
ORDER BY rc.changed_at;
```

### 5. Get Relationship Properties from History

```cypher
MATCH (rc:HUBSPOT_RelationshipChange)
WHERE rc.from_entity_id = '12345'
  AND rc.relationship_type = 'VISITED'
RETURN rc.change_type AS change,
       rc.to_entity_id AS page_url,
       rc.relationship_properties.timestamp AS visit_time,
       rc.relationship_properties.source AS traffic_source,
       rc.changed_at AS detected_at
ORDER BY rc.relationship_properties.timestamp DESC;
```

### 6. Reconstruct Relationship State at a Point in Time

```cypher
// Get all relationships that existed on 2024-06-01
MATCH (rc:HUBSPOT_RelationshipChange)
WHERE rc.from_entity_type = 'HUBSPOT_Contact'
  AND rc.from_entity_id = '12345'
WITH rc
ORDER BY rc.changed_at

// Logic: Add all 'added' before date, subtract all 'removed' before date
WITH collect({
  type: rc.change_type,
  rel_type: rc.relationship_type,
  to_id: rc.to_entity_id,
  when: rc.changed_at
}) AS changes

// Process changes chronologically
// (Implement in application code for complex reconstruction)
RETURN changes;
```

### 7. Count Relationship Changes by Type

```cypher
MATCH (rc:HUBSPOT_RelationshipChange)
RETURN rc.relationship_type AS rel_type,
       rc.change_type AS change_type,
       count(*) AS count
ORDER BY count DESC;
```

### 8. Find Entities with Most Relationship Changes

```cypher
MATCH (rc:HUBSPOT_RelationshipChange)
WITH rc.from_entity_type AS entity_type,
     rc.from_entity_id AS entity_id,
     count(*) AS change_count
ORDER BY change_count DESC
LIMIT 10
RETURN entity_type, entity_id, change_count;
```

---

## Performance Considerations

### Indexes

All critical fields on `HUBSPOT_RelationshipChange` are indexed:

```cypher
CREATE INDEX hubspot_rel_change_timestamp 
  FOR (rc:HUBSPOT_RelationshipChange) ON (rc.changed_at);

CREATE INDEX hubspot_rel_change_type 
  FOR (rc:HUBSPOT_RelationshipChange) ON (rc.change_type);

CREATE INDEX hubspot_rel_change_from_entity 
  FOR (rc:HUBSPOT_RelationshipChange) ON (rc.from_entity_id);

CREATE INDEX hubspot_rel_change_to_entity 
  FOR (rc:HUBSPOT_RelationshipChange) ON (rc.to_entity_id);

CREATE INDEX hubspot_rel_change_rel_type 
  FOR (rc:HUBSPOT_RelationshipChange) ON (rc.relationship_type);
```

### Query Performance

**Operational Queries (Current State):**
- ✅ **No impact** - queries on current relationships work exactly as before
- ✅ No `WHERE is_current = true` filtering needed
- ✅ Fast traversals, no temporal overhead

**Historical Queries (Audit Trail):**
- ⚠️ Scoped queries (specific entity/time range) are fast with indexes
- ⚠️ Full reconstructions can be slow for large datasets
- 💡 Consider archiving old changes if audit retention exceeds years

### Storage Growth

**Change Node Growth Rate:**
- Directly proportional to relationship churn
- Typical: 2-5% of relationship count per sync (low churn)
- High churn (e.g., daily web visits): 20-50% per sync

**Mitigation Strategies:**
1. Archive old changes to separate database
2. Aggregate similar changes (e.g., multiple web visits → summary)
3. Set retention policy (e.g., keep only last 2 years)

---

## Implementation Details

### Code Location

**Temporal Loader:**
- File: `loaders/temporal_loader.py`
- Methods:
  - `_process_relationship_changes()` - Main orchestrator
  - `_track_added_relationships()` - Create change nodes for additions
  - `_track_removed_relationships()` - Create change nodes for deletions

**Change Detector:**
- File: `utils/change_detector.py`
- Method: `detect_relationship_changes()` - Compare new vs. existing

**Schema:**
- File: `config/neo4j_schema.py`
- Indexes for `HUBSPOT_RelationshipChange` nodes

### Batch Processing

Changes are loaded in batches (default: 500) for efficiency:

```python
BATCH_SIZE = 500

for i in tqdm(range(0, len(added), BATCH_SIZE)):
    batch = added[i:i + BATCH_SIZE]
    # Create change nodes in batch
```

---

## Testing & Verification

### Test Script

Run the test pipeline to verify temporal tracking:

```bash
python run_test_pipeline.py
```

**Expected Behavior:**

**Run #1 (Initial Load):**
```
✅ All relationships marked as 'added'
✅ 22 relationship changes tracked
```

**Run #2 (Same Data):**
```
✅ 0 added, 0 removed (no changes detected)
```

**Run #3 (Modified Data):**
```
✅ Removed relationships create 'removed' change nodes
✅ New relationships create 'added' change nodes
```

### Verification Queries

```cypher
// Count change nodes
MATCH (rc:HUBSPOT_RelationshipChange)
RETURN rc.change_type, count(*) AS count;

// Verify properties are captured
MATCH (rc:HUBSPOT_RelationshipChange)
WHERE rc.relationship_properties IS NOT NULL
RETURN rc.relationship_type, rc.relationship_properties
LIMIT 10;
```

---

## Migration Guide

### For Existing Data

If you already have data in Neo4j without temporal tracking:

**Option 1: Clean Start (Recommended for Testing)**
```cypher
// Clear database
MATCH (n) DETACH DELETE n;
```

**Option 2: Initialize Existing Data**
- All existing relationships will show as `'added'` on first sync after deployment
- This is expected and represents the baseline state

### Backward Compatibility

- ✅ Current-state queries work unchanged
- ✅ No breaking changes to graph structure
- ✅ Opt-in historical queries (don't have to use change nodes)

---

## Future Enhancements

### Possible Improvements

1. **Relationship Property Change Detection**
   - Currently: Track add/remove only
   - Future: Detect property updates (e.g., visit timestamp changes)

2. **Change Aggregation**
   - Group multiple similar changes into summaries
   - Example: "Contact visited 15 pages" instead of 15 individual changes

3. **Retention Policies**
   - Automatic archival of old changes
   - Configurable retention (e.g., 2 years)

4. **Enhanced Queries**
   - Pre-built query library for common audit scenarios
   - Python helpers for complex reconstructions

5. **Visualization**
   - Timeline views of relationship changes
   - Entity relationship history graphs

---

## Troubleshooting

### Issue: Too Many Changes Detected

**Symptoms:**
- Every sync shows thousands of added/removed relationships
- Same data produces different results

**Causes:**
1. Dynamic data in transformations (timestamps changing)
2. Inconsistent sorting/ordering
3. Email matching inconsistencies

**Solution:**
```bash
# Run test pipeline to isolate the issue
python run_test_pipeline.py  # Run twice with same data
# Should show 0 changes on second run
```

### Issue: Missing Relationship Properties

**Symptoms:**
- `relationship_properties` is empty `{}`

**Cause:**
- Most relationships intentionally have no properties
- Only `VISITED` relationships have properties currently

**Verification:**
```cypher
MATCH (rc:HUBSPOT_RelationshipChange)
WHERE rc.relationship_type = 'VISITED'
RETURN rc.relationship_properties;
```

### Issue: Change Nodes Not Created

**Symptoms:**
- Relationships change but no `HUBSPOT_RelationshipChange` nodes

**Check:**
1. Verify `TemporalLoader` is being used (not old `Neo4jLoader`)
2. Check logs for errors during `_track_added/removed_relationships`
3. Ensure indexes are created (run schema setup)

---

## Summary

**Architecture:** Hybrid approach with separate change nodes  
**Current State:** Clean, fast, no temporal overhead  
**Historical Data:** Complete audit trail in `HUBSPOT_RelationshipChange` nodes  
**Properties:** Preserved for all relationships  
**Performance:** Indexed for efficient querying  
**Consistency:** Matches node history pattern (`_HISTORY` nodes)  

This design provides the best of both worlds: operational efficiency and comprehensive historical tracking.

