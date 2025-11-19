# HubSpot → Neo4j Complete Data Model

## Overview
This document describes the complete graph data model, including all node types, relationships, properties, and naming conventions.

---

## Node Types

### Core CRM Entities

#### `HUBSPOT_Contact`
**Description:** HubSpot contacts (people)

**Key Properties:**
- `hubspot_id` (string, UNIQUE) - HubSpot contact ID
- `email` (string, INDEXED) - Email address (normalized to lowercase)
- `first_name` (string)
- `last_name` (string)
- `full_name` (string) - Computed from first + last
- `phone` (string)
- `company` (string) - Company name as string
- `jobtitle` (string)
- `lifecycle_stage` (string) - e.g., "lead", "customer"
- `lead_status` (string)
- `owner_id` (string, INDEXED) - HubSpot owner/user ID
- `created_date` (datetime, INDEXED)
- `last_modified` (datetime, INDEXED)
- `total_email_opens` (integer) - Aggregate count
- `total_email_clicks` (integer) - Aggregate count
- `total_page_views` (integer) - Aggregate count

**Constraints:**
- UNIQUE constraint on `hubspot_id`

**Indexes:**
- `email`
- `owner_id`
- `created_date`
- `last_modified`

---

#### `HUBSPOT_Company`
**Description:** HubSpot companies (organizations)

**Key Properties:**
- `hubspot_id` (string, UNIQUE)
- `name` (string) - Company name
- `domain` (string, INDEXED) - Primary domain
- `industry` (string)
- `city` (string)
- `state` (string)
- `country` (string)
- `owner_id` (string, INDEXED)
- `created_date` (datetime, INDEXED)
- `last_modified` (datetime, INDEXED)
- `number_of_employees` (integer)
- `annual_revenue` (float)

**Constraints:**
- UNIQUE constraint on `hubspot_id`

**Indexes:**
- `domain`
- `owner_id`
- `created_date`
- `last_modified`

---

#### `HUBSPOT_Deal`
**Description:** HubSpot deals (sales opportunities)

**Key Properties:**
- `hubspot_id` (string, UNIQUE)
- `name` (string) - Deal name
- `amount` (float) - Deal value
- `stage` (string, INDEXED) - Current pipeline stage
- `pipeline` (string) - Pipeline name
- `is_won` (boolean) - Deal closed-won status
- `owner_id` (string, INDEXED)
- `created_date` (datetime, INDEXED)
- `last_modified` (datetime, INDEXED)
- `close_date` (datetime, INDEXED) - Expected/actual close date
- `deal_type` (string)

**Constraints:**
- UNIQUE constraint on `hubspot_id`

**Indexes:**
- `stage`
- `owner_id`
- `created_date`
- `last_modified`
- `close_date`

---

#### `HUBSPOT_Activity`
**Description:** HubSpot engagements (meetings, calls, notes, tasks)

**Key Properties:**
- `hubspot_id` (string, UNIQUE)
- `type` (string, INDEXED) - "MEETING", "CALL", "NOTE", "TASK"
- `timestamp` (datetime, INDEXED) - When activity occurred
- `created_date` (datetime, INDEXED)
- `title` (string)
- `body` (string) - Activity details/notes
- `status` (string) - For tasks: "COMPLETED", "NOT_STARTED"
- `owner_id` (string)

**Constraints:**
- UNIQUE constraint on `hubspot_id`

**Indexes:**
- `type`
- `timestamp`
- `created_date`

---

#### `HUBSPOT_User`
**Description:** HubSpot users/owners (sales reps, account managers)

**Key Properties:**
- `hubspot_id` (string, UNIQUE)
- `email` (string, INDEXED)
- `first_name` (string)
- `last_name` (string)
- `active` (boolean) - Is user active
- `teams` (list of strings) - Team memberships
- `created_date` (datetime)
- `last_modified` (datetime)

**Constraints:**
- UNIQUE constraint on `hubspot_id`

**Indexes:**
- `email`

---

### Marketing Entities

#### `HUBSPOT_EmailCampaign`
**Description:** HubSpot marketing email campaigns

