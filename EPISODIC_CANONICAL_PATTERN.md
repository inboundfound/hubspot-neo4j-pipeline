# Episodic vs Canonical Pattern for Knowledge Graph

## Your Architecture (Episodic + Canonical)

Based on your feedback: *"We will have lots of episodic instances in the knowledge graph and then we will also have a canonical node representing those people"*

This is a **much better architecture** than what I originally recommended! Here's why:

---

## The Pattern

### Canonical Nodes (Universal Identity)
```cypher
// Single canonical person across ALL systems
(:Person {
  canonical_id: "person_12345",
  email: "john@acme.com",
  full_name: "John Smith",
  is_canonical: true
})
```

### Episodic Nodes (System-Specific Snapshots)
```cypher
// HubSpot's view of this person at a point in time
(:HUBSPOT_Contact {
  hubspot_id: "123",
  email: "john@acme.com",
  lifecycle_stage: "customer",
  created_at: "2024-01-15",
  extracted_at: "2025-01-31",
  is_episodic: true
})

// Salesforce's view of the same person
(:SALESFORCE_Lead {
  salesforce_id: "003ABC",
  email: "john@acme.com",
  status: "qualified",
  created_at: "2024-02-01",
  extracted_at: "2025-01-31",
  is_episodic: true
})
```

### Linking Pattern
```cypher
(:HUBSPOT_Contact)-[:REPRESENTS]->(canonical:Person)
(:SALESFORCE_Lead)-[:REPRESENTS]->(canonical:Person)
```

---

## Why This Is Better

### ✅ Data Refresh Problem Solved
**Your concern:** "refreshing CRM import data will be hard to untangle from data from other sources"

**Solution with Episodic Pattern:**
```cypher
// Delete all HubSpot episodic data from last import
MATCH (n:HUBSPOT_Contact {import_batch_id: "2025-01-31"})
DETACH DELETE n

// Load fresh HubSpot data
CREATE (:HUBSPOT_Contact {
  hubspot_id: "123",
  import_batch_id: "2025-02-01",
  ...
})
```

**Canonical nodes remain untouched!** Other systems' data is preserved.

---

### ✅ Time-Series Analysis
You can query how a person's data evolved over time:

```cypher
// Show all historical snapshots of a person across systems
MATCH (canonical:Person {email: "john@acme.com"})<-[:REPRESENTS]-(episode)
RETURN episode.extracted_at, labels(episode), episode
ORDER BY episode.extracted_at
```

**Output:**
```
2024-01-15: HUBSPOT_Contact {lifecycle_stage: "lead"}
2024-03-01: HUBSPOT_Contact {lifecycle_stage: "customer"}
2024-06-15: SALESFORCE_Lead {status: "qualified"}
2025-01-31: HUBSPOT_Contact {lifecycle_stage: "customer"}
```

---

### ✅ System-Specific Context Preserved
Different systems have different data models:

```cypher
// HubSpot has lifecycle stages
(:HUBSPOT_Contact {
  lifecycle_stage: "customer",
  hs_lead_status: "qualified"
})

// Salesforce has different status model
(:SALESFORCE_Lead {
  status: "qualified",
  rating: "hot"
})

// LinkedIn has professional context
(:LINKEDIN_Profile {
  headline: "VP of Engineering",
  connections: 500
})

// All represent same canonical person
```

Each keeps its native data model!

---

### ✅ AI Agent Queries Work Naturally

**Find all people (canonical):**
```cypher
MATCH (p:Person)
WHERE p.is_canonical = true
RETURN p
```

**Find HubSpot's view of specific person:**
```cypher
MATCH (p:Person {email: "john@acme.com"})<-[:REPRESENTS]-(hs:HUBSPOT_Contact)
RETURN hs
ORDER BY hs.extracted_at DESC
LIMIT 1  // Most recent snapshot
```

**Cross-system query:**
```cypher
// Find people who are customers in HubSpot AND qualified leads in Salesforce
MATCH (p:Person)<-[:REPRESENTS]-(hs:HUBSPOT_Contact)
WHERE hs.lifecycle_stage = "customer"
MATCH (p)<-[:REPRESENTS]-(sf:SALESFORCE_Lead)
WHERE sf.status = "qualified"
RETURN p, hs, sf
```

---

## Recommended Data Model

### Canonical Nodes (Identity Layer)

#### Person (Canonical Identity)
```cypher
(:Person {
  // Identity
  canonical_id: string,           // Your internal canonical ID
  email: string,                  // Primary identity key
  full_name: string,

  // Flags
  is_canonical: true,

  // Metadata
  first_seen: datetime,           // When first appeared in ANY system
  last_seen: datetime,            // Last activity across ALL systems
  confidence_score: float,        // Entity resolution confidence

  // Aggregated properties (optional)
  total_systems: int,             // Number of systems this person appears in
  primary_system: string          // Which system is "source of truth"
})

Labels: Person
Constraints: UNIQUE(canonical_id), UNIQUE(email)
```

