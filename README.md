# HubSpot → Neo4j Pipeline

A Python pipeline that extracts CRM data from HubSpot (contacts, companies, deals, engagements, users/owners, marketing email events, and form submissions), transforms it into a graph model, and loads it into Neo4j.

## Features
- Contacts, Companies, Deals extraction (with associations where supported)
- **Users/Owners extraction** with ownership relationships (v2)
- Engagements (meetings, calls, notes, tasks)
- Marketing Email Events (opens/clicks via legacy Email Events API)
- **Form Submissions** with field values and contact linking (v2.1)
- **Timestamp indexing** for temporal queries and recency analysis (v2)
- **Entity matching** to link HubSpot users to existing Knowledge Graph Person nodes (v2)
- Graph transformation into nodes and relationships
- Loader to push into Neo4j with simple verification queries

## Prerequisites
- Python 3.9+
- Neo4j running and reachable
- HubSpot Private App with required scopes (see below)

## Installation

```bash
# from the hubspot-neo4j-pipeline directory
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration (.env)
Place a `.env` file in this folder (hubspot-neo4j-pipeline/.env). The pipeline now deterministically loads this .env first.

Required:
```
HUBSPOT_ACCESS_TOKEN=pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

Multiple apps (optional):
- You can keep multiple tokens and select one at runtime.
```
# Default app token
HUBSPOT_ACCESS_TOKEN=pat-na1-...

# Additional app token(s)
BIGCO_ACCESS_TOKEN=pat-na1-...
# Select via HUBSPOT_APP
# HUBSPOT_APP=BIGCO
```
At runtime you can also override:
```bash
HUBSPOT_APP=BIGCO python main.py
```
If `HUBSPOT_APP` is set, the pipeline uses `<APPNAME>_ACCESS_TOKEN`. Otherwise it uses `HUBSPOT_ACCESS_TOKEN`.

Optional feature flags (for easy rollback/testing):
```
# Use Contacts basic_api.get_page instead of Search API (avoids 10k cap). Default: true
USE_BASIC_API_FOR_CONTACTS=true

# Use offset query parameter for legacy Email Events pagination. Default: true
USE_EMAIL_EVENTS_OFFSET_PAGINATION=true

# Log a progress message every N contacts during extraction. Default: 5000
CONTACTS_PAGE_LOG_INTERVAL=5000
```

## Required HubSpot Scopes
The pipeline reads these resources:
- Contacts, Companies, Deals
- Engagements (meetings, calls, notes, tasks)
- Marketing Email Events (legacy endpoint)
- Form Submissions
- Users/Owners

Grant the following scopes to your Private App (read-only where applicable):

**Core CRM Objects:**
- crm.objects.contacts.read
- crm.objects.companies.read
- crm.objects.deals.read
- EITHER crm.objects.engagements.read OR granular:
  - crm.objects.calls.read
  - crm.objects.meetings.read
  - crm.objects.notes.read
  - crm.objects.tasks.read

**Marketing & Events:**
- marketing-email (required by GET /email/public/v1/events)
- **forms** or **forms-uploaded-files** - Required for extracting form submissions

**Ownership & Users:**
- **crm.objects.owners.read** - Required for extracting owner/user data and creating ownership relationships (`OWNED_BY`)
- **settings.users.read** - Alternative scope for users/owners (either this or crm.objects.owners.read)

Optional (recommended):
- crm.pipelines.read (pipeline/stage metadata)
- crm.schemas.read (property metadata)
- crm.lists.read (if using lists)
- crm.objects.tickets.read (if adding tickets)
- crm.objects.products.read, crm.objects.line_items.read (if adding products/line items)

## HubSpot APIs Used (and why)
- Contacts: `hubspot.crm.contacts.basic_api.get_page`
  - Rationale: avoids the HubSpot Search API's hard cap at 10,000 results. Paginates through all contacts.
  - Toggle with `USE_BASIC_API_FOR_CONTACTS`.
- Companies: `hubspot.crm.companies.basic_api.get_page`
- Deals: `hubspot.crm.deals.basic_api.get_page` with `associations` where supported
- Engagements: `hubspot.crm.objects.search_api.do_search(object_type="engagements")`
  - Important: the `object_type` parameter is required by the Objects Search API.