**Key Properties:**
- `hubspot_id` (string, UNIQUE)
- `name` (string) - Campaign name
- `subject` (string) - Email subject line
- `sent_date` (datetime)
- `campaign_type` (string)

**Constraints:**
- UNIQUE constraint on `hubspot_id`

---

#### `HUBSPOT_WebPage`
**Description:** Web pages (from email clicks, page visits, form submissions)

**Key Properties:**
- `url` (string, UNIQUE) - Full URL (used as ID)
- `domain` (string, INDEXED) - Domain name
- `path` (string) - URL path

**Constraints:**
- UNIQUE constraint on `url`

**Indexes:**
- `domain`

---

### Event Nodes (Time-Series Data)

#### `HUBSPOT_EmailOpenEvent`
**Description:** Individual email open events

**Key Properties:**
- `hubspot_id` (string, UNIQUE) - Generated event ID
- `timestamp` (datetime, INDEXED) - When email was opened
- `campaign_id` (string, INDEXED) - Related campaign
- `recipient_email` (string) - Who opened it
- `device_type` (string) - "COMPUTER", "MOBILE", etc.
- `location` (string) - City/region
- `browser` (string) - User agent

**Constraints:**
- UNIQUE constraint on `hubspot_id`

**Indexes:**
- `timestamp`
- `campaign_id`

---

#### `HUBSPOT_EmailClickEvent`
**Description:** Individual email click events

**Key Properties:**
- `hubspot_id` (string, UNIQUE) - Generated event ID
- `timestamp` (datetime, INDEXED) - When link was clicked
- `campaign_id` (string, INDEXED) - Related campaign
- `recipient_email` (string) - Who clicked
- `clicked_url` (string) - URL that was clicked
- `device_type` (string)
- `location` (string)
- `browser` (string)

**Constraints:**
- UNIQUE constraint on `hubspot_id`

**Indexes:**
- `timestamp`
- `campaign_id`

---

#### `HUBSPOT_FormSubmission`
**Description:** Individual form submission events

**Key Properties:**
- `hubspot_id` (string, UNIQUE) - Generated event ID
- `timestamp` (datetime, INDEXED) - When form was submitted
- `created_date` (datetime)
- `form_guid` (string, INDEXED) - Form identifier
- `form_name` (string) - Form name
- `email` (string) - Submitter email (for contact matching)
- `page_url` (string) - Page where form was submitted
- `page_title` (string)
- `ip_address` (string)

**Constraints:**
- UNIQUE constraint on `hubspot_id`

**Indexes:**
- `timestamp`
- `form_guid`

---

## Relationships

### Core CRM Relationships

#### `(HUBSPOT_Contact)-[:WORKS_AT]->(HUBSPOT_Company)`
**Description:** Contact works at company
**Source:** HubSpot `associatedcompanyid` property
**Properties:** None

---

#### `(HUBSPOT_Contact)-[:ASSOCIATED_WITH]->(HUBSPOT_Deal)`
**Description:** Contact associated with deal
**Source:** HubSpot deal associations API
**Properties:** None

---

#### `(HUBSPOT_Deal)-[:BELONGS_TO]->(HUBSPOT_Company)`
**Description:** Deal belongs to company
**Source:** HubSpot deal associations API
**Properties:** None

---

#### `(HUBSPOT_Activity)-[:INVOLVES]->(HUBSPOT_Contact)`
**Description:** Activity involves contact
**Source:** HubSpot engagement associations API
**Properties:** None

---

#### `(HUBSPOT_Activity)-[:RELATED_TO]->(HUBSPOT_Deal)`
**Description:** Activity related to deal
**Source:** HubSpot engagement associations API
**Properties:** None

---

### Ownership Relationships

#### `(HUBSPOT_Contact)-[:OWNED_BY]->(HUBSPOT_User)`
**Description:** Contact owned by user
**Source:** `hubspot_owner_id` property on contacts
**Properties:** None
**Note:** Requires `crm.objects.owners.read` scope

---

#### `(HUBSPOT_Company)-[:OWNED_BY]->(HUBSPOT_User)`
**Description:** Company owned by user
**Source:** `hubspot_owner_id` property on companies
**Properties:** None
**Note:** Requires `crm.objects.owners.read` scope