#### Organization (Canonical Identity)
```cypher
(:Organization {
  canonical_id: string,
  domain: string,                 // Primary identity key
  name: string,

  is_canonical: true,
  first_seen: datetime,
  last_seen: datetime,
  confidence_score: float
})

Labels: Organization
Constraints: UNIQUE(canonical_id), UNIQUE(domain)
```

---

### Episodic Nodes (System Snapshots)

#### HUBSPOT_Contact (Episodic)
```cypher
(:HUBSPOT_Contact {
  // Source identity
  hubspot_id: string,             // HubSpot's ID
  source_system: "hubspot",
  source_type: "contact",

  // Import tracking
  import_batch_id: string,        // Which import batch created this
  extracted_at: datetime,         // When extracted from HubSpot API
  imported_at: datetime,          // When loaded into Neo4j

  // HubSpot-specific properties (keep native structure!)
  email: string,
  firstname: string,
  lastname: string,
  lifecycle_stage: string,
  hs_lead_status: string,
  associatedcompanyid: string,
  hubspot_owner_id: string,
  createdate: datetime,
  lastmodifieddate: datetime,

  // Flags
  is_episodic: true,
  is_latest: true                 // Flag for most recent snapshot
})

Labels: HUBSPOT_Contact
Constraints: UNIQUE(hubspot_id, import_batch_id)
Indexes: email, import_batch_id, extracted_at
```

#### HUBSPOT_Company (Episodic)
```cypher
(:HUBSPOT_Company {
  hubspot_id: string,
  source_system: "hubspot",
  source_type: "company",

  import_batch_id: string,
  extracted_at: datetime,
  imported_at: datetime,

  // HubSpot-specific properties
  name: string,
  domain: string,
  industry: string,
  city: string,
  hubspot_owner_id: string,
  createdate: datetime,
  lastmodifieddate: datetime,

  is_episodic: true,
  is_latest: true
})

Labels: HUBSPOT_Company
Constraints: UNIQUE(hubspot_id, import_batch_id)
Indexes: domain, import_batch_id
```

#### HUBSPOT_Deal (Episodic)
```cypher
(:HUBSPOT_Deal {
  hubspot_id: string,
  source_system: "hubspot",
  source_type: "deal",

  import_batch_id: string,
  extracted_at: datetime,
  imported_at: datetime,

  // HubSpot-specific properties
  dealname: string,
  amount: float,
  dealstage: string,
  pipeline: string,
  closedate: datetime,
  hubspot_owner_id: string,
  createdate: datetime,

  is_episodic: true,
  is_latest: true
})

Labels: HUBSPOT_Deal
```

---

### Episodic Events (Keep as-is, these are already episodic!)

#### HUBSPOT_EmailOpenEvent
```cypher
(:HUBSPOT_EmailOpenEvent {
  event_id: string,
  timestamp: datetime,

  import_batch_id: string,
  extracted_at: datetime,

  // Event details
  campaign_id: string,
  recipient_email: string,
  device_type: string,

  is_episodic: true               // Events are inherently episodic
})
```

**Note:** Events are ALREADY episodic by nature! They represent something that happened at a specific point in time. No need for canonical event nodes.

---

## Relationship Patterns

### Episodic → Canonical (Identity Resolution)

```cypher
// HubSpot contact represents a canonical person
(hs:HUBSPOT_Contact)-[:REPRESENTS]->(p:Person)

// Salesforce lead represents same canonical person
(sf:SALESFORCE_Lead)-[:REPRESENTS]->(p:Person)

// HubSpot company represents a canonical organization
(hc:HUBSPOT_Company)-[:REPRESENTS]->(o:Organization)
```

**Properties on REPRESENTS relationship:**
```cypher
(hs)-[r:REPRESENTS {
  matched_on: "email",           // How was this match made?
  confidence: 0.95,              // How confident are we?
  matched_at: datetime(),        // When was entity resolution performed?
  is_primary: true               // Is this the primary/preferred instance?
}]->(p)
```

---

### Episodic → Episodic (System-Specific)

**Within Same System (Time-Series):**
```cypher
// Link snapshots from same import batches
(old:HUBSPOT_Contact {hubspot_id: "123", import_batch_id: "2025-01-15"})
  -[:NEXT_SNAPSHOT]->
(new:HUBSPOT_Contact {hubspot_id: "123", import_batch_id: "2025-01-31"})
```

**Cross-System at Episodic Level:**
```cypher
// HubSpot contact works at HubSpot company (both episodic)
(hs_contact:HUBSPOT_Contact)-[:WORKS_AT]->(hs_company:HUBSPOT_Company)
```

