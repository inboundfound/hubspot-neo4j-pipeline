# Neo4j schema definitions
CONSTRAINTS = [
    # Primary entity constraints
    "CREATE CONSTRAINT hubspot_contact_id IF NOT EXISTS FOR (c:HUBSPOT_Contact) REQUIRE c.hubspot_id IS UNIQUE",
    "CREATE CONSTRAINT hubspot_company_id IF NOT EXISTS FOR (c:HUBSPOT_Company) REQUIRE c.hubspot_id IS UNIQUE",
    "CREATE CONSTRAINT hubspot_deal_id IF NOT EXISTS FOR (d:HUBSPOT_Deal) REQUIRE d.hubspot_id IS UNIQUE",
    "CREATE CONSTRAINT hubspot_email_campaign_id IF NOT EXISTS FOR (e:HUBSPOT_EmailCampaign) REQUIRE e.hubspot_id IS UNIQUE",
    "CREATE CONSTRAINT hubspot_activity_id IF NOT EXISTS FOR (a:HUBSPOT_Activity) REQUIRE a.hubspot_id IS UNIQUE",
    "CREATE CONSTRAINT hubspot_webpage_url IF NOT EXISTS FOR (w:HUBSPOT_WebPage) REQUIRE w.url IS UNIQUE",
    "CREATE CONSTRAINT hubspot_user_id IF NOT EXISTS FOR (u:HUBSPOT_User) REQUIRE u.hubspot_id IS UNIQUE",
    "CREATE CONSTRAINT hubspot_email_open_event_id IF NOT EXISTS FOR (e:HUBSPOT_EmailOpenEvent) REQUIRE e.hubspot_id IS UNIQUE",
    "CREATE CONSTRAINT hubspot_email_click_event_id IF NOT EXISTS FOR (e:HUBSPOT_EmailClickEvent) REQUIRE e.hubspot_id IS UNIQUE",
    "CREATE CONSTRAINT hubspot_form_submission_id IF NOT EXISTS FOR (f:HUBSPOT_FormSubmission) REQUIRE f.hubspot_id IS UNIQUE",
    "CREATE CONSTRAINT hubspot_page_visit_id IF NOT EXISTS FOR (p:HUBSPOT_PageVisit) REQUIRE p.hubspot_id IS UNIQUE",
    
    # History node constraints (composite: hubspot_id + valid_from must be unique)
    "CREATE CONSTRAINT hubspot_contact_history_id IF NOT EXISTS FOR (h:HUBSPOT_Contact_HISTORY) REQUIRE (h.hubspot_id, h.valid_from) IS UNIQUE",
    "CREATE CONSTRAINT hubspot_company_history_id IF NOT EXISTS FOR (h:HUBSPOT_Company_HISTORY) REQUIRE (h.hubspot_id, h.valid_from) IS UNIQUE",
    "CREATE CONSTRAINT hubspot_deal_history_id IF NOT EXISTS FOR (h:HUBSPOT_Deal_HISTORY) REQUIRE (h.hubspot_id, h.valid_from) IS UNIQUE",
    "CREATE CONSTRAINT hubspot_activity_history_id IF NOT EXISTS FOR (h:HUBSPOT_Activity_HISTORY) REQUIRE (h.hubspot_id, h.valid_from) IS UNIQUE",
    "CREATE CONSTRAINT hubspot_user_history_id IF NOT EXISTS FOR (h:HUBSPOT_User_HISTORY) REQUIRE (h.hubspot_id, h.valid_from) IS UNIQUE"
]

