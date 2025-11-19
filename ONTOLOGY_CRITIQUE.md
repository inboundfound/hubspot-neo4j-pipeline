# HubSpot Data Model: Ontological Critique & Recommendations

## Executive Summary

**Current State:** HubSpot data uses `HUBSPOT_` prefixed labels which maintain clear separation but **break common-sense ontological semantics** for AI agents.

**Core Problem:** An AI agent asked "find all people who work at companies" won't understand that `HUBSPOT_Contact` represents a person and `HUBSPOT_Company` represents an organization. The system-specific naming obscures the universal concepts.

**Recommendation:** Use **multi-label ontology** - combine semantic labels with source system labels.

---

## Critical Issues with Current Model

### ❌ Issue #1: Semantic Opacity

**Current:**
```cypher
(:HUBSPOT_Contact {email: "john@acme.com"})
(:HUBSPOT_Company {name: "Acme Corp"})
```

**Problem:** An AI agent doesn't know:
- `HUBSPOT_Contact` represents a `Person`
- `HUBSPOT_Company` represents an `Organization`
- These are universal concepts, not HubSpot-specific entities

**AI Impact:** Requires explicit mapping documentation for every query. Not "common sense understandable."

---

### ❌ Issue #2: Relationship Semantics Unclear

**Current:**
```cypher
(HUBSPOT_Contact)-[:WORKS_AT]->(HUBSPOT_Company)
```

**Problem:**
- Relationship name is semantic (`WORKS_AT`) ✅
- But endpoints are opaque (`HUBSPOT_Contact` vs `HUBSPOT_Company`) ❌
- AI agents must be taught that `HUBSPOT_Contact` is an employment entity

---

### ❌ Issue #3: Cross-System Queries Require Explicit Mapping

**Current:** If you add Salesforce data later:
```cypher
(:HUBSPOT_Contact)  // Person from HubSpot
(:SALESFORCE_Lead)  // Person from Salesforce
(:LINKEDIN_Profile) // Person from LinkedIn
```

**Problem:** AI agent must be explicitly taught:
```
"To find all people, query:
MATCH (p) WHERE p:HUBSPOT_Contact OR p:SALESFORCE_Lead OR p:LINKEDIN_Profile"
```

**This defeats the purpose of a Knowledge Graph!**

---

### ❌ Issue #4: Event Ontology is Inconsistent

**Current:**
- `HUBSPOT_EmailOpenEvent` - System prefix + action + "Event"
- `HUBSPOT_FormSubmission` - System prefix + noun (no "Event")

**Problem:** Inconsistent naming makes pattern recognition harder for AI agents.

**Ontologically correct:** All events should follow same pattern:
- Event class (Action + Event)
- Provenance label (system source)

---

## Recommended Solution: Multi-Label Ontology

Use **Neo4j's multi-label capability** to maintain both semantic AND provenance information.

### ✅ Solution: Semantic + Provenance Labels

**Pattern:**
```
(:SemanticLabel:ProvenanceLabel {properties})
```

**Example:**
```cypher
// Person from HubSpot
(:Person:HubSpot {
  hubspot_id: "123",
  email: "john@acme.com",
  source_system: "hubspot",
  source_type: "contact"
})

// Organization from HubSpot
(:Organization:HubSpot {
  hubspot_id: "456",
  name: "Acme Corp",
  source_system: "hubspot",
  source_type: "company"
})
```

---

## Complete Recommended Ontology

### Core Entity Nodes

#### Person (replaces HUBSPOT_Contact)
```cypher
(:Person:HubSpot {
  // Identity
  hubspot_id: string,           // Source system ID
  email: string,                // Primary identifier
  full_name: string,            // Display name

  // Source metadata
  source_system: "hubspot",
  source_type: "contact",
  source_created_date: datetime,
  source_modified_date: datetime,

  // Properties
  phone: string,
  job_title: string,
  lifecycle_stage: string,

  // Cached aggregates (denormalized for performance)
  total_email_opens: int,
  total_email_clicks: int
})

Labels: Person, HubSpot
Constraints: UNIQUE(hubspot_id), INDEX(email)
```

**AI Understanding:** "This is a Person. The HubSpot label tells me it came from HubSpot. The `source_type` tells me it was originally a 'contact' in HubSpot's data model."

---

