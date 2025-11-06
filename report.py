#!/usr/bin/env python3
"""
HubSpot Neo4j Reporter - CLI Tool

Generate reports from HubSpot data stored in Neo4j.

Examples:
    # Get all contacts and companies owned by Lynne
    python3 report.py --owner "Lynne" --output table

    # Export to CSV
    python3 report.py --owner "Lynn" --type contacts --output csv

    # Get summary statistics
    python3 report.py --owner "Bartos" --type summary

    # List all owners with their portfolios
    python3 report.py --all-owners

    # Find an owner by partial name
    python3 report.py --find-owner "Lyn"
"""

import argparse
import sys
import logging
from pathlib import Path

from reporting import Neo4jReporter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_owner_interactive(reporter: Neo4jReporter, search_term: str) -> str:
    """Interactive owner search if multiple matches found

    Args:
        reporter: Neo4jReporter instance
        search_term: Initial search term

    Returns:
        Selected owner name or original search term
    """
    matches = reporter.find_owner(search_term)

    if not matches:
        logger.warning(f"No owners found matching '{search_term}'")
        return search_term

    if len(matches) == 1:
        owner = matches[0]
        full_name = f"{owner['first_name']} {owner['last_name']}"
        logger.info(f"Found owner: {full_name} ({owner['email']})")
        return full_name

    # Multiple matches - show options
    print(f"\nFound {len(matches)} owners matching '{search_term}':\n")
    for i, owner in enumerate(matches, 1):
        active_status = "Active" if owner['active'] else "Inactive"
        print(f"{i}. {owner['first_name']} {owner['last_name']} ({owner['email']}) - {active_status}")

    print(f"\n0. Use original search term '{search_term}'")

    while True:
        try:
            choice = input("\nSelect owner number (or 0 for original): ").strip()
            choice_num = int(choice)

            if choice_num == 0:
                return search_term
            elif 1 <= choice_num <= len(matches):
                owner = matches[choice_num - 1]
                full_name = f"{owner['first_name']} {owner['last_name']}"
                logger.info(f"Selected: {full_name}")
                return full_name
            else:
                print(f"Please enter a number between 0 and {len(matches)}")
        except ValueError:
            print("Please enter a valid number")
        except KeyboardInterrupt:
            print("\nCancelled")
            sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description='Generate reports from HubSpot data in Neo4j',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --owner "Lynne" --output table
  %(prog)s --owner "Lynn Bartos" --type contacts --output csv
  %(prog)s --owner "Bartos" --type summary
  %(prog)s --all-owners
  %(prog)s --find-owner "Lyn"
        """
    )

    # Owner-based reports
    parser.add_argument(
        '--owner',
        type=str,
        help='Owner name to search for (first or last name, partial match supported)'
    )

    parser.add_argument(
        '--type',
        choices=['contacts', 'companies', 'deals', 'summary', 'all'],
        default='all',
        help='Type of report to generate (default: all)'
    )

    # All owners summary
    parser.add_argument(
        '--all-owners',
        action='store_true',
        help='Show summary of all owners and their portfolios'
    )

    # Find owner
    parser.add_argument(
        '--find-owner',
        type=str,
        metavar='NAME',
        help='Search for owners by name or email'
    )

    # Activity reports
    parser.add_argument(
        '--recent-activity',
        action='store_true',
        help='Show contacts with recent activity for the specified owner'
    )

    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days to look back for activity reports (default: 30)'
    )

    # Aggregate reports
    parser.add_argument(
        '--lifecycle-stages',
        action='store_true',
        help='Show contact counts by lifecycle stage'
    )

    parser.add_argument(
        '--industries',
        action='store_true',
        help='Show company counts by industry'
    )

    # Output options
    parser.add_argument(
        '--output',
        choices=['table', 'csv', 'json'],
        default='table',
        help='Output format (default: table)'
    )

    parser.add_argument(
        '--output-file',
        type=str,
        help='Output file path (auto-generated if not specified for csv/json)'
    )

    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Interactive owner selection if multiple matches found'
    )

    args = parser.parse_args()

    # Validate arguments
    if not any([args.owner, args.all_owners, args.find_owner, args.lifecycle_stages, args.industries]):
        parser.error("Must specify --owner, --all-owners, --find-owner, --lifecycle-stages, or --industries")

    try:
        with Neo4jReporter() as reporter:

            # Find owner command
            if args.find_owner:
                matches = reporter.find_owner(args.find_owner)
                if not matches:
                    print(f"No owners found matching '{args.find_owner}'")
                    return

                print(f"\nFound {len(matches)} owner(s):\n")
                reporter.print_table(matches)
                return

            # All owners summary
            if args.all_owners:
                print("\nAll Owners Summary\n")
                results = reporter.get_all_owners_summary()
                reporter.print_table(results)
                return

            # Lifecycle stages
            if args.lifecycle_stages:
                print("\nContacts by Lifecycle Stage\n")
                results = reporter.get_contacts_by_lifecycle_stage()
                reporter.print_table(results)
                return

            # Industries
            if args.industries:
                print("\nCompanies by Industry\n")
                results = reporter.get_companies_by_industry()
                reporter.print_table(results)
                return

            # Owner-based reports
            if args.owner:
                # Interactive owner selection if requested
                owner_name = args.owner
                if args.interactive:
                    owner_name = find_owner_interactive(reporter, args.owner)

                # Recent activity report
                if args.recent_activity:
                    print(f"\nContacts with Recent Activity (last {args.days} days) - Owner: {owner_name}\n")
                    results = reporter.get_contacts_with_recent_activity(owner_name, args.days)

                    if args.output == 'table':
                        reporter.print_table(results)
                    elif args.output == 'csv':
                        path = args.output_file or f"reports/{owner_name.replace(' ', '_')}_recent_activity.csv"
                        reporter.to_csv(results, path)
                        print(f"Report saved to: {path}")
                    elif args.output == 'json':
                        path = args.output_file or f"reports/{owner_name.replace(' ', '_')}_recent_activity.json"
                        reporter.to_json(results, path)
                        print(f"Report saved to: {path}")
                    return

                # Standard owner reports
                results = {}

                if args.type in ['contacts', 'all']:
                    results['contacts'] = reporter.get_contacts_by_owner(owner_name)
                    logger.info(f"Found {len(results['contacts'])} contacts")

                if args.type in ['companies', 'all']:
                    results['companies'] = reporter.get_companies_by_owner(owner_name)
                    logger.info(f"Found {len(results['companies'])} companies")

                if args.type in ['deals', 'all']:
                    results['deals'] = reporter.get_deals_by_owner(owner_name)
                    logger.info(f"Found {len(results['deals'])} deals")

                if args.type == 'summary':
                    results['summary'] = reporter.get_owner_summary(owner_name)

                # Output results
                if args.output == 'table':
                    for result_type, data in results.items():
                        print(f"\n{'=' * 80}")
                        print(f"{result_type.upper()} - Owner: {owner_name}")
                        print('=' * 80)
                        if data:
                            reporter.print_table(data)
                        else:
                            print("No results found")

                elif args.output == 'csv':
                    for result_type, data in results.items():
                        path = args.output_file or f"reports/{owner_name.replace(' ', '_')}_{result_type}.csv"
                        if data:
                            reporter.to_csv(data, path)
                            print(f"{result_type.capitalize()} report saved to: {path}")
                        else:
                            logger.warning(f"No {result_type} data to export")

                elif args.output == 'json':
                    path = args.output_file or f"reports/{owner_name.replace(' ', '_')}_report.json"
                    reporter.to_json(results, path)
                    print(f"Report saved to: {path}")

    except Exception as e:
        logger.error(f"Error generating report: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
