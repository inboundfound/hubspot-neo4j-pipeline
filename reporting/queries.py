"""
Predefined Cypher queries for HubSpot Neo4j reporting
"""

class ReportQueries:
    """Collection of Cypher queries for common reporting needs"""

    @staticmethod
    def contacts_by_owner(owner_name_pattern: str) -> str:
        """Get all contacts owned by a specific owner

        Args:
            owner_name_pattern: Name to match (supports first_name or last_name)

        Returns:
            Cypher query string
        """
        return """
        MATCH (c:HUBSPOT_Contact)-[:OWNED_BY]->(u:HUBSPOT_User)
        WHERE u.first_name CONTAINS $owner_name
           OR u.last_name CONTAINS $owner_name
        RETURN
            u.email AS owner_email,
            u.first_name + ' ' + u.last_name AS owner_name,
            c.hubspot_id AS contact_id,
            c.email AS contact_email,
            c.first_name AS contact_first_name,
            c.last_name AS contact_last_name,
            c.job_title AS job_title,
            c.lifecycle_stage AS lifecycle_stage,
            c.created_date AS created_date,
            c.last_modified AS last_modified
        ORDER BY c.created_date DESC
        """

    @staticmethod
    def companies_by_owner(owner_name_pattern: str) -> str:
        """Get all companies owned by a specific owner

        Args:
            owner_name_pattern: Name to match (supports first_name or last_name)

        Returns:
            Cypher query string
        """
        return """
        MATCH (co:HUBSPOT_Company)-[:OWNED_BY]->(u:HUBSPOT_User)
        WHERE u.first_name CONTAINS $owner_name
           OR u.last_name CONTAINS $owner_name
        RETURN
            u.email AS owner_email,
            u.first_name + ' ' + u.last_name AS owner_name,
            co.hubspot_id AS company_id,
            co.name AS company_name,
            co.domain AS domain,
            co.industry AS industry,
            co.employee_count AS employee_count,
            co.annual_revenue AS annual_revenue,
            co.city AS city,
            co.state AS state,
            co.country AS country,
            co.created_date AS created_date,
            co.last_modified AS last_modified
        ORDER BY co.created_date DESC
        """

    @staticmethod
    def deals_by_owner(owner_name_pattern: str) -> str:
        """Get all deals owned by a specific owner

        Args:
            owner_name_pattern: Name to match (supports first_name or last_name)

        Returns:
            Cypher query string
        """
        return """
        MATCH (d:HUBSPOT_Deal)-[:OWNED_BY]->(u:HUBSPOT_User)
        WHERE u.first_name CONTAINS $owner_name
           OR u.last_name CONTAINS $owner_name
        RETURN
            u.email AS owner_email,
            u.first_name + ' ' + u.last_name AS owner_name,
            d.hubspot_id AS deal_id,
            d.name AS deal_name,
            d.amount AS amount,
            d.stage AS stage,
            d.pipeline AS pipeline,
            d.close_date AS close_date,
            d.created_date AS created_date,
            d.last_modified AS last_modified
        ORDER BY d.created_date DESC
        """

    @staticmethod
    def owner_summary(owner_name_pattern: str) -> str:
        """Get summary statistics for an owner

        Args:
            owner_name_pattern: Name to match (supports first_name or last_name)

        Returns:
            Cypher query string
        """
        return """
        MATCH (u:HUBSPOT_User)
        WHERE u.first_name CONTAINS $owner_name
           OR u.last_name CONTAINS $owner_name
        OPTIONAL MATCH (c:HUBSPOT_Contact)-[:OWNED_BY]->(u)
        OPTIONAL MATCH (co:HUBSPOT_Company)-[:OWNED_BY]->(u)
        OPTIONAL MATCH (d:HUBSPOT_Deal)-[:OWNED_BY]->(u)
        RETURN
            u.email AS owner_email,
            u.first_name + ' ' + u.last_name AS owner_name,
            u.active AS active,
            count(DISTINCT c) AS contacts_owned,
            count(DISTINCT co) AS companies_owned,
            count(DISTINCT d) AS deals_owned
        """

    @staticmethod
    def all_owners_summary() -> str:
        """Get portfolio summary for all owners

        Returns:
            Cypher query string
        """
        return """
        MATCH (u:HUBSPOT_User)
        OPTIONAL MATCH (c:HUBSPOT_Contact)-[:OWNED_BY]->(u)
        OPTIONAL MATCH (co:HUBSPOT_Company)-[:OWNED_BY]->(u)
        OPTIONAL MATCH (d:HUBSPOT_Deal)-[:OWNED_BY]->(u)
        RETURN
            u.email AS owner_email,
            u.first_name + ' ' + u.last_name AS owner_name,
            u.active AS active,
            count(DISTINCT c) AS contacts_owned,
            count(DISTINCT co) AS companies_owned,
            count(DISTINCT d) AS deals_owned
        ORDER BY contacts_owned DESC
        """

    @staticmethod
    def contacts_by_lifecycle_stage() -> str:
        """Get contact counts by lifecycle stage

        Returns:
            Cypher query string
        """
        return """
        MATCH (c:HUBSPOT_Contact)
        RETURN
            c.lifecycle_stage AS lifecycle_stage,
            count(c) AS count
        ORDER BY count DESC
        """

    @staticmethod
    def companies_by_industry() -> str:
        """Get company counts by industry

        Returns:
            Cypher query string
        """
        return """
        MATCH (co:HUBSPOT_Company)
        WHERE co.industry IS NOT NULL
        RETURN
            co.industry AS industry,
            count(co) AS count
        ORDER BY count DESC
        """

    @staticmethod
    def recent_form_submissions(days: int = 30) -> str:
        """Get recent form submissions

        Args:
            days: Number of days to look back

        Returns:
            Cypher query string
        """
        return """
        MATCH (c:HUBSPOT_Contact)-[:SUBMITTED]->(f:HUBSPOT_FormSubmission)
        WHERE datetime(f.timestamp) >= datetime() - duration({days: $days})
        RETURN
            c.email AS contact_email,
            c.first_name + ' ' + c.last_name AS contact_name,
            f.form_id AS form_id,
            f.title AS form_title,
            f.timestamp AS submission_date
        ORDER BY f.timestamp DESC
        """

    @staticmethod
    def recent_email_activity(days: int = 30) -> str:
        """Get recent email opens and clicks

        Args:
            days: Number of days to look back

        Returns:
            Cypher query string
        """
        return """
        MATCH (c:HUBSPOT_Contact)-[:OPENED|CLICKED]->(e)
        WHERE (e:HUBSPOT_EmailOpenEvent OR e:HUBSPOT_EmailClickEvent)
          AND datetime(e.timestamp) >= datetime() - duration({days: $days})
        OPTIONAL MATCH (c)-[:OWNED_BY]->(u:HUBSPOT_User)
        RETURN
            c.email AS contact_email,
            c.first_name + ' ' + c.last_name AS contact_name,
            u.first_name + ' ' + u.last_name AS owner_name,
            labels(e)[0] AS event_type,
            e.timestamp AS event_date,
            e.campaign_id AS campaign_id
        ORDER BY e.timestamp DESC
        """

    @staticmethod
    def contacts_with_recent_activity(owner_name_pattern: str, days: int = 30) -> str:
        """Get contacts owned by specific owner with recent activity

        Args:
            owner_name_pattern: Owner name to match
            days: Number of days to look back

        Returns:
            Cypher query string
        """
        return """
        MATCH (c:HUBSPOT_Contact)-[:OWNED_BY]->(u:HUBSPOT_User)
        WHERE u.first_name CONTAINS $owner_name
           OR u.last_name CONTAINS $owner_name
        OPTIONAL MATCH (c)-[:OPENED|CLICKED|SUBMITTED]->(event)
        WHERE datetime(event.timestamp) >= datetime() - duration({days: $days})
        WITH c, u, count(event) AS activity_count
        WHERE activity_count > 0
        RETURN
            u.email AS owner_email,
            c.email AS contact_email,
            c.first_name + ' ' + c.last_name AS contact_name,
            c.lifecycle_stage AS lifecycle_stage,
            activity_count AS recent_activities
        ORDER BY activity_count DESC
        """

    @staticmethod
    def contact_engagement_history(contact_email: str) -> str:
        """Get full engagement history for a specific contact

        Args:
            contact_email: Contact email to query

        Returns:
            Cypher query string
        """
        return """
        MATCH (c:HUBSPOT_Contact {email: $contact_email})
        OPTIONAL MATCH (c)-[r]->(related)
        WHERE type(r) IN ['OPENED', 'CLICKED', 'SUBMITTED', 'VISITED', 'ATTENDED', 'CALLED']
        RETURN
            c.email AS contact_email,
            c.first_name + ' ' + c.last_name AS contact_name,
            type(r) AS engagement_type,
            labels(related)[0] AS related_entity_type,
            related.timestamp AS timestamp,
            related
        ORDER BY related.timestamp DESC
        """

    @staticmethod
    def find_owner_by_name(name_pattern: str) -> str:
        """Find owners matching a name pattern

        Args:
            name_pattern: Partial name to search for

        Returns:
            Cypher query string
        """
        return """
        MATCH (u:HUBSPOT_User)
        WHERE u.first_name CONTAINS $name_pattern
           OR u.last_name CONTAINS $name_pattern
           OR u.email CONTAINS $name_pattern
        RETURN
            u.hubspot_id AS user_id,
            u.email AS email,
            u.first_name AS first_name,
            u.last_name AS last_name,
            u.active AS active,
            u.teams AS teams
        """

    @staticmethod
    def contacts_companies_by_owner_combined(owner_name_pattern: str) -> str:
        """Get both contacts and companies for an owner in a combined view

        Args:
            owner_name_pattern: Name to match

        Returns:
            Cypher query string
        """
        return """
        MATCH (u:HUBSPOT_User)
        WHERE u.first_name CONTAINS $owner_name
           OR u.last_name CONTAINS $owner_name
        WITH u
        OPTIONAL MATCH (c:HUBSPOT_Contact)-[:OWNED_BY]->(u)
        OPTIONAL MATCH (co:HUBSPOT_Company)-[:OWNED_BY]->(u)
        RETURN
            'Contact' AS entity_type,
            c.email AS identifier,
            c.first_name + ' ' + c.last_name AS name,
            c.lifecycle_stage AS status,
            c.created_date AS created_date,
            u.first_name + ' ' + u.last_name AS owner_name,
            u.email AS owner_email
        WHERE c IS NOT NULL
        UNION
        RETURN
            'Company' AS entity_type,
            co.domain AS identifier,
            co.name AS name,
            co.industry AS status,
            co.created_date AS created_date,
            u.first_name + ' ' + u.last_name AS owner_name,
            u.email AS owner_email
        WHERE co IS NOT NULL
        ORDER BY created_date DESC
        """