**Key Decision:** Do you want episodic-to-episodic relationships OR canonical-only relationships?

**Option A: Episodic relationships (preserve source system context)**
```cypher
(hs_contact:HUBSPOT_Contact)-[:WORKS_AT]->(hs_company:HUBSPOT_Company)
```
✅ Preserves HubSpot's understanding of the relationship
✅ Can track relationship over time
❌ Duplicate relationships across systems

**Option B: Canonical relationships only**
```cypher
(person:Person)-[:WORKS_AT]->(org:Organization)
```
✅ Single source of truth for relationships
✅ Simpler queries
❌ Loses system-specific relationship context

**Recommended: Hybrid**
- Keep episodic relationships for system fidelity
- Derive canonical relationships through entity resolution

---

### Event → Episodic

```cypher
// Email open event performed by HubSpot contact instance
(event:HUBSPOT_EmailOpenEvent)
  -[:PERFORMED_BY]->
(contact:HUBSPOT_Contact {import_batch_id: "2025-01-31"})
```

### Event → Canonical (Derived)

```cypher
// Derive canonical relationship via REPRESENTS
MATCH (event:HUBSPOT_EmailOpenEvent {recipient_email: "john@acme.com"})
MATCH (hs:HUBSPOT_Contact {email: "john@acme.com", is_latest: true})
MATCH (hs)-[:REPRESENTS]->(person:Person)
RETURN event, person

// Or create derived relationship
MATCH (event)-[:PERFORMED_BY]->(hs:HUBSPOT_Contact)-[:REPRESENTS]->(p:Person)
MERGE (event)-[:CANONICAL_ACTOR]->(p)
```

---

## Import Workflow

### Phase 1: Extract Episodic Data
```python
# Extract from HubSpot
import_batch_id = datetime.now().isoformat()

contacts = extract_hubspot_contacts()
for contact in contacts:
    contact['import_batch_id'] = import_batch_id
    contact['extracted_at'] = datetime.now()
    contact['is_episodic'] = True
    contact['is_latest'] = True  # Mark as latest for now
```

### Phase 2: Load Episodic Nodes
```cypher
// Mark previous snapshots as not latest
MATCH (old:HUBSPOT_Contact)
WHERE old.is_latest = true
SET old.is_latest = false

// Load new episodic nodes
CREATE (:HUBSPOT_Contact {
  hubspot_id: "123",
  import_batch_id: $batch_id,
  extracted_at: $timestamp,
  is_episodic: true,
  is_latest: true,
  ...
})
```

### Phase 3: Entity Resolution (Match to Canonical)
```cypher
// Find or create canonical person
MATCH (hs:HUBSPOT_Contact {import_batch_id: $batch_id})
MERGE (p:Person {email: hs.email})
ON CREATE SET
  p.canonical_id = randomUUID(),
  p.full_name = hs.firstname + ' ' + hs.lastname,
  p.is_canonical = true,
  p.first_seen = hs.createdate
ON MATCH SET
  p.last_seen = hs.lastmodifieddate

// Create REPRESENTS relationship
MERGE (hs)-[r:REPRESENTS]->(p)
SET r.matched_on = "email",
    r.confidence = 1.0,
    r.matched_at = datetime(),
    r.is_primary = true
```

### Phase 4: Create Episodic Relationships
```cypher
// Create episodic relationships within HubSpot data
MATCH (c:HUBSPOT_Contact {import_batch_id: $batch_id})
WHERE c.associatedcompanyid IS NOT NULL
MATCH (co:HUBSPOT_Company {
  hubspot_id: c.associatedcompanyid,
  import_batch_id: $batch_id
})
MERGE (c)-[:WORKS_AT]->(co)
```

### Phase 5: Derive Canonical Relationships (Optional)
```cypher
// Derive canonical WORKS_AT from episodic relationships
MATCH (c:HUBSPOT_Contact {is_latest: true})-[:WORKS_AT]->(co:HUBSPOT_Company {is_latest: true})
MATCH (c)-[:REPRESENTS]->(person:Person)
MATCH (co)-[:REPRESENTS]->(org:Organization)
MERGE (person)-[r:WORKS_AT]->(org)
SET r.source_systems = ["hubspot"],
    r.derived_at = datetime()
```

---

## Querying Patterns

### Get Latest View of a Person
```cypher
MATCH (p:Person {email: "john@acme.com"})<-[:REPRESENTS]-(hs:HUBSPOT_Contact)
WHERE hs.is_latest = true
RETURN p, hs
```

### Get Historical Timeline
```cypher
MATCH (p:Person {email: "john@acme.com"})<-[:REPRESENTS]-(episode)
RETURN
  episode.extracted_at,
  labels(episode),
  episode.lifecycle_stage,
  episode.source_system
ORDER BY episode.extracted_at DESC
```

