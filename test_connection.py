import hubspot
from neo4j import GraphDatabase
from config.settings import HUBSPOT_ACCESS_TOKEN, NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
from utils.logger import setup_logger


def test_hubspot_connection():
    """Test HubSpot API connection using current token resolution."""
    logger = setup_logger('ConnectionTest')

    try:
        client = hubspot.Client.create(access_token=HUBSPOT_ACCESS_TOKEN)

        # Minimal search to validate token works
        from hubspot.crm.contacts import PublicObjectSearchRequest
        search_request = PublicObjectSearchRequest(
            properties=['email'],
            limit=1
        )

        client.crm.contacts.search_api.do_search(
            public_object_search_request=search_request
        )

        logger.info("✅ HubSpot connection successful")
        return True

    except Exception as e:
        logger.error(f"❌ HubSpot connection failed: {str(e)}")
        return False


def test_neo4j_connection():
    """Test Neo4j connection using environment configuration."""
    logger = setup_logger('ConnectionTest')

    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            value = result.single()['test']
            if value == 1:
                logger.info("✅ Neo4j connection successful")
                driver.close()
                return True
        return False
    except Exception as e:
        logger.error(f"❌ Neo4j connection failed: {str(e)}")
        return False


def main():
    print("\n🔧 Testing connections...\n")
    hubspot_ok = test_hubspot_connection()
    neo4j_ok = test_neo4j_connection()
    print("\n" + "="*50)
    if hubspot_ok and neo4j_ok:
        print("✅ All connections successful! You're ready to run the pipeline.")
    else:
        print("❌ Some connections failed. Please check your configuration.")
    print("="*50 + "\n")


if __name__ == "__main__":
    main()
