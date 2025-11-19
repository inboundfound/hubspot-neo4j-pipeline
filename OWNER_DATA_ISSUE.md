# Owner Data Issue - Action Required

## Summary

The reporting system has been successfully created, but **owner data is not available** in the Neo4j database. This prevents querying contacts/companies by owner name (e.g., "Lynne Bartos").

## Root Causes

### 1. Owner Properties Not Requested During Extraction

The extractors don't request owner-related properties from HubSpot:

**File:** `extractors/contacts.py` (line 40-56)
**Issue:** The `get_properties_list()` method doesn't include `hubspot_owner_id`

**Current properties list:**
```python
def get_properties_list(self) -> List[str]:
    return [
        'firstname', 'lastname', 'email', 'phone', 'company',
        'associatedcompanyid',
        'jobtitle', 'lifecyclestage', 'hs_lead_status',
        # ... other properties ...
        # ❌ Missing: 'hubspot_owner_id'
    ]
```

**Same issue in:**
- `extractors/companies.py` - missing `hubspot_owner_id`
- `extractors/deals.py` - missing `hubspot_owner_id`

### 2. Users API Scope Missing

The users/owners extraction failed during pipeline execution:

```
2025-10-29 17:19:25,162 - UsersExtractor - ERROR - API call failed: (403)
Reason: Forbidden
...
"message":"This app hasn't been granted all required scopes to make this call."
"requiredGranularScopes":["crm.objects.owners.read"]
```

**Issue:** The HubSpot access token doesn't have the `crm.objects.owners.read` scope.

## Impact

Current state of data in Neo4j:
- ✅ **7,435 contacts** loaded
- ✅ **6,877 companies** loaded
- ✅ **1,970 deals** loaded
- ✅ **12,263 activities** loaded
- ✅ **4,094 email open events** loaded
- ✅ **201 email click events** loaded
- ❌ **0 users** loaded (API scope missing)
- ❌ **Contact owner_id** property is empty string
- ❌ **Company owner_id** property is empty string
- ❌ **Deal owner_id** property is empty string
- ❌ **No OWNED_BY relationships** created

## Fixes Required

### Fix 1: Add Owner Properties to Extractors

**File:** `extractors/contacts.py`

```python
def get_properties_list(self) -> List[str]:
    return [
        'firstname', 'lastname', 'email', 'phone', 'company',
        'associatedcompanyid',
        'hubspot_owner_id',  # ← ADD THIS
        'jobtitle', 'lifecyclestage', 'hs_lead_status',
        # ... rest of properties
    ]
```

**File:** `extractors/companies.py`

```python
def get_properties_list(self) -> List[str]:
    return [
        'name', 'domain', 'website',
        'hubspot_owner_id',  # ← ADD THIS
        'industry', 'type', 'description',
        # ... rest of properties
    ]
```

**File:** `extractors/deals.py`

```python
def get_properties_list(self) -> List[str]:
    return [
        'dealname', 'amount', 'dealstage', 'pipeline',
        'hubspot_owner_id',  # ← ADD THIS
        'closedate', 'createdate',
        # ... rest of properties
    ]
```

### Fix 2: Add HubSpot API Scope

The HubSpot access token needs the `crm.objects.owners.read` scope added:

1. Go to your HubSpot app settings: https://app.hubspot.com/developer/{your-account-id}
2. Select your app
3. Navigate to "Auth" → "Scopes"
4. Add scope: `crm.objects.owners.read`
5. Re-generate your access token
6. Update `.env` with the new token

**Required scopes for full functionality:**
```
crm.objects.contacts.read
crm.objects.companies.read
crm.objects.deals.read
crm.objects.owners.read    ← ADD THIS
timeline
settings.users.read         ← May also be needed
```

### Fix 3: Re-run the Pipeline

After making the above fixes:

```bash
# Clear Neo4j database
# (Open Neo4j Browser and run: MATCH (n) DETACH DELETE n)

# Re-run pipeline
source venv/bin/activate
python3 main.py
```

## Workaround for Now

Since owner data is not available, you can still use the reporting system for non-owner queries:

```bash
# View all contacts by lifecycle stage
python3 report.py --lifecycle-stages

# View all companies by industry
python3 report.py --industries

# Search contacts by email
# (Would need to add custom query)
```

## After Fixes Are Applied

Once owner data is available, these queries will work:

```bash
# Find all contacts and companies owned by Lynne
python3 report.py --owner "Lynne" --output table

# Export to CSV
python3 report.py --owner "Lynn" --output csv

# Get summary stats for an owner
python3 report.py --owner "Bartos" --type summary

# Interactive owner selection
python3 report.py --owner "Lyn" --interactive

# Find an owner
python3 report.py --find-owner "Lynne"
```

## Verification Queries

After re-running the pipeline, verify owner data loaded correctly:

```cypher
// Check if HUBSPOT_User nodes exist
MATCH (u:HUBSPOT_User)
RETURN count(u) as user_count

// Check if owner_id properties are populated
MATCH (c:HUBSPOT_Contact)
WHERE c.owner_id IS NOT NULL AND c.owner_id <> ''
RETURN count(c) as contacts_with_owner

// Check if OWNED_BY relationships exist
MATCH ()-[r:OWNED_BY]->()
RETURN count(r) as owned_by_relationships

// Find owners by name
MATCH (u:HUBSPOT_User)
WHERE u.first_name CONTAINS 'Lynne' OR u.last_name CONTAINS 'Bartos'
RETURN u.first_name, u.last_name, u.email

// Get contacts owned by specific user
MATCH (c:HUBSPOT_Contact)-[:OWNED_BY]->(u:HUBSPOT_User {first_name: 'Lynne'})
RETURN c.email, c.first_name, c.last_name, c.lifecycle_stage
LIMIT 10
```

## Current Pipeline Results

From the last pipeline run (2025-10-29):

```
✅ Extraction summary:
  - contacts: 7435 records
  - companies: 6877 records
  - deals: 1970 records
  - engagements: 12263 records
  - email_events: 10047 records
  - users: 0 records ← FAILED (403 Forbidden)
  - form_submissions: 0 records

✅ Graph summary:
  - Nodes: 36231
  - Relationships: 52461

❌ Neo4j summary:
  - HUBSPOT_User nodes: 0 (not created)
  - OWNED_BY relationships: 0 (not created)
```

## Next Steps

1. ✅ Reporting system created and tested (works for non-owner queries)
2. ❌ Add `hubspot_owner_id` to extractor property lists
3. ❌ Add `crm.objects.owners.read` scope to HubSpot app
4. ❌ Re-generate and update access token
5. ❌ Clear Neo4j and re-run pipeline
6. ❌ Verify owner data with queries above
7. ❌ Test owner-based reports

## Files Created

1. **`reporting/queries.py`** - 20+ predefined Cypher queries for owner-based reports
2. **`reporting/neo4j_reporter.py`** - Core reporting class with Neo4j connection & output formatting
3. **`reporting/__init__.py`** - Module initialization
4. **`report.py`** - CLI tool for running reports

The reporting infrastructure is ready - it just needs owner data to be available in Neo4j!