### Cross-System Reconciliation
```cypher
// Find people who exist in multiple systems
MATCH (p:Person)<-[:REPRESENTS]-(episode)
WITH p, collect(DISTINCT episode.source_system) as systems, count(episode) as snapshots
WHERE size(systems) > 1
RETURN p.email, systems, snapshots
ORDER BY snapshots DESC
```

### AI Agent Query (Canonical View)
```cypher
// Find all people who work at organizations (canonical)
MATCH (p:Person)-[:WORKS_AT]->(o:Organization)
RETURN p.full_name, o.name
```

### AI Agent Query (Episodic View)
```cypher
// Find all HubSpot contacts who work at HubSpot companies
MATCH (c:HUBSPOT_Contact {is_latest: true})-[:WORKS_AT]->(co:HUBSPOT_Company {is_latest: true})
RETURN c.email, co.name
```

---

## Benefits of This Pattern

### ✅ Clean Data Refresh
```cypher
// Delete all old HubSpot data
MATCH (n)
WHERE any(label IN labels(n) WHERE label STARTS WITH 'HUBSPOT_')
  AND n.import_batch_id < $cutoff_date
DETACH DELETE n
```
**Canonical nodes untouched!**

### ✅ System Fidelity Preserved
Each system keeps its native data model and properties. No lossy transformation.

### ✅ Time-Series Analysis
Track how entities evolve over time within and across systems.

### ✅ Entity Resolution Explicit
The `REPRESENTS` relationship makes identity resolution transparent and auditable.

### ✅ Multi-Tenant Ready
Different import batches can coexist:
```cypher
(:HUBSPOT_Contact {
  import_batch_id: "client_A_2025-01-31"
})
(:HUBSPOT_Contact {
  import_batch_id: "client_B_2025-01-31"
})
```

---

## Naming Convention Summary

### Canonical Nodes:
- `Person` (no prefix)
- `Organization` (no prefix)
- `Deal` (if you want canonical deals)

### Episodic Nodes:
- `HUBSPOT_Contact` (system prefix)
- `HUBSPOT_Company`
- `HUBSPOT_Deal`
- `SALESFORCE_Lead`
- `LINKEDIN_Profile`
- etc.

### Events (Already Episodic):
- `HUBSPOT_EmailOpenEvent`
- `HUBSPOT_EmailClickEvent`
- `HUBSPOT_FormSubmission`

### Relationships:
- `REPRESENTS` - episodic → canonical
- `WORKS_AT` - both episodic-to-episodic AND canonical-to-canonical
- `NEXT_SNAPSHOT` - episodic → episodic (time-series)

---

## AI Agent Understanding

**Question:** "Find all people who work at Acme Corp"

**AI Reasoning:**
1. Query canonical layer: `MATCH (p:Person)-[:WORKS_AT]->(o:Organization {name: "Acme Corp"})`
2. If not found, query episodic: `MATCH (c {is_latest: true})-[:WORKS_AT]->(co {name: "Acme Corp"})<-[:REPRESENTS]-(o:Organization)`

**The AI understands:**
- `Person` = canonical identity (across all systems)
- `HUBSPOT_Contact` = HubSpot's episodic view of a person
- `REPRESENTS` = links episodic to canonical
- `is_latest: true` = most recent snapshot

**This is "common sense understandable"** because the pattern is explicit, not implicit.

---

## Migration Path

Your current data is already episodic! You just need to:

### Step 1: Add `is_episodic` flag
```cypher
MATCH (n)
WHERE any(label IN labels(n) WHERE label STARTS WITH 'HUBSPOT_')
SET n.is_episodic = true,
    n.import_batch_id = "2025-01-31",  // Current batch
    n.is_latest = true
```

### Step 2: Create canonical nodes
```cypher
// Create canonical Person nodes
MATCH (c:HUBSPOT_Contact)
MERGE (p:Person {email: c.email})
ON CREATE SET
  p.canonical_id = randomUUID(),
  p.full_name = c.first_name + ' ' + c.last_name,
  p.is_canonical = true

// Link episodic to canonical
MERGE (c)-[:REPRESENTS {
  matched_on: "email",
  confidence: 1.0,
  matched_at: datetime()
}]->(p)
```

### Step 3: Update pipeline
Modify transformers to:
1. Create episodic nodes with `import_batch_id`
2. Run entity resolution to create/link canonical nodes
3. Optionally derive canonical relationships

---

## Conclusion

Your instinct about **episodic + canonical** is absolutely correct! This pattern:
- ✅ Solves the data refresh problem
- ✅ Preserves system fidelity
- ✅ Enables time-series analysis
- ✅ Makes entity resolution explicit
- ✅ Is AI-interpretable (both layers have clear semantics)

The `HUBSPOT_` prefix now makes perfect sense - it identifies the source system for episodic snapshots, while canonical nodes use semantic names (`Person`, `Organization`).
