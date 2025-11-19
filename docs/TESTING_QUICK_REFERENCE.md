# Testing Quick Reference

Quick guide for testing temporal tracking implementation.

## 📦 Available Test Datasets

| Dataset | Size | Purpose | Time |
|---------|------|---------|------|
| **dataset1** | Medium (5 users, 12 contacts, 8 companies, 6 deals) | Comprehensive testing | ~30s |
| **dataset1_modified** | Same as dataset1 with changes | Change detection testing | ~30s |
| **dataset2** | Small (3 users, 6 contacts, 4 companies, 3 deals) | Quick smoke test | ~15s |

## 🚀 Quick Tests

### Test 1: No False Positives (Most Important!)

Verify duplicate runs produce zero changes:

```bash
# Clear DB and load dataset1
python3 -c "from neo4j import GraphDatabase; from config.settings import *; GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)).session().run('MATCH (n) DETACH DELETE n')"

cp data/dataset1/* data/raw/
python3 main.py | grep "Relationship changes:"
# Should show: "Relationship changes: X added, 0 removed"

# Run again - MUST show 0 changes
python3 main.py | grep "Relationship changes:"
# MUST show: "Relationship changes: 0 added, 0 removed" ✅
```

**Expected:** Second run shows `0 added, 0 removed`

---

### Test 2: Change Detection

Verify all 8 scenarios are detected:

```bash
# Load baseline
cp data/dataset1/* data/raw/
python3 main.py > run1.log

# Load modified version
cp data/dataset1_modified/* data/raw/
python3 main.py > run2.log

# Check for changes
grep "updated\|new\|deleted" run2.log
```

**Expected Changes:**
- 4 nodes updated (1 user, 1 contact, 1 deal, 1 company)
- 1 node added (new contact)
- 1 node deleted (soft delete)
- 2 relationships removed (ownership transfers)
- 2 relationships added (new ownerships + association)

---

### Test 3: Archived Users

Verify archived users are extracted and labeled:

```bash
cp data/dataset1/* data/raw/
python3 main.py

# Check archived users in Neo4j
python3 << 'EOF'
from neo4j import GraphDatabase
from config.settings import *

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
with driver.session() as session:
    result = session.run('MATCH (u:HUBSPOT_User:Archived) RETURN count(u) as cnt')
    print(f"Archived users with label: {result.single()['cnt']}")
    
    result = session.run('MATCH (u:HUBSPOT_User) WHERE u.archived = true RETURN count(u) as cnt')
    print(f"Archived users (property): {result.single()['cnt']}")
EOF
```

**Expected:** Both queries return the same count (2 for dataset1)

---

## 🔍 What to Look For

### ✅ Success Indicators

1. **No missing node warnings:** `Filtered out 0 relationships with missing nodes`
2. **Zero false changes:** Second run shows `0 added, 0 removed`
3. **Archived labels present:** `Archived` label on deactivated users
4. **History created:** `_HISTORY` nodes for updated entities
5. **Soft deletes:** Deleted entities have `is_deleted: true`

### ❌ Failure Indicators

1. **Missing node warnings:** `Filtered out X relationships` (on first run)
2. **False positives:** Second run shows changes
3. **No archived labels:** Archived users missing `Archived` label
4. **No history:** Updates don't create history nodes
5. **Hard deletes:** Deleted entities removed from database

---

## 📊 Key Metrics

After loading any dataset **twice**, run:

```bash
python3 query_temporal.py
```

**Look for:**
- `Relationship changes tracked:` should be **same** on both runs
- `Historical versions:` should increase only on actual updates
- `Deleted:` should show soft-deleted entities

---

## 🐛 Troubleshooting

### Issue: False relationship changes on second run

**Check logs for:**
```
Relationship changes: X added, 0 removed
```

**Causes:**
1. Immutable relationships being tracked → Check `IMMUTABLE_EVENT_RELATIONSHIPS`
2. Missing node validation failing → Check `_filter_valid_relationships()`
3. Hash mismatch on unchanged nodes → Check `snapshot_hash` generation

**Fix:** Review `utils/change_detector.py` and `loaders/temporal_loader.py`

---

### Issue: Missing archived users

**Check logs for:**
```
Filtered out X relationships with missing nodes
```

**Causes:**
1. Archived users not being fetched → Check `extractors/users.py` fetches `archived=true`
2. User extraction error → Check HubSpot API scopes

**Fix:** Verify `extract_all()` makes two API calls (active + archived)

---

### Issue: Archived label not applied

**Check Neo4j:**
```cypher
MATCH (u:HUBSPOT_User {hubspot_id: '<archived_user_id>'})
RETURN labels(u)
```

**Should return:** `['HUBSPOT_User', 'Archived']`

**Causes:**
1. Cypher `FOREACH` logic failing → Check `_load_new_nodes()`
2. `archived` property not set → Check transformer

**Fix:** Review `loaders/temporal_loader.py` label assignment

---

## 📝 Test Checklist

Before considering temporal tracking "complete":

- [ ] **Dataset1 twice:** Second run shows 0 changes
- [ ] **Dataset2 twice:** Second run shows 0 changes  
- [ ] **Dataset1 → Dataset1_modified:** All 8 scenarios detected
- [ ] **Archived users:** Label applied correctly
- [ ] **No missing nodes:** Zero warnings in logs
- [ ] **History created:** `_HISTORY` nodes for updates
- [ ] **Soft deletes work:** `is_deleted=true`, node preserved
- [ ] **query_temporal.py:** Shows correct statistics

---

## 🎯 Most Critical Test

```bash
# This is the GOLD STANDARD test:
cp data/dataset1/* data/raw/
python3 main.py > /dev/null 2>&1
python3 main.py 2>&1 | grep "Relationship changes:"
```

**MUST output:**
```
Relationship changes: 0 added, 0 removed
```

If this passes, temporal tracking is working correctly! ✅

---

## 📚 Full Documentation

- **[TEST_DATASETS_README.md](data/TEST_DATASETS_README.md)** - Dataset descriptions
- **[TEST_SCENARIOS.md](data/TEST_SCENARIOS.md)** - Detailed scenario testing
- **[RELATIONSHIP_TEMPORAL_TRACKING.md](docs/RELATIONSHIP_TEMPORAL_TRACKING.md)** - Architecture docs

---

**Quick Win:** Run `cp data/dataset1/* data/raw/ && python3 main.py && python3 main.py 2>&1 | tail -5`

Should see: `Relationship changes tracked: X` (same value both times)

