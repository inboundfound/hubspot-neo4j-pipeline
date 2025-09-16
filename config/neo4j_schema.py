# Neo4j schema definitions
CONSTRAINTS = [
    "CREATE CONSTRAINT contact_id IF NOT EXISTS FOR (c:Contact) REQUIRE c.hubspot_id IS UNIQUE",
    "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.hubspot_id IS UNIQUE",
    "CREATE CONSTRAINT deal_id IF NOT EXISTS FOR (d:Deal) REQUIRE d.hubspot_id IS UNIQUE",
    "CREATE CONSTRAINT email_campaign_id IF NOT EXISTS FOR (e:EmailCampaign) REQUIRE e.hubspot_id IS UNIQUE",
    "CREATE CONSTRAINT activity_id IF NOT EXISTS FOR (a:Activity) REQUIRE a.hubspot_id IS UNIQUE",
    "CREATE CONSTRAINT webpage_url IF NOT EXISTS FOR (w:WebPage) REQUIRE w.url IS UNIQUE"
]

INDEXES = [
    "CREATE INDEX contact_email IF NOT EXISTS FOR (c:Contact) ON (c.email)",
    "CREATE INDEX company_domain IF NOT EXISTS FOR (c:Company) ON (c.domain)",
    "CREATE INDEX deal_stage IF NOT EXISTS FOR (d:Deal) ON (d.stage)",
    "CREATE INDEX activity_type IF NOT EXISTS FOR (a:Activity) ON (a.type)",
    "CREATE INDEX webpage_domain IF NOT EXISTS FOR (w:WebPage) ON (w.domain)"
]

# Node property mappings
CONTACT_PROPERTIES = [
    'email', 'firstname', 'lastname', 'company', 'jobtitle', 'phone',
    'lifecyclestage', 'hs_lead_status', 'createdate', 'lastmodifieddate',
    'hs_analytics_source', 'hs_analytics_first_url', 'hs_analytics_last_url',
    'hs_email_open', 'hs_email_click', 'hs_email_last_send_date',
    'hs_analytics_num_visits', 'hubspot_owner_id'
]

COMPANY_PROPERTIES = [
    'name', 'domain', 'industry', 'numberofemployees', 'annualrevenue',
    'description', 'createdate', 'hs_lastmodifieddate', 'country', 'city',
    'state', 'zip', 'website', 'type', 'hubspot_owner_id'
]

DEAL_PROPERTIES = [
    'dealname', 'amount', 'dealstage', 'pipeline', 'closedate',
    'createdate', 'hs_lastmodifieddate', 'hs_is_closed_won',
    'description', 'hubspot_owner_id', 'hs_forecast_probability'
]