---

#### `(HUBSPOT_Deal)-[:OWNED_BY]->(HUBSPOT_User)`
**Description:** Deal owned by user
**Source:** `hubspot_owner_id` property on deals
**Properties:** None
**Note:** Requires `crm.objects.owners.read` scope

---

### Email Event Relationships

#### `(HUBSPOT_Contact)-[:PERFORMED]->(HUBSPOT_EmailOpenEvent)`
**Description:** Contact performed email open action
**Source:** Matched by `recipient_email` to `Contact.email`
**Properties:** None
**Matching:** Email-based (case-insensitive)

---

#### `(HUBSPOT_EmailOpenEvent)-[:FOR_CAMPAIGN]->(HUBSPOT_EmailCampaign)`
**Description:** Email open event for specific campaign
**Source:** `campaign_id` from email events API
**Properties:** None

---

#### `(HUBSPOT_Contact)-[:PERFORMED]->(HUBSPOT_EmailClickEvent)`
**Description:** Contact performed email click action
**Source:** Matched by `recipient_email` to `Contact.email`
**Properties:** None
**Matching:** Email-based (case-insensitive)

---

#### `(HUBSPOT_EmailClickEvent)-[:FOR_CAMPAIGN]->(HUBSPOT_EmailCampaign)`
**Description:** Email click event for specific campaign
**Source:** `campaign_id` from email events API
**Properties:** None

---

#### `(HUBSPOT_EmailClickEvent)-[:CLICKED_URL]->(HUBSPOT_WebPage)`
**Description:** Email click event clicked specific URL
**Source:** `clicked_url` from email events API
**Properties:** None

---

### Form Submission Relationships

#### `(HUBSPOT_FormSubmission)-[:SUBMITTED_BY]->(HUBSPOT_Contact)`
**Description:** Form submission submitted by contact
**Source:** Matched by `email` field in form values to `Contact.email`
**Properties:** None
**Matching:** Email-based (case-insensitive)
**Note:** Only created when email matches an existing contact

---

#### `(HUBSPOT_FormSubmission)-[:ON_PAGE]->(HUBSPOT_WebPage)`
**Description:** Form submission occurred on webpage
**Source:** `page_url` from form submission
**Properties:** None

---

### Legacy/Deprecated Relationships

#### `(HUBSPOT_Contact)-[:VISITED]->(HUBSPOT_WebPage)`
**Description:** Contact visited webpage (DEPRECATED - use event nodes instead)
**Source:** Legacy page visit tracking
**Properties:** None
**Note:** This is a rollup relationship, not event-based. Use `HUBSPOT_PageVisit` events instead (coming soon)

---

## Naming Conventions

### Node Labels
- **Format:** `HUBSPOT_{EntityType}`
- **Examples:** `HUBSPOT_Contact`, `HUBSPOT_Deal`, `HUBSPOT_EmailOpenEvent`
- **Rationale:**
  - `HUBSPOT_` prefix identifies source system
  - Allows multiple CRM systems in same graph
  - Clear separation from Knowledge Graph entities (e.g., `Person`, `Organization`)

### Property Names
- **Format:** `snake_case`
- **Examples:** `hubspot_id`, `first_name`, `created_date`, `recipient_email`
- **Special Properties:**
  - `hubspot_id` - Always the unique identifier from HubSpot (or generated for events)
  - `*_date` suffix - Always stored as ISO 8601 datetime strings
  - `owner_id` - Always references a `HUBSPOT_User.hubspot_id`

### Relationship Types
- **Format:** `SCREAMING_SNAKE_CASE`
- **Examples:** `WORKS_AT`, `OWNED_BY`, `PERFORMED`, `FOR_CAMPAIGN`
- **Conventions:**
  - Use present tense verbs: `WORKS_AT`, not `WORKED_AT`
  - Be specific: `SUBMITTED_BY` instead of generic `CREATED_BY`
  - Direction matters: `(Contact)-[:PERFORMED]->(Event)` not `(Event)-[:PERFORMED_BY]->(Contact)`

### Relationship Direction Conventions

