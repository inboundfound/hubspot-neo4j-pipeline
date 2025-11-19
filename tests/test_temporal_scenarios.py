#!/usr/bin/env python3
"""
Safe temporal tracking test that loads datasets directly without overwriting data/raw/
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from neo4j import GraphDatabase

from config.settings import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
from transformers.graph_transformer import GraphTransformer
from loaders.temporal_loader import TemporalLoader
from utils.logger import setup_logger

def clear_database():
    """Clear Neo4j database"""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    with driver.session() as session:
        session.run('MATCH (n) DETACH DELETE n')
    driver.close()
    print('✅ Database cleared\n')

def load_dataset(dataset_path: Path, run_name: str):
    """Load a dataset and return summary"""
    logger = setup_logger(f'TestRun-{run_name}')
    
    print(f"{'='*70}")
    print(f"  Loading: {dataset_path.name}")
    print(f"{'='*70}\n")
    
    # Read all data files
    all_data = {}
    
    files_to_load = [
        'contacts.json',
        'companies.json', 
        'deals.json',
        'engagements.json',
        'email_events.json',
        'users.json',
        'form_submissions.json'
    ]
    
    for filename in files_to_load:
        file_path = dataset_path / filename
        if file_path.exists():
            with open(file_path, 'r') as f:
                data_key = filename.replace('.json', '')
                all_data[data_key] = json.load(f)
                logger.info(f"Loaded {len(all_data[data_key])} {data_key}")
        else:
            logger.warning(f"File not found: {filename}")
            all_data[filename.replace('.json', '')] = []
    
    # Transform data
    print("\n📊 Transforming data...")
    transformer = GraphTransformer()
    nodes, relationships = transformer.transform_all(all_data)
    
    # Load into Neo4j with temporal tracking
    print("💾 Loading into Neo4j with temporal tracking...")
    loader = TemporalLoader()
    loader.load_with_history(nodes, relationships)
    
    # Get verification counts
    counts = loader.verify_load()
    
    print("\n✅ Load complete!")
    print(f"\nSummary:")
    print(f"  Nodes: {sum(counts.get(k, 0) for k in counts if not k.endswith('_HISTORY') and k not in ['relationships', 'relationship_changes', 'deleted_nodes'])}")
    print(f"  Relationships: {counts.get('relationships', 0)}")
    print(f"  Relationship changes tracked: {counts.get('relationship_changes', 0)}")
    print(f"  Deleted nodes: {counts.get('deleted_nodes', 0)}")
    
    history_total = sum(counts.get(f'{et}_HISTORY', 0) for et in 
                       ['HUBSPOT_Contact', 'HUBSPOT_Company', 'HUBSPOT_Deal', 
                        'HUBSPOT_Activity', 'HUBSPOT_User'])
    if history_total > 0:
        print(f"  Historical versions: {history_total}")
    
    loader.close()
    
    return counts

def run_query_temporal(output_file: str):
    """Run query_temporal.py and save output"""
    print(f"\n📊 Running temporal queries...")
    
    import subprocess
    result = subprocess.run(
        ['python3', 'query_temporal.py'],
        capture_output=True,
        text=True
    )
    
    # Save output
    with open(output_file, 'w') as f:
        f.write(result.stdout)
        if result.stderr:
            f.write("\n\n=== STDERR ===\n")
            f.write(result.stderr)
    
    print(f"✅ Temporal report saved: {output_file}\n")
    
    return result.stdout

def print_change_summary(baseline_counts, modified_counts):
    """Print summary of detected changes"""
    print("\n" + "="*70)
    print("  CHANGE DETECTION SUMMARY")
    print("="*70 + "\n")
    
    entity_types = ['HUBSPOT_Contact', 'HUBSPOT_Company', 'HUBSPOT_Deal', 
                   'HUBSPOT_Activity', 'HUBSPOT_User', 'HUBSPOT_EmailCampaign',
                   'HUBSPOT_WebPage', 'HUBSPOT_EmailOpenEvent', 'HUBSPOT_EmailClickEvent',
                   'HUBSPOT_FormSubmission']
    
    print("Node Changes:")
    print("-" * 40)
    changes_detected = False
    for entity_type in entity_types:
        baseline = baseline_counts.get(entity_type, 0)
        modified = modified_counts.get(entity_type, 0)
        if baseline != modified:
            print(f"  {entity_type}: {baseline} → {modified} (Δ {modified - baseline:+d})")
            changes_detected = True
    
    if not changes_detected:
        print("  No node count changes detected")
    
    print("\nHistory Created:")
    print("-" * 40)
    history_types = ['HUBSPOT_Contact_HISTORY', 'HUBSPOT_Company_HISTORY', 
                    'HUBSPOT_Deal_HISTORY', 'HUBSPOT_Activity_HISTORY', 'HUBSPOT_User_HISTORY']
    history_detected = False
    for history_type in history_types:
        count = modified_counts.get(history_type, 0)
        if count > 0:
            print(f"  {history_type}: {count}")
            history_detected = True
    
    if not history_detected:
        print("  No history nodes created")
    
    print("\nRelationship Changes:")
    print("-" * 40)
    baseline_rels = baseline_counts.get('relationship_changes', 0)
    modified_rels = modified_counts.get('relationship_changes', 0)
    new_changes = modified_rels - baseline_rels
    
    print(f"  Baseline: {baseline_rels} changes tracked")
    print(f"  Modified: {modified_rels} changes tracked")
    print(f"  New changes detected: {new_changes}")
    
    print("\nDeleted Nodes:")
    print("-" * 40)
    deleted = modified_counts.get('deleted_nodes', 0)
    print(f"  Total deleted: {deleted}")
    
    print("\n" + "="*70 + "\n")

def main():
    """Main test execution"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    print("\n" + "╔" + "="*70 + "╗")
    print("║" + "  TEMPORAL TRACKING TEST - Safe Dataset Loading".center(70) + "║")
    print("╚" + "="*70 + "╝\n")
    
    print("📁 Test datasets:")
    print("   1. data/dataset1/ (baseline)")
    print("   2. data/dataset1_modified/ (with 8 changes)")
    print()
    
    # Verify datasets exist
    dataset1_path = Path('data/dataset1')
    dataset1_modified_path = Path('data/dataset1_modified')
    
    if not dataset1_path.exists():
        print("❌ Error: data/dataset1/ not found")
        sys.exit(1)
    
    if not dataset1_modified_path.exists():
        print("❌ Error: data/dataset1_modified/ not found")
        sys.exit(1)
    
    print("✅ Both datasets found\n")
    
    # Step 1: Clear database
    print("🗑️  Clearing Neo4j database...")
    clear_database()
    
    # Step 2: Load baseline dataset
    print("="*70)
    print("  STEP 1: Load Dataset 1 (Baseline)")
    print("="*70 + "\n")
    
    baseline_counts = load_dataset(dataset1_path, 'baseline')
    
    # Step 3: Query baseline state
    baseline_report = run_query_temporal(f'test_baseline_{timestamp}.txt')
    
    print("\n" + "⏸️  " + "Baseline loaded. Press Enter to load modified dataset...")
    input()
    
    # Step 4: Load modified dataset
    print("\n" + "="*70)
    print("  STEP 2: Load Dataset 1 Modified (With Changes)")
    print("="*70 + "\n")
    
    modified_counts = load_dataset(dataset1_modified_path, 'modified')
    
    # Step 5: Query modified state
    modified_report = run_query_temporal(f'test_modified_{timestamp}.txt')
    
    # Step 6: Print change summary
    print_change_summary(baseline_counts, modified_counts)
    
    # Print expected scenarios
    print("📋 Expected Changes (8 scenarios):")
    print("-" * 40)
    scenarios = [
        "1. ✓ User 11 deactivated (active → archived)",
        "2. ✓ Contact 35 ownership transferred",
        "3. ✓ Contact 62 name changed",
        "4. ✓ Deal 18153848732 stage changed to 'closedwon'",
        "5. ✓ New contact 99999999 added",
        "6. ✓ Contact 438914 deleted (soft delete)",
        "7. ✓ Deal 18153848732 associated with contact 99999999",
        "8. ✓ Company 144665164 ownership transferred"
    ]
    for scenario in scenarios:
        print(f"  {scenario}")
    
    print("\n" + "="*70)
    print("  TEST COMPLETE")
    print("="*70 + "\n")
    
    print("📁 Test artifacts created:")
    print(f"   - test_baseline_{timestamp}.txt (baseline temporal state)")
    print(f"   - test_modified_{timestamp}.txt (modified temporal state)")
    print()
    print("🔍 To compare reports:")
    print(f"   diff test_baseline_{timestamp}.txt test_modified_{timestamp}.txt")
    print()
    print("✅ Production data/raw/ was never touched!")
    print()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

