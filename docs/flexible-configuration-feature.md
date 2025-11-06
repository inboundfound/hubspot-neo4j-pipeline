# Flexible Configuration Feature - Design Document

## Context

This HubSpot-Neo4j pipeline is an open-source tool that serves different clients with varying HubSpot portal configurations, subscription tiers, and feature availability. Not all clients use all HubSpot features (sequences, predictive scoring, call recordings, etc.), so we need a flexible, configuration-driven approach to data extraction.

## Problem Statement

Current implementation has several limitations:
1. **Hard-coded data sources** - All extractors run regardless of client needs
2. **No feature detection** - Pipeline doesn't know what APIs are available in a given HubSpot portal
3. **Wasted API calls** - Attempts to extract data from unavailable features
4. **Rigid architecture** - Adding new data sources requires code changes
5. **Client-specific needs** - Different clients need different subsets of data

## User Requirements

From conversation:
> "i dont want to do all that. whats predictive scoring? sequences? pretty sure they dont use the rest.. its open source tool so it might make sense to 'check' what data is available and then conditionally load a diff data model? based on client needs? or have some kind of like json/yaml to say includes? idk"

Key requirements:
- **Conditional data loading** based on client needs
- **Configuration file** (JSON/YAML) to specify what to include
- **Auto-detection** of available features/APIs
- **Flexible architecture** for open-source multi-client use

## HubSpot Features Overview

### Predictive Lead Scoring
HubSpot's AI-powered feature that automatically scores contacts/companies based on their likelihood to convert into customers. It analyzes historical data (which deals closed, what behaviors they showed) and assigns scores to current leads.

**Requirements:** Enterprise tier only
**Use case:** Prioritizing outreach to high-probability leads

### Sequences
Automated email follow-up campaigns. Sales reps enroll contacts into sequences - a series of emails sent automatically over time with delays between them. Tracks opens, clicks, and replies.

**Requirements:** Sales Hub Professional+
**Use case:** Tracking which automated touchpoints leads receive, measuring sequence effectiveness

### Other Optional Features
- **Call Recordings & Transcripts** - Requires calling features enabled
- **Tickets** - Service Hub required
- **Products/Line Items** - E-commerce/sales configuration
- **Workflows** - Marketing/Sales automation execution history
- **Timeline Events** - Custom activity types
- **Tasks** - Follow-up reminders and assignments

## Proposed Architecture

### 1. Configuration File Structure

**File:** `config/data_sources.yaml`

```yaml
# HubSpot Data Pipeline Configuration
# Enable/disable data sources based on your HubSpot portal capabilities

data_sources:
  # Core CRM entities (always recommended)
  contacts:
    enabled: true
    include_owner: true
    properties:
      - firstname
      - lastname
      - email
      - phone
      - lifecyclestage
      - createdate
      - lastmodifieddate
      - hs_lead_status
      # Add custom properties as needed

  companies:
    enabled: true
    include_owner: true
    properties:
      - name
      - domain
      - industry
      - numberofemployees
      - city
      - state
      - country
      - createdate
      - hs_lastmodifieddate

  deals:
    enabled: true
    include_owner: true
    include_line_items: false  # Product/pricing details
    properties:
      - dealname
      - amount
      - dealstage
      - pipeline
      - closedate
      - createdate

  # Activity/Engagement data
  engagements:
    enabled: true
    types:
      - MEETING
      - CALL
      - NOTE
      - EMAIL
      - TASK  # Can be disabled if not used

  # Event data (for recency analysis)
  email_events:
    enabled: true
    event_types:
      - OPEN
      - CLICK
      - BOUNCE
      - DELIVERED
    # Optional: filter by date range
    # date_range:
    #   start: "2024-01-01"
    #   end: null  # null = current date

  form_submissions:
    enabled: true

  page_visits:
    enabled: false  # Requires Marketing Hub
    # track_anonymous: false

  # User/Owner data
  users:
    enabled: true
    link_to_persons: true  # Create SAME_AS relationships with existing Person nodes

  # Advanced features (optional, tier-dependent)
  sequences:
    enabled: false  # Sales Hub Professional+
    include_enrollment_data: true
    include_step_data: true
    # Extracts: which sequences exist, who's enrolled, what step they're on

  calls:
    enabled: false  # Requires calling features
    include_recordings: false
    include_transcripts: false
    # Note: Recordings/transcripts may have storage/privacy implications

  tickets:
    enabled: false  # Service Hub
    # include_ticket_threads: true

  products:
    enabled: false
    include_line_items: false  # Link products to deals

  predictive_scoring:
    enabled: false  # Enterprise tier only
    # Extracts: contact_score, company_score, deal_score

  workflows:
    enabled: false
    include_execution_history: false  # Can be high volume

  tasks:
    enabled: false
    include_completed: false  # Only extract open tasks

# Knowledge Graph Integration
integration:
  entity_matching:
    enabled: true
    match_strategies:
      - linkedin_url  # Primary matching strategy
      - email         # Fallback strategy
    # Strategy for HUBSPOT_User -> Person linking

  custom_labels:
    # Override default HUBSPOT_ prefix if needed
    # prefix: "HS_"
    pass

# Performance & Limits
extraction:
  batch_size: 100  # API requests per batch
  rate_limit_delay: 0.1  # Seconds between requests
  max_retries: 3

  # Optional: Date-based incremental extraction
  # incremental:
  #   enabled: false
  #   last_sync_file: "data/.last_sync"
  #   sync_from: "2024-01-01"

# Neo4j Loading
loading:
  clear_existing: false  # WARNING: Set to true to clear Neo4j before loading
  create_indexes: true
  create_constraints: true
```