**Agent → Action Pattern:**
- `(Contact)-[:PERFORMED]->(EmailOpenEvent)`
- `(Contact)-[:PERFORMED]->(EmailClickEvent)`
- `(Contact)-[:SUBMITTED_BY]->(FormSubmission)` ← Note: reversed for semantic clarity

**Entity → Owner Pattern:**
- `(Contact)-[:OWNED_BY]->(User)`
- `(Company)-[:OWNED_BY]->(User)`
- `(Deal)-[:OWNED_BY]->(User)`

**Entity → Association Pattern:**
- `(Contact)-[:WORKS_AT]->(Company)`
- `(Contact)-[:ASSOCIATED_WITH]->(Deal)`
- `(Deal)-[:BELONGS_TO]->(Company)`

**Event → Context Pattern:**
- `(EmailOpenEvent)-[:FOR_CAMPAIGN]->(EmailCampaign)`
- `(EmailClickEvent)-[:CLICKED_URL]->(WebPage)`
- `(FormSubmission)-[:ON_PAGE]->(WebPage)`

---

## Email-Based Relationship Matching

Some relationships are matched by email address rather than HubSpot ID because:

1. **Email events don't include contact IDs** - HubSpot's email events API only provides email addresses
2. **Form submissions may not have contact IDs** - Forms API doesn't always link to contacts
3. **Cross-system linking** - Email is the universal identifier across systems

### Email Matching Process:
1. Extract email from event (e.g., `recipient_email` or form field)
2. Normalize to lowercase: `user@example.com`
3. Match to `HUBSPOT_Contact.email` (also normalized)
4. Create relationship only if match found

### Email-Matched Relationships:
- `PERFORMED` (Contact → EmailOpenEvent)
- `PERFORMED` (Contact → EmailClickEvent)
- `SUBMITTED_BY` (FormSubmission → Contact)

---

## Multi-Tenancy and Custom Labels

The loader supports custom labels for multi-tenancy:

```python
custom_labels = {
    "HUBSPOT_Contact": ["ACME_CORP", "Q4_2023"],
    "HUBSPOT_Company": ["ACME_CORP"],
}
```

Results in nodes like:
```cypher
(:HUBSPOT_Contact:ACME_CORP:Q4_2023 {hubspot_id: "123", ...})
```

---

## Knowledge Graph Integration

### Entity Matching: HUBSPOT_User → Person

The `SAME_AS` relationship links HubSpot users to Knowledge Graph Person nodes:

#### `(HUBSPOT_User)-[:SAME_AS]->(Person)`
**Description:** HubSpot user is the same person as Knowledge Graph Person
**Source:** Entity matcher (loaders/entity_matcher.py)
**Matching Strategy:**
1. Primary: LinkedIn URL match
2. Fallback: Email address match
**Properties:** None

**Usage:**
```cypher
// Find all contacts owned by a specific person
MATCH (c:HUBSPOT_Contact)-[:OWNED_BY]->(hu:HUBSPOT_User)-[:SAME_AS]->(p:Person)
WHERE p.full_name = 'Jane Smith'
RETURN c.email, c.lifecycle_stage
```

---

## Graph Schema Visualization

```
HUBSPOT_Contact
├── WORKS_AT → HUBSPOT_Company
├── ASSOCIATED_WITH → HUBSPOT_Deal
├── OWNED_BY → HUBSPOT_User
├── PERFORMED → HUBSPOT_EmailOpenEvent
├── PERFORMED → HUBSPOT_EmailClickEvent
└── VISITED → HUBSPOT_WebPage (legacy)

HUBSPOT_Company
├── OWNED_BY → HUBSPOT_User
└── ← BELONGS_TO ← HUBSPOT_Deal

HUBSPOT_Deal
├── BELONGS_TO → HUBSPOT_Company
├── OWNED_BY → HUBSPOT_User
└── ← RELATED_TO ← HUBSPOT_Activity

HUBSPOT_Activity
├── INVOLVES → HUBSPOT_Contact
└── RELATED_TO → HUBSPOT_Deal

HUBSPOT_User
└── SAME_AS → Person (Knowledge Graph)

HUBSPOT_EmailOpenEvent
├── FOR_CAMPAIGN → HUBSPOT_EmailCampaign
└── ← PERFORMED ← HUBSPOT_Contact

HUBSPOT_EmailClickEvent
├── FOR_CAMPAIGN → HUBSPOT_EmailCampaign
├── CLICKED_URL → HUBSPOT_WebPage
└── ← PERFORMED ← HUBSPOT_Contact

HUBSPOT_FormSubmission
├── SUBMITTED_BY → HUBSPOT_Contact
└── ON_PAGE → HUBSPOT_WebPage
```

