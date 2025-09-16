import os
import sys
import importlib


def reload_settings(monkeypatch, env):
    # Ensure a clean import of config.settings with desired env
    for k, v in env.items():
        monkeypatch.setenv(k, v)

    # Unload module if already imported
    sys.modules.pop('config.settings', None)
    importlib.invalidate_caches()
    settings = importlib.import_module('config.settings')
    return settings


def test_uses_default_token_when_no_app(monkeypatch):
    settings = reload_settings(monkeypatch, {
        'HUBSPOT_ACCESS_TOKEN': 'pat-default',
        'NEO4J_PASSWORD': 'pass',
        'NEO4J_USERNAME': 'neo4j',
        'NEO4J_URI': 'bolt://localhost:7687',
    })
    assert settings.HUBSPOT_ACCESS_TOKEN == 'pat-default'


def test_uses_named_app_token_when_set(monkeypatch):
    settings = reload_settings(monkeypatch, {
        'HUBSPOT_APP': 'INSTONE',
        'INSTONE_ACCESS_TOKEN': 'pat-instone',
        'HUBSPOT_ACCESS_TOKEN': 'pat-default',
        'NEO4J_PASSWORD': 'pass',
        'NEO4J_USERNAME': 'neo4j',
        'NEO4J_URI': 'bolt://localhost:7687',
    })
    assert settings.HUBSPOT_ACCESS_TOKEN == 'pat-instone'


def test_falls_back_to_default_when_named_missing(monkeypatch):
    settings = reload_settings(monkeypatch, {
        'HUBSPOT_APP': 'MISSING',
        'HUBSPOT_ACCESS_TOKEN': 'pat-default',
        'NEO4J_PASSWORD': 'pass',
        'NEO4J_USERNAME': 'neo4j',
        'NEO4J_URI': 'bolt://localhost:7687',
    })
    assert settings.HUBSPOT_ACCESS_TOKEN == 'pat-default'