- **Users/Owners (v2)**: `hubspot.crm.owners.owners_api.get_page`
  - Extracts all HubSpot users/owners with their details (email, name, teams, active status)
  - Requires `crm.objects.owners.read` or `settings.users.read` scope
- Email Events (legacy): `GET https://api.hubapi.com/email/public/v1/events` with `offset` passed as a query parameter
  - Toggle the pagination style with `USE_EMAIL_EVENTS_OFFSET_PAGINATION`.
- **Form Submissions (v2.1)**: Two-step workflow using Forms API
  - Step 1: `hubspot.marketing.forms.forms_api.get_page` - List all forms
  - Step 2: `GET https://api.hubapi.com/form-integrations/v1/submissions/forms/{form_guid}` - Get submissions per form (legacy v1 endpoint)
  - Requires `forms` or `forms-uploaded-files` scope

## Running the Pipeline
From this folder:
```bash
python main.py
```
The pipeline will:
1) Extract HubSpot data (saved to data/raw/*.json)
2) Transform to graph (saved to data/transformed/nodes.json and relationships.json)
3) Load to Neo4j and print counts

Example Cypher queries are logged at the end to explore results.

## Graph Model (Nodes and Relationships)

### Nodes

#### Core Entities
- `HUBSPOT_Contact(hubspot_id, email, first_name, last_name, lifecycle_stage, owner_id, created_date, last_modified, total_email_opens, total_email_clicks, total_page_views, …)`
- `HUBSPOT_Company(hubspot_id, name, domain, owner_id, created_date, last_modified, …)`
- `HUBSPOT_Deal(hubspot_id, name, amount, stage, owner_id, created_date, last_modified, close_date, …)`
- `HUBSPOT_Activity(hubspot_id, type, timestamp, created_date, …)` – from Engagements (meetings, calls, notes, tasks)
- `HUBSPOT_EmailCampaign(hubspot_id, name, subject, sent_date)`
- `HUBSPOT_WebPage(url, domain, path)`
- **`HUBSPOT_User(hubspot_id, email, first_name, last_name, active, created_date, last_modified, teams)` (v2)** – HubSpot users/owners

#### Event Nodes (v2.1 - Timestamp Refactor)
**These event nodes have indexed timestamps for temporal queries:**
- **`HUBSPOT_EmailOpenEvent(hubspot_id, timestamp, campaign_id, recipient_email, device_type, location, browser)`** – Individual email opens
- **`HUBSPOT_EmailClickEvent(hubspot_id, timestamp, campaign_id, recipient_email, clicked_url, device_type, location, browser)`** – Individual email clicks
- **`HUBSPOT_FormSubmission(hubspot_id, timestamp, created_date, form_guid, page_url, page_title, ip_address)`** – Form submissions
- **`HUBSPOT_PageVisit(hubspot_id, timestamp, page_url, contact_id, referrer, session_id)` (coming soon)** – Page visits

### Relationships

#### Core Relationships
- `(HUBSPOT_Contact)-[:WORKS_AT]->(HUBSPOT_Company)` – via `associatedcompanyid`
- `(HUBSPOT_Contact)-[:ASSOCIATED_WITH]->(HUBSPOT_Deal)`
- `(HUBSPOT_Deal)-[:BELONGS_TO]->(HUBSPOT_Company)`
- `(HUBSPOT_Activity)-[:INVOLVES]->(HUBSPOT_Contact)`
- `(HUBSPOT_Contact)-[:VISITED]->(HUBSPOT_WebPage)` – Last visit only (legacy)
- **`(HUBSPOT_Contact)-[:OWNED_BY]->(HUBSPOT_User)` (v2)** – Contact ownership
- **`(HUBSPOT_Company)-[:OWNED_BY]->(HUBSPOT_User)` (v2)** – Company ownership
- **`(HUBSPOT_Deal)-[:OWNED_BY]->(HUBSPOT_User)` (v2)** – Deal ownership
- **`(HUBSPOT_User)-[:SAME_AS]->(Person)` (v2, optional)** – Links to existing Knowledge Graph Person nodes

#### Event Relationships (v2.1)
**New event-based relationships with queryable timestamps:**
- **`(HUBSPOT_Contact)-[:PERFORMED]->(HUBSPOT_EmailOpenEvent)`** – Contact performed email open
- **`(HUBSPOT_EmailOpenEvent)-[:FOR_CAMPAIGN]->(HUBSPOT_EmailCampaign)`** – Event for specific campaign
- **`(HUBSPOT_Contact)-[:PERFORMED]->(HUBSPOT_EmailClickEvent)`** – Contact performed email click
- **`(HUBSPOT_EmailClickEvent)-[:FOR_CAMPAIGN]->(HUBSPOT_EmailCampaign)`** – Event for specific campaign
- **`(HUBSPOT_EmailClickEvent)-[:CLICKED_URL]->(HUBSPOT_WebPage)`** – Event clicked specific URL
- **`(HUBSPOT_FormSubmission)-[:SUBMITTED_BY]->(HUBSPOT_Contact)`** – Form submission by contact
- **`(HUBSPOT_FormSubmission)-[:ON_PAGE]->(HUBSPOT_WebPage)`** – Submission on specific page

### Indexes (v2/v2.1)
All timestamp fields are indexed for efficient temporal queries:

**Core Entities:**
- Contact: `email`, `created_date`, `last_modified`, `owner_id`
- Company: `domain`, `created_date`, `last_modified`, `owner_id`
- Deal: `stage`, `created_date`, `last_modified`, `close_date`, `owner_id`
- Activity: `type`, `timestamp`, `created_date`
- User: `email`

**Event Nodes (v2.1):**
- EmailOpenEvent: `timestamp`, `campaign_id`
- EmailClickEvent: `timestamp`, `campaign_id`
- FormSubmission: `timestamp`, `form_guid`
- PageVisit: `timestamp`, `page_url`

## Example Neo4j Queries (Reporting)

### v2 Owner Queries

**Find all contacts owned by a specific user:**
```cypher
MATCH (c:HUBSPOT_Contact)-[:OWNED_BY]->(u:HUBSPOT_User {email: 'owner@company.com'})
RETURN c.email, c.first_name, c.last_name, c.lifecycle_stage
```

**Owner performance - total deal value by owner:**
```cypher
MATCH (d:HUBSPOT_Deal)-[:OWNED_BY]->(u:HUBSPOT_User)
WHERE d.is_won = true
RETURN u.first_name + ' ' + u.last_name AS owner,
       count(d) AS won_deals,
       sum(d.amount) AS total_value
ORDER BY total_value DESC
```

**Contacts owned by a Knowledge Graph Person (via SAME_AS):**
```cypher
MATCH (c:HUBSPOT_Contact)-[:OWNED_BY]->(hu:HUBSPOT_User)-[:SAME_AS]->(p:Person)
WHERE p.full_name = 'Gina Sus'
RETURN c.email, c.first_name, c.last_name, c.lifecycle_stage
```

### v2 Temporal Queries

**Recent activities (last 30 days):**
```cypher
MATCH (a:HUBSPOT_Activity)
WHERE a.timestamp > datetime() - duration('P30D')
RETURN a.type, a.timestamp, a.details
ORDER BY a.timestamp DESC
```

**Contacts with recent activity:**
```cypher
MATCH (c:HUBSPOT_Contact)<-[:INVOLVES]-(a:HUBSPOT_Activity)
WHERE a.timestamp > datetime() - duration('P30D')
RETURN c.email, c.owner_id, count(a) AS recent_activities
ORDER BY recent_activities DESC
```

**Deals closing this quarter:**
```cypher
MATCH (d:HUBSPOT_Deal)
WHERE d.close_date >= datetime('2025-10-01')
  AND d.close_date < datetime('2026-01-01')
RETURN d.name, d.amount, d.close_date, d.stage
ORDER BY d.close_date
```

**Recently modified contacts (last 7 days):**
```cypher
MATCH (c:HUBSPOT_Contact)
WHERE c.last_modified > datetime() - duration('P7D')
RETURN c.email, c.last_modified
ORDER BY c.last_modified DESC
```

### v2.1 Event-Based Recency Queries

**Contacts who opened emails in last 30 days (with event details):**
```cypher
MATCH (c:HUBSPOT_Contact)-[:PERFORMED]->(e:HUBSPOT_EmailOpenEvent)
WHERE e.timestamp > datetime() - duration('P30D')
RETURN c.email, c.first_name, c.last_name,
       count(e) AS opens_last_30_days,
       max(e.timestamp) AS most_recent_open
ORDER BY opens_last_30_days DESC
```

**Contacts who clicked emails in last 7 days:**
```cypher
MATCH (c:HUBSPOT_Contact)-[:PERFORMED]->(e:HUBSPOT_EmailClickEvent)
WHERE e.timestamp > datetime() - duration('P7D')
RETURN c.email, count(e) AS clicks, collect(DISTINCT e.clicked_url) AS urls_clicked
ORDER BY clicks DESC
```

**Recent form submissions with page context:**
```cypher
MATCH (f:HUBSPOT_FormSubmission)-[:SUBMITTED_BY]->(c:HUBSPOT_Contact)
WHERE f.timestamp > datetime() - duration('P30D')
OPTIONAL MATCH (f)-[:ON_PAGE]->(w:HUBSPOT_WebPage)
RETURN c.email, f.timestamp, f.page_title, w.url AS submission_page
ORDER BY f.timestamp DESC
```

**Email campaign engagement timeline:**
```cypher
MATCH (e:HUBSPOT_EmailOpenEvent)-[:FOR_CAMPAIGN]->(campaign:HUBSPOT_EmailCampaign)
WHERE campaign.hubspot_id = 'YOUR_CAMPAIGN_ID'
WITH campaign, e
ORDER BY e.timestamp
RETURN campaign.name,
       count(e) AS total_opens,
       min(e.timestamp) AS first_open,
       max(e.timestamp) AS last_open,
       collect(e.timestamp)[0..10] AS first_10_opens
```

**Engaged contacts (multiple event types in last 30 days):**
```cypher
MATCH (c:HUBSPOT_Contact)
WHERE EXISTS {
    MATCH (c)-[:PERFORMED]->(e:HUBSPOT_EmailOpenEvent)
    WHERE e.timestamp > datetime() - duration('P30D')
} OR EXISTS {
    MATCH (c)-[:PERFORMED]->(e:HUBSPOT_EmailClickEvent)
    WHERE e.timestamp > datetime() - duration('P30D')
} OR EXISTS {
    MATCH (c)<-[:INVOLVES]-(a:HUBSPOT_Activity)
    WHERE a.timestamp > datetime() - duration('P30D')
}
RETURN c.email, c.lifecycle_stage, c.owner_id
```

**Form submission conversion funnel:**
```cypher
MATCH (c:HUBSPOT_Contact)
OPTIONAL MATCH (c)-[:PERFORMED]->(open:HUBSPOT_EmailOpenEvent)
  WHERE open.timestamp > datetime() - duration('P30D')
OPTIONAL MATCH (c)-[:PERFORMED]->(click:HUBSPOT_EmailClickEvent)
  WHERE click.timestamp > datetime() - duration('P30D')
OPTIONAL MATCH (f:HUBSPOT_FormSubmission)-[:SUBMITTED_BY]->(c)
  WHERE f.timestamp > datetime() - duration('P30D')
WITH c,
     count(DISTINCT open) AS opens,
     count(DISTINCT click) AS clicks,
     count(DISTINCT f) AS submissions
WHERE opens > 0 OR clicks > 0 OR submissions > 0
RETURN
  c.lifecycle_stage,
  count(c) AS contacts,
  sum(opens) AS total_opens,
  sum(clicks) AS total_clicks,
  sum(submissions) AS total_submissions,
  (sum(submissions) * 100.0 / count(c)) AS conversion_rate
ORDER BY conversion_rate DESC
```

### Classic Queries

**Deals by company with totals:**
```cypher
MATCH (d:HUBSPOT_Deal)-[:BELONGS_TO]->(c:HUBSPOT_Company)
RETURN c.name AS company, count(d) AS deals, sum(d.amount) AS total_value
ORDER BY total_value DESC
LIMIT 10
```

**Email campaign open/click rates:**
```cypher
MATCH (c:HUBSPOT_Contact)-[o:OPENED]->(e:HUBSPOT_EmailCampaign)
WITH e, count(DISTINCT c) AS opens
MATCH (c:HUBSPOT_Contact)-[cl:CLICKED]->(e)
WITH e, opens, count(DISTINCT c) AS clicks
RETURN e.name AS campaign, opens, clicks, (clicks * 100.0 / opens) AS click_rate
ORDER BY opens DESC
```

**Most active contacts by page visits:**
```cypher
MATCH (c:HUBSPOT_Contact)-[:VISITED]->(:HUBSPOT_WebPage)
RETURN c.email AS contact, count(*) AS visit_count
ORDER BY visit_count DESC
LIMIT 10
```

**Top email-engaged contacts:**
```cypher
MATCH (c:HUBSPOT_Contact)
WHERE c.total_email_opens > 0
RETURN c.email, c.total_email_opens, c.total_email_clicks
ORDER BY c.total_email_opens DESC
LIMIT 10
```

**Contacts with no company:**
```cypher
MATCH (c:HUBSPOT_Contact)
WHERE NOT (c)-[:WORKS_AT]->(:HUBSPOT_Company)
RETURN c.email
LIMIT 25
```

## Example Data (for reference)
We include tiny sample JSONs to illustrate expected filenames and formats:
- `data/raw-example/` → `contacts.json`, `companies.json`, `deals.json`, `engagements.json`, `email_events.json`
- `data/transformed-example/` → `nodes.json`, `relationships.json`

The real pipeline writes to `data/raw/` and `data/transformed/`, which are git-ignored by default.

## Quick Start Demo (no HubSpot required)
The quickest way to see the graph model is to seed a small example dataset directly into Neo4j.

Prerequisites:
- Neo4j running locally (e.g., Neo4j Desktop or Docker)
  - Default bolt URI: `bolt://localhost:7687`
  - Username: `neo4j`
  - Password: set one on first launch (replace `your_password` below)
- `cypher-shell` available on your PATH (bundled with Neo4j Desktop, or install via package manager)

Seed the example graph:
```
cypher-shell -a bolt://localhost:7687 -u neo4j -p 'your_password' -f scripts/seed_example_graph.cypher
```

Then open Neo4j Browser (http://localhost:7474) and try:
```
MATCH (c:Contact)-[:WORKS_AT]->(co:Company)
RETURN c.email, co.name
```

If `cypher-shell` is not found:
- Neo4j Desktop: open the Database, click “Open Terminal,” and run the command there; or
- macOS (brew): `brew install --cask neo4j` (Desktop) or `brew install neo4j` (Server tools)

## Troubleshooting
- 403 Forbidden: your token is missing a required scope → add scope in Private App, regenerate token.
- Missing env var: ensure `.env` in this folder defines HUBSPOT_ACCESS_TOKEN and Neo4j creds.
- Rate limits: the extractors include simple rate-limit handling and retries; re-run if you hit limits.

## Development & Tests

### Local File Loading for Development
For development and testing purposes, you can bypass HubSpot API calls by loading data from local JSON files. This is particularly useful when:
- Testing transformations without API rate limits
- Working with a specific dataset repeatedly
- Debugging pipeline issues with known data

To use local file loading, modify `main.py` to replace the HubSpot extraction section with:

```python
# Instead of extracting from HubSpot APIs, load from local files
company_folder = 'data/instoneco/'  # or your data folder

with open(company_folder + 'contacts.json', 'r') as f:
    contacts = json.load(f)
    
with open(company_folder + 'companies.json', 'r') as f:
    companies = json.load(f)
    
with open(company_folder + 'deals.json', 'r') as f:
    deals = json.load(f)
    
with open(company_folder + 'engagements.json', 'r') as f:
    engagements = json.load(f)
    
with open(company_folder + 'email_events.json', 'r') as f:
    email_events = json.load(f)

all_data['contacts'] = contacts
all_data['companies'] = companies
all_data['deals'] = deals
all_data['engagements'] = engagements
all_data['email_events'] = email_events
```

This approach allows you to:
- Work offline without HubSpot connectivity
- Test with consistent datasets
- Speed up development cycles
- Debug specific data scenarios

### Custom Labels in Neo4j
The `Neo4jLoader.load_all()` method supports a `custom_labels` parameter that allows you to add additional labels to nodes in Neo4j. This is useful for:
- Multi-tenancy (adding company-specific labels)
- Data versioning (adding timestamp or version labels)
- Custom categorization and querying

Usage example:
```python
loader = Neo4jLoader()
custom_labels = {
    "HUBSPOT_Contact": ["ACME_CORP", "Q4_2023"],
    "HUBSPOT_Company": ["ACME_CORP"],
    "HUBSPOT_Deal": ["ACME_CORP", "HIGH_VALUE"],
    # Other node types can have empty lists if no custom labels needed
}

loader.load_all(nodes, relationships, custom_labels=custom_labels)
```

This will create nodes like:
```cypher
(:HUBSPOT_Contact:ACME_CORP:Q4_2023 {hubspot_id: "123", email: "john@example.com", ...})
(:HUBSPOT_Company:ACME_CORP {hubspot_id: "456", name: "Example Corp", ...})
```

Benefits of custom labels:
- **Multi-tenant queries**: `MATCH (c:HUBSPOT_Contact:ACME_CORP) RETURN c`
- **Filtered operations**: `MATCH (d:HUBSPOT_Deal:HIGH_VALUE) WHERE d.amount > 100000`
- **Data lifecycle management**: Easy to identify and clean up specific datasets

### Test Suite
We use pytest for smoke/integration tests.

Install test dependencies (already included in requirements.txt):
```bash
pip install -r requirements.txt
```

Run tests:
```bash
pytest -q
```

## Entity Matching (v2) - Linking to Knowledge Graph

If you have existing `Person` nodes in your Knowledge Graph (from other data sources), you can link them to `HUBSPOT_User` nodes using the entity matcher.

### Running the Entity Matcher

After the main pipeline completes, run:

```bash
python -m loaders.entity_matcher
```

This will:
1. Match `HUBSPOT_User` nodes to `Person` nodes by:
   - **Primary strategy**: LinkedIn URL (most reliable)
   - **Fallback strategy**: Email address
2. Create `SAME_AS` relationships between matched entities
3. Report matching statistics

### Example: Query Contacts via Person

Once entities are linked, you can query across systems:

```cypher
// Find all HubSpot contacts owned by a specific Person
MATCH (c:HUBSPOT_Contact)-[:OWNED_BY]->(hu:HUBSPOT_User)-[:SAME_AS]->(p:Person)
WHERE p.full_name = 'Gina Sus'
RETURN c.email, c.lifecycle_stage, c.last_modified
```

```cypher
// Show Person's owned contacts and companies
MATCH (p:Person)<-[:SAME_AS]-(hu:HUBSPOT_User)
OPTIONAL MATCH (c:HUBSPOT_Contact)-[:OWNED_BY]->(hu)
OPTIONAL MATCH (co:HUBSPOT_Company)-[:OWNED_BY]->(hu)
RETURN p.full_name AS person,
       count(DISTINCT c) AS contacts_owned,
       count(DISTINCT co) AS companies_owned
```

### Unmatched Users

HUBSPOT_User nodes that don't match any Person will remain in the graph as standalone nodes. This ensures completeness - all HubSpot users are represented, whether or not they exist in your Knowledge Graph.

## Project Structure
- config/ - Settings, schema definitions
- extractors/ - HubSpot data extractors (contacts, companies, deals, engagements, users)
- transformers/ - Graph transformation logic
- loaders/ - Neo4j loader and entity matcher
- utils/ - Logging, helpers
- tests/ - pytest-based test suite




## License
MIT