---

## Required HubSpot API Scopes

To extract all data types:

### Core CRM Objects:
- `crm.objects.contacts.read`
- `crm.objects.companies.read`
- `crm.objects.deals.read`
- `crm.objects.engagements.read` (or granular: calls, meetings, notes, tasks)

### Marketing & Events:
- `marketing-email` - For email events API
- `forms` or `forms-uploaded-files` - For form submissions

### Ownership & Users:
- `crm.objects.owners.read` - For user/owner data and `OWNED_BY` relationships
- `settings.users.read` - Alternative scope for users

---

## Data Freshness and Merged Records

### Merged Records
When HubSpot records are merged:
- **Old record IDs are removed** from API responses
- **Canonical (surviving) record ID** is returned
- **Email addresses are preserved** on the canonical record
- **No action needed** - email-based matching handles this automatically

### Incremental Updates
Currently the pipeline does a full extract/load. Future enhancements:
- Delta extraction using `lastmodifieddate` filters
- Incremental relationship updates
- Soft deletes for removed records

---

## Example Queries

### Find engaged contacts (multiple interactions)
```cypher
MATCH (c:HUBSPOT_Contact)
WHERE EXISTS {
  MATCH (c)-[:PERFORMED]->(:HUBSPOT_EmailOpenEvent)
}
AND EXISTS {
  MATCH (c)-[:PERFORMED]->(:HUBSPOT_EmailClickEvent)
}
AND EXISTS {
  MATCH (:HUBSPOT_FormSubmission)-[:SUBMITTED_BY]->(c)
}
RETURN c.email, c.lifecycle_stage, c.owner_id
```

### Owner performance dashboard
```cypher
MATCH (u:HUBSPOT_User)<-[:OWNED_BY]-(d:HUBSPOT_Deal)
WHERE d.is_won = true
RETURN u.first_name + ' ' + u.last_name AS owner,
       count(d) AS deals_won,
       sum(d.amount) AS total_revenue
ORDER BY total_revenue DESC
```

### Recent form submissions by campaign traffic
```cypher
MATCH (fs:HUBSPOT_FormSubmission)-[:SUBMITTED_BY]->(c:HUBSPOT_Contact)
WHERE fs.timestamp > datetime() - duration('P30D')
OPTIONAL MATCH (c)-[:PERFORMED]->(click:HUBSPOT_EmailClickEvent)
  WHERE click.timestamp < fs.timestamp
  AND click.timestamp > fs.timestamp - duration('P7D')
RETURN c.email,
       fs.form_name,
       fs.timestamp AS submission_time,
       count(click) AS email_clicks_before_submission
ORDER BY submission_time DESC
```

---

## Version History

- **v1.0** - Basic CRM objects (contacts, companies, deals, engagements)
- **v2.0** - Added users/owners and OWNED_BY relationships
- **v2.1** - Added event nodes (EmailOpenEvent, EmailClickEvent, FormSubmission) with indexed timestamps
- **v2.2** - Fixed email-based relationship matching bug (HUBSPOT_Contact label)
- **v2.3** - Added form submission email extraction and contact matching

---

## Maintenance Notes

### Updating the Schema
When adding new node types or relationships:
1. Update `config/neo4j_schema.py` with constraints and indexes
2. Update transformer in `transformers/graph_transformer.py`
3. Update loader in `loaders/neo4j_loader.py`
4. Update this documentation
5. Add example queries to README.md

### Performance Considerations
- All timestamp fields are indexed for temporal queries
- Email fields are indexed for relationship matching
- Owner IDs are indexed for ownership queries
- Batch size: 100 nodes/relationships per Neo4j transaction
- Use `MERGE` for idempotent loads (safe to re-run)
