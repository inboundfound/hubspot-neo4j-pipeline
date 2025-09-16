# HubSpot → Neo4j Pipeline

A Python pipeline that extracts CRM data from HubSpot (contacts, companies, deals, engagements, and marketing email events), transforms it into a graph model, and loads it into Neo4j.

## Features
- Contacts, Companies, Deals extraction (with associations where supported)
- Engagements (meetings, calls, notes, tasks)
- Marketing Email Events (opens/clicks via legacy Email Events API)
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
INSTONE_ACCESS_TOKEN=pat-na1-...
# Select via HUBSPOT_APP
# HUBSPOT_APP=INSTONE
```
At runtime you can also override:
```bash
HUBSPOT_APP=INSTONE python main.py
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

Grant the following scopes to your Private App (read-only where applicable):
- crm.objects.contacts.read
- crm.objects.companies.read
- crm.objects.deals.read
- EITHER crm.objects.engagements.read OR granular:
  - crm.objects.calls.read
  - crm.objects.meetings.read
  - crm.objects.notes.read
  - crm.objects.tasks.read
- marketing-email (required by GET /email/public/v1/events)

Optional (recommended):
- settings.users.read (resolve owners)
- crm.pipelines.read (pipeline/stage metadata)
- crm.schemas.read (property metadata)
- crm.lists.read (if using lists)
- crm.objects.tickets.read (if adding tickets)
- crm.objects.products.read, crm.objects.line_items.read (if adding products/line items)

## HubSpot APIs Used (and why)
- Contacts: `hubspot.crm.contacts.basic_api.get_page`
  - Rationale: avoids the HubSpot Search API’s hard cap at 10,000 results. Paginates through all contacts.
  - Toggle with `USE_BASIC_API_FOR_CONTACTS`.
- Companies: `hubspot.crm.companies.basic_api.get_page`
- Deals: `hubspot.crm.deals.basic_api.get_page` with `associations` where supported
- Engagements: `hubspot.crm.objects.search_api.do_search(object_type="engagements")`
  - Important: the `object_type` parameter is required by the Objects Search API.
- Email Events (legacy): `GET https://api.hubapi.com/email/public/v1/events` with `offset` passed as a query parameter
  - Toggle the pagination style with `USE_EMAIL_EVENTS_OFFSET_PAGINATION`.

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
Nodes:
- `Contact(hubspot_id, email, first_name, last_name, lifecycle_stage, total_email_opens, total_email_clicks, total_page_views, …)`
- `Company(hubspot_id, name, domain, …)`
- `Deal(hubspot_id, name, amount, dealstage, …)`
- `Activity(hubspot_id, type, timestamp, …)` – from Engagements (if enabled/available)
- `EmailCampaign(hubspot_id, name, subject, sent_date)`
- `WebPage(hubspot_id=url, url, domain, path)`

Relationships:
- `(Contact)-[:WORKS_AT]->(Company)` – via `associatedcompanyid`
- `(Contact)-[:ASSOCIATED_WITH]->(Deal)`
- `(Deal)-[:BELONGS_TO]->(Company)`
- `(Activity)-[:INVOLVES]->(Contact)`
- `(Contact)-[:OPENED|CLICKED]->(EmailCampaign)`
- `(Contact)-[:VISITED]->(WebPage)`

## Example Neo4j Queries (Reporting)
Deals by company with totals:
```
MATCH (d:Deal)-[:BELONGS_TO]->(c:Company)
RETURN c.name AS company, count(d) AS deals, sum(d.amount) AS total_value
ORDER BY total_value DESC
LIMIT 10
```

Email campaign open/click rates:
```
MATCH (c:Contact)-[o:OPENED]->(e:EmailCampaign)
WITH e, count(DISTINCT c) AS opens
MATCH (c:Contact)-[cl:CLICKED]->(e)
WITH e, opens, count(DISTINCT c) AS clicks
RETURN e.name AS campaign, opens, clicks, (clicks * 100.0 / opens) AS click_rate
ORDER BY opens DESC
```

Most active contacts by page visits:
```
MATCH (c:Contact)-[:VISITED]->(:WebPage)
RETURN c.email AS contact, count(*) AS visit_count
ORDER BY visit_count DESC
LIMIT 10
```

Top email-engaged contacts:
```
MATCH (c:Contact)
WHERE c.total_email_opens > 0
RETURN c.email, c.total_email_opens, c.total_email_clicks
ORDER BY c.total_email_opens DESC
LIMIT 10
```

Contacts with no company:
```
MATCH (c:Contact)
WHERE NOT (c)-[:WORKS_AT]->(:Company)
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
We use pytest for smoke/integration tests.

Install test dependencies (already included in requirements.txt):
```bash
pip install -r requirements.txt
```

Run tests:
```bash
pytest -q
```

## Project Structure
- config/ settings, schema
- extractors/ HubSpot data extractors
- transformers/ Graph transformation
- loaders/ Neo4j loader
- utils/ logging, helpers
- tests/ pytest-based minimal suite

## License
MIT
