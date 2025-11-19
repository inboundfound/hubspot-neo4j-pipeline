"""
Create minimal test dataset for temporal tracking testing.

This generates small JSON files with just a few records of each type
to make testing and debugging easier.

Usage:
    python scripts/create_test_data.py
"""

import json
import os
from datetime import datetime


def create_test_data():
    """Create minimal test dataset"""
    
    # Create test data directory
    os.makedirs('data/test', exist_ok=True)
    
    # Test Users (2)
    users = [
        {
            "id": "test_user_1",
            "email": "john.doe@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "archived": False,
            "created_at": "2024-01-01T10:00:00Z",
            "updated_at": "2024-01-01T10:00:00Z",
            "user_id": "100",
            "teams": []
        },
        {
            "id": "test_user_2",
            "email": "jane.smith@example.com",
            "first_name": "Jane",
            "last_name": "Smith",
            "archived": False,
            "created_at": "2024-01-01T10:00:00Z",
            "updated_at": "2024-01-01T10:00:00Z",
            "user_id": "101",
            "teams": []
        }
    ]
    
    # Test Contacts (3)
    contacts = [
        {
            "id": "test_contact_1",
            "properties": {
                "email": "alice@company1.com",
                "firstname": "Alice",
                "lastname": "Johnson",
                "jobtitle": "CEO",
                "lifecyclestage": "customer",
                "createdate": "2024-01-15T10:00:00Z",
                "lastmodifieddate": "2024-01-15T10:00:00Z",
                "hubspot_owner_id": "test_user_1",
                "associatedcompanyid": "test_company_1",
                "hs_email_open": "5",
                "hs_email_click": "2",
                "hs_analytics_num_visits": "10"
            }
        },
        {
            "id": "test_contact_2",
            "properties": {
                "email": "bob@company2.com",
                "firstname": "Bob",
                "lastname": "Williams",
                "jobtitle": "CTO",
                "lifecyclestage": "lead",
                "createdate": "2024-02-01T10:00:00Z",
                "lastmodifieddate": "2024-02-01T10:00:00Z",
                "hubspot_owner_id": "test_user_2",
                "associatedcompanyid": "test_company_2",
                "hs_email_open": "3",
                "hs_email_click": "1",
                "hs_analytics_num_visits": "5"
            }
        },
        {
            "id": "test_contact_3",
            "properties": {
                "email": "charlie@company1.com",
                "firstname": "Charlie",
                "lastname": "Brown",
                "jobtitle": "Manager",
                "lifecyclestage": "opportunity",
                "createdate": "2024-03-01T10:00:00Z",
                "lastmodifieddate": "2024-03-01T10:00:00Z",
                "hubspot_owner_id": "test_user_1",
                "associatedcompanyid": "test_company_1",
                "hs_email_open": "8",
                "hs_email_click": "4"
            }
        }
    ]
    
    # Test Companies (2)
    companies = [
        {
            "id": "test_company_1",
            "properties": {
                "name": "Acme Corp",
                "domain": "acme.com",
                "industry": "Technology",
                "numberofemployees": "100",
                "annualrevenue": "10000000",
                "createdate": "2024-01-10T10:00:00Z",
                "hs_lastmodifieddate": "2024-01-10T10:00:00Z",
                "hubspot_owner_id": "test_user_1",
                "city": "San Francisco",
                "state": "CA",
                "country": "USA"
            }
        },
        {
            "id": "test_company_2",
            "properties": {
                "name": "TechStart Inc",
                "domain": "techstart.io",
                "industry": "Software",
                "numberofemployees": "50",
                "annualrevenue": "5000000",
                "createdate": "2024-01-20T10:00:00Z",
                "hs_lastmodifieddate": "2024-01-20T10:00:00Z",
                "hubspot_owner_id": "test_user_2",
                "city": "Austin",
                "state": "TX",
                "country": "USA"
            }
        }
    ]
    
    # Test Deals (2)
    deals = [
        {
            "id": "test_deal_1",
            "properties": {
                "dealname": "Big Sale",
                "amount": "50000",
                "dealstage": "closedwon",
                "pipeline": "default",
                "closedate": "2024-03-15T10:00:00Z",
                "createdate": "2024-02-01T10:00:00Z",
                "hs_lastmodifieddate": "2024-03-15T10:00:00Z",
                "hubspot_owner_id": "test_user_1",
                "hs_is_closed_won": "true"
            },
            "associations": {
                "companies": [{"id": "test_company_1"}],
                "contacts": [{"id": "test_contact_1"}, {"id": "test_contact_3"}]
            }
        },
        {
            "id": "test_deal_2",
            "properties": {
                "dealname": "Small Deal",
                "amount": "10000",
                "dealstage": "presentation",
                "pipeline": "default",
                "closedate": "2024-04-30T10:00:00Z",
                "createdate": "2024-03-01T10:00:00Z",
                "hs_lastmodifieddate": "2024-03-01T10:00:00Z",
                "hubspot_owner_id": "test_user_2",
                "hs_is_closed_won": "false"
            },
            "associations": {
                "companies": [{"id": "test_company_2"}],
                "contacts": [{"id": "test_contact_2"}]
            }
        }
    ]
    
    # Test Engagements (3)
    engagements = [
        {
            "id": "test_engagement_1",
            "properties": {
                "hs_engagement_type": "MEETING",
                "hs_timestamp": "2024-02-10T14:00:00Z",
                "hs_createdate": "2024-02-10T14:00:00Z",
                "hs_lastmodifieddate": "2024-02-10T14:00:00Z",
                "hs_meeting_title": "Kickoff Meeting",
                "hs_meeting_body": "Initial discussion about the project"
            },
            "associations": {
                "contacts": [{"id": "test_contact_1"}],
                "companies": [{"id": "test_company_1"}],
                "deals": [{"id": "test_deal_1"}]
            }
        },
        {
            "id": "test_engagement_2",
            "properties": {
                "hs_engagement_type": "CALL",
                "hs_timestamp": "2024-03-05T11:30:00Z",
                "hs_createdate": "2024-03-05T11:30:00Z",
                "hs_lastmodifieddate": "2024-03-05T11:30:00Z",
                "hs_call_title": "Follow-up Call",
                "hs_call_body": "Discussed next steps",
                "hs_call_duration": "1800"
            },
            "associations": {
                "contacts": [{"id": "test_contact_2"}],
                "companies": [{"id": "test_company_2"}]
            }
        },
        {
            "id": "test_engagement_3",
            "properties": {
                "hs_engagement_type": "NOTE",
                "hs_timestamp": "2024-03-20T16:00:00Z",
                "hs_createdate": "2024-03-20T16:00:00Z",
                "hs_lastmodifieddate": "2024-03-20T16:00:00Z",
                "hs_note_body": "Customer is very interested in our product"
            },
            "associations": {
                "contacts": [{"id": "test_contact_1"}],
                "companies": [{"id": "test_company_1"}]
            }
        }
    ]
    
    # Test Email Events (2 opens, 1 click)
    email_events = [
        {
            "id": "test_email_open_1",
            "eventType": "OPEN",
            "recipient": "alice@company1.com",
            "created": "2024-02-15T09:00:00.000Z",
            "emailCampaignId": "test_campaign_1"
        },
        {
            "id": "test_email_open_2",
            "eventType": "OPEN",
            "recipient": "bob@company2.com",
            "created": "2024-02-16T10:00:00.000Z",
            "emailCampaignId": "test_campaign_1"
        },
        {
            "id": "test_email_click_1",
            "eventType": "CLICK",
            "recipient": "alice@company1.com",
            "created": "2024-02-15T09:05:00.000Z",
            "url": "https://example.com/product",
            "emailCampaignId": "test_campaign_1"
        }
    ]
    
    # Test Form Submissions (2)
    form_submissions = [
        {
            "submittedAt": "2024-01-15T10:00:00.000Z",
            "values": [
                {"name": "email", "value": "alice@company1.com"},
                {"name": "firstname", "value": "Alice"},
                {"name": "lastname", "value": "Johnson"}
            ],
            "pageUrl": "https://example.com/contact",
            "pageName": "Contact Us"
        },
        {
            "submittedAt": "2024-02-01T10:00:00.000Z",
            "values": [
                {"name": "email", "value": "bob@company2.com"},
                {"name": "firstname", "value": "Bob"},
                {"name": "lastname", "value": "Williams"}
            ],
            "pageUrl": "https://example.com/demo",
            "pageName": "Request Demo"
        }
    ]
    
    # Save all test data
    test_files = {
        'users.json': users,
        'contacts.json': contacts,
        'companies.json': companies,
        'deals.json': deals,
        'engagements.json': engagements,
        'email_events.json': email_events,
        'form_submissions.json': form_submissions
    }
    
    for filename, data in test_files.items():
        filepath = f'data/test/{filename}'
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"✓ Created {filepath} ({len(data)} records)")
    
    print(f"\n✅ Test data created in data/test/")
    print("\nTo use this test data, modify main.py to read from data/test/ instead of data/raw/")
    print("\nTest dataset summary:")
    print(f"  - 2 Users")
    print(f"  - 3 Contacts")
    print(f"  - 2 Companies")
    print(f"  - 2 Deals")
    print(f"  - 3 Engagements (1 meeting, 1 call, 1 note)")
    print(f"  - 3 Email Events (2 opens, 1 click)")
    print(f"  - 2 Form Submissions")
    print(f"\nExpected relationships: ~15-20")


if __name__ == "__main__":
    create_test_data()


