// Constraints & Indexes (safe to re-run)
CREATE CONSTRAINT contact_id IF NOT EXISTS FOR (c:Contact) REQUIRE c.hubspot_id IS UNIQUE;
CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.hubspot_id IS UNIQUE;
CREATE CONSTRAINT deal_id IF NOT EXISTS FOR (d:Deal) REQUIRE d.hubspot_id IS UNIQUE;
CREATE CONSTRAINT activity_id IF NOT EXISTS FOR (a:Activity) REQUIRE a.hubspot_id IS UNIQUE;
CREATE CONSTRAINT email_campaign_id IF NOT EXISTS FOR (e:EmailCampaign) REQUIRE e.hubspot_id IS UNIQUE;
CREATE CONSTRAINT webpage_url IF NOT EXISTS FOR (w:WebPage) REQUIRE w.hubspot_id IS UNIQUE;

// Example nodes
MERGE (c1:Contact {hubspot_id: '1'})
  ON CREATE SET c1.email='alice@example.com', c1.first_name='Alice', c1.last_name='Anderson',
                c1.total_email_opens=3, c1.total_email_clicks=1, c1.total_page_views=5;

MERGE (co1:Company {hubspot_id: '10'})
  ON CREATE SET co1.name='Acme Co', co1.domain='acme.example';

MERGE (d1:Deal {hubspot_id: '200'})
  ON CREATE SET d1.name='Sample Deal', d1.amount=1000.0, d1.dealstage='closedwon';

MERGE (e1:EmailCampaign {hubspot_id: '999'})
  ON CREATE SET e1.name='Spring Campaign', e1.subject='Sample Subject', e1.sent_date='2024-06-12T00:00:00';

MERGE (w1:WebPage {hubspot_id: 'https://example.com/page'})
  ON CREATE SET w1.url='https://example.com/page', w1.domain='example.com', w1.path='/page';

// Optional sample activity
MERGE (a1:Activity {hubspot_id: 'e1'})
  ON CREATE SET a1.type='MEETING', a1.timestamp='2024-06-12T00:00:00';

// Relationships
MERGE (c1)-[:WORKS_AT]->(co1);
MERGE (c1)-[:ASSOCIATED_WITH]->(d1);
MERGE (d1)-[:BELONGS_TO]->(co1);
MERGE (a1)-[:INVOLVES]->(c1);
MERGE (c1)-[:OPENED {timestamp:'2024-06-12T00:00:00'}]->(e1);
MERGE (c1)-[:CLICKED {timestamp:'2024-06-12T00:00:00', url:'https://example.com/page'}]->(e1);
MERGE (c1)-[:VISITED]->(w1);

// Return quick counts
RETURN {
  nodes: {
    contacts: COUNT { MATCH (:Contact) },
    companies: COUNT { MATCH (:Company) },
    deals: COUNT { MATCH (:Deal) },
    activities: COUNT { MATCH (:Activity) },
    campaigns: COUNT { MATCH (:EmailCampaign) },
    webpages: COUNT { MATCH (:WebPage) }
  },
  relationships: {
    WORKS_AT: COUNT { MATCH ()-[:WORKS_AT]->() },
    ASSOCIATED_WITH: COUNT { MATCH ()-[:ASSOCIATED_WITH]->() },
    BELONGS_TO: COUNT { MATCH ()-[:BELONGS_TO]->() },
    INVOLVES: COUNT { MATCH ()-[:INVOLVES]->() },
    OPENED: COUNT { MATCH ()-[:OPENED]->() },
    CLICKED: COUNT { MATCH ()-[:CLICKED]->() },
    VISITED: COUNT { MATCH ()-[:VISITED]->() }
  }
} AS summary;
