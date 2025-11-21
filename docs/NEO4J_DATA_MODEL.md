# Neo4j Data Model Documentation
## HubSpot to Neo4j Integration Pipeline

**Version:** 1.0  
**Last Updated:** 2025-11-21  
**Audience:** LLMs and Developers

---

## Table of Contents

1. [Introduction & Architecture](#1-introduction--architecture)
2. [Node Types](#2-node-types)
   - 2.1 [HUBSPOT_Contact](#21-hubspot_contact)
   - 2.2 [HUBSPOT_Company](#22-hubspot_company)
   - 2.3 [HUBSPOT_Deal](#23-hubspot_deal)
   - 2.4 [HUBSPOT_Activity](#24-hubspot_activity)
   - 2.5 [HUBSPOT_User](#25-hubspot_user)
   - 2.6 [HUBSPOT_EmailCampaign](#26-hubspot_emailcampaign)
   - 2.7 [HUBSPOT_WebPage](#27-hubspot_webpage)
   - 2.8 [HUBSPOT_EmailOpenEvent](#28-hubspot_emailopenevent)
   - 2.9 [HUBSPOT_EmailClickEvent](#29-hubspot_emailclickevent)
   - 2.10 [HUBSPOT_FormSubmission](#210-hubspot_formsubmission)
   - 2.11 [HUBSPOT_PageVisit](#211-hubspot_pagevisit)
3. [History Nodes](#3-history-nodes)
4. [Change Tracking Node](#4-change-tracking-node)
5. [Relationship Types](#5-relationship-types)
6. [Temporal Tracking System](#6-temporal-tracking-system)
7. [Schema Constraints & Indexes](#7-schema-constraints--indexes)
8. [Query Patterns & Examples](#8-query-patterns--examples)
9. [Data Flow Summary](#9-data-flow-summary)
10. [Special Patterns](#10-special-patterns)

---

## 1. Introduction & Architecture

### Pipeline Overview

The HubSpot-to-Neo4j pipeline consists of three main stages:

```
HubSpot API → Extract → Transform → Load → Neo4j
```

1. **Extract** (`main.py`): Fetches data from HubSpot APIs
   - Contacts, Companies, Deals, Engagements
   - Users/Owners
   - Email Events (opens, clicks)
   - Form Submissions

2. **Transform** (`transformers/graph_transformer.py`): Converts flat data into graph structures
   - Creates node representations with properties
   - Establishes relationships between entities
   - Generates property hashes for change detection
   - Adds temporal metadata

3. **Load** (`loaders/temporal_loader.py`): Loads into Neo4j with temporal tracking
   - Detects changes via hash comparison
   - Creates history snapshots for updates
   - Tracks relationship changes
   - Manages soft deletes

### Temporal Tracking Approach

The pipeline implements a **bitemporal pattern** that maintains:
- **Current State**: Active version of each entity (is_current=true)
- **Historical Snapshots**: Previous versions stored in _HISTORY nodes
- **Change Timeline**: All modifications tracked with timestamps

This enables:
- Point-in-time queries (view data as it was at any timestamp)
- Change auditing (see what changed and when)
- Rollback capability (restore previous states)
- Data lineage tracking

### Change Detection Methodology

**Hash-based Comparison**:
1. Generate SHA-256 hash of entity properties (excluding temporal fields)
2. Compare new hash with existing hash
3. Categorize records as: new, updated, unchanged, or deleted
4. Create history snapshot before applying updates

**Implementation**: `utils/change_detector.py`

```python
snapshot_hash = sha256(sorted_properties_json)
```

Excluded from hash: `valid_from`, `valid_to`, `is_current`, `is_deleted`, `snapshot_hash`, `last_modified`

---

## 2. Node Types

### 2.1 HUBSPOT_Contact

**Purpose**: Represents people/contacts in HubSpot CRM with email engagement tracking.

**Primary Identifier**: `hubspot_id` (string)

**Source**: HubSpot Contacts API (`/crm/v3/objects/contacts`)

**Properties**:

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `hubspot_id` | string | Unique HubSpot contact ID | "12345" |
| `email` | string | Email address (normalized, lowercase) | "john@example.com" |
| `first_name` | string | First name | "John" |
| `last_name` | string | Last name | "Doe" |
| `job_title` | string | Job title | "VP of Sales" |
| `lifecycle_stage` | string | Sales lifecycle stage | "lead", "customer" |
| `created_date` | ISO datetime | When contact was created | "2024-01-15T10:30:00Z" |
| `last_modified` | ISO datetime | Last modification timestamp | "2024-11-20T14:22:00Z" |
| `owner_id` | string | HubSpot owner/user ID | "67890" |
| `total_email_opens` | integer | Total email opens count | 45 |
| `total_email_clicks` | integer | Total email clicks count | 12 |
| `total_page_views` | integer | Total website visits | 8 |
| `source` | string | Acquisition source | "organic search" |
| `first_page_seen` | string | First URL visited | "https://..." |
| `country` | string | Country | "United States" |
| `city` | string | City | "San Francisco" |
| `state` | string | State/region | "CA" |
| `valid_from` | ISO datetime | Temporal validity start | "2024-11-21T12:00:00Z" |
| `valid_to` | ISO datetime | Temporal validity end (null if current) | null |
| `is_current` | boolean | Is this the current version? | true |
| `is_deleted` | boolean | Soft delete flag | false |
| `snapshot_hash` | string | SHA-256 hash for change detection | "a3f2b..." |

**Example Node**:
```cypher
(:HUBSPOT_Contact {
  hubspot_id: "12345",
  email: "john@example.com",
  first_name: "John",
  last_name: "Doe",
  job_title: "VP of Sales",
  lifecycle_stage: "customer",
  total_email_opens: 45,
  total_email_clicks: 12,
  owner_id: "67890",
  is_current: true,
  is_deleted: false
})
```

**Relationships**:
- `(Contact)-[:OWNED_BY]->(User)` - Contact ownership
- `(Contact)-[:WORKS_AT]->(Company)` - Employment relationship
- `(Contact)-[:ASSOCIATED_WITH]->(Deal)` - Deal associations
- `(Contact)-[:VISITED]->(WebPage)` - Page visits
- `(Contact)-[:PERFORMED]->(EmailOpenEvent)` - Email opens
- `(Contact)-[:PERFORMED]->(EmailClickEvent)` - Email clicks
- `(Contact)-[:HAS_HISTORY]->(Contact_HISTORY)` - Historical versions

---

### 2.2 HUBSPOT_Company

**Purpose**: Represents organizations/companies in HubSpot CRM.

**Primary Identifier**: `hubspot_id` (string)

**Source**: HubSpot Companies API (`/crm/v3/objects/companies`)

**Properties**:

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `hubspot_id` | string | Unique HubSpot company ID | "98765" |
| `name` | string | Company name | "Acme Corp" |
| `domain` | string | Website domain (normalized) | "acme.com" |
| `industry` | string | Industry classification | "Technology" |
| `employee_count` | integer | Number of employees | 250 |
| `annual_revenue` | float | Annual revenue | 5000000.00 |
| `description` | string | Company description | "Leading SaaS provider" |
| `created_date` | ISO datetime | When company was created | "2024-01-10T09:00:00Z" |
| `last_modified` | ISO datetime | Last modification timestamp | "2024-11-20T16:45:00Z" |
| `owner_id` | string | HubSpot owner/user ID | "67890" |
| `country` | string | Country | "United States" |
| `city` | string | City | "Austin" |
| `state` | string | State/region | "TX" |
| `valid_from` | ISO datetime | Temporal validity start | "2024-11-21T12:00:00Z" |
| `valid_to` | ISO datetime | Temporal validity end (null if current) | null |
| `is_current` | boolean | Is this the current version? | true |
| `is_deleted` | boolean | Soft delete flag | false |
| `snapshot_hash` | string | SHA-256 hash for change detection | "b4e8c..." |

**Example Node**:
```cypher
(:HUBSPOT_Company {
  hubspot_id: "98765",
  name: "Acme Corp",
  domain: "acme.com",
  industry: "Technology",
  employee_count: 250,
  annual_revenue: 5000000.00,
  owner_id: "67890",
  is_current: true
})
```

**Relationships**:
- `(Company)-[:OWNED_BY]->(User)` - Company ownership
- `(Contact)-[:WORKS_AT]->(Company)` - Employees
- `(Deal)-[:BELONGS_TO]->(Company)` - Deals associated with company
- `(Activity)-[:INVOLVES]->(Company)` - Activities related to company
- `(Company)-[:HAS_HISTORY]->(Company_HISTORY)` - Historical versions

---

### 2.3 HUBSPOT_Deal

**Purpose**: Represents sales opportunities/deals in the sales pipeline.

**Primary Identifier**: `hubspot_id` (string)

**Source**: HubSpot Deals API (`/crm/v3/objects/deals`)

**Properties**:

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `hubspot_id` | string | Unique HubSpot deal ID | "54321" |
| `name` | string | Deal name | "Q4 Enterprise Deal" |
| `amount` | float | Deal value | 125000.00 |
| `stage` | string | Current deal stage | "negotiation" |
| `pipeline` | string | Sales pipeline name | "default" |
| `close_date` | ISO datetime | Expected close date | "2024-12-31T23:59:59Z" |
| `created_date` | ISO datetime | When deal was created | "2024-10-01T08:00:00Z" |
| `last_modified` | ISO datetime | Last modification timestamp | "2024-11-21T09:15:00Z" |
| `owner_id` | string | HubSpot owner/user ID | "67890" |
| `is_won` | boolean | Has deal been won? | false |
| `probability` | float | Win probability (0-100) | 75.0 |
| `valid_from` | ISO datetime | Temporal validity start | "2024-11-21T12:00:00Z" |
| `valid_to` | ISO datetime | Temporal validity end (null if current) | null |
| `is_current` | boolean | Is this the current version? | true |
| `is_deleted` | boolean | Soft delete flag | false |
| `snapshot_hash` | string | SHA-256 hash for change detection | "c7d9a..." |

**Example Node**:
```cypher
(:HUBSPOT_Deal {
  hubspot_id: "54321",
  name: "Q4 Enterprise Deal",
  amount: 125000.00,
  stage: "negotiation",
  probability: 75.0,
  is_won: false,
  owner_id: "67890",
  is_current: true
})
```

**Relationships**:
- `(Deal)-[:OWNED_BY]->(User)` - Deal ownership
- `(Deal)-[:BELONGS_TO]->(Company)` - Associated company
- `(Contact)-[:ASSOCIATED_WITH]->(Deal)` - Associated contacts
- `(Activity)-[:RELATED_TO]->(Deal)` - Deal activities
- `(Deal)-[:HAS_HISTORY]->(Deal_HISTORY)` - Historical versions

---

### 2.4 HUBSPOT_Activity

**Purpose**: Represents engagements/interactions (meetings, calls, notes, tasks).

**Primary Identifier**: `hubspot_id` (string)

**Source**: HubSpot Engagements API (`/crm/v3/objects/engagements`)

**Properties**:

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `hubspot_id` | string | Unique HubSpot engagement ID | "11111" |
| `type` | string | Engagement type | "MEETING", "CALL", "NOTE", "TASK" |
| `timestamp` | ISO datetime | When activity occurred | "2024-11-20T14:00:00Z" |
| `created_date` | ISO datetime | When record was created | "2024-11-20T14:05:00Z" |
| `details` | string | Short description | "Product demo call" |
| `body` | string | Full content/notes | "Discussed pricing..." |
| `start_time` | ISO datetime | Meeting start time (MEETING only) | "2024-11-20T14:00:00Z" |
| `end_time` | ISO datetime | Meeting end time (MEETING only) | "2024-11-20T15:00:00Z" |
| `duration` | integer | Call duration in seconds (CALL only) | 1800 |
| `status` | string | Task status (TASK only) | "COMPLETED" |
| `valid_from` | ISO datetime | Temporal validity start | "2024-11-21T12:00:00Z" |
| `valid_to` | ISO datetime | Temporal validity end (null if current) | null |
| `is_current` | boolean | Is this the current version? | true |
| `is_deleted` | boolean | Soft delete flag | false |
| `snapshot_hash` | string | SHA-256 hash for change detection | "d8e1f..." |

**Activity Types**:
- **MEETING**: Scheduled meetings with title, body, start/end times
- **CALL**: Phone calls with duration and notes
- **NOTE**: Text notes with body content
- **TASK**: Tasks with subject, body, and status

**Example Node**:
```cypher
(:HUBSPOT_Activity {
  hubspot_id: "11111",
  type: "MEETING",
  timestamp: "2024-11-20T14:00:00Z",
  details: "Product demo call",
  body: "Discussed enterprise features and pricing",
  start_time: "2024-11-20T14:00:00Z",
  end_time: "2024-11-20T15:00:00Z",
  is_current: true
})
```

**Relationships**:
- `(Activity)-[:INVOLVES]->(Contact)` - Contacts involved
- `(Activity)-[:INVOLVES]->(Company)` - Companies involved
- `(Activity)-[:RELATED_TO]->(Deal)` - Related deals
- `(Activity)-[:HAS_HISTORY]->(Activity_HISTORY)` - Historical versions

---

### 2.5 HUBSPOT_User

**Purpose**: Represents HubSpot CRM users/owners (sales reps, account managers).

**Primary Identifier**: `hubspot_id` (string)

**Source**: HubSpot Owners API (`/crm/v3/owners`)

**Labels**: 
- Base: `HUBSPOT_User`
- Optional: `Archived` (added when user is archived)

**Properties**:

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `hubspot_id` | string | Unique HubSpot owner ID | "67890" |
| `email` | string | User email (normalized) | "sarah@company.com" |
| `first_name` | string | First name | "Sarah" |
| `last_name` | string | Last name | "Johnson" |
| `active` | boolean | Is user active? | true |
| `archived` | boolean | Is user archived? | false |
| `created_date` | ISO datetime | When user was created | "2023-06-15T09:00:00Z" |
| `last_modified` | ISO datetime | Last modification timestamp | "2024-11-21T08:00:00Z" |
| `user_id` | string | Internal user ID | "user_123" |
| `teams` | string | Comma-separated team names | "Sales, Enterprise" |
| `valid_from` | ISO datetime | Temporal validity start | "2024-11-21T12:00:00Z" |
| `valid_to` | ISO datetime | Temporal validity end (null if current) | null |
| `is_current` | boolean | Is this the current version? | true |
| `is_deleted` | boolean | Soft delete flag | false |
| `snapshot_hash` | string | SHA-256 hash for change detection | "e9f2a..." |

**Example Node**:
```cypher
(:HUBSPOT_User {
  hubspot_id: "67890",
  email: "sarah@company.com",
  first_name: "Sarah",
  last_name: "Johnson",
  active: true,
  archived: false,
  teams: "Sales, Enterprise",
  is_current: true
})
```

**Example Archived User**:
```cypher
(:HUBSPOT_User:Archived {
  hubspot_id: "11111",
  email: "former@company.com",
  first_name: "Former",
  last_name: "Employee",
  active: false,
  archived: true,
  is_current: true
})
```

**Relationships**:
- `(Contact)-[:OWNED_BY]->(User)` - Owned contacts
- `(Company)-[:OWNED_BY]->(User)` - Owned companies
- `(Deal)-[:OWNED_BY]->(User)` - Owned deals
- `(User)-[:HAS_HISTORY]->(User_HISTORY)` - Historical versions

---

### 2.6 HUBSPOT_EmailCampaign

**Purpose**: Represents email marketing campaigns sent through HubSpot.

**Primary Identifier**: `hubspot_id` (string - campaign ID)

**Source**: Email Events API (extracted from email event metadata)

**Properties**:

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `hubspot_id` | string | Unique email campaign ID | "campaign_456" |
| `name` | string | Campaign name | "November Newsletter" |
| `subject` | string | Email subject line | "New Features Announced" |
| `sent_date` | ISO datetime | When campaign was sent | "2024-11-15T10:00:00Z" |

**Example Node**:
```cypher
(:HUBSPOT_EmailCampaign {
  hubspot_id: "campaign_456",
  name: "November Newsletter",
  subject: "New Features Announced",
  sent_date: "2024-11-15T10:00:00Z"
})
```

**Relationships**:
- `(EmailOpenEvent)-[:FOR_CAMPAIGN]->(EmailCampaign)` - Opens for this campaign
- `(EmailClickEvent)-[:FOR_CAMPAIGN]->(EmailCampaign)` - Clicks for this campaign

**Note**: EmailCampaigns are not temporally tracked as they are immutable once sent.

---

### 2.7 HUBSPOT_WebPage

**Purpose**: Represents web pages that were visited or clicked from emails.

**Primary Identifier**: `url` (string - full URL)

**Source**: Derived from contact properties and email click events

**Properties**:

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `hubspot_id` | string | URL (used as ID for consistency) | "https://example.com/pricing" |
| `url` | string | Full URL | "https://example.com/pricing" |
| `domain` | string | Domain name | "example.com" |
| `path` | string | URL path | "/pricing" |
| `title` | string | Page title (if available) | "Pricing Plans" |

**Example Node**:
```cypher
(:HUBSPOT_WebPage {
  hubspot_id: "https://example.com/pricing",
  url: "https://example.com/pricing",
  domain: "example.com",
  path: "/pricing",
  title: ""
})
```

**Relationships**:
- `(Contact)-[:VISITED]->(WebPage)` - Page visits
- `(EmailClickEvent)-[:CLICKED_URL]->(WebPage)` - URLs clicked in emails
- `(FormSubmission)-[:ON_PAGE]->(WebPage)` - Forms submitted on page

**Note**: WebPages are not temporally tracked as they represent URLs, not changing entities.

---

### 2.8 HUBSPOT_EmailOpenEvent

**Purpose**: Individual email open events (immutable event nodes).

**Primary Identifier**: `hubspot_id` (string - generated unique ID)

**Source**: HubSpot Email Events API (filtered for OPEN events)

**Properties**:

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `hubspot_id` | string | Generated unique event ID | "email_open_1234" |
| `timestamp` | ISO datetime | When email was opened | "2024-11-20T09:15:33Z" |
| `campaign_id` | string | Associated campaign ID | "campaign_456" |
| `recipient_email` | string | Email recipient (normalized) | "john@example.com" |
| `device_type` | string | Device used | "MOBILE", "DESKTOP" |
| `location` | string | Geographic location (city) | "San Francisco" |
| `browser` | string | Browser user agent | "Mozilla/5.0..." |

**Example Node**:
```cypher
(:HUBSPOT_EmailOpenEvent {
  hubspot_id: "email_open_1234",
  timestamp: "2024-11-20T09:15:33Z",
  campaign_id: "campaign_456",
  recipient_email: "john@example.com",
  device_type: "MOBILE",
  location: "San Francisco"
})
```

**Relationships**:
- `(Contact)-[:PERFORMED]->(EmailOpenEvent)` - Contact who opened
- `(EmailOpenEvent)-[:FOR_CAMPAIGN]->(EmailCampaign)` - Campaign opened

**Note**: Email open events are **immutable** - never updated or deleted once created.

---

### 2.9 HUBSPOT_EmailClickEvent

**Purpose**: Individual email click events (immutable event nodes).

**Primary Identifier**: `hubspot_id` (string - generated unique ID)

**Source**: HubSpot Email Events API (filtered for CLICK events)

**Properties**:

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `hubspot_id` | string | Generated unique event ID | "email_click_5678" |
| `timestamp` | ISO datetime | When link was clicked | "2024-11-20T09:20:45Z" |
| `campaign_id` | string | Associated campaign ID | "campaign_456" |
| `recipient_email` | string | Email recipient (normalized) | "john@example.com" |
| `device_type` | string | Device used | "MOBILE", "DESKTOP" |
| `location` | string | Geographic location (city) | "San Francisco" |
| `browser` | string | Browser user agent | "Mozilla/5.0..." |
| `clicked_url` | string | URL that was clicked | "https://example.com/product" |

**Example Node**:
```cypher
(:HUBSPOT_EmailClickEvent {
  hubspot_id: "email_click_5678",
  timestamp: "2024-11-20T09:20:45Z",
  campaign_id: "campaign_456",
  recipient_email: "john@example.com",
  device_type: "MOBILE",
  clicked_url: "https://example.com/product"
})
```

**Relationships**:
- `(Contact)-[:PERFORMED]->(EmailClickEvent)` - Contact who clicked
- `(EmailClickEvent)-[:FOR_CAMPAIGN]->(EmailCampaign)` - Campaign clicked
- `(EmailClickEvent)-[:CLICKED_URL]->(WebPage)` - URL clicked

**Note**: Email click events are **immutable** - never updated or deleted once created.

---

### 2.10 HUBSPOT_FormSubmission

**Purpose**: Form submission events from HubSpot forms.

**Primary Identifier**: `hubspot_id` (string - generated unique ID)

**Source**: HubSpot Forms API (`/form-integrations/v1/submissions/forms/{formGuid}`)

**Properties**:

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `hubspot_id` | string | Generated unique submission ID | "form_submission_9012" |
| `timestamp` | ISO datetime | When form was submitted | "2024-11-19T16:30:22Z" |
| `created_date` | ISO datetime | Same as timestamp | "2024-11-19T16:30:22Z" |
| `form_guid` | string | HubSpot form GUID | "abc123-def456" |
| `form_name` | string | Form name | "Contact Us Form" |
| `page_url` | string | Page where form was submitted | "https://example.com/contact" |
| `page_title` | string | Page title | "Contact Us" |
| `ip_address` | string | Submitter's IP address | "192.168.1.1" |
| `email` | string | Submitter's email | "john@example.com" |

**Example Node**:
```cypher
(:HUBSPOT_FormSubmission {
  hubspot_id: "form_submission_9012",
  timestamp: "2024-11-19T16:30:22Z",
  form_guid: "abc123-def456",
  form_name: "Contact Us Form",
  page_url: "https://example.com/contact",
  email: "john@example.com"
})
```

**Relationships**:
- `(FormSubmission)-[:SUBMITTED_BY]->(Contact)` - Contact who submitted
- `(FormSubmission)-[:ON_PAGE]->(WebPage)` - Page where form was submitted

**Note**: Form submissions are **immutable** - never updated or deleted once created.

---

### 2.11 HUBSPOT_PageVisit

**Purpose**: Page visit events (placeholder for future implementation).

**Primary Identifier**: `hubspot_id` (string)

**Source**: Not yet implemented

**Properties**: TBD

**Note**: This node type is defined in the schema but not currently populated by the pipeline.

---

## 3. History Nodes

### Overview

History nodes store previous versions of entity records when changes are detected. They use a `_HISTORY` suffix pattern and are connected to their current version via `HAS_HISTORY` relationships.

### 3.1 History Node Types

- `HUBSPOT_Contact_HISTORY`
- `HUBSPOT_Company_HISTORY`
- `HUBSPOT_Deal_HISTORY`
- `HUBSPOT_Activity_HISTORY`
- `HUBSPOT_User_HISTORY`

### 3.2 History Node Structure

History nodes contain:
- **All properties** from the original node at the time of change
- **Temporal fields** marking when the version was valid

### 3.3 Temporal Properties

| Property | Type | Description |
|----------|------|-------------|
| `valid_from` | ISO datetime | When this version became valid |
| `valid_to` | ISO datetime | When this version was superseded |
| `is_current` | boolean | Always false for history nodes |
| `snapshot_hash` | string | Hash of the historical state |

### 3.4 Example: Contact History

```cypher
// Current version
(:HUBSPOT_Contact {
  hubspot_id: "12345",
  email: "john@example.com",
  job_title: "VP of Sales",  // Updated value
  valid_from: "2024-11-21T12:00:00Z",
  valid_to: null,
  is_current: true
})-[:HAS_HISTORY]->

// Historical version (before job title changed)
(:HUBSPOT_Contact_HISTORY {
  hubspot_id: "12345",
  email: "john@example.com",
  job_title: "Director of Sales",  // Old value
  valid_from: "2024-10-01T08:00:00Z",
  valid_to: "2024-11-21T12:00:00Z",
  is_current: false
})
```

### 3.5 History Creation Process

When a change is detected:

1. **Fetch** current node from Neo4j
2. **Compare** hash with incoming data
3. **Create** history node with copy of current state
4. **Set** `valid_to` on history node to current timestamp
5. **Update** current node with new data
6. **Create** `HAS_HISTORY` relationship

**Implementation**: `temporal_loader.py` → `_update_nodes_with_history()`

### 3.6 Uniqueness Constraint

History nodes have a **composite uniqueness constraint**:
```cypher
(hubspot_id, valid_from) IS UNIQUE
```

This ensures one history snapshot per entity per timestamp.

---

## 4. Change Tracking Node

### 4.1 HUBSPOT_RelationshipChange

**Purpose**: Tracks when relationships are added or removed between entities.

**Properties**:

| Property | Type | Description | Example |
|----------|------|-------------|---------|
| `change_type` | string | Type of change | "added", "removed" |
| `from_entity_type` | string | Source node type | "HUBSPOT_Contact" |
| `from_entity_id` | string | Source node ID | "12345" |
| `to_entity_type` | string | Target node type | "HUBSPOT_Deal" |
| `to_entity_id` | string | Target node ID | "54321" |
| `relationship_type` | string | Relationship type | "ASSOCIATED_WITH" |
| `relationship_properties` | map | Relationship properties (if any) | {} |
| `changed_at` | ISO datetime | When change was detected | "2024-11-21T12:00:00Z" |

**Example Node**:
```cypher
(:HUBSPOT_RelationshipChange {
  change_type: "added",
  from_entity_type: "HUBSPOT_Contact",
  from_entity_id: "12345",
  to_entity_type: "HUBSPOT_Deal",
  to_entity_id: "54321",
  relationship_type: "ASSOCIATED_WITH",
  relationship_properties: {},
  changed_at: "2024-11-21T12:00:00Z"
})
```

### 4.2 What Gets Tracked

**Tracked Relationships** (mutable entity relationships):
- `OWNED_BY`
- `WORKS_AT`
- `ASSOCIATED_WITH`
- `BELONGS_TO`
- `INVOLVES`
- `RELATED_TO`

**Not Tracked** (immutable event relationships):
- `PERFORMED`
- `SUBMITTED_BY`
- `ON_PAGE`
- `FOR_CAMPAIGN`
- `CLICKED_URL`
- `VISITED`

**Rationale**: Immutable relationships represent historical events that never change once created, so tracking adds/removes would be misleading.

### 4.3 Change Detection Process

1. **Build** set of current relationships from Neo4j
2. **Build** set of new relationships from HubSpot data
3. **Compare** sets to find added/removed relationships
4. **Create** RelationshipChange nodes for differences
5. **Delete** removed relationships from graph
6. **Create** new relationships in graph

**Implementation**: `temporal_loader.py` → `_process_relationship_changes()`

---

## 5. Relationship Types

### 5.1 OWNED_BY (Trackable)

**Direction**: Entity → User  
**Cardinality**: Many-to-One  
**Properties**: None

**Variants**:
- `(Contact)-[:OWNED_BY]->(User)`
- `(Company)-[:OWNED_BY]->(User)`
- `(Deal)-[:OWNED_BY]->(User)`

**Purpose**: Links entities to their HubSpot owner/sales rep.

**Change Tracking**: Yes - ownership changes are tracked.

**Example**:
```cypher
MATCH (c:HUBSPOT_Contact {hubspot_id: "12345"})-[:OWNED_BY]->(u:HUBSPOT_User)
RETURN c.email, u.first_name, u.last_name
```

---

### 5.2 WORKS_AT (Trackable)

**Direction**: Contact → Company  
**Cardinality**: Many-to-One  
**Properties**: None

**Purpose**: Links contacts to their employer company.

**Source**: `associatedcompanyid` property from HubSpot Contact

**Change Tracking**: Yes - job changes are tracked.

**Example**:
```cypher
MATCH (contact:HUBSPOT_Contact)-[:WORKS_AT]->(company:HUBSPOT_Company)
WHERE company.name = "Acme Corp"
RETURN contact.first_name, contact.last_name, contact.job_title
```

---

### 5.3 ASSOCIATED_WITH (Trackable)

**Direction**: Contact → Deal  
**Cardinality**: Many-to-Many  
**Properties**: None

**Purpose**: Links contacts to deals they're involved in.

**Source**: Contact-Deal associations from HubSpot

**Change Tracking**: Yes - deal associations are tracked.

**Example**:
```cypher
MATCH (contact:HUBSPOT_Contact)-[:ASSOCIATED_WITH]->(deal:HUBSPOT_Deal)
WHERE contact.email = "john@example.com"
RETURN deal.name, deal.amount, deal.stage
```

---

### 5.4 BELONGS_TO (Trackable)

**Direction**: Deal → Company  
**Cardinality**: Many-to-One  
**Properties**: None

**Purpose**: Links deals to the company they belong to.

**Source**: Deal-Company associations from HubSpot

**Change Tracking**: Yes - deal-company associations are tracked.

**Example**:
```cypher
MATCH (deal:HUBSPOT_Deal)-[:BELONGS_TO]->(company:HUBSPOT_Company)
WHERE deal.amount > 100000
RETURN company.name, sum(deal.amount) as total_value
```

---

### 5.5 VISITED (Immutable)

**Direction**: Contact → WebPage  
**Cardinality**: Many-to-Many  
**Properties**:
- `timestamp` (ISO datetime): When page was visited
- `source` (string): Traffic source

**Purpose**: Tracks contact page visits.

**Source**: Contact properties (`hs_analytics_last_url`)

**Change Tracking**: No - historical visits are immutable.

**Example**:
```cypher
MATCH (contact:HUBSPOT_Contact)-[v:VISITED]->(page:HUBSPOT_WebPage)
WHERE contact.email = "john@example.com"
RETURN page.url, v.timestamp, v.source
ORDER BY v.timestamp DESC
```

---

### 5.6 INVOLVES (Trackable)

**Direction**: Activity → Contact/Company  
**Cardinality**: Many-to-Many  
**Properties**: None

**Variants**:
- `(Activity)-[:INVOLVES]->(Contact)`
- `(Activity)-[:INVOLVES]->(Company)`

**Purpose**: Links activities to the contacts/companies involved.

**Source**: Activity-Contact and Activity-Company associations from HubSpot

**Change Tracking**: Yes - activity associations are tracked.

**Example**:
```cypher
MATCH (activity:HUBSPOT_Activity)-[:INVOLVES]->(contact:HUBSPOT_Contact)
WHERE activity.type = "MEETING"
AND activity.timestamp > datetime("2024-11-01")
RETURN contact.email, activity.details, activity.timestamp
ORDER BY activity.timestamp DESC
```

---

### 5.7 RELATED_TO (Trackable)

**Direction**: Activity → Deal  
**Cardinality**: Many-to-Many  
**Properties**: None

**Purpose**: Links activities to related deals.

**Source**: Activity-Deal associations from HubSpot

**Change Tracking**: Yes - activity-deal associations are tracked.

**Example**:
```cypher
MATCH (activity:HUBSPOT_Activity)-[:RELATED_TO]->(deal:HUBSPOT_Deal)
WHERE deal.hubspot_id = "54321"
RETURN activity.type, activity.details, activity.timestamp
ORDER BY activity.timestamp DESC
```

---

### 5.8 PERFORMED (Immutable)

**Direction**: Contact → EmailOpenEvent/EmailClickEvent  
**Cardinality**: One-to-Many  
**Properties**: None

**Variants**:
- `(Contact)-[:PERFORMED]->(EmailOpenEvent)`
- `(Contact)-[:PERFORMED]->(EmailClickEvent)`

**Purpose**: Links contacts to their email interaction events.

**Source**: Email events matched by email address (not HubSpot ID)

**Change Tracking**: No - email events are immutable historical records.

**Example**:
```cypher
MATCH (contact:HUBSPOT_Contact)-[:PERFORMED]->(event:HUBSPOT_EmailOpenEvent)
WHERE contact.email = "john@example.com"
RETURN event.timestamp, event.campaign_id, event.device_type
ORDER BY event.timestamp DESC
LIMIT 10
```

---

### 5.9 FOR_CAMPAIGN (Immutable)

**Direction**: EmailOpenEvent/EmailClickEvent → EmailCampaign  
**Cardinality**: Many-to-One  
**Properties**: None

**Variants**:
- `(EmailOpenEvent)-[:FOR_CAMPAIGN]->(EmailCampaign)`
- `(EmailClickEvent)-[:FOR_CAMPAIGN]->(EmailCampaign)`

**Purpose**: Links email events to their campaign.

**Source**: Email event metadata

**Change Tracking**: No - campaign associations are immutable.

**Example**:
```cypher
MATCH (event:HUBSPOT_EmailOpenEvent)-[:FOR_CAMPAIGN]->(campaign:HUBSPOT_EmailCampaign)
WHERE campaign.name = "November Newsletter"
RETURN count(DISTINCT event) as total_opens
```

---

### 5.10 CLICKED_URL (Immutable)

**Direction**: EmailClickEvent → WebPage  
**Cardinality**: Many-to-One  
**Properties**: None

**Purpose**: Links email click events to the URL clicked.

**Source**: Email click event `url` field

**Change Tracking**: No - click events are immutable.

**Example**:
```cypher
MATCH (event:HUBSPOT_EmailClickEvent)-[:CLICKED_URL]->(page:HUBSPOT_WebPage)
WHERE page.domain = "example.com"
RETURN page.url, count(event) as click_count
ORDER BY click_count DESC
```

---

### 5.11 SUBMITTED_BY (Immutable)

**Direction**: FormSubmission → Contact  
**Cardinality**: Many-to-One  
**Properties**: None

**Purpose**: Links form submissions to the contact who submitted.

**Source**: Form submission matched by email address

**Change Tracking**: No - form submissions are immutable.

**Example**:
```cypher
MATCH (form:HUBSPOT_FormSubmission)-[:SUBMITTED_BY]->(contact:HUBSPOT_Contact)
WHERE form.form_name = "Contact Us Form"
RETURN contact.email, form.timestamp, form.page_url
ORDER BY form.timestamp DESC
```

---

### 5.12 ON_PAGE (Immutable)

**Direction**: FormSubmission → WebPage  
**Cardinality**: Many-to-One  
**Properties**: None

**Purpose**: Links form submissions to the page where they occurred.

**Source**: Form submission `page_url` field

**Change Tracking**: No - form submissions are immutable.

**Example**:
```cypher
MATCH (form:HUBSPOT_FormSubmission)-[:ON_PAGE]->(page:HUBSPOT_WebPage)
RETURN page.url, count(form) as submission_count
ORDER BY submission_count DESC
```

---

### 5.13 HAS_HISTORY (System)

**Direction**: Entity → Entity_HISTORY  
**Cardinality**: One-to-Many  
**Properties**: None

**Variants**:
- `(Contact)-[:HAS_HISTORY]->(Contact_HISTORY)`
- `(Company)-[:HAS_HISTORY]->(Company_HISTORY)`
- `(Deal)-[:HAS_HISTORY]->(Deal_HISTORY)`
- `(Activity)-[:HAS_HISTORY]->(Activity_HISTORY)`
- `(User)-[:HAS_HISTORY]->(User_HISTORY)`

**Purpose**: Links current entities to their historical versions.

**Source**: Created automatically by temporal loader

**Change Tracking**: N/A - system relationship

**Example**:
```cypher
MATCH (contact:HUBSPOT_Contact {hubspot_id: "12345"})-[:HAS_HISTORY]->(history:HUBSPOT_Contact_HISTORY)
RETURN history.job_title, history.valid_from, history.valid_to
ORDER BY history.valid_from DESC
```

---

## 6. Temporal Tracking System

### 6.1 Architecture Overview

The temporal tracking system maintains two parallel states:

1. **Current State**: Active version of each entity
2. **Historical State**: Chain of previous versions

This enables:
- Point-in-time queries (time travel)
- Change auditing
- Data lineage tracking
- Rollback capabilities

### 6.2 Current State Pattern

**Main entity nodes** represent the current, active version:

```cypher
(:HUBSPOT_Contact {
  hubspot_id: "12345",
  email: "john@example.com",
  job_title: "VP of Sales",
  valid_from: "2024-11-21T12:00:00Z",
  valid_to: null,                    // null = current
  is_current: true,                  // true = current
  is_deleted: false,                 // false = active
  snapshot_hash: "a3f2b..."         // for change detection
})
```

**Querying Current State**:
```cypher
MATCH (n:HUBSPOT_Contact)
WHERE n.is_current = true
RETURN n
```

Or simply:
```cypher
MATCH (n:HUBSPOT_Contact)
WHERE n.valid_to IS NULL
RETURN n
```

### 6.3 History Pattern

**Historical versions** are stored in `_HISTORY` nodes:

```cypher
(:HUBSPOT_Contact_HISTORY {
  hubspot_id: "12345",
  email: "john@example.com",
  job_title: "Director of Sales",   // Old value
  valid_from: "2024-10-01T08:00:00Z",
  valid_to: "2024-11-21T12:00:00Z",  // Superseded timestamp
  is_current: false,
  snapshot_hash: "b4c1a..."
})
```

**Querying Historical State**:
```cypher
// Get state at specific time
MATCH (h:HUBSPOT_Contact_HISTORY {hubspot_id: "12345"})
WHERE h.valid_from <= datetime("2024-11-01T00:00:00Z")
  AND h.valid_to > datetime("2024-11-01T00:00:00Z")
RETURN h
```

### 6.4 Change Detection Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    CHANGE DETECTION PROCESS                  │
└─────────────────────────────────────────────────────────────┘

1. EXTRACT
   ├─> Fetch data from HubSpot API
   └─> Raw JSON responses

2. TRANSFORM
   ├─> Convert to node structure
   ├─> Generate snapshot_hash (SHA-256)
   │   └─> Hash excludes: valid_from, valid_to, is_current, 
   │                       is_deleted, snapshot_hash, last_modified
   └─> Add temporal metadata (valid_from, is_current=true)

3. COMPARE (ChangeDetector)
   ├─> Fetch existing nodes from Neo4j
   ├─> Compare hashes
   └─> Categorize records:
       ├─> NEW: hubspot_id not in Neo4j
       ├─> UPDATED: hash differs from existing
       ├─> UNCHANGED: hash matches existing
       └─> DELETED: in Neo4j but not in new data

4. LOAD (TemporalLoader)
   ├─> NEW NODES
   │   └─> Create with is_current=true
   │
   ├─> UPDATED NODES
   │   ├─> Create history snapshot (copy current state)
   │   ├─> Set valid_to on history node
   │   ├─> Create HAS_HISTORY relationship
   │   └─> Update current node with new data
   │
   ├─> UNCHANGED NODES
   │   └─> Skip (no action needed)
   │
   └─> DELETED NODES
       ├─> Create history snapshot
       ├─> Set is_deleted=true on current node
       ├─> Set valid_to on current node
       └─> Set is_current=false
```

### 6.5 Hash Generation

**Purpose**: Detect meaningful property changes while ignoring metadata.

**Algorithm**:
```python
def generate_property_hash(properties: dict) -> str:
    # Exclude temporal/metadata fields
    excluded = {'valid_from', 'valid_to', 'is_current', 
                'is_deleted', 'snapshot_hash', 'last_modified'}
    
    # Filter and sort
    filtered = {k: v for k, v in sorted(properties.items())
                if k not in excluded and v is not None}
    
    # JSON serialize and hash
    json_str = json.dumps(filtered, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode()).hexdigest()
```

**Implementation**: `utils/change_detector.py` → `generate_property_hash()`

### 6.6 Deletion Handling (Soft Deletes)

When an entity is no longer present in HubSpot data:

1. **Create** history snapshot of current state
2. **Set** flags on current node:
   - `is_deleted = true`
   - `is_current = false`
   - `valid_to = current_timestamp`
3. **Preserve** node in graph (soft delete)

**Querying Deleted Nodes**:
```cypher
MATCH (n)
WHERE n.is_deleted = true
RETURN n.hubspot_id, n.valid_to as deleted_at, labels(n)[0] as type
```

**Querying Active Nodes Only**:
```cypher
MATCH (n:HUBSPOT_Contact)
WHERE (n.is_deleted IS NULL OR n.is_deleted = false)
  AND (n.is_current = true OR n.is_current IS NULL)
RETURN n
```

### 6.7 Relationship Change Tracking

**Trackable Relationships** (entity-to-entity):
- Additions and removals are logged in `HUBSPOT_RelationshipChange` nodes
- Actual relationships are created/deleted in graph
- Change events preserved for auditing

**Immutable Relationships** (event-based):
- Never tracked for changes
- Represent historical facts that cannot change
- Examples: email opens, clicks, form submissions

**Why Separate Treatment?**

| Aspect | Trackable | Immutable |
|--------|-----------|-----------|
| Nature | Mutable entity associations | Historical events |
| Matching | HubSpot ID-based | Email-based |
| Change Meaning | Relationship evolved | Event occurrence |
| Tracking Value | High (shows evolution) | Low (creates noise) |

### 6.8 Temporal Query Patterns

**Current State**:
```cypher
// Simple current state query
MATCH (c:HUBSPOT_Contact)
WHERE c.is_current = true
RETURN c
```

**Point-in-Time (as of date)**:
```cypher
// Get contact state as of November 1, 2024
WITH datetime("2024-11-01T00:00:00Z") as target_date
MATCH (h:HUBSPOT_Contact_HISTORY {hubspot_id: "12345"})
WHERE h.valid_from <= target_date
  AND (h.valid_to > target_date OR h.valid_to IS NULL)
RETURN h
```

**Change History**:
```cypher
// Show all versions of a contact
MATCH (c:HUBSPOT_Contact {hubspot_id: "12345"})-[:HAS_HISTORY]->(h:HUBSPOT_Contact_HISTORY)
RETURN h.job_title, h.valid_from, h.valid_to
ORDER BY h.valid_from DESC
```

**Recent Changes**:
```cypher
// Contacts modified in last 7 days
MATCH (c:HUBSPOT_Contact)
WHERE c.valid_from > datetime() - duration({days: 7})
RETURN c.email, c.valid_from
ORDER BY c.valid_from DESC
```

**Relationship Changes**:
```cypher
// Show ownership changes for contact
MATCH (rc:HUBSPOT_RelationshipChange)
WHERE rc.from_entity_id = "12345"
  AND rc.relationship_type = "OWNED_BY"
RETURN rc.change_type, rc.to_entity_id, rc.changed_at
ORDER BY rc.changed_at DESC
```

### 6.9 Temporal Fields Reference

| Field | Type | Purpose | Values |
|-------|------|---------|--------|
| `valid_from` | ISO datetime | When version became valid | "2024-11-21T12:00:00Z" |
| `valid_to` | ISO datetime | When version was superseded | null (current) or timestamp |
| `is_current` | boolean | Is this the active version? | true (current), false (historical) |
| `is_deleted` | boolean | Has entity been deleted? | true (deleted), false (active) |
| `snapshot_hash` | string | SHA-256 of properties | "a3f2b..." |

---

## 7. Schema Constraints & Indexes

### 7.1 Uniqueness Constraints

**Primary Entity Constraints** (ensure one node per HubSpot ID):

```cypher
CREATE CONSTRAINT hubspot_contact_id IF NOT EXISTS 
FOR (c:HUBSPOT_Contact) REQUIRE c.hubspot_id IS UNIQUE;

CREATE CONSTRAINT hubspot_company_id IF NOT EXISTS 
FOR (c:HUBSPOT_Company) REQUIRE c.hubspot_id IS UNIQUE;

CREATE CONSTRAINT hubspot_deal_id IF NOT EXISTS 
FOR (d:HUBSPOT_Deal) REQUIRE d.hubspot_id IS UNIQUE;

CREATE CONSTRAINT hubspot_activity_id IF NOT EXISTS 
FOR (a:HUBSPOT_Activity) REQUIRE a.hubspot_id IS UNIQUE;

CREATE CONSTRAINT hubspot_user_id IF NOT EXISTS 
FOR (u:HUBSPOT_User) REQUIRE u.hubspot_id IS UNIQUE;

CREATE CONSTRAINT hubspot_email_campaign_id IF NOT EXISTS 
FOR (e:HUBSPOT_EmailCampaign) REQUIRE e.hubspot_id IS UNIQUE;

CREATE CONSTRAINT hubspot_webpage_url IF NOT EXISTS 
FOR (w:HUBSPOT_WebPage) REQUIRE w.url IS UNIQUE;

CREATE CONSTRAINT hubspot_email_open_event_id IF NOT EXISTS 
FOR (e:HUBSPOT_EmailOpenEvent) REQUIRE e.hubspot_id IS UNIQUE;

CREATE CONSTRAINT hubspot_email_click_event_id IF NOT EXISTS 
FOR (e:HUBSPOT_EmailClickEvent) REQUIRE e.hubspot_id IS UNIQUE;

CREATE CONSTRAINT hubspot_form_submission_id IF NOT EXISTS 
FOR (f:HUBSPOT_FormSubmission) REQUIRE f.hubspot_id IS UNIQUE;

CREATE CONSTRAINT hubspot_page_visit_id IF NOT EXISTS 
FOR (p:HUBSPOT_PageVisit) REQUIRE p.hubspot_id IS UNIQUE;
```

**History Node Constraints** (composite: ID + valid_from):

```cypher
CREATE CONSTRAINT hubspot_contact_history_id IF NOT EXISTS 
FOR (h:HUBSPOT_Contact_HISTORY) REQUIRE (h.hubspot_id, h.valid_from) IS UNIQUE;

CREATE CONSTRAINT hubspot_company_history_id IF NOT EXISTS 
FOR (h:HUBSPOT_Company_HISTORY) REQUIRE (h.hubspot_id, h.valid_from) IS UNIQUE;

CREATE CONSTRAINT hubspot_deal_history_id IF NOT EXISTS 
FOR (h:HUBSPOT_Deal_HISTORY) REQUIRE (h.hubspot_id, h.valid_from) IS UNIQUE;

CREATE CONSTRAINT hubspot_activity_history_id IF NOT EXISTS 
FOR (h:HUBSPOT_Activity_HISTORY) REQUIRE (h.hubspot_id, h.valid_from) IS UNIQUE;

CREATE CONSTRAINT hubspot_user_history_id IF NOT EXISTS 
FOR (h:HUBSPOT_User_HISTORY) REQUIRE (h.hubspot_id, h.valid_from) IS UNIQUE;
```

### 7.2 Business Logic Indexes

**Contact Indexes**:
```cypher
CREATE INDEX hubspot_contact_email IF NOT EXISTS 
FOR (c:HUBSPOT_Contact) ON (c.email);

CREATE INDEX hubspot_contact_owner IF NOT EXISTS 
FOR (c:HUBSPOT_Contact) ON (c.owner_id);

CREATE INDEX hubspot_contact_created IF NOT EXISTS 
FOR (c:HUBSPOT_Contact) ON (c.created_date);

CREATE INDEX hubspot_contact_modified IF NOT EXISTS 
FOR (c:HUBSPOT_Contact) ON (c.last_modified);
```

**Company Indexes**:
```cypher
CREATE INDEX hubspot_company_domain IF NOT EXISTS 
FOR (c:HUBSPOT_Company) ON (c.domain);

CREATE INDEX hubspot_company_owner IF NOT EXISTS 
FOR (c:HUBSPOT_Company) ON (c.owner_id);

CREATE INDEX hubspot_company_created IF NOT EXISTS 
FOR (c:HUBSPOT_Company) ON (c.created_date);

CREATE INDEX hubspot_company_modified IF NOT EXISTS 
FOR (c:HUBSPOT_Company) ON (c.last_modified);
```

**Deal Indexes**:
```cypher
CREATE INDEX hubspot_deal_stage IF NOT EXISTS 
FOR (d:HUBSPOT_Deal) ON (d.stage);

CREATE INDEX hubspot_deal_owner IF NOT EXISTS 
FOR (d:HUBSPOT_Deal) ON (d.owner_id);

CREATE INDEX hubspot_deal_created IF NOT EXISTS 
FOR (d:HUBSPOT_Deal) ON (d.created_date);

CREATE INDEX hubspot_deal_modified IF NOT EXISTS 
FOR (d:HUBSPOT_Deal) ON (d.last_modified);

CREATE INDEX hubspot_deal_closedate IF NOT EXISTS 
FOR (d:HUBSPOT_Deal) ON (d.close_date);
```

**Activity Indexes**:
```cypher
CREATE INDEX hubspot_activity_type IF NOT EXISTS 
FOR (a:HUBSPOT_Activity) ON (a.type);

CREATE INDEX hubspot_activity_timestamp IF NOT EXISTS 
FOR (a:HUBSPOT_Activity) ON (a.timestamp);

CREATE INDEX hubspot_activity_created IF NOT EXISTS 
FOR (a:HUBSPOT_Activity) ON (a.created_date);
```

**User Indexes**:
```cypher
CREATE INDEX hubspot_user_email IF NOT EXISTS 
FOR (u:HUBSPOT_User) ON (u.email);
```

**Web & Event Indexes**:
```cypher
CREATE INDEX hubspot_webpage_domain IF NOT EXISTS 
FOR (w:HUBSPOT_WebPage) ON (w.domain);

CREATE INDEX hubspot_email_open_timestamp IF NOT EXISTS 
FOR (e:HUBSPOT_EmailOpenEvent) ON (e.timestamp);

CREATE INDEX hubspot_email_open_campaign IF NOT EXISTS 
FOR (e:HUBSPOT_EmailOpenEvent) ON (e.campaign_id);

CREATE INDEX hubspot_email_click_timestamp IF NOT EXISTS 
FOR (e:HUBSPOT_EmailClickEvent) ON (e.timestamp);

CREATE INDEX hubspot_email_click_campaign IF NOT EXISTS 
FOR (e:HUBSPOT_EmailClickEvent) ON (e.campaign_id);

CREATE INDEX hubspot_form_submission_timestamp IF NOT EXISTS 
FOR (f:HUBSPOT_FormSubmission) ON (f.timestamp);

CREATE INDEX hubspot_form_submission_form IF NOT EXISTS 
FOR (f:HUBSPOT_FormSubmission) ON (f.form_guid);

CREATE INDEX hubspot_page_visit_timestamp IF NOT EXISTS 
FOR (p:HUBSPOT_PageVisit) ON (p.timestamp);

CREATE INDEX hubspot_page_visit_url IF NOT EXISTS 
FOR (p:HUBSPOT_PageVisit) ON (p.page_url);
```

### 7.3 Temporal Indexes

**Main Entity Temporal Indexes**:
```cypher
// Contact temporal indexes
CREATE INDEX hubspot_contact_valid_from IF NOT EXISTS 
FOR (c:HUBSPOT_Contact) ON (c.valid_from);

CREATE INDEX hubspot_contact_valid_to IF NOT EXISTS 
FOR (c:HUBSPOT_Contact) ON (c.valid_to);

CREATE INDEX hubspot_contact_is_current IF NOT EXISTS 
FOR (c:HUBSPOT_Contact) ON (c.is_current);

CREATE INDEX hubspot_contact_is_deleted IF NOT EXISTS 
FOR (c:HUBSPOT_Contact) ON (c.is_deleted);

// Company temporal indexes
CREATE INDEX hubspot_company_valid_from IF NOT EXISTS 
FOR (c:HUBSPOT_Company) ON (c.valid_from);

CREATE INDEX hubspot_company_valid_to IF NOT EXISTS 
FOR (c:HUBSPOT_Company) ON (c.valid_to);

CREATE INDEX hubspot_company_is_current IF NOT EXISTS 
FOR (c:HUBSPOT_Company) ON (c.is_current);

CREATE INDEX hubspot_company_is_deleted IF NOT EXISTS 
FOR (c:HUBSPOT_Company) ON (c.is_deleted);

// Deal temporal indexes
CREATE INDEX hubspot_deal_valid_from IF NOT EXISTS 
FOR (d:HUBSPOT_Deal) ON (d.valid_from);

CREATE INDEX hubspot_deal_valid_to IF NOT EXISTS 
FOR (d:HUBSPOT_Deal) ON (d.valid_to);

CREATE INDEX hubspot_deal_is_current IF NOT EXISTS 
FOR (d:HUBSPOT_Deal) ON (d.is_current);

CREATE INDEX hubspot_deal_is_deleted IF NOT EXISTS 
FOR (d:HUBSPOT_Deal) ON (d.is_deleted);

// Activity temporal indexes
CREATE INDEX hubspot_activity_valid_from IF NOT EXISTS 
FOR (a:HUBSPOT_Activity) ON (a.valid_from);

CREATE INDEX hubspot_activity_valid_to IF NOT EXISTS 
FOR (a:HUBSPOT_Activity) ON (a.valid_to);

CREATE INDEX hubspot_activity_is_current IF NOT EXISTS 
FOR (a:HUBSPOT_Activity) ON (a.is_current);

CREATE INDEX hubspot_activity_is_deleted IF NOT EXISTS 
FOR (a:HUBSPOT_Activity) ON (a.is_deleted);

// User temporal indexes
CREATE INDEX hubspot_user_valid_from IF NOT EXISTS 
FOR (u:HUBSPOT_User) ON (u.valid_from);

CREATE INDEX hubspot_user_valid_to IF NOT EXISTS 
FOR (u:HUBSPOT_User) ON (u.valid_to);

CREATE INDEX hubspot_user_is_current IF NOT EXISTS 
FOR (u:HUBSPOT_User) ON (u.is_current);

CREATE INDEX hubspot_user_is_deleted IF NOT EXISTS 
FOR (u:HUBSPOT_User) ON (u.is_deleted);
```

**History Node Temporal Indexes**:
```cypher
// Contact history
CREATE INDEX hubspot_contact_history_valid_from IF NOT EXISTS 
FOR (h:HUBSPOT_Contact_HISTORY) ON (h.valid_from);

CREATE INDEX hubspot_contact_history_valid_to IF NOT EXISTS 
FOR (h:HUBSPOT_Contact_HISTORY) ON (h.valid_to);

// Company history
CREATE INDEX hubspot_company_history_valid_from IF NOT EXISTS 
FOR (h:HUBSPOT_Company_HISTORY) ON (h.valid_from);

CREATE INDEX hubspot_company_history_valid_to IF NOT EXISTS 
FOR (h:HUBSPOT_Company_HISTORY) ON (h.valid_to);

// Deal history
CREATE INDEX hubspot_deal_history_valid_from IF NOT EXISTS 
FOR (h:HUBSPOT_Deal_HISTORY) ON (h.valid_from);

CREATE INDEX hubspot_deal_history_valid_to IF NOT EXISTS 
FOR (h:HUBSPOT_Deal_HISTORY) ON (h.valid_to);

// Activity history
CREATE INDEX hubspot_activity_history_valid_from IF NOT EXISTS 
FOR (h:HUBSPOT_Activity_HISTORY) ON (h.valid_from);

CREATE INDEX hubspot_activity_history_valid_to IF NOT EXISTS 
FOR (h:HUBSPOT_Activity_HISTORY) ON (h.valid_to);

// User history
CREATE INDEX hubspot_user_history_valid_from IF NOT EXISTS 
FOR (h:HUBSPOT_User_HISTORY) ON (h.valid_from);

CREATE INDEX hubspot_user_history_valid_to IF NOT EXISTS 
FOR (h:HUBSPOT_User_HISTORY) ON (h.valid_to);
```

### 7.4 Relationship Change Indexes

```cypher
CREATE INDEX hubspot_rel_change_timestamp IF NOT EXISTS 
FOR (rc:HUBSPOT_RelationshipChange) ON (rc.changed_at);

CREATE INDEX hubspot_rel_change_type IF NOT EXISTS 
FOR (rc:HUBSPOT_RelationshipChange) ON (rc.change_type);

CREATE INDEX hubspot_rel_change_from_entity IF NOT EXISTS 
FOR (rc:HUBSPOT_RelationshipChange) ON (rc.from_entity_id);

CREATE INDEX hubspot_rel_change_to_entity IF NOT EXISTS 
FOR (rc:HUBSPOT_RelationshipChange) ON (rc.to_entity_id);

CREATE INDEX hubspot_rel_change_rel_type IF NOT EXISTS 
FOR (rc:HUBSPOT_RelationshipChange) ON (rc.relationship_type);
```

---

## 8. Query Patterns & Examples

### 8.1 Current State Queries

**Find All Active Contacts**:
```cypher
MATCH (c:HUBSPOT_Contact)
WHERE c.is_current = true
  AND (c.is_deleted IS NULL OR c.is_deleted = false)
RETURN c
LIMIT 100;
```

**Get Contact with Company and Owner**:
```cypher
MATCH (c:HUBSPOT_Contact {email: "john@example.com"})
WHERE c.is_current = true
OPTIONAL MATCH (c)-[:WORKS_AT]->(company:HUBSPOT_Company)
OPTIONAL MATCH (c)-[:OWNED_BY]->(owner:HUBSPOT_User)
RETURN c.first_name, c.last_name, c.job_title,
       company.name as company,
       owner.first_name + ' ' + owner.last_name as owner;
```

**Find High-Value Deals by Stage**:
```cypher
MATCH (d:HUBSPOT_Deal)
WHERE d.is_current = true
  AND d.amount > 100000
  AND d.stage IN ['proposal', 'negotiation', 'contract_sent']
OPTIONAL MATCH (d)-[:OWNED_BY]->(owner:HUBSPOT_User)
OPTIONAL MATCH (d)-[:BELONGS_TO]->(company:HUBSPOT_Company)
RETURN d.name, d.amount, d.stage, d.close_date,
       company.name as company,
       owner.email as owner_email
ORDER BY d.amount DESC;
```

### 8.2 Historical Queries (Point-in-Time)

**Get Contact State at Specific Date**:
```cypher
WITH datetime("2024-10-01T00:00:00Z") as target_date, "12345" as contact_id

// Try to find in history first
OPTIONAL MATCH (h:HUBSPOT_Contact_HISTORY {hubspot_id: contact_id})
WHERE h.valid_from <= target_date
  AND h.valid_to > target_date
RETURN h as contact

UNION

// If not in history, check if current node existed then
MATCH (c:HUBSPOT_Contact {hubspot_id: contact_id})
WHERE c.valid_from <= target_date
  AND (c.valid_to IS NULL OR c.valid_to > target_date)
RETURN c as contact;
```

**Show Job Title Changes Over Time**:
```cypher
MATCH (c:HUBSPOT_Contact {hubspot_id: "12345"})-[:HAS_HISTORY]->(h:HUBSPOT_Contact_HISTORY)
RETURN h.job_title as title, 
       h.valid_from as from_date, 
       h.valid_to as to_date
ORDER BY h.valid_from DESC;
```

### 8.3 Change Tracking Queries

**Recent Contact Updates (Last 7 Days)**:
```cypher
MATCH (c:HUBSPOT_Contact)
WHERE c.valid_from > datetime() - duration({days: 7})
  AND c.is_current = true
RETURN c.email, c.first_name, c.last_name, c.valid_from
ORDER BY c.valid_from DESC;
```

**Show Ownership Changes**:
```cypher
MATCH (rc:HUBSPOT_RelationshipChange)
WHERE rc.relationship_type = "OWNED_BY"
  AND rc.changed_at > datetime() - duration({days: 30})
MATCH (from) WHERE from.hubspot_id = rc.from_entity_id
MATCH (to) WHERE to.hubspot_id = rc.to_entity_id
RETURN rc.change_type,
       labels(from)[0] as entity_type,
       from.email or from.name as entity,
       to.first_name + ' ' + to.last_name as owner,
       rc.changed_at
ORDER BY rc.changed_at DESC;
```

**Find Deleted Records**:
```cypher
MATCH (n)
WHERE n.is_deleted = true
RETURN labels(n)[0] as entity_type,
       n.hubspot_id,
       n.email or n.name as identifier,
       n.valid_to as deleted_at
ORDER BY n.valid_to DESC
LIMIT 50;
```

### 8.4 Ownership Analysis

**Contacts Per Owner**:
```cypher
MATCH (c:HUBSPOT_Contact)-[:OWNED_BY]->(u:HUBSPOT_User)
WHERE c.is_current = true
  AND (c.is_deleted IS NULL OR c.is_deleted = false)
RETURN u.first_name + ' ' + u.last_name as owner,
       count(c) as contact_count,
       u.email as owner_email
ORDER BY contact_count DESC;
```

**Deals Per Owner with Total Value**:
```cypher
MATCH (d:HUBSPOT_Deal)-[:OWNED_BY]->(u:HUBSPOT_User)
WHERE d.is_current = true
  AND (d.is_deleted IS NULL OR d.is_deleted = false)
RETURN u.first_name + ' ' + u.last_name as owner,
       count(d) as deal_count,
       sum(d.amount) as total_value,
       avg(d.amount) as avg_deal_size
ORDER BY total_value DESC;
```

**Owner Portfolio (Contacts + Companies + Deals)**:
```cypher
MATCH (u:HUBSPOT_User {email: "sarah@company.com"})
OPTIONAL MATCH (u)<-[:OWNED_BY]-(c:HUBSPOT_Contact)
WHERE c.is_current = true
OPTIONAL MATCH (u)<-[:OWNED_BY]-(co:HUBSPOT_Company)
WHERE co.is_current = true
OPTIONAL MATCH (u)<-[:OWNED_BY]-(d:HUBSPOT_Deal)
WHERE d.is_current = true
RETURN u.first_name + ' ' + u.last_name as owner,
       count(DISTINCT c) as contacts,
       count(DISTINCT co) as companies,
       count(DISTINCT d) as deals,
       sum(d.amount) as total_deal_value;
```

### 8.5 Engagement Metrics

**Contacts with Most Email Engagement**:
```cypher
MATCH (c:HUBSPOT_Contact)
WHERE c.is_current = true
  AND c.total_email_opens > 0
RETURN c.email, c.first_name, c.last_name,
       c.total_email_opens as opens,
       c.total_email_clicks as clicks,
       round(toFloat(c.total_email_clicks) / c.total_email_opens * 100, 1) as click_rate
ORDER BY c.total_email_opens DESC
LIMIT 20;
```

**Email Campaign Performance**:
```cypher
MATCH (campaign:HUBSPOT_EmailCampaign)<-[:FOR_CAMPAIGN]-(open:HUBSPOT_EmailOpenEvent)
WITH campaign, count(DISTINCT open) as opens
MATCH (campaign)<-[:FOR_CAMPAIGN]-(click:HUBSPOT_EmailClickEvent)
WITH campaign, opens, count(DISTINCT click) as clicks
RETURN campaign.name,
       campaign.subject,
       campaign.sent_date,
       opens,
       clicks,
       round(toFloat(clicks) / opens * 100, 2) as click_through_rate
ORDER BY opens DESC;
```

**Recent Email Opens by Contact**:
```cypher
MATCH (c:HUBSPOT_Contact {email: "john@example.com"})-[:PERFORMED]->(event:HUBSPOT_EmailOpenEvent)
MATCH (event)-[:FOR_CAMPAIGN]->(campaign:HUBSPOT_EmailCampaign)
RETURN event.timestamp,
       campaign.name,
       campaign.subject,
       event.device_type,
       event.location
ORDER BY event.timestamp DESC
LIMIT 10;
```

### 8.6 Relationship Traversal (Multi-Hop)

**Contact → Deal → Company Path**:
```cypher
MATCH path = (c:HUBSPOT_Contact)-[:ASSOCIATED_WITH]->(d:HUBSPOT_Deal)-[:BELONGS_TO]->(co:HUBSPOT_Company)
WHERE c.email = "john@example.com"
  AND c.is_current = true
  AND d.is_current = true
  AND co.is_current = true
RETURN c.first_name + ' ' + c.last_name as contact,
       d.name as deal,
       d.amount as deal_value,
       co.name as company;
```

**Company → Deals → Contacts (All Relationships)**:
```cypher
MATCH (company:HUBSPOT_Company {name: "Acme Corp"})
WHERE company.is_current = true
OPTIONAL MATCH (company)<-[:BELONGS_TO]-(deal:HUBSPOT_Deal)
WHERE deal.is_current = true
OPTIONAL MATCH (deal)<-[:ASSOCIATED_WITH]-(contact:HUBSPOT_Contact)
WHERE contact.is_current = true
RETURN company.name,
       collect(DISTINCT {
         deal: deal.name,
         amount: deal.amount,
         stage: deal.stage,
         contacts: collect(contact.first_name + ' ' + contact.last_name)
       }) as deals;
```

**Activity Timeline for Deal**:
```cypher
MATCH (d:HUBSPOT_Deal {hubspot_id: "54321"})<-[:RELATED_TO]-(a:HUBSPOT_Activity)
WHERE d.is_current = true
  AND a.is_current = true
OPTIONAL MATCH (a)-[:INVOLVES]->(c:HUBSPOT_Contact)
RETURN a.timestamp,
       a.type,
       a.details,
       collect(c.first_name + ' ' + c.last_name) as participants
ORDER BY a.timestamp DESC;
```

### 8.7 Event Timeline (Time-Series)

**Email Engagement Timeline**:
```cypher
MATCH (c:HUBSPOT_Contact {email: "john@example.com"})
MATCH (c)-[:PERFORMED]->(event)
WHERE event:HUBSPOT_EmailOpenEvent OR event:HUBSPOT_EmailClickEvent
RETURN event.timestamp,
       labels(event)[0] as event_type,
       event.campaign_id
ORDER BY event.timestamp DESC
LIMIT 50;
```

**Daily Email Opens (Aggregated)**:
```cypher
MATCH (event:HUBSPOT_EmailOpenEvent)
WHERE event.timestamp > datetime() - duration({days: 30})
RETURN date(event.timestamp) as day,
       count(event) as opens
ORDER BY day DESC;
```

**Form Submissions Over Time**:
```cypher
MATCH (form:HUBSPOT_FormSubmission)
WHERE form.timestamp > datetime() - duration({days: 90})
RETURN date(form.timestamp) as day,
       form.form_name,
       count(form) as submissions
ORDER BY day DESC, submissions DESC;
```

### 8.8 Advanced Analysis

**Lead-to-Customer Conversion Path**:
```cypher
// Find contacts that became customers
MATCH (c:HUBSPOT_Contact)
WHERE c.is_current = true
  AND c.lifecycle_stage = "customer"
OPTIONAL MATCH (c)-[:HAS_HISTORY]->(h:HUBSPOT_Contact_HISTORY)
WHERE h.lifecycle_stage = "lead"
WITH c, h
ORDER BY h.valid_from
RETURN c.email,
       h.lifecycle_stage as from_stage,
       h.valid_to as became_customer_at,
       duration.between(h.valid_from, h.valid_to).days as days_to_convert
LIMIT 20;
```

**Deal Velocity by Owner**:
```cypher
MATCH (d:HUBSPOT_Deal)-[:OWNED_BY]->(u:HUBSPOT_User)
WHERE d.is_won = true
  AND d.close_date IS NOT NULL
WITH u, d, 
     duration.between(datetime(d.created_date), datetime(d.close_date)).days as days_to_close
RETURN u.first_name + ' ' + u.last_name as owner,
       count(d) as deals_won,
       avg(days_to_close) as avg_days_to_close,
       sum(d.amount) as total_won_value
ORDER BY deals_won DESC;
```

**Contact Engagement Score**:
```cypher
MATCH (c:HUBSPOT_Contact)
WHERE c.is_current = true
WITH c,
     c.total_email_opens * 1 as open_score,
     c.total_email_clicks * 3 as click_score,
     c.total_page_views * 2 as visit_score
OPTIONAL MATCH (c)-[:PERFORMED]->(form:HUBSPOT_FormSubmission)
WITH c, open_score, click_score, visit_score, count(form) * 10 as form_score
RETURN c.email,
       c.first_name + ' ' + c.last_name as name,
       open_score + click_score + visit_score + form_score as engagement_score,
       {opens: open_score, clicks: click_score, visits: visit_score, forms: form_score} as breakdown
ORDER BY engagement_score DESC
LIMIT 50;
```

---

## 9. Data Flow Summary

### 9.1 Pipeline Stages

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA FLOW ARCHITECTURE                    │
└─────────────────────────────────────────────────────────────┘

STAGE 1: EXTRACT (main.py)
├─> ContactsExtractor      → /crm/v3/objects/contacts
├─> CompaniesExtractor     → /crm/v3/objects/companies
├─> DealsExtractor         → /crm/v3/objects/deals
├─> EngagementsExtractor   → /crm/v3/objects/engagements
├─> EmailEventsExtractor   → /events/v3/email-events
├─> UsersExtractor         → /crm/v3/owners
└─> FormSubmissionsExtractor → /form-integrations/v1/submissions/forms
    │
    └─> Raw JSON data saved to data/raw/

STAGE 2: TRANSFORM (graph_transformer.py)
├─> Transform Users (needed for owner relationships)
├─> Transform Contacts
├─> Transform Companies
├─> Transform Deals
├─> Transform Engagements → Activities
├─> Transform Email Events → EmailCampaigns, OpenEvents, ClickEvents, WebPages
└─> Transform Form Submissions → FormSubmission nodes
    │
    ├─> Create node dictionaries with properties
    ├─> Generate snapshot hashes
    ├─> Add temporal metadata (valid_from, is_current)
    ├─> Build relationships list
    └─> Saved to data/transformed/

STAGE 3: LOAD (temporal_loader.py)
├─> Setup schema (constraints & indexes)
├─> For each node type:
│   ├─> Fetch existing nodes from Neo4j
│   ├─> Compare hashes (ChangeDetector)
│   ├─> Categorize: new, updated, unchanged, deleted
│   ├─> Load new nodes
│   ├─> Update changed nodes (with history)
│   └─> Mark deleted nodes (soft delete)
│
└─> For relationships:
    ├─> Separate into trackable vs immutable
    ├─> Load immutable relationships (no tracking)
    ├─> Detect changes in trackable relationships
    ├─> Create RelationshipChange nodes
    └─> Update graph relationships
```

### 9.2 When Nodes Are Created

| Event | Action | Location |
|-------|--------|----------|
| First pipeline run | All nodes created as new | `_load_new_nodes()` |
| Subsequent runs - new entity in HubSpot | New node created | `_load_new_nodes()` |
| Subsequent runs - entity changed | History snapshot + update current | `_update_nodes_with_history()` |
| Subsequent runs - entity gone | Mark deleted (soft delete) | `_mark_nodes_deleted()` |
| Email event detected | Create immutable event node | `_transform_email_events()` |
| Form submission detected | Create immutable submission node | `_transform_form_submissions()` |

### 9.3 When Nodes Are Updated

**Update Triggers**:
- Property hash differs from existing
- Any business property changed (except temporal/metadata fields)

**Update Process**:
1. Snapshot current state → create _HISTORY node
2. Set valid_to on history node
3. Create HAS_HISTORY relationship
4. Update current node properties
5. Update valid_from on current node
6. Regenerate snapshot_hash

**Implementation**: `temporal_loader.py` → `_update_nodes_with_history()`

### 9.4 When Nodes Are Deleted

**Deletion Triggers**:
- Entity present in Neo4j but not in new HubSpot data
- Soft delete approach (never hard delete)

**Deletion Process**:
1. Create history snapshot
2. Set is_deleted = true
3. Set is_current = false
4. Set valid_to = current_timestamp
5. Preserve all relationships (for historical queries)

**Implementation**: `temporal_loader.py` → `_mark_nodes_deleted()`

### 9.5 When Relationships Are Tracked

**Trackable Relationships** (changes logged):
- OWNED_BY
- WORKS_AT
- ASSOCIATED_WITH
- BELONGS_TO
- INVOLVES
- RELATED_TO

**Immutable Relationships** (never tracked):
- PERFORMED
- SUBMITTED_BY
- ON_PAGE
- FOR_CAMPAIGN
- CLICKED_URL
- VISITED

**Tracking Process**:
1. Build set of existing trackable relationships
2. Build set of new trackable relationships
3. Compare sets: added = new - existing, removed = existing - new
4. Create HUBSPOT_RelationshipChange nodes for changes
5. Delete removed relationships from graph
6. Create new relationships in graph

**Implementation**: `temporal_loader.py` → `_process_relationship_changes()`

### 9.6 Configuration

**Batch Size**: 100 records per Neo4j transaction (configurable in `config/settings.py`)

**Immutable Relationship Types**: Defined in `config/settings.py`:
```python
IMMUTABLE_EVENT_RELATIONSHIPS = {
    'PERFORMED',
    'SUBMITTED_BY',
    'ON_PAGE',
    'FOR_CAMPAIGN',
    'CLICKED_URL',
    'VISITED'
}
```

---

## 10. Special Patterns

### 10.1 Email Matching Pattern

**Problem**: Email events from HubSpot don't include HubSpot contact IDs, only email addresses.

**Solution**: Match by email address instead of hubspot_id.

**Implementation**:

In `graph_transformer.py`:
```python
# Create relationship using email instead of ID
self.relationships.append({
    'type': 'PERFORMED',
    'from_type': 'HUBSPOT_Contact',
    'from_email': 'john@example.com',  # Email instead of from_id
    'to_type': 'HUBSPOT_EmailOpenEvent',
    'to_id': event_id,
    'properties': {}
})
```

In `temporal_loader.py`:
```cypher
// Special query for email-based relationships
MATCH (a:HUBSPOT_Contact {email: rel.from_email})
MATCH (b:HUBSPOT_EmailOpenEvent {hubspot_id: rel.to_id})
MERGE (a)-[r:PERFORMED]->(b)
```

**Affected Relationships**:
- Contact → EmailOpenEvent
- Contact → EmailClickEvent
- FormSubmission → Contact (matched by submission email)

**Implications**:
- Email changes can break historical links
- Email normalization critical (lowercase, trimmed)
- These relationships excluded from change tracking

### 10.2 Archived Users Pattern

**Purpose**: Distinguish active users from deactivated/archived ones.

**Implementation**:

Users have two possible label combinations:
1. Active: `HUBSPOT_User`
2. Archived: `HUBSPOT_User:Archived`

**Loading Logic** (`temporal_loader.py`):
```cypher
// Add Archived label conditionally
FOREACH (_ IN CASE WHEN node.archived = true THEN [1] ELSE [] END |
    SET n:Archived
)
```

**Querying**:
```cypher
// Find only active users
MATCH (u:HUBSPOT_User)
WHERE NOT u:Archived
RETURN u;

// Find archived users
MATCH (u:HUBSPOT_User:Archived)
RETURN u;
```

**Ownership Queries**:
```cypher
// Include archived owner's name even if archived
MATCH (c:HUBSPOT_Contact)-[:OWNED_BY]->(u:HUBSPOT_User)
RETURN c.email, 
       u.first_name + ' ' + u.last_name as owner,
       u.archived as owner_archived;
```

### 10.3 Immutable Event Node Pattern

**Purpose**: Represent historical events that never change once created.

**Event Types**:
- EmailOpenEvent
- EmailClickEvent
- FormSubmission
- PageVisit (future)

**Characteristics**:
- No temporal tracking (no valid_from/valid_to)
- No history nodes
- Never updated or deleted
- Generated unique IDs (not from HubSpot)
- Timestamp property indexed for time-series queries

**ID Generation**:
```python
self.event_id_counter += 1
event_id = f"email_open_{self.event_id_counter}"
```

**Why Immutable?**:
- Events are historical facts
- Updating an event doesn't make semantic sense
- High volume (millions of events)
- Tracking changes would create noise

**Query Optimization**:
```cypher
// Use timestamp indexes for time ranges
MATCH (e:HUBSPOT_EmailOpenEvent)
WHERE e.timestamp > datetime("2024-11-01")
  AND e.timestamp < datetime("2024-12-01")
RETURN count(e);
```

### 10.4 URL-Based Identity Pattern

**Purpose**: Use URL as primary identifier for web pages.

**Implementation**:

WebPage nodes use URL as both ID and unique constraint:
```cypher
CREATE CONSTRAINT hubspot_webpage_url IF NOT EXISTS 
FOR (w:HUBSPOT_WebPage) REQUIRE w.url IS UNIQUE;
```

Node structure:
```python
{
    'hubspot_id': 'https://example.com/pricing',  # URL as ID
    'url': 'https://example.com/pricing',         # Also stored as url
    'domain': 'example.com',
    'path': '/pricing'
}
```

**Rationale**:
- Web pages don't have HubSpot IDs
- URLs are naturally unique
- Enables deduplication across contexts (email clicks + page visits)

**Relationships**:
```cypher
// Create/match by URL
MERGE (page:HUBSPOT_WebPage {url: $url})

// Link from events
MATCH (event:HUBSPOT_EmailClickEvent)-[:CLICKED_URL]->(page:HUBSPOT_WebPage {url: $url})
```

### 10.5 Form Submission Matching Pattern

**Challenge**: Form submissions from Forms API don't include contact IDs.

**Solution**: Build email-to-contact lookup during transformation.

**Implementation** (`graph_transformer.py`):
```python
# Build lookup table
email_to_contact = {}
for contact in self.nodes['HUBSPOT_Contact']:
    email = contact.get('email', '').lower().strip()
    if email:
        email_to_contact[email] = contact.get('hubspot_id')

# Match submissions
for submission in submissions:
    submission_email = submission.get('email', '').lower().strip()
    if submission_email in email_to_contact:
        contact_id = email_to_contact[submission_email]
        # Create relationship
```

**Match Statistics**:
- Matched: Submission email found in contacts
- Unmatched: Submission from unknown email (not in CRM)

**Logging**:
```
Form submissions: 45 matched to contacts, 3 unmatched
```

### 10.6 Deduplication Pattern

**WebPages**:
- Tracked in `processed_urls` set during transformation
- Only create once per URL even if seen multiple times

**EmailCampaigns**:
- Tracked in `processed_campaigns` set
- Only create once per campaign_id even if many events

**Implementation**:
```python
if url not in self.processed_urls:
    self.processed_urls.add(url)
    # Create webpage node

if campaign_id not in self.processed_campaigns:
    self.processed_campaigns.add(campaign_id)
    # Create campaign node
```

**Rationale**: Avoid duplicate nodes when same URL/campaign appears in multiple events.

### 10.7 Timestamp Parsing Pattern

**Multiple Formats Handled**:
1. Unix timestamps (milliseconds): `1700000000000`
2. ISO format: `"2024-11-20T14:30:00Z"`
3. Other string formats

**Implementation**:
```python
def _parse_date(self, date_str: str) -> str:
    if not date_str:
        return ''
    
    try:
        # Handle Unix timestamp
        if isinstance(date_str, (int, float)):
            return datetime.fromtimestamp(date_str / 1000).isoformat()
        
        # Handle ISO format
        if 'T' in str(date_str):
            return date_str
        
        # Try to parse other formats
        return datetime.fromisoformat(date_str.replace('Z', '+00:00')).isoformat()
    except:
        return str(date_str)
```

**Normalization**: All timestamps stored as ISO 8601 strings in UTC.

---

## Appendix A: Quick Reference

### Node Types Summary

| Node Type | Temporal | Immutable | Primary Key | Count (Typical) |
|-----------|----------|-----------|-------------|-----------------|
| HUBSPOT_Contact | ✓ | ✗ | hubspot_id | 10K-100K |
| HUBSPOT_Company | ✓ | ✗ | hubspot_id | 1K-10K |
| HUBSPOT_Deal | ✓ | ✗ | hubspot_id | 1K-50K |
| HUBSPOT_Activity | ✓ | ✗ | hubspot_id | 10K-500K |
| HUBSPOT_User | ✓ | ✗ | hubspot_id | 10-1000 |
| HUBSPOT_EmailCampaign | ✗ | ✓ | hubspot_id | 100-5K |
| HUBSPOT_WebPage | ✗ | ✓ | url | 1K-10K |
| HUBSPOT_EmailOpenEvent | ✗ | ✓ | generated | 100K-10M |
| HUBSPOT_EmailClickEvent | ✗ | ✓ | generated | 10K-1M |
| HUBSPOT_FormSubmission | ✗ | ✓ | generated | 1K-100K |

### Relationship Types Summary

| Relationship | Trackable | Matching | Cardinality |
|--------------|-----------|----------|-------------|
| OWNED_BY | ✓ | hubspot_id | Many-to-One |
| WORKS_AT | ✓ | hubspot_id | Many-to-One |
| ASSOCIATED_WITH | ✓ | hubspot_id | Many-to-Many |
| BELONGS_TO | ✓ | hubspot_id | Many-to-One |
| INVOLVES | ✓ | hubspot_id | Many-to-Many |
| RELATED_TO | ✓ | hubspot_id | Many-to-Many |
| VISITED | ✗ | hubspot_id | Many-to-Many |
| PERFORMED | ✗ | email | One-to-Many |
| FOR_CAMPAIGN | ✗ | hubspot_id | Many-to-One |
| CLICKED_URL | ✗ | hubspot_id | Many-to-One |
| SUBMITTED_BY | ✗ | email | Many-to-One |
| ON_PAGE | ✗ | hubspot_id | Many-to-One |
| HAS_HISTORY | N/A | hubspot_id | One-to-Many |

### Common Cypher Patterns

```cypher
-- Current state only
WHERE n.is_current = true AND (n.is_deleted IS NULL OR n.is_deleted = false)

-- Point-in-time query
WHERE n.valid_from <= $timestamp 
  AND (n.valid_to IS NULL OR n.valid_to > $timestamp)

-- Recent changes
WHERE n.valid_from > datetime() - duration({days: 7})

-- History chain
MATCH (n)-[:HAS_HISTORY]->(h)
ORDER BY h.valid_from DESC
```

---

## Appendix B: File References

| Component | File Path | Purpose |
|-----------|-----------|---------|
| Pipeline orchestrator | `main.py` | Extract → Transform → Load flow |
| Graph transformer | `transformers/graph_transformer.py` | Convert HubSpot data to nodes/rels |
| Temporal loader | `loaders/temporal_loader.py` | Load with change detection |
| Change detector | `utils/change_detector.py` | Hash comparison & change detection |
| Schema definitions | `config/neo4j_schema.py` | Constraints & indexes |
| Settings | `config/settings.py` | Configuration & immutable rel types |
| Extractors | `extractors/*.py` | HubSpot API clients |

---

## Appendix C: Glossary

**Temporal Tracking**: Maintaining time-based versions of data to enable point-in-time queries.

**Bitemporal**: Tracking two timelines - when data was valid in the real world (valid time) and when it was recorded in the database (transaction time). This implementation focuses on valid time.

**Snapshot Hash**: SHA-256 hash of entity properties used to detect changes.

**Soft Delete**: Marking records as deleted without removing them from the database.

**Immutable Event**: Historical event that never changes once created (e.g., email open).

**Change Detection**: Comparing new data with existing data to identify what changed.

**History Node**: Node storing a previous version of an entity.

**Relationship Change**: Tracked event when a relationship is added or removed.

---

**End of Documentation**

---

For questions or contributions, please refer to the main project README.md.