### 2. Implementation Components

#### A. Config Loader Module

**File:** `utils/config_loader.py`

```python
import yaml
from pathlib import Path
from typing import Dict, Any

class ConfigLoader:
    """Load and validate configuration file"""

    def __init__(self, config_path: str = 'config/data_sources.yaml'):
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load YAML configuration file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)

        self._validate_config(config)
        return config

    def _validate_config(self, config: Dict[str, Any]):
        """Validate configuration structure"""
        required_sections = ['data_sources', 'integration', 'extraction', 'loading']
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required config section: {section}")

    def is_enabled(self, data_source: str) -> bool:
        """Check if a data source is enabled"""
        return self.config['data_sources'].get(data_source, {}).get('enabled', False)

    def get_data_source_config(self, data_source: str) -> Dict[str, Any]:
        """Get configuration for a specific data source"""
        return self.config['data_sources'].get(data_source, {})

    def get_integration_config(self) -> Dict[str, Any]:
        """Get integration configuration"""
        return self.config['integration']

    def get_extraction_config(self) -> Dict[str, Any]:
        """Get extraction configuration"""
        return self.config['extraction']
```

#### B. Capability Detector

**File:** `utils/capability_detector.py`

```python
from hubspot import HubSpot
from hubspot.crm.contacts import ApiException
import logging

logger = logging.getLogger(__name__)

class HubSpotCapabilityDetector:
    """Detect which APIs/features are available in the connected HubSpot portal"""

    def __init__(self, client: HubSpot):
        self.client = client

    def detect_available_features(self) -> Dict[str, bool]:
        """Test API endpoints to see what's available"""
        capabilities = {
            'contacts': self._test_contacts(),
            'companies': self._test_companies(),
            'deals': self._test_deals(),
            'engagements': self._test_engagements(),
            'users': self._test_users(),
            'email_events': self._test_email_events(),
            'form_submissions': self._test_form_submissions(),
            'sequences': self._test_sequences(),
            'calls': self._test_calls(),
            'tickets': self._test_tickets(),
            'products': self._test_products(),
        }

        return capabilities

    def _test_contacts(self) -> bool:
        """Test if contacts API is accessible"""
        try:
            self.client.crm.contacts.basic_api.get_page(limit=1)
            return True
        except ApiException as e:
            logger.warning(f"Contacts API not available: {e}")
            return False

    def _test_sequences(self) -> bool:
        """Test if sequences API is accessible (Sales Hub Pro+)"""
        try:
            # Attempt to access sequences endpoint
            # Note: This is a placeholder - actual endpoint may vary
            self.client.automation.actions.get_page(limit=1)
            return True
        except ApiException as e:
            if e.status == 403:  # Forbidden = feature not available
                logger.info("Sequences API not available (requires Sales Hub Pro+)")
                return False
            logger.warning(f"Sequences API error: {e}")
            return False

    def _test_email_events(self) -> bool:
        """Test if email events API is accessible"""
        try:
            # Test email events endpoint
            return True
        except ApiException as e:
            logger.warning(f"Email events API not available: {e}")
            return False

    # Similar methods for other features...

    def generate_suggested_config(self) -> Dict[str, Any]:
        """Generate a suggested configuration based on detected capabilities"""
        capabilities = self.detect_available_features()

        suggested_config = {
            'data_sources': {}
        }

        for feature, available in capabilities.items():
            suggested_config['data_sources'][feature] = {
                'enabled': available,
                'note': 'Auto-detected' if available else 'Not available in your portal'
            }

        return suggested_config

    def save_suggested_config(self, output_path: str = 'config/suggested_data_sources.yaml'):
        """Save suggested configuration to file"""
        suggested = self.generate_suggested_config()

        with open(output_path, 'w') as f:
            yaml.dump(suggested, f, default_flow_style=False)

        logger.info(f"Suggested configuration saved to: {output_path}")
```