INDEXES = [
    # Existing indexes
    "CREATE INDEX hubspot_contact_email IF NOT EXISTS FOR (c:HUBSPOT_Contact) ON (c.email)",
    "CREATE INDEX hubspot_contact_owner IF NOT EXISTS FOR (c:HUBSPOT_Contact) ON (c.owner_id)",
    "CREATE INDEX hubspot_contact_created IF NOT EXISTS FOR (c:HUBSPOT_Contact) ON (c.created_date)",
    "CREATE INDEX hubspot_contact_modified IF NOT EXISTS FOR (c:HUBSPOT_Contact) ON (c.last_modified)",
    "CREATE INDEX hubspot_company_domain IF NOT EXISTS FOR (c:HUBSPOT_Company) ON (c.domain)",
    "CREATE INDEX hubspot_company_owner IF NOT EXISTS FOR (c:HUBSPOT_Company) ON (c.owner_id)",
    "CREATE INDEX hubspot_company_created IF NOT EXISTS FOR (c:HUBSPOT_Company) ON (c.created_date)",
    "CREATE INDEX hubspot_company_modified IF NOT EXISTS FOR (c:HUBSPOT_Company) ON (c.last_modified)",
    "CREATE INDEX hubspot_deal_stage IF NOT EXISTS FOR (d:HUBSPOT_Deal) ON (d.stage)",
    "CREATE INDEX hubspot_deal_owner IF NOT EXISTS FOR (d:HUBSPOT_Deal) ON (d.owner_id)",
    "CREATE INDEX hubspot_deal_created IF NOT EXISTS FOR (d:HUBSPOT_Deal) ON (d.created_date)",
    "CREATE INDEX hubspot_deal_modified IF NOT EXISTS FOR (d:HUBSPOT_Deal) ON (d.last_modified)",
    "CREATE INDEX hubspot_deal_closedate IF NOT EXISTS FOR (d:HUBSPOT_Deal) ON (d.close_date)",
    "CREATE INDEX hubspot_activity_type IF NOT EXISTS FOR (a:HUBSPOT_Activity) ON (a.type)",
    "CREATE INDEX hubspot_activity_timestamp IF NOT EXISTS FOR (a:HUBSPOT_Activity) ON (a.timestamp)",
    "CREATE INDEX hubspot_activity_created IF NOT EXISTS FOR (a:HUBSPOT_Activity) ON (a.created_date)",
    "CREATE INDEX hubspot_webpage_domain IF NOT EXISTS FOR (w:HUBSPOT_WebPage) ON (w.domain)",
    "CREATE INDEX hubspot_user_email IF NOT EXISTS FOR (u:HUBSPOT_User) ON (u.email)",
    "CREATE INDEX hubspot_email_open_timestamp IF NOT EXISTS FOR (e:HUBSPOT_EmailOpenEvent) ON (e.timestamp)",
    "CREATE INDEX hubspot_email_open_campaign IF NOT EXISTS FOR (e:HUBSPOT_EmailOpenEvent) ON (e.campaign_id)",
    "CREATE INDEX hubspot_email_click_timestamp IF NOT EXISTS FOR (e:HUBSPOT_EmailClickEvent) ON (e.timestamp)",
    "CREATE INDEX hubspot_email_click_campaign IF NOT EXISTS FOR (e:HUBSPOT_EmailClickEvent) ON (e.campaign_id)",
    "CREATE INDEX hubspot_form_submission_timestamp IF NOT EXISTS FOR (f:HUBSPOT_FormSubmission) ON (f.timestamp)",
    "CREATE INDEX hubspot_form_submission_form IF NOT EXISTS FOR (f:HUBSPOT_FormSubmission) ON (f.form_guid)",
    "CREATE INDEX hubspot_page_visit_timestamp IF NOT EXISTS FOR (p:HUBSPOT_PageVisit) ON (p.timestamp)",
    "CREATE INDEX hubspot_page_visit_url IF NOT EXISTS FOR (p:HUBSPOT_PageVisit) ON (p.page_url)",
    
    # Temporal indexes for main entity nodes
    "CREATE INDEX hubspot_contact_valid_from IF NOT EXISTS FOR (c:HUBSPOT_Contact) ON (c.valid_from)",
    "CREATE INDEX hubspot_contact_valid_to IF NOT EXISTS FOR (c:HUBSPOT_Contact) ON (c.valid_to)",
    "CREATE INDEX hubspot_contact_is_current IF NOT EXISTS FOR (c:HUBSPOT_Contact) ON (c.is_current)",
    "CREATE INDEX hubspot_contact_is_deleted IF NOT EXISTS FOR (c:HUBSPOT_Contact) ON (c.is_deleted)",
    "CREATE INDEX hubspot_company_valid_from IF NOT EXISTS FOR (c:HUBSPOT_Company) ON (c.valid_from)",
    "CREATE INDEX hubspot_company_valid_to IF NOT EXISTS FOR (c:HUBSPOT_Company) ON (c.valid_to)",
    "CREATE INDEX hubspot_company_is_current IF NOT EXISTS FOR (c:HUBSPOT_Company) ON (c.is_current)",
    "CREATE INDEX hubspot_company_is_deleted IF NOT EXISTS FOR (c:HUBSPOT_Company) ON (c.is_deleted)",
    "CREATE INDEX hubspot_deal_valid_from IF NOT EXISTS FOR (d:HUBSPOT_Deal) ON (d.valid_from)",
    "CREATE INDEX hubspot_deal_valid_to IF NOT EXISTS FOR (d:HUBSPOT_Deal) ON (d.valid_to)",
    "CREATE INDEX hubspot_deal_is_current IF NOT EXISTS FOR (d:HUBSPOT_Deal) ON (d.is_current)",
    "CREATE INDEX hubspot_deal_is_deleted IF NOT EXISTS FOR (d:HUBSPOT_Deal) ON (d.is_deleted)",
    "CREATE INDEX hubspot_activity_valid_from IF NOT EXISTS FOR (a:HUBSPOT_Activity) ON (a.valid_from)",
    "CREATE INDEX hubspot_activity_valid_to IF NOT EXISTS FOR (a:HUBSPOT_Activity) ON (a.valid_to)",
    "CREATE INDEX hubspot_activity_is_current IF NOT EXISTS FOR (a:HUBSPOT_Activity) ON (a.is_current)",
    "CREATE INDEX hubspot_activity_is_deleted IF NOT EXISTS FOR (a:HUBSPOT_Activity) ON (a.is_deleted)",
    "CREATE INDEX hubspot_user_valid_from IF NOT EXISTS FOR (u:HUBSPOT_User) ON (u.valid_from)",
    "CREATE INDEX hubspot_user_valid_to IF NOT EXISTS FOR (u:HUBSPOT_User) ON (u.valid_to)",
    "CREATE INDEX hubspot_user_is_current IF NOT EXISTS FOR (u:HUBSPOT_User) ON (u.is_current)",
    "CREATE INDEX hubspot_user_is_deleted IF NOT EXISTS FOR (u:HUBSPOT_User) ON (u.is_deleted)",
    
    # Temporal indexes for history nodes
    "CREATE INDEX hubspot_contact_history_valid_from IF NOT EXISTS FOR (h:HUBSPOT_Contact_HISTORY) ON (h.valid_from)",
    "CREATE INDEX hubspot_contact_history_valid_to IF NOT EXISTS FOR (h:HUBSPOT_Contact_HISTORY) ON (h.valid_to)",
    "CREATE INDEX hubspot_company_history_valid_from IF NOT EXISTS FOR (h:HUBSPOT_Company_HISTORY) ON (h.valid_from)",
    "CREATE INDEX hubspot_company_history_valid_to IF NOT EXISTS FOR (h:HUBSPOT_Company_HISTORY) ON (h.valid_to)",
    "CREATE INDEX hubspot_deal_history_valid_from IF NOT EXISTS FOR (h:HUBSPOT_Deal_HISTORY) ON (h.valid_from)",
    "CREATE INDEX hubspot_deal_history_valid_to IF NOT EXISTS FOR (h:HUBSPOT_Deal_HISTORY) ON (h.valid_to)",
    "CREATE INDEX hubspot_activity_history_valid_from IF NOT EXISTS FOR (h:HUBSPOT_Activity_HISTORY) ON (h.valid_from)",
    "CREATE INDEX hubspot_activity_history_valid_to IF NOT EXISTS FOR (h:HUBSPOT_Activity_HISTORY) ON (h.valid_to)",
    "CREATE INDEX hubspot_user_history_valid_from IF NOT EXISTS FOR (h:HUBSPOT_User_HISTORY) ON (h.valid_from)",
    "CREATE INDEX hubspot_user_history_valid_to IF NOT EXISTS FOR (h:HUBSPOT_User_HISTORY) ON (h.valid_to)",
    
    # Relationship change tracking indexes
    "CREATE INDEX hubspot_rel_change_timestamp IF NOT EXISTS FOR (rc:HUBSPOT_RelationshipChange) ON (rc.changed_at)",
    "CREATE INDEX hubspot_rel_change_type IF NOT EXISTS FOR (rc:HUBSPOT_RelationshipChange) ON (rc.change_type)",
    "CREATE INDEX hubspot_rel_change_from_entity IF NOT EXISTS FOR (rc:HUBSPOT_RelationshipChange) ON (rc.from_entity_id)",
    "CREATE INDEX hubspot_rel_change_to_entity IF NOT EXISTS FOR (rc:HUBSPOT_RelationshipChange) ON (rc.to_entity_id)",
    "CREATE INDEX hubspot_rel_change_rel_type IF NOT EXISTS FOR (rc:HUBSPOT_RelationshipChange) ON (rc.relationship_type)"
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