#### Organization (replaces HUBSPOT_Company)
```cypher
(:Organization:HubSpot {
  hubspot_id: string,
  name: string,
  domain: string,

  source_system: "hubspot",
  source_type: "company",
  source_created_date: datetime,
  source_modified_date: datetime,

  industry: string,
  city: string,
  state: string,
  country: string,
  employee_count: int,
  annual_revenue: float
})

Labels: Organization, HubSpot
Constraints: UNIQUE(hubspot_id), INDEX(domain)
```

---

#### Deal (replaces HUBSPOT_Deal)
```cypher
(:Deal:HubSpot {
  hubspot_id: string,
  name: string,
  amount: float,
  stage: string,
  pipeline: string,
  is_closed: boolean,
  is_won: boolean,

  source_system: "hubspot",
  source_type: "deal",
  source_created_date: datetime,
  source_modified_date: datetime,
  close_date: datetime
})

Labels: Deal, HubSpot
```

**Ontological Note:** `Deal` is a domain-specific concept (sales/CRM). This is acceptable as there's no universal semantic equivalent. An AI agent can infer it represents a "commercial opportunity."

---

#### Activity (replaces HUBSPOT_Activity)
```cypher
(:Activity:HubSpot {
  hubspot_id: string,
  activity_type: string,        // "meeting", "call", "note", "task"
  timestamp: datetime,
  title: string,
  description: string,
  status: string,

  source_system: "hubspot",
  source_type: "engagement",
  source_created_date: datetime
})

Labels: Activity, HubSpot
```

**Alternative:** Break into semantic subtypes:
```cypher
(:Meeting:Activity:HubSpot)
(:Call:Activity:HubSpot)
(:Note:Activity:HubSpot)
(:Task:Activity:HubSpot)
```

This enables: `MATCH (m:Meeting)` without filtering on `activity_type`.

---

#### User (replaces HUBSPOT_User)
```cypher
(:Person:User:HubSpot {
  hubspot_id: string,
  email: string,
  full_name: string,
  is_active: boolean,
  teams: [string],

  source_system: "hubspot",
  source_type: "user",
  source_created_date: datetime
})

Labels: Person, User, HubSpot
```

**Key Insight:** Users are also People! Multi-label allows:
- `MATCH (p:Person)` - finds ALL people (contacts + users)
- `MATCH (u:User)` - finds only users (employees)
- `MATCH (p:Person:HubSpot)` - finds people from HubSpot
- `MATCH (p:Person:!User)` - finds external people (contacts, not users)

---

### Event Nodes

#### EmailOpenEvent
```cypher
(:EmailOpenEvent:Event:HubSpot {
  event_id: string,              // Use generic event_id instead of hubspot_id
  timestamp: datetime,

  // Event details
  campaign_id: string,
  recipient_email: string,
  device_type: string,
  location: string,
  browser: string,

  source_system: "hubspot",
  source_type: "email_event"
})

Labels: EmailOpenEvent, Event, HubSpot
```

**Ontological Reasoning:**
- `Event` - Universal concept (something that happened at a point in time)
- `EmailOpenEvent` - Specific type of event
- `HubSpot` - Provenance

---

#### EmailClickEvent
```cypher
(:EmailClickEvent:Event:HubSpot {
  event_id: string,
  timestamp: datetime,

  campaign_id: string,
  recipient_email: string,
  clicked_url: string,
  device_type: string,
  location: string,
  browser: string,

  source_system: "hubspot",
  source_type: "email_event"
})

Labels: EmailClickEvent, Event, HubSpot
```

---

#### FormSubmissionEvent
```cypher
(:FormSubmissionEvent:Event:HubSpot {
  event_id: string,
  timestamp: datetime,

  form_id: string,
  form_name: string,
  submitter_email: string,
  page_url: string,
  page_title: string,
  ip_address: string,

  source_system: "hubspot",
  source_type: "form_submission"
})

Labels: FormSubmissionEvent, Event, HubSpot
```

**Rename Rationale:** Changed from `FormSubmission` to `FormSubmissionEvent` for consistency. All events end in "Event".

---

### Marketing Entities

#### EmailCampaign
```cypher
(:EmailCampaign:Campaign:HubSpot {
  hubspot_id: string,
  name: string,
  subject: string,
  sent_date: datetime,
  campaign_type: string,

  source_system: "hubspot",
  source_type: "email_campaign"
})

Labels: EmailCampaign, Campaign, HubSpot
```

**Multi-level hierarchy:** `EmailCampaign` → `Campaign` → `HubSpot`

---

#### WebPage
```cypher
(:WebPage:Resource {
  url: string,                  // Primary ID
  domain: string,
  path: string,

  // No source_system - web pages are universal resources
  first_seen: datetime,
  last_seen: datetime
})

Labels: WebPage, Resource
```

