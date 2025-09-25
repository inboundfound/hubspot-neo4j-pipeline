# Neo4j schema definitions
CONSTRAINTS = [
    "CREATE CONSTRAINT hubspot_contact_id IF NOT EXISTS FOR (c:HUBSPOT_Contact) REQUIRE c.hubspot_id IS UNIQUE",
    "CREATE CONSTRAINT hubspot_company_id IF NOT EXISTS FOR (c:HUBSPOT_Company) REQUIRE c.hubspot_id IS UNIQUE",
    "CREATE CONSTRAINT hubspot_deal_id IF NOT EXISTS FOR (d:HUBSPOT_Deal) REQUIRE d.hubspot_id IS UNIQUE",
    "CREATE CONSTRAINT hubspot_email_campaign_id IF NOT EXISTS FOR (e:HUBSPOT_EmailCampaign) REQUIRE e.hubspot_id IS UNIQUE",
    "CREATE CONSTRAINT hubspot_activity_id IF NOT EXISTS FOR (a:HUBSPOT_Activity) REQUIRE a.hubspot_id IS UNIQUE",
    "CREATE CONSTRAINT hubspot_webpage_url IF NOT EXISTS FOR (w:HUBSPOT_WebPage) REQUIRE w.url IS UNIQUE"
]

INDEXES = [
    "CREATE INDEX hubspot_contact_email IF NOT EXISTS FOR (c:HUBSPOT_Contact) ON (c.email)",
    "CREATE INDEX hubspot_company_domain IF NOT EXISTS FOR (c:HUBSPOT_Company) ON (c.domain)",
    "CREATE INDEX hubspot_deal_stage IF NOT EXISTS FOR (d:HUBSPOT_Deal) ON (d.stage)",
    "CREATE INDEX hubspot_activity_type IF NOT EXISTS FOR (a:HUBSPOT_Activity) ON (a.type)",
    "CREATE INDEX hubspot_webpage_domain IF NOT EXISTS FOR (w:HUBSPOT_WebPage) ON (w.domain)"
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