#### C. Modified Pipeline Orchestrator

**File:** `main.py` (modified)

```python
import logging
from utils.config_loader import ConfigLoader
from utils.capability_detector import HubSpotCapabilityDetector

def run_pipeline(config_path: str = 'config/data_sources.yaml'):
    """Run the HubSpot to Neo4j pipeline with configuration"""

    # Load configuration
    config = ConfigLoader(config_path)
    logger.info(f"Loaded configuration from {config_path}")

    # Initialize HubSpot client
    client = HubSpot(access_token=os.getenv('HUBSPOT_ACCESS_TOKEN'))

    # Step 1: Extract data (only enabled sources)
    logger.info("==================================================")
    logger.info("STEP 1: EXTRACTING DATA FROM HUBSPOT")
    logger.info("==================================================")

    extracted_data = {}

    # Contacts
    if config.is_enabled('contacts'):
        logger.info("📋 Extracting Contacts...")
        contacts_config = config.get_data_source_config('contacts')
        extractor = ContactsExtractor(client)
        extracted_data['contacts'] = extractor.extract_all()
    else:
        logger.info("⏭️  Skipping Contacts (disabled in config)")

    # Companies
    if config.is_enabled('companies'):
        logger.info("🏢 Extracting Companies...")
        extracted_data['companies'] = CompaniesExtractor(client).extract_all()
    else:
        logger.info("⏭️  Skipping Companies (disabled in config)")

    # Deals
    if config.is_enabled('deals'):
        logger.info("💰 Extracting Deals...")
        extracted_data['deals'] = DealsExtractor(client).extract_all()
    else:
        logger.info("⏭️  Skipping Deals (disabled in config)")

    # Users/Owners
    if config.is_enabled('users'):
        logger.info("👤 Extracting Users/Owners...")
        extracted_data['users'] = UsersExtractor(client).extract_all()
    else:
        logger.info("⏭️  Skipping Users (disabled in config)")

    # Form Submissions
    if config.is_enabled('form_submissions'):
        logger.info("📝 Extracting Form Submissions...")
        extracted_data['form_submissions'] = FormSubmissionsExtractor(client).extract_all()
    else:
        logger.info("⏭️  Skipping Form Submissions (disabled in config)")

    # Email Events
    if config.is_enabled('email_events'):
        logger.info("📧 Extracting Email Events...")
        email_config = config.get_data_source_config('email_events')
        event_types = email_config.get('event_types', ['OPEN', 'CLICK'])
        extracted_data['email_events'] = EmailEventsExtractor(client).extract_all(event_types)
    else:
        logger.info("⏭️  Skipping Email Events (disabled in config)")

    # Sequences (optional - tier dependent)
    if config.is_enabled('sequences'):
        logger.info("🔄 Extracting Sequences...")
        try:
            extracted_data['sequences'] = SequencesExtractor(client).extract_all()
        except Exception as e:
            logger.warning(f"Failed to extract sequences: {e}")
            logger.warning("This feature may not be available in your HubSpot tier")
    else:
        logger.info("⏭️  Skipping Sequences (disabled in config)")

    # Calls (optional)
    if config.is_enabled('calls'):
        logger.info("📞 Extracting Calls...")
        calls_config = config.get_data_source_config('calls')
        extracted_data['calls'] = CallsExtractor(client).extract_all(
            include_recordings=calls_config.get('include_recordings', False),
            include_transcripts=calls_config.get('include_transcripts', False)
        )
    else:
        logger.info("⏭️  Skipping Calls (disabled in config)")

    # Step 2: Transform to graph format
    logger.info("==================================================")
    logger.info("STEP 2: TRANSFORMING TO GRAPH FORMAT")
    logger.info("==================================================")

    transformer = GraphTransformer()
    nodes, relationships = transformer.transform_all(extracted_data, config)

    # Step 3: Load into Neo4j
    logger.info("==================================================")
    logger.info("STEP 3: LOADING INTO NEO4J")
    logger.info("==================================================")

    loading_config = config.config['loading']
    loader = Neo4jLoader(
        uri=os.getenv('NEO4J_URI'),
        username=os.getenv('NEO4J_USERNAME'),
        password=os.getenv('NEO4J_PASSWORD')
    )

    loader.load_all(
        nodes=nodes,
        relationships=relationships,
        clear_existing=loading_config.get('clear_existing', False),
        create_indexes=loading_config.get('create_indexes', True)
    )

    # Step 4: Entity matching (if enabled)
    integration_config = config.get_integration_config()
    if integration_config.get('entity_matching', {}).get('enabled', False):
        logger.info("==================================================")
        logger.info("STEP 4: ENTITY MATCHING")
        logger.info("==================================================")

        matcher = EntityMatcher(loader.driver)
        strategies = integration_config['entity_matching'].get('match_strategies', ['linkedin_url', 'email'])
        matcher.link_users_to_persons(strategies=strategies)

    logger.info("✅ Pipeline completed successfully!")

def detect_capabilities():
    """Detect available HubSpot features and generate suggested config"""
    client = HubSpot(access_token=os.getenv('HUBSPOT_ACCESS_TOKEN'))
    detector = HubSpotCapabilityDetector(client)

    logger.info("🔍 Detecting available HubSpot features...")
    capabilities = detector.detect_available_features()

    logger.info("\nAvailable features:")
    for feature, available in capabilities.items():
        status = "✅" if available else "❌"
        logger.info(f"  {status} {feature}")

    detector.save_suggested_config()
    logger.info("\n💡 Suggested configuration saved to config/suggested_data_sources.yaml")
    logger.info("   Review and copy to config/data_sources.yaml to use")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='HubSpot to Neo4j Pipeline')
    parser.add_argument('--detect', action='store_true', help='Detect available features and generate config')
    parser.add_argument('--config', default='config/data_sources.yaml', help='Path to configuration file')

    args = parser.parse_args()

    if args.detect:
        detect_capabilities()
    else:
        run_pipeline(config_path=args.config)
```

