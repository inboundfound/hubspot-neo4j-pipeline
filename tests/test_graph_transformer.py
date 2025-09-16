from transformers.graph_transformer import GraphTransformer


def test_transformer_with_minimal_data():
    transformer = GraphTransformer()
    sample = {
        'contacts': [
            {
                'id': '1',
                'properties': {
                    'email': 'Alice@example.com',
                    'firstname': 'Alice',
                    'lastname': 'A',
                    'associatedcompanyid': '10',
                    'hs_email_open': '3',
                    'hs_email_click': '1',
                    'hs_analytics_num_visits': '5',
                },
                'associations': {
                    # Match the structure produced by BaseExtractor._extract_associations
                    'deals': [{'id': '200'}]
                }
            }
        ],
        'companies': [
            {
                'id': '10',
                'properties': {
                    'name': 'Acme Co'
                }
            }
        ],
        'deals': [
            {
                'id': '200',
                'properties': {
                    'amount': '1000'
                },
                'associations': {
                    'contacts': [{'id': '1'}],
                    'companies': [{'id': '10'}]
                }
            }
        ],
        'email_events': [
            {
                'recipient': 'alice@example.com',
                'event_type': 'OPEN',
                'emailCampaignId': 999,
                'emailCampaignName': 'Spring Campaign',
                'created': 1718131200000
            },
            {
                'recipient': 'alice@example.com',
                'event_type': 'CLICK',
                'emailCampaignId': 999,
                'emailCampaignName': 'Spring Campaign',
                'created': 1718131200000,
                'url': 'https://example.com/page'
            }
        ]
    }

    nodes, rels = transformer.transform_all(sample)

    # Basic shape checks
    assert 'Contact' in nodes and nodes['Contact'], 'Contacts should be generated'
    assert 'Company' in nodes and nodes['Company'], 'Companies should be generated'
    assert 'Deal' in nodes and nodes['Deal'], 'Deals should be generated'

    # Relationship presence (WORKS_AT from associatedcompanyid)
    assert any(r['type'] == 'WORKS_AT' for r in rels), 'Expected WORKS_AT contact->company relationship'

    # Email campaign node and relationships
    assert 'EmailCampaign' in nodes and nodes['EmailCampaign'], 'EmailCampaign node should be created'
    assert any(r['type'] in ('OPENED', 'CLICKED') for r in rels), 'Expected email OPENED/CLICKED relationships'