**Important:** WebPages are NOT HubSpot-specific! They're universal resources that exist independently. Don't use `HubSpot` label.

---

## Recommended Relationships

### Semantic Relationships (No Changes Needed)

These relationship names are already ontologically correct:

```cypher
(Person)-[:WORKS_AT]->(Organization)
(Person)-[:ASSOCIATED_WITH]->(Deal)
(Deal)-[:BELONGS_TO]->(Organization)
(Activity)-[:INVOLVES]->(Person)
(Activity)-[:RELATED_TO]->(Deal)
(Person)-[:OWNS]->(Person)           // Changed from OWNED_BY (direction flip)
(Person)-[:OWNS]->(Organization)
(Person)-[:OWNS]->(Deal)
```

**Key Change:** `OWNED_BY` → `OWNS` (reverse direction)
- `(Contact)-[:OWNED_BY]->(User)` ❌ Passive voice, unclear
- `(User)-[:OWNS]->(Contact)` ✅ Active voice, clear agent

---

### Event Relationships

```cypher
(Person)-[:PERFORMED]->(EmailOpenEvent)
(Person)-[:PERFORMED]->(EmailClickEvent)
(Person)-[:PERFORMED]->(FormSubmissionEvent)

(EmailOpenEvent)-[:FOR_CAMPAIGN]->(EmailCampaign)
(EmailClickEvent)-[:FOR_CAMPAIGN]->(EmailCampaign)
(EmailClickEvent)-[:CLICKED]->(WebPage)        // Changed from CLICKED_URL
(FormSubmissionEvent)-[:SUBMITTED_ON]->(WebPage) // Changed from ON_PAGE
```

**Naming Improvements:**
- `CLICKED_URL` → `CLICKED` (verb is sufficient, object type is clear)
- `ON_PAGE` → `SUBMITTED_ON` (more specific, clearer semantics)

---

## Property Naming Standards

### Source System Properties (Always Include)

Every node should have:
```
source_system: string         // "hubspot", "salesforce", "linkedin", etc.
source_type: string           // Original entity type in source system
source_id: string             // Original ID (renamed from hubspot_id)
source_created_date: datetime // When created in source system
source_modified_date: datetime // When last modified in source system
```

**Rationale:** Clear provenance without polluting the label namespace.

---

### Timestamp Properties

**Standard naming:**
- `timestamp` - When an event occurred (for Event nodes)
- `created_date` - When entity was created
- `modified_date` - When entity was last updated
- `*_date` suffix - All dates/times use this pattern

---

## AI Agent Query Examples

With the new ontology, AI agents can write intuitive queries:

### Example 1: Find all people who work at organizations
```cypher
// Before (opaque):
MATCH (c:HUBSPOT_Contact)-[:WORKS_AT]->(co:HUBSPOT_Company)
RETURN c, co

// After (semantic):
MATCH (p:Person)-[:WORKS_AT]->(o:Organization)
RETURN p, o
```

**AI Understanding:** "Find Person nodes connected to Organization nodes via WORKS_AT relationship. This makes sense - people work at organizations."

---

### Example 2: Find engaged people (across all systems)
```cypher
// With semantic labels, AI can query across systems:
MATCH (p:Person)-[:PERFORMED]->(e:Event)
WHERE e.timestamp > datetime() - duration('P30D')
RETURN p.full_name, count(e) as recent_events
ORDER BY recent_events DESC
```

**AI Understanding:** "Find all Person nodes that performed any Event in the last 30 days. Person and Event are universal concepts."

---

### Example 3: Owner performance (semantic query)
```cypher
// Before:
MATCH (u:HUBSPOT_User)<-[:OWNED_BY]-(d:HUBSPOT_Deal)
WHERE d.is_won = true
RETURN u

// After:
MATCH (owner:Person:User)-[:OWNS]->(d:Deal)
WHERE d.is_won = true
RETURN owner
```

**AI Understanding:** "Find Person nodes that are also Users (employees) who own Deals that are won. Clear agent-action-object semantics."

---

## Cross-System Integration Example

When you add Salesforce data later:

```cypher
// HubSpot person
(:Person:HubSpot {
  source_id: "123",
  source_system: "hubspot",
  source_type: "contact",
  email: "john@acme.com"
})

// Salesforce person
(:Person:Salesforce {
  source_id: "003ABC",
  source_system: "salesforce",
  source_type: "lead",
  email: "john@acme.com"
})

// Entity resolution creates:
(:Person:HubSpot:Salesforce {
  source_ids: ["hubspot:123", "salesforce:003ABC"],
  email: "john@acme.com",
  is_merged: true
})
```

