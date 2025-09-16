import os
import pytest

pytestmark = pytest.mark.integration


def test_env_has_minimums():
    # This test doesn't call external services; it only ensures required envs exist for a real run
    assert os.getenv('HUBSPOT_ACCESS_TOKEN') or (
        os.getenv('HUBSPOT_APP') and os.getenv(f"{os.getenv('HUBSPOT_APP').upper()}_ACCESS_TOKEN")
    ), "Provide HUBSPOT_ACCESS_TOKEN or HUBSPOT_APP + <APP>_ACCESS_TOKEN to run real integration."
    assert os.getenv('NEO4J_PASSWORD'), "NEO4J_PASSWORD must be set for Neo4j integration run."
