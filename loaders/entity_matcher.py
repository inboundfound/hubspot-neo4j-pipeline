from neo4j import GraphDatabase
from config.settings import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
from utils.logger import setup_logger


class EntityMatcher:
    """Match and link HubSpot entities to existing Knowledge Graph entities"""

    def __init__(self):
        self.logger = setup_logger(self.__class__.__name__)
        self.driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )

    def close(self):
        """Close the Neo4j driver"""
        self.driver.close()

    def link_users_to_persons(self):
        """
        Create SAME_AS relationships between HUBSPOT_User nodes and existing Person nodes.

        Matching strategy:
        1. Primary: Match by linkedin_url (most reliable)
        2. Fallback: Match by email address

        This preserves both node types and creates clear linkage for cross-system queries.
        """
        self.logger.info("Starting HUBSPOT_User to Person matching")

        with self.driver.session() as session:
            # Match by LinkedIn URL (primary strategy)
            linkedin_matches = self._match_by_linkedin(session)
            self.logger.info(f"Matched {linkedin_matches} users by LinkedIn URL")

            # Match by email (fallback strategy, only for unmatched users)
            email_matches = self._match_by_email(session)
            self.logger.info(f"Matched {email_matches} users by email address")

            # Report unmatched users
            unmatched = self._count_unmatched_users(session)
            self.logger.info(f"Unmatched HUBSPOT_Users: {unmatched}")

            total_matches = linkedin_matches + email_matches
            self.logger.info(f"Total matches created: {total_matches}")

            return {
                'linkedin_matches': linkedin_matches,
                'email_matches': email_matches,
                'unmatched': unmatched,
                'total_matches': total_matches
            }

    def _match_by_linkedin(self, session) -> int:
        """Match HUBSPOT_User to Person by LinkedIn URL"""
        # Note: linkedin_url may not be available in HubSpot Owners API
        # This query will only match if both sides have the linkedin_url property
        query = """
        MATCH (hu:HUBSPOT_User)
        WHERE hu.linkedin_url IS NOT NULL AND hu.linkedin_url <> ''
        MATCH (p:Person {linkedin_url: hu.linkedin_url})
        WHERE NOT EXISTS((hu)-[:SAME_AS]->(:Person))
        MERGE (hu)-[:SAME_AS]->(p)
        RETURN count(hu) as matched
        """

        result = session.run(query)
        record = result.single()
        return record['matched'] if record else 0

    def _match_by_email(self, session) -> int:
        """Match HUBSPOT_User to Person by email address (fallback)"""
        query = """
        MATCH (hu:HUBSPOT_User)
        WHERE hu.email IS NOT NULL AND hu.email <> ''
        AND NOT EXISTS((hu)-[:SAME_AS]->(:Person))
        MATCH (p:Person {email: hu.email})
        MERGE (hu)-[:SAME_AS]->(p)
        RETURN count(hu) as matched
        """

        result = session.run(query)
        record = result.single()
        return record['matched'] if record else 0

    def _count_unmatched_users(self, session) -> int:
        """Count HUBSPOT_Users that don't have SAME_AS relationships"""
        query = """
        MATCH (hu:HUBSPOT_User)
        WHERE NOT EXISTS((hu)-[:SAME_AS]->(:Person))
        RETURN count(hu) as unmatched
        """

        result = session.run(query)
        record = result.single()
        return record['unmatched'] if record else 0

    def verify_person_linkage(self):
        """
        Verify the Person linkage by showing statistics and examples.
        Useful for debugging and validation.
        """
        self.logger.info("Verifying HUBSPOT_User to Person linkage")

        with self.driver.session() as session:
            # Get total counts
            total_users_query = "MATCH (hu:HUBSPOT_User) RETURN count(hu) as total"
            total_users = session.run(total_users_query).single()['total']

            total_persons_query = "MATCH (p:Person) RETURN count(p) as total"
            total_persons = session.run(total_persons_query).single()['total']

            # Get linked counts
            linked_users_query = """
            MATCH (hu:HUBSPOT_User)-[:SAME_AS]->(p:Person)
            RETURN count(DISTINCT hu) as linked_users, count(DISTINCT p) as linked_persons
            """
            linked_result = session.run(linked_users_query).single()

            # Get sample linkages
            sample_query = """
            MATCH (hu:HUBSPOT_User)-[:SAME_AS]->(p:Person)
            RETURN hu.email as user_email, hu.first_name as user_first, hu.last_name as user_last,
                   p.email as person_email, p.full_name as person_name
            LIMIT 5
            """
            samples = session.run(sample_query)

            # Report results
            self.logger.info(f"\n{'='*60}")
            self.logger.info("PERSON LINKAGE VERIFICATION")
            self.logger.info(f"{'='*60}")
            self.logger.info(f"Total HUBSPOT_Users: {total_users}")
            self.logger.info(f"Total Persons: {total_persons}")
            self.logger.info(f"Linked HUBSPOT_Users: {linked_result['linked_users']}")
            self.logger.info(f"Linked Persons: {linked_result['linked_persons']}")
            self.logger.info(f"\nSample Linkages:")

            for i, sample in enumerate(samples, 1):
                self.logger.info(f"{i}. {sample['user_first']} {sample['user_last']} ({sample['user_email']}) "
                               f"-> {sample['person_name']} ({sample['person_email']})")

            return {
                'total_users': total_users,
                'total_persons': total_persons,
                'linked_users': linked_result['linked_users'],
                'linked_persons': linked_result['linked_persons']
            }


if __name__ == "__main__":
    """
    Standalone script to run entity matching after the main pipeline.

    Usage:
        python -m loaders.entity_matcher

    This can be run:
    1. After the main pipeline completes
    2. As a separate maintenance task to re-link entities
    3. When new Person nodes are added to the Knowledge Graph
    """
    import sys

    matcher = EntityMatcher()

    try:
        # Perform matching
        results = matcher.link_users_to_persons()

        # Verify results
        verification = matcher.verify_person_linkage()

        # Print summary
        print("\n" + "="*60)
        print("ENTITY MATCHING COMPLETE")
        print("="*60)
        print(f"LinkedIn matches: {results['linkedin_matches']}")
        print(f"Email matches: {results['email_matches']}")
        print(f"Total matches: {results['total_matches']}")
        print(f"Unmatched users: {results['unmatched']}")
        print("\nTo query linked entities:")
        print("  MATCH (hu:HUBSPOT_User)-[:SAME_AS]->(p:Person)")
        print("  RETURN hu, p")
        print("\nTo find contacts owned by a specific person:")
        print("  MATCH (c:HUBSPOT_Contact)-[:OWNED_BY]->(hu:HUBSPOT_User)-[:SAME_AS]->(p:Person)")
        print("  WHERE p.full_name = 'Gina Sus'")
        print("  RETURN c")

    except Exception as e:
        print(f"\nError during entity matching: {str(e)}")
        sys.exit(1)
    finally:
        matcher.close()