**AI Understanding:** This is a single Person that exists in both HubSpot and Salesforce.

---

## Migration Strategy

### Phase 1: Add Semantic Labels (Non-Breaking)
Keep existing `HUBSPOT_*` labels, add semantic labels:

```cypher
// Add Person label to all contacts
MATCH (c:HUBSPOT_Contact)
SET c:Person

// Add Organization label to all companies
MATCH (c:HUBSPOT_Company)
SET c:Organization
```

**Benefit:** Both old and new queries work during transition.

---

### Phase 2: Add Source Metadata Properties
```cypher
MATCH (c:HUBSPOT_Contact)
SET c.source_system = "hubspot",
    c.source_type = "contact",
    c.source_id = c.hubspot_id,
    c.source_created_date = c.created_date,
    c.source_modified_date = c.last_modified
```

---

### Phase 3: Update Application Code
Change extractors/transformers to create nodes with new label pattern:
```python
# Old
node_label = "HUBSPOT_Contact"

# New
node_labels = ["Person", "HubSpot"]
```

---

### Phase 4: Remove Old Labels (Optional)
```cypher
MATCH (p:HUBSPOT_Contact)
REMOVE p:HUBSPOT_Contact
```

**Note:** Only do this after all queries are updated.

---

## Implementation Recommendations

### 1. Use Label Hierarchies
```
Person
├── User (employees)
└── Customer (external)

Event
├── EmailOpenEvent
├── EmailClickEvent
└── FormSubmissionEvent

Campaign
└── EmailCampaign
```

### 2. Consistent Property Naming
- Use `snake_case` for all properties
- Use `*_date` suffix for timestamps
- Use `is_*` prefix for booleans
- Use `source_*` prefix for provenance

### 3. Provenance Labels Strategy
- Primary provenance: `HubSpot`, `Salesforce`, `LinkedIn`
- Never mix with semantic labels: ❌ `Person_HubSpot`
- Always multi-label: ✅ `Person:HubSpot`

### 4. Event Sourcing Pattern
Events should be immutable:
- Never update event nodes
- Always create new events
- Use `timestamp` as primary temporal property
- Keep `source_created_date` for audit trail

---

## Benefits Summary

### ✅ For AI Agents:
- **Common sense understandable**: `Person` and `Organization` are universal concepts
- **No explicit mapping required**: AI can infer semantics from labels
- **Cross-system queries intuitive**: `MATCH (p:Person)` finds all people, regardless of source
- **Pattern recognition easier**: Consistent event naming (`*Event`)

### ✅ For Developers:
- **Backward compatible**: Can add semantic labels without breaking existing queries
- **Clear provenance**: Source system always visible via label
- **Future-proof**: Easy to add new systems (Salesforce, LinkedIn, etc.)
- **Flexible querying**: Can filter by semantic type OR source system

### ✅ For Data Quality:
- **Source metadata preserved**: `source_system`, `source_type`, `source_id`
- **Audit trail maintained**: `source_created_date`, `source_modified_date`
- **Merge tracking possible**: Multi-label for merged entities

---

## Final Recommendations

### Immediate Actions:
1. ✅ **Add semantic labels to existing nodes** (non-breaking change)
2. ✅ **Standardize event naming** (all events end with "Event")
3. ✅ **Reverse OWNED_BY direction** → use `OWNS` instead
4. ✅ **Add source_* properties** to all nodes

### Short-term (next sprint):
5. ✅ **Update transformer to create multi-label nodes**
6. ✅ **Update neo4j_schema.py with new label patterns**
7. ✅ **Add constraints on semantic labels** (e.g., UNIQUE Person.email when merged)

### Long-term:
8. ✅ **Build entity resolution** for cross-system merging
9. ✅ **Create ontology documentation** for AI agents
10. ✅ **Implement entity lifecycle tracking** (created, updated, deleted, merged)

---

## Conclusion

The current `HUBSPOT_` prefix approach maintains separation but **sacrifices semantic clarity**.

**Recommended approach:** Multi-label ontology combines the best of both:
- **Semantic labels** (`Person`, `Organization`) for AI interpretability
- **Provenance labels** (`HubSpot`) for system separation
- **Source properties** (`source_system`, `source_type`) for detailed tracking

This makes the Knowledge Graph **"common sense understandable"** while maintaining complete data lineage.
