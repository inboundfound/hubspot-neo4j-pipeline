import os
from dotenv import load_dotenv
from pathlib import Path

# Always load the pipeline-local .env first (this file is in hubspot-neo4j-pipeline/config)
_PIPELINE_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=_PIPELINE_ROOT / '.env')

# Then also load from current working directory as a fallback (won't override existing vars)
load_dotenv()

# HubSpot settings
"""
Multi-app token resolution

Supports selecting different HubSpot Private Apps by setting HUBSPOT_APP to a
name that corresponds to an env var suffix. For example:

  HUBSPOT_APP=INSTONE
  INSTONE_ACCESS_TOKEN=pat-...

If HUBSPOT_APP is not set, falls back to HUBSPOT_ACCESS_TOKEN.
"""

def _resolve_hubspot_token() -> str:
    # 1) Explicit default token if provided
    default_token = os.getenv('HUBSPOT_ACCESS_TOKEN')

    # 2) Named app selection via HUBSPOT_APP, e.g. "INSTONE" -> INSTONE_ACCESS_TOKEN
    app_name = os.getenv('HUBSPOT_APP')
    if app_name:
        env_var = f"{app_name.upper()}_ACCESS_TOKEN"
        selected = os.getenv(env_var)
        if selected:
            return selected
        # If HUBSPOT_APP is set but the matching var is missing, fall back to default
        if default_token:
            return default_token
        raise ValueError(
            f"HUBSPOT_APP is set to '{app_name}', but {env_var} is not defined and HUBSPOT_ACCESS_TOKEN is not set."
        )

    # 3) No HUBSPOT_APP provided; use default token
    if default_token:
        return default_token

    raise ValueError("No HubSpot token found. Set HUBSPOT_ACCESS_TOKEN or set HUBSPOT_APP and a matching <APPNAME>_ACCESS_TOKEN.")

HUBSPOT_ACCESS_TOKEN = _resolve_hubspot_token()

# Neo4j settings
NEO4J_URI = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
NEO4J_USERNAME = os.getenv('NEO4J_USERNAME', 'neo4j')
NEO4J_PASSWORD = os.getenv('NEO4J_PASSWORD')
if not NEO4J_PASSWORD:
    raise ValueError("NEO4J_PASSWORD not found in environment variables")

# Pipeline settings
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '100'))
MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Feature flags (to simplify rollback of API behaviors)
# Use basic_api.get_page for contacts to avoid 10k Search API cap
USE_BASIC_API_FOR_CONTACTS = os.getenv('USE_BASIC_API_FOR_CONTACTS', 'true').lower() == 'true'
# Use offset query parameter for legacy email events pagination (recommended)
USE_EMAIL_EVENTS_OFFSET_PAGINATION = os.getenv('USE_EMAIL_EVENTS_OFFSET_PAGINATION', 'true').lower() == 'true'
# Log interval for contacts extraction progress
CONTACTS_PAGE_LOG_INTERVAL = int(os.getenv('CONTACTS_PAGE_LOG_INTERVAL', '5000'))

# HubSpot API Rate Limiting (Professional tier: 190 req/10s, 625k/day)
# Using conservative limits to ensure we stay within bounds and avoid 502/500 errors
HUBSPOT_MAX_REQUESTS_PER_10S = int(os.getenv('HUBSPOT_MAX_REQUESTS_PER_10S', '120'))
HUBSPOT_DAILY_LIMIT = int(os.getenv('HUBSPOT_DAILY_LIMIT', '625000'))
