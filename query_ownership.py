#!/usr/bin/env python3
"""
Easy ownership queries for Neo4j
Query who owns what contacts, companies, and deals
"""

from neo4j import GraphDatabase
from config.settings import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
import pandas as pd


class OwnershipQueries:
    """Simple ownership queries for Neo4j"""
    
    def __init__(self):
        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )
    
    def close(self):
        self.driver.close()
    
    def get_contact_owner(self, email: str):
        """Get owner of a specific contact by email"""
        query = """
        MATCH (c:HUBSPOT_Contact {email: $email})-[:OWNED_BY]->(u:HUBSPOT_User)
        RETURN c.first_name,
               c.last_name,
               c.email,
               u.email as owner_email,
               u.first_name as owner_first_name,
               u.last_name as owner_last_name
        """
        with self.driver.session() as session:
            result = session.run(query, email=email)
            return [dict(record) for record in result]
    
    def get_company_owner(self, company_name: str):
        """Get owner of a specific company by name"""
        query = """
        MATCH (comp:HUBSPOT_Company)-[:OWNED_BY]->(u:HUBSPOT_User)
        WHERE comp.name CONTAINS $company_name
        RETURN comp.name,
               comp.domain,
               u.email as owner_email,
               u.first_name as owner_first_name,
               u.last_name as owner_last_name
        """
        with self.driver.session() as session:
            result = session.run(query, company_name=company_name)
            return [dict(record) for record in result]
    
    def get_deal_owner(self, deal_name: str):
        """Get owner of a specific deal by name"""
        query = """
        MATCH (d:HUBSPOT_Deal)-[:OWNED_BY]->(u:HUBSPOT_User)
        WHERE d.name CONTAINS $deal_name
        RETURN d.name,
               d.amount,
               d.dealstage,
               u.email as owner_email,
               u.first_name as owner_first_name,
               u.last_name as owner_last_name
        """
        with self.driver.session() as session:
            result = session.run(query, deal_name=deal_name)
            return [dict(record) for record in result]
    
    def get_user_ownership(self, user_email: str):
        """Get everything a user owns"""
        query = """
        MATCH (u:HUBSPOT_User {email: $email})
        OPTIONAL MATCH (u)<-[:OWNED_BY]-(c:HUBSPOT_Contact)
        OPTIONAL MATCH (u)<-[:OWNED_BY]-(comp:HUBSPOT_Company)
        OPTIONAL MATCH (u)<-[:OWNED_BY]-(d:HUBSPOT_Deal)
        RETURN u.first_name + ' ' + u.last_name as owner,
               u.email,
               collect(DISTINCT c.email) as contacts,
               collect(DISTINCT comp.name) as companies,
               collect(DISTINCT d.name) as deals,
               count(DISTINCT c) as contact_count,
               count(DISTINCT comp) as company_count,
               count(DISTINCT d) as deal_count,
               sum(d.amount) as total_deal_value
        """
        with self.driver.session() as session:
            result = session.run(query, email=user_email)
            return [dict(record) for record in result]
    
    def get_all_ownerships(self):
        """Get ownership summary for all users"""
        query = """
        MATCH (u:HUBSPOT_User)
        OPTIONAL MATCH (u)<-[:OWNED_BY]-(c:HUBSPOT_Contact)
        OPTIONAL MATCH (u)<-[:OWNED_BY]-(comp:HUBSPOT_Company)
        OPTIONAL MATCH (u)<-[:OWNED_BY]-(d:HUBSPOT_Deal)
        RETURN u.first_name + ' ' + u.last_name as owner,
               u.email,
               count(DISTINCT c) as contacts,
               count(DISTINCT comp) as companies,
               count(DISTINCT d) as deals,
               sum(d.amount) as total_pipeline_value
        ORDER BY total_pipeline_value DESC
        """
        with self.driver.session() as session:
            result = session.run(query)
            return [dict(record) for record in result]
    
    def get_contacts_with_owners(self, limit: int = 100):
        """Get all contacts with their owners"""
        query = """
        MATCH (c:HUBSPOT_Contact)-[:OWNED_BY]->(u:HUBSPOT_User)
        RETURN c.first_name + ' ' + c.last_name as contact_name,
               c.email,
               c.company,
               u.first_name + ' ' + u.last_name as owner
        LIMIT $limit
        """
        with self.driver.session() as session:
            result = session.run(query, limit=limit)
            return [dict(record) for record in result]
    
    def get_companies_with_owners(self, limit: int = 100):
        """Get all companies with their owners"""
        query = """
        MATCH (comp:HUBSPOT_Company)-[:OWNED_BY]->(u:HUBSPOT_User)
        RETURN comp.name,
               comp.domain,
               comp.industry,
               u.first_name + ' ' + u.last_name as owner
        LIMIT $limit
        """
        with self.driver.session() as session:
            result = session.run(query, limit=limit)
            return [dict(record) for record in result]
    
    def get_deals_with_owners(self, limit: int = 100):
        """Get all deals with their owners"""
        query = """
        MATCH (d:HUBSPOT_Deal)-[:OWNED_BY]->(u:HUBSPOT_User)
        RETURN d.name,
               d.amount,
               d.dealstage,
               d.closedate,
               u.first_name + ' ' + u.last_name as owner
        ORDER BY d.amount DESC
        LIMIT $limit
        """
        with self.driver.session() as session:
            result = session.run(query, limit=limit)
            return [dict(record) for record in result]


def main():
    """Example usage"""
    print("=" * 60)
    print("OWNERSHIP QUERIES - NEO4J")
    print("=" * 60)
    print()
    
    queries = OwnershipQueries()
    
    try:
        # 1. Get all ownership summary
        print("📊 OWNERSHIP SUMMARY")
        print("-" * 60)
        ownership = queries.get_all_ownerships()
        df = pd.DataFrame(ownership)
        print(df.to_string(index=False))
        print()
        
        # 2. Get contacts with owners (sample)
        print("📋 CONTACTS WITH OWNERS (First 10)")
        print("-" * 60)
        contacts = queries.get_contacts_with_owners(limit=10)
        df = pd.DataFrame(contacts)
        if not df.empty:
            print(df.to_string(index=False))
        else:
            print("No contacts with owners found")
        print()
        
        # 3. Get companies with owners (sample)
        print("🏢 COMPANIES WITH OWNERS (First 10)")
        print("-" * 60)
        companies = queries.get_companies_with_owners(limit=10)
        df = pd.DataFrame(companies)
        if not df.empty:
            print(df.to_string(index=False))
        else:
            print("No companies with owners found")
        print()
        
        # 4. Get deals with owners (sample)
        print("💰 DEALS WITH OWNERS (Top 10 by Value)")
        print("-" * 60)
        deals = queries.get_deals_with_owners(limit=10)
        df = pd.DataFrame(deals)
        if not df.empty:
            print(df.to_string(index=False))
        else:
            print("No deals with owners found")
        print()
        
    finally:
        queries.close()
    
    print()
    print("=" * 60)
    print("TIP: Use these functions in your own scripts!")
    print("=" * 60)
    print()
    print("Example:")
    print("  queries = OwnershipQueries()")
    print("  owner_data = queries.get_contact_owner('john@example.com')")
    print("  queries.close()")


if __name__ == "__main__":
    main()

