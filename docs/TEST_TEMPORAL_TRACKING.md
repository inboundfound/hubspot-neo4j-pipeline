# Testing Temporal Tracking

This guide helps you test and debug the temporal tracking system with a minimal dataset.

## Setup

### 1. Clear the Neo4j Database

In Neo4j Browser, run:
```cypher
MATCH (n) DETACH DELETE n
```

### 2. Test Data Created

The test dataset has been created in `data/test/`:
- **2 Users** (John Doe, Jane Smith)
- **3 Contacts** (Alice, Bob, Charlie)
- **2 Companies** (Acme Corp, TechStart Inc)
- **2 Deals** (Big Sale, Small Deal)
- **3 Engagements** (1 meeting, 1 call, 1 note)
- **3 Email Events** (2 opens, 1 click)
- **2 Form Submissions**

Expected: ~15-20 relationships

## Testing Scenarios

### Scenario 1: First Load (Baseline)

```bash
python run_test_pipeline.py
```

**Expected Results:**
- All nodes created as NEW
- All relationships created
- Relationship changes = total relationships (all "added")
- 0 historical versions
- 0 deleted nodes

### Scenario 2: Reload Same Data (No Changes)

```bash
python run_test_pipeline.py
```

**Expected Results:**
- 0 new nodes
- 0 updated nodes
- All nodes marked as UNCHANGED
- 0 deleted nodes
- **Relationship changes: 0 added, 0 removed** ← KEY TEST
- 0 new historical versions

### Scenario 3: Update a Contact

Edit `data/test/contacts.json`, change Alice's job title:
```json
{
  "id": "test_contact_1",
  "properties": {
    ...
    "jobtitle": "Chief Executive Officer",  // Changed from "CEO"
    "lastmodifieddate": "2024-04-01T10:00:00Z"  // Update date
  }
}
```

Run:
```bash
python run_test_pipeline.py
```

**Expected Results:**
- 0 new nodes
- 1 updated node (test_contact_1)
- 1 new historical version (HUBSPOT_Contact_HISTORY)
- Relationship changes: 0 (relationships didn't change)

### Scenario 4: Delete a Contact

Remove the entire Bob record from `data/test/contacts.json` (keep just Alice and Charlie).

Run:
```bash
python run_test_pipeline.py
```

**Expected Results:**
- 0 new nodes
- 1 deleted node (test_contact_2)
- 1 new historical version
- Bob's node still exists but marked `is_deleted=true`
- Relationships involving Bob should be removed

### Scenario 5: Add a New Deal

Add to `data/test/deals.json`:
```json
{
  "id": "test_deal_3",
  "properties": {
    "dealname": "New Opportunity",
    "amount": "25000",
    "dealstage": "qualified",
    "pipeline": "default",
    "createdate": "2024-04-01T10:00:00Z",
    "hs_lastmodifieddate": "2024-04-01T10:00:00Z",
    "hubspot_owner_id": "test_user_1"
  },
  "associations": {
    "companies": [{"id": "test_company_1"}],
    "contacts": [{"id": "test_contact_3"}]
  }
}
```

Run:
```bash
python run_test_pipeline.py
```

**Expected Results:**
- 1 new node (test_deal_3)
- New relationships created
- Relationship changes: N added (new deal relationships)

### Scenario 6: Change Relationship (Move Deal to Different Company)

Edit `data/test/deals.json`, change test_deal_1's company association:
```json
{
  "id": "test_deal_1",
  ...
  "associations": {
    "companies": [{"id": "test_company_2"}],  // Changed from test_company_1
    "contacts": [{"id": "test_contact_1"}, {"id": "test_contact_3"}]
  }
}
```

Run:
```bash
python run_test_pipeline.py
```

**Expected Results:**
- 0 new nodes (deal already exists)
- Relationship changes:
  - 1 removed: test_deal_1 → test_company_1
  - 1 added: test_deal_1 → test_company_2
- HUBSPOT_RelationshipChange nodes track the change

## Debugging

### Check What's in Neo4j

```cypher
// Count all nodes by type
MATCH (n)
RETURN labels(n)[0] as type, count(n) as count
ORDER BY count DESC

// Check temporal fields
MATCH (n:HUBSPOT_Contact)
RETURN n.hubspot_id, n.email, n.is_current, n.is_deleted, n.valid_from, n.valid_to
LIMIT 5

// View relationship changes
MATCH (rc:HUBSPOT_RelationshipChange)
RETURN rc.change_type, rc.from_entity_type, rc.relationship_type, 
       rc.to_entity_type, rc.changed_at
ORDER BY rc.changed_at DESC
LIMIT 10

// Check for history
MATCH (n)-[:HAS_HISTORY]->(h)
RETURN labels(n)[0] as entity_type, count(h) as history_count
```

### View Transformed Data

After running the test pipeline, check:
- `data/test/transformed/nodes.json` - See all transformed nodes
- `data/test/transformed/relationships.json` - See all relationships

### Common Issues

**Issue: Relationships showing as "changed" when data is identical**
- Check relationship structure in transformed data
- Verify `from_id`, `to_id`, and `type` fields are consistent
- Look for email relationships (`from_email`) vs standard relationships

**Issue: All nodes showing as "updated" every time**
- Check if `snapshot_hash` is being computed correctly
- Verify temporal fields are present on all nodes
- Look at the change detector comparison logic

**Issue: Relationships not loading**
- Check that referenced nodes exist (hubspot_id matches)
- Verify relationship structure has required fields
- Check for constraint violations in Neo4j

## Reset and Retry

To start completely fresh:

1. Clear Neo4j:
   ```cypher
   MATCH (n) DETACH DELETE n
   ```

2. Run test pipeline:
   ```bash
   python run_test_pipeline.py
   ```

3. Run again (should show no changes):
   ```bash
   python run_test_pipeline.py
   ```

## Expected Behavior Summary

| Run | Scenario | New | Updated | Unchanged | Deleted | Rel Added | Rel Removed | History |
|-----|----------|-----|---------|-----------|---------|-----------|-------------|---------|
| 1st | Initial load | All | 0 | 0 | 0 | All | 0 | 0 |
| 2nd | Same data | 0 | 0 | All | 0 | **0** | **0** | 0 |
| 3rd | Update 1 node | 0 | 1 | Rest | 0 | 0 | 0 | 1 |
| 4th | Delete 1 node | 0 | 0 | Rest | 1 | 0 | Some | 1 |
| 5th | Add 1 node | 1 | 0 | Rest | 0 | New rels | 0 | 0 |

The key test is Run #2 - reloading the same data should result in **0 changes**.