### 3. Usage Workflows

#### Workflow A: First-Time Setup with Auto-Detection

```bash
# 1. Detect available features in your HubSpot portal
python3 main.py --detect

# 2. Review suggested configuration
cat config/suggested_data_sources.yaml

# 3. Copy and customize
cp config/suggested_data_sources.yaml config/data_sources.yaml
nano config/data_sources.yaml  # Edit as needed

# 4. Run pipeline with your config
python3 main.py
```

#### Workflow B: Manual Configuration

```bash
# 1. Copy example configuration
cp config/data_sources.example.yaml config/data_sources.yaml

# 2. Edit to enable/disable features
nano config/data_sources.yaml

# 3. Run pipeline
python3 main.py
```

#### Workflow C: Multiple Configurations

```bash
# Different configs for different environments/clients
python3 main.py --config config/client_a.yaml
python3 main.py --config config/client_b_minimal.yaml
python3 main.py --config config/full_enterprise.yaml
```

### 4. Benefits

1. **Client Flexibility**: Each client/environment can have different configurations
2. **Graceful Degradation**: Missing features don't break the pipeline
3. **Performance Optimization**: Don't waste API calls on unavailable/unwanted features
4. **Maintainability**: Adding new features is config updates, not code changes
5. **Documentation**: Config file serves as self-documenting feature list
6. **Testing**: Easy to test subsets of functionality
7. **Open Source Friendly**: Users can share configs, not code changes
8. **Tier Awareness**: Automatically detects and suggests based on HubSpot subscription

