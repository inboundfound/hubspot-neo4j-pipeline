"""
Neo4j Reporter - Core reporting functionality for HubSpot data in Neo4j
"""

import os
import csv
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError
import logging

from config.settings import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
from reporting.queries import ReportQueries

logger = logging.getLogger(__name__)


class Neo4jReporter:
    """Handle Neo4j connections and report generation"""

    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        """Initialize Neo4j connection

        Args:
            uri: Neo4j connection URI (defaults to env var)
            username: Neo4j username (defaults to env var)
            password: Neo4j password (defaults to env var)
        """
        self.uri = uri or NEO4J_URI
        self.username = username or NEO4J_USERNAME
        self.password = password or NEO4J_PASSWORD

        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info(f"Connected to Neo4j at {self.uri}")
        except (ServiceUnavailable, AuthError) as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self):
        """Close the Neo4j driver connection"""
        if self.driver:
            self.driver.close()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

    def execute_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a Cypher query and return results

        Args:
            query: Cypher query string
            parameters: Query parameters

        Returns:
            List of result records as dictionaries
        """
        parameters = parameters or {}

        with self.driver.session() as session:
            result = session.run(query, parameters)
            records = [dict(record) for record in result]

        logger.info(f"Query returned {len(records)} records")
        return records

    # Owner-based reports
    def get_contacts_by_owner(self, owner_name: str) -> List[Dict[str, Any]]:
        """Get all contacts owned by a specific owner

        Args:
            owner_name: Owner's first or last name (partial match supported)

        Returns:
            List of contact records
        """
        query = ReportQueries.contacts_by_owner(owner_name)
        return self.execute_query(query, {'owner_name': owner_name})

    def get_companies_by_owner(self, owner_name: str) -> List[Dict[str, Any]]:
        """Get all companies owned by a specific owner

        Args:
            owner_name: Owner's first or last name (partial match supported)

        Returns:
            List of company records
        """
        query = ReportQueries.companies_by_owner(owner_name)
        return self.execute_query(query, {'owner_name': owner_name})

    def get_deals_by_owner(self, owner_name: str) -> List[Dict[str, Any]]:
        """Get all deals owned by a specific owner

        Args:
            owner_name: Owner's first or last name (partial match supported)

        Returns:
            List of deal records
        """
        query = ReportQueries.deals_by_owner(owner_name)
        return self.execute_query(query, {'owner_name': owner_name})

    def get_owner_summary(self, owner_name: str) -> List[Dict[str, Any]]:
        """Get summary statistics for an owner

        Args:
            owner_name: Owner's first or last name (partial match supported)

        Returns:
            Summary record with counts
        """
        query = ReportQueries.owner_summary(owner_name)
        return self.execute_query(query, {'owner_name': owner_name})

    def get_all_owners_summary(self) -> List[Dict[str, Any]]:
        """Get portfolio summary for all owners

        Returns:
            List of owner summaries
        """
        query = ReportQueries.all_owners_summary()
        return self.execute_query(query)

    def find_owner(self, name_pattern: str) -> List[Dict[str, Any]]:
        """Find owners matching a name pattern

        Args:
            name_pattern: Partial name or email to search for

        Returns:
            List of matching owners
        """
        query = ReportQueries.find_owner_by_name(name_pattern)
        return self.execute_query(query, {'name_pattern': name_pattern})

    # Activity-based reports
    def get_recent_form_submissions(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get recent form submissions

        Args:
            days: Number of days to look back

        Returns:
            List of form submission records
        """
        query = ReportQueries.recent_form_submissions(days)
        return self.execute_query(query, {'days': days})

    def get_recent_email_activity(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get recent email opens and clicks

        Args:
            days: Number of days to look back

        Returns:
            List of email activity records
        """
        query = ReportQueries.recent_email_activity(days)
        return self.execute_query(query, {'days': days})

    def get_contacts_with_recent_activity(self, owner_name: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get contacts owned by specific owner with recent activity

        Args:
            owner_name: Owner's first or last name
            days: Number of days to look back

        Returns:
            List of active contact records
        """
        query = ReportQueries.contacts_with_recent_activity(owner_name, days)
        return self.execute_query(query, {'owner_name': owner_name, 'days': days})

    # Aggregate reports
    def get_contacts_by_lifecycle_stage(self) -> List[Dict[str, Any]]:
        """Get contact counts by lifecycle stage

        Returns:
            List of lifecycle stage counts
        """
        query = ReportQueries.contacts_by_lifecycle_stage()
        return self.execute_query(query)

    def get_companies_by_industry(self) -> List[Dict[str, Any]]:
        """Get company counts by industry

        Returns:
            List of industry counts
        """
        query = ReportQueries.companies_by_industry()
        return self.execute_query(query)

    # Output formatters
    @staticmethod
    def to_csv(data: List[Dict[str, Any]], output_path: str, include_header: bool = True):
        """Write results to CSV file

        Args:
            data: List of record dictionaries
            output_path: Path to output CSV file
            include_header: Whether to include column headers
        """
        if not data:
            logger.warning("No data to write to CSV")
            return

        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # Get all unique keys across all records (handle varying fields)
        fieldnames = []
        for record in data:
            for key in record.keys():
                if key not in fieldnames:
                    fieldnames.append(key)

        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            if include_header:
                writer.writeheader()

            writer.writerows(data)

        logger.info(f"Wrote {len(data)} records to {output_path}")

    @staticmethod
    def to_json(data: List[Dict[str, Any]], output_path: str, indent: int = 2):
        """Write results to JSON file

        Args:
            data: List of record dictionaries
            output_path: Path to output JSON file
            indent: JSON indentation level
        """
        if not data:
            logger.warning("No data to write to JSON")
            return

        # Ensure output directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(data, jsonfile, indent=indent, default=str)

        logger.info(f"Wrote {len(data)} records to {output_path}")

    @staticmethod
    def to_table(data: List[Dict[str, Any]], max_width: int = 50) -> str:
        """Format results as a pretty text table

        Args:
            data: List of record dictionaries
            max_width: Maximum column width (truncate longer values)

        Returns:
            Formatted table string
        """
        if not data:
            return "No results found"

        try:
            from tabulate import tabulate

            # Truncate long values
            truncated_data = []
            for record in data:
                truncated = {}
                for key, value in record.items():
                    str_value = str(value) if value is not None else ''
                    if len(str_value) > max_width:
                        truncated[key] = str_value[:max_width-3] + '...'
                    else:
                        truncated[key] = str_value
                truncated_data.append(truncated)

            return tabulate(truncated_data, headers='keys', tablefmt='grid')

        except ImportError:
            # Fallback if tabulate not installed
            logger.warning("tabulate not installed, using simple format")
            return Neo4jReporter._simple_table_format(data, max_width)

    @staticmethod
    def _simple_table_format(data: List[Dict[str, Any]], max_width: int = 50) -> str:
        """Simple table format fallback (if tabulate not available)

        Args:
            data: List of record dictionaries
            max_width: Maximum column width

        Returns:
            Simple formatted table string
        """
        if not data:
            return "No results found"

        # Get all keys
        keys = list(data[0].keys())

        # Build header
        lines = []
        lines.append(" | ".join(keys))
        lines.append("-" * (len(keys) * (max_width + 3)))

        # Build rows
        for record in data:
            row_values = []
            for key in keys:
                value = str(record.get(key, '')) if record.get(key) is not None else ''
                if len(value) > max_width:
                    value = value[:max_width-3] + '...'
                row_values.append(value)
            lines.append(" | ".join(row_values))

        return "\n".join(lines)

    def print_table(self, data: List[Dict[str, Any]], max_width: int = 50):
        """Print results as a formatted table

        Args:
            data: List of record dictionaries
            max_width: Maximum column width
        """
        table = self.to_table(data, max_width)
        print(table)


# Convenience functions for quick reporting
def quick_report(
    owner_name: str,
    report_type: str = 'all',
    output_format: str = 'table',
    output_path: Optional[str] = None
):
    """Quick report generation helper

    Args:
        owner_name: Owner name to search for
        report_type: 'contacts', 'companies', 'deals', 'summary', or 'all'
        output_format: 'table', 'csv', or 'json'
        output_path: Path for CSV/JSON output (auto-generated if not provided)
    """
    with Neo4jReporter() as reporter:
        results = {}

        if report_type in ['contacts', 'all']:
            results['contacts'] = reporter.get_contacts_by_owner(owner_name)

        if report_type in ['companies', 'all']:
            results['companies'] = reporter.get_companies_by_owner(owner_name)

        if report_type in ['deals', 'all']:
            results['deals'] = reporter.get_deals_by_owner(owner_name)

        if report_type == 'summary':
            results['summary'] = reporter.get_owner_summary(owner_name)

        # Output handling
        if output_format == 'table':
            for result_type, data in results.items():
                print(f"\n{'=' * 80}")
                print(f"{result_type.upper()}")
                print('=' * 80)
                reporter.print_table(data)

        elif output_format == 'csv':
            for result_type, data in results.items():
                path = output_path or f"reports/{owner_name.replace(' ', '_')}_{result_type}.csv"
                reporter.to_csv(data, path)

        elif output_format == 'json':
            path = output_path or f"reports/{owner_name.replace(' ', '_')}_report.json"
            reporter.to_json(results, path)

        return results
