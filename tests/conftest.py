"""GWS OS test configuration."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def gws_os_dir(tmp_path: Path) -> Path:
    """Create a temporary GWS OS directory structure for testing."""
    dirs = [
        "accounts/personas",
        "memory/contacts",
        "memory/topics",
        "memory/actions",
        "skills",
        "hooks",
    ]
    for d in dirs:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def sample_registry(gws_os_dir: Path) -> Path:
    """Create a sample account registry for testing."""
    registry = {
        "accounts": [
            {
                "id": "business",
                "email": "alice@testcorp.example.com",
                "label": "TestCorp Business",
                "persona": "personas/business.md",
                "gws_profile": "business",
                "is_default": True,
                "scan_window": "24h",
            },
            {
                "id": "personal",
                "email": "alice.test@gmail.com",
                "label": "Personal",
                "persona": "personas/personal.md",
                "gws_profile": "personal",
                "is_default": False,
                "scan_window": "1w",
            },
        ],
        "default_account": "business",
    }
    registry_path = gws_os_dir / "accounts" / "registry.json"
    registry_path.write_text(json.dumps(registry, indent=2))
    return registry_path


@pytest.fixture
def sample_trust_levels(gws_os_dir: Path) -> Path:
    """Create sample trust-levels.json template."""
    trust = {
        "_comment": "Global defaults — template for new contacts only.",
        "defaults": {
            "reply": "observe",
            "archive": "observe",
            "schedule": "observe",
            "followup": "observe",
            "search": "suggest",
        },
        "promotion_thresholds": {
            "observe_to_suggest": 5,
            "suggest_to_assist": 3,
            "assist_to_automate": 5,
        },
    }
    path = gws_os_dir / "memory" / "trust-levels.json"
    path.write_text(json.dumps(trust, indent=2))
    return path


@pytest.fixture
def sample_contact(gws_os_dir: Path) -> Path:
    """Create a sample contact node."""
    content = """---
email: jane@testcorp.example.com
name: Jane Smith
accounts_seen: [business]
topics: [quarterly-reports, performance-marketing]
communication_pattern: formal, responsive
last_contact: 2026-03-25
frequency: 3-4x/week
observations: 12
trust_levels:
  reply: assist
  archive: automate
  schedule: suggest
---
"""
    path = gws_os_dir / "memory" / "contacts" / "jane-smith.md"
    path.write_text(content)
    return path