### 5. Migration Path

For existing users:

1. **Default behavior**: If no config file exists, run with all core features enabled (backward compatible)
2. **Migration script**: Auto-generate config from current code behavior
3. **Documentation**: Clear upgrade guide in README

```python
# Backward compatibility in main.py
def run_pipeline(config_path: str = 'config/data_sources.yaml'):
    if not Path(config_path).exists():
        logger.warning("No config file found, using default configuration")
        logger.warning("Run 'python3 main.py --detect' to generate a configuration")
        config = ConfigLoader.get_default_config()
    else:
        config = ConfigLoader(config_path)
```

### 6. Future Enhancements

1. **Incremental Sync**: Track last extraction timestamp, only pull new/updated records
2. **Webhook Integration**: Real-time updates instead of batch extraction
3. **Data Validation**: Schema validation for extracted data
4. **Monitoring Dashboard**: Track extraction statistics, API usage
5. **Config Presets**: Pre-built configs for common use cases (sales-focused, marketing-focused, etc.)
6. **Environment Variables**: Override config with env vars for CI/CD

### 7. Example Configurations

#### Minimal Configuration (Sales Focus)

```yaml
data_sources:
  contacts:
    enabled: true
    include_owner: true

  companies:
    enabled: true
    include_owner: true

  deals:
    enabled: true
    include_owner: true

  users:
    enabled: true
    link_to_persons: true

  engagements:
    enabled: true
    types:
      - MEETING
      - CALL

  # Everything else disabled
  email_events:
    enabled: false
  form_submissions:
    enabled: false
  sequences:
    enabled: false
```

#### Enterprise Configuration (Everything Enabled)

```yaml
data_sources:
  contacts:
    enabled: true
    include_owner: true

  companies:
    enabled: true
    include_owner: true

  deals:
    enabled: true
    include_owner: true
    include_line_items: true

  engagements:
    enabled: true
    types:
      - MEETING
      - CALL
      - NOTE
      - EMAIL
      - TASK

  email_events:
    enabled: true
    event_types:
      - OPEN
      - CLICK
      - BOUNCE
      - DELIVERED

  form_submissions:
    enabled: true

  users:
    enabled: true
    link_to_persons: true

  sequences:
    enabled: true
    include_enrollment_data: true

  calls:
    enabled: true
    include_recordings: true
    include_transcripts: true

  predictive_scoring:
    enabled: true

  products:
    enabled: true
    include_line_items: true
```

#### Marketing Hub Configuration

```yaml
data_sources:
  contacts:
    enabled: true
    include_owner: false

  companies:
    enabled: true
    include_owner: false

  deals:
    enabled: false

  email_events:
    enabled: true
    event_types:
      - OPEN
      - CLICK

  form_submissions:
    enabled: true

  page_visits:
    enabled: true

  workflows:
    enabled: true
    include_execution_history: true

  users:
    enabled: false
```

## Implementation Priority

1. **Phase 1** (Core): Config loader, basic enable/disable logic
2. **Phase 2** (Detection): Capability detector, auto-generate configs
3. **Phase 3** (Advanced): Incremental sync, property-level customization
4. **Phase 4** (Polish): Config validation, error messages, documentation

## Glossary

- **HubSpot Tier**: Subscription level (Free, Starter, Professional, Enterprise)
- **Hub**: Product category (Marketing Hub, Sales Hub, Service Hub, CMS Hub)
- **Scope**: OAuth permission required to access specific APIs
- **Portal**: A HubSpot account/instance
- **Association**: Relationship between CRM objects (contact-to-company, deal-to-contact)
- **Engagement**: Activity record (meeting, call, email, note, task)
- **Sequence**: Automated email campaign with multiple steps
- **Workflow**: Marketing/sales automation (if-this-then-that logic)

## References

- [HubSpot API Documentation](https://developers.hubspot.com/docs/api/overview)
- [OAuth Scopes](https://developers.hubspot.com/docs/api/oauth/scopes)
- [Rate Limits](https://developers.hubspot.com/docs/api/usage-details)
- [Current Pipeline Architecture](../README.md)
