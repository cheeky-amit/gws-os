"""Phase 2 tests: lib/gws-common.sh shared library functions."""

import json
import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def gws_env(tmp_path: Path) -> dict:
    """Create a temporary GWS OS environment for testing shell functions."""
    # Create directory structure
    dirs = [
        "accounts/personas",
        "memory/contacts",
        "memory/topics",
        "memory/actions",
        "lib",
    ]
    for d in dirs:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)

    # Copy the real gws-common.sh
    lib_src = Path(__file__).parent.parent.parent / "lib" / "gws-common.sh"
    lib_dst = tmp_path / "lib" / "gws-common.sh"
    lib_dst.write_text(lib_src.read_text())
    lib_dst.chmod(0o755)

    # Create registry
    registry = {
        "accounts": [
            {
                "id": "work",
                "email": "user@company.com",
                "label": "Work",
                "persona": "personas/work.md",
                "gws_profile": "work",
                "is_default": True,
                "scan_window": "24h",
            },
            {
                "id": "personal",
                "email": "user@gmail.com",
                "label": "Personal",
                "persona": "personas/personal.md",
                "gws_profile": "personal",
                "is_default": False,
                "scan_window": "1w",
            },
        ],
        "default_account": "work",
    }
    (tmp_path / "accounts" / "registry.json").write_text(json.dumps(registry, indent=2))

    # Create trust-levels.json
    trust = {
        "defaults": {
            "reply": "observe",
            "archive": "observe",
            "schedule": "observe",
        },
        "promotion_thresholds": {
            "observe_to_suggest": 5,
            "suggest_to_assist": 3,
            "assist_to_automate": 5,
        },
    }
    (tmp_path / "memory" / "trust-levels.json").write_text(json.dumps(trust, indent=2))

    return {"root": tmp_path, "registry": registry, "trust": trust}


def run_bash(gws_env: dict, script: str) -> subprocess.CompletedProcess:
    """Run a bash script that sources gws-common.sh in the test environment."""
    root = gws_env["root"]
    # We need to mock gws and jq as available commands
    full_script = f"""
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
# Override GWS_OS_DIR directly since we're not sourcing from a skill
export GWS_OS_DIR="{root}"
export GWS_REGISTRY="{root}/accounts/registry.json"
export GWS_MEMORY_DIR="{root}/memory"
export GWS_PROFILES_DIR="{root}/profiles"

# Source the library functions (skip gws_init since we set vars manually)
source "{root}/lib/gws-common.sh"

{script}
"""
    return subprocess.run(
        ["bash", "-c", full_script],
        capture_output=True,
        text=True,
        timeout=10,
    )


class TestRegistryFunctions:
    """Test registry access functions from gws-common.sh."""

    def test_get_profiles(self, gws_env: dict) -> None:
        result = run_bash(gws_env, "get_profiles")
        assert result.returncode == 0
        profiles = result.stdout.strip().split("\n")
        assert "work" in profiles
        assert "personal" in profiles

    def test_get_account_field_label(self, gws_env: dict) -> None:
        result = run_bash(gws_env, 'get_account_field "work" "label"')
        assert result.returncode == 0
        assert result.stdout.strip() == "Work"

    def test_get_account_field_email(self, gws_env: dict) -> None:
        result = run_bash(gws_env, 'get_account_field "personal" "email"')
        assert result.returncode == 0
        assert result.stdout.strip() == "user@gmail.com"

    def test_get_account_field_scan_window(self, gws_env: dict) -> None:
        result = run_bash(gws_env, 'get_account_field "personal" "scan_window"')
        assert result.returncode == 0
        assert result.stdout.strip() == "1w"

    def test_get_default_profile(self, gws_env: dict) -> None:
        result = run_bash(gws_env, "get_default_profile")
        assert result.returncode == 0
        assert result.stdout.strip() == "work"

    def test_print_accounts(self, gws_env: dict) -> None:
        result = run_bash(gws_env, "print_accounts")
        assert result.returncode == 0
        assert "work:" in result.stdout
        assert "personal:" in result.stdout
        assert "user@company.com" in result.stdout


class TestContactCRUD:
    """Test contact node create, read, update operations."""

    def test_create_contact(self, gws_env: dict) -> None:
        result = run_bash(gws_env, 'create_contact "jane@acme.com" "Jane Smith" "work"')
        assert result.returncode == 0
        assert "Created contact" in result.stdout

        contact_file = gws_env["root"] / "memory" / "contacts" / "jane-smith.md"
        assert contact_file.exists()
        content = contact_file.read_text()
        assert "email: jane@acme.com" in content
        assert "name: Jane Smith" in content
        assert "observations: 1" in content

    def test_create_contact_duplicate(self, gws_env: dict) -> None:
        run_bash(gws_env, 'create_contact "jane@acme.com" "Jane Smith" "work"')
        result = run_bash(gws_env, 'create_contact "jane@acme.com" "Jane Smith" "work"')
        assert result.returncode == 1
        assert "already exists" in result.stdout

    def test_create_contact_has_trust_defaults(self, gws_env: dict) -> None:
        run_bash(gws_env, 'create_contact "bob@test.com" "Bob Jones" "work"')
        contact_file = gws_env["root"] / "memory" / "contacts" / "bob-jones.md"
        content = contact_file.read_text()
        assert "reply: observe" in content
        assert "archive: observe" in content

    def test_get_contact(self, gws_env: dict) -> None:
        run_bash(gws_env, 'create_contact "jane@acme.com" "Jane Smith" "work"')
        result = run_bash(gws_env, 'get_contact "jane@acme.com"')
        assert result.returncode == 0
        assert "email: jane@acme.com" in result.stdout

    def test_get_contact_not_found(self, gws_env: dict) -> None:
        result = run_bash(gws_env, 'get_contact "nobody@nowhere.com"')
        assert result.returncode == 1

    def test_update_contact_field(self, gws_env: dict) -> None:
        run_bash(gws_env, 'create_contact "jane@acme.com" "Jane Smith" "work"')
        run_bash(
            gws_env,
            'update_contact "jane@acme.com" "communication_pattern" "formal, responsive"',
        )
        contact_file = gws_env["root"] / "memory" / "contacts" / "jane-smith.md"
        content = contact_file.read_text()
        assert "communication_pattern: formal, responsive" in content

    def test_update_contact_increment_observations(self, gws_env: dict) -> None:
        run_bash(gws_env, 'create_contact "jane@acme.com" "Jane Smith" "work"')
        run_bash(gws_env, 'update_contact "jane@acme.com" "observations" "+1"')
        contact_file = gws_env["root"] / "memory" / "contacts" / "jane-smith.md"
        content = contact_file.read_text()
        assert "observations: 2" in content

    def test_update_contact_not_found(self, gws_env: dict) -> None:
        result = run_bash(gws_env, 'update_contact "nobody@nowhere.com" "name" "test"')
        assert result.returncode == 1


class TestTrustResolution:
    """Test trust level resolution: contact node > global defaults."""

    def test_trust_from_global_defaults(self, gws_env: dict) -> None:
        """Unknown contact falls back to global defaults."""
        result = run_bash(gws_env, 'resolve_trust "unknown@test.com" "reply"')
        assert result.returncode == 0
        assert result.stdout.strip() == "observe"

    def test_trust_from_contact_node(self, gws_env: dict) -> None:
        """Contact node trust overrides global defaults."""
        # Create contact with custom trust
        run_bash(gws_env, 'create_contact "jane@acme.com" "Jane Smith" "work"')
        # Manually set higher trust on the contact
        contact_file = gws_env["root"] / "memory" / "contacts" / "jane-smith.md"
        content = contact_file.read_text()
        content = content.replace("reply: observe", "reply: assist")
        contact_file.write_text(content)

        result = run_bash(gws_env, 'resolve_trust "jane@acme.com" "reply"')
        assert result.returncode == 0
        assert result.stdout.strip() == "assist"

    def test_trust_contact_overrides_global(self, gws_env: dict) -> None:
        """Contact with automate trust returns automate even though global is observe."""
        run_bash(gws_env, 'create_contact "vip@acme.com" "VIP User" "work"')
        contact_file = gws_env["root"] / "memory" / "contacts" / "vip-user.md"
        content = contact_file.read_text()
        content = content.replace("archive: observe", "archive: automate")
        contact_file.write_text(content)

        result = run_bash(gws_env, 'resolve_trust "vip@acme.com" "archive"')
        assert result.stdout.strip() == "automate"

    def test_trust_unknown_action_defaults_observe(self, gws_env: dict) -> None:
        """Unknown action type defaults to observe."""
        result = run_bash(gws_env, 'resolve_trust "unknown@test.com" "unknown_action"')
        assert result.stdout.strip() == "observe"

    def test_trust_no_trust_file_defaults_observe(self, gws_env: dict) -> None:
        """Missing trust-levels.json still returns observe."""
        os.remove(gws_env["root"] / "memory" / "trust-levels.json")
        result = run_bash(gws_env, 'resolve_trust "unknown@test.com" "reply"')
        assert result.stdout.strip() == "observe"


class TestActionLogging:
    """Test action logging and contact auto-update."""

    def test_log_action_creates_jsonl(self, gws_env: dict) -> None:
        result = run_bash(
            gws_env, 'log_action "reply" "work" "jane@acme.com" "quarterly-reports"'
        )
        assert result.returncode == 0

        action_file = gws_env["root"] / "memory" / "actions" / "reply.jsonl"
        assert action_file.exists()
        entry = json.loads(action_file.read_text().strip())
        assert entry["action"] == "reply"
        assert entry["contact"] == "jane@acme.com"
        assert entry["topic"] == "quarterly-reports"

    def test_log_action_updates_contact(self, gws_env: dict) -> None:
        """Logging an action auto-increments observations on the contact node."""
        run_bash(gws_env, 'create_contact "jane@acme.com" "Jane Smith" "work"')
        run_bash(gws_env, 'log_action "reply" "work" "jane@acme.com"')

        contact_file = gws_env["root"] / "memory" / "contacts" / "jane-smith.md"
        content = contact_file.read_text()
        assert "observations: 2" in content

    def test_log_action_appends(self, gws_env: dict) -> None:
        """Multiple log_action calls append to the same JSONL file."""
        run_bash(gws_env, 'log_action "reply" "work" "jane@acme.com"')
        run_bash(gws_env, 'log_action "reply" "work" "bob@test.com"')

        action_file = gws_env["root"] / "memory" / "actions" / "reply.jsonl"
        lines = action_file.read_text().strip().split("\n")
        assert len(lines) == 2


class TestMemoryLoading:
    """Test memory loading and summary functions."""

    def test_load_contacts_empty(self, gws_env: dict) -> None:
        result = run_bash(gws_env, "load_contacts")
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data == []

    def test_load_contacts_with_data(self, gws_env: dict) -> None:
        run_bash(gws_env, 'create_contact "jane@acme.com" "Jane Smith" "work"')
        run_bash(gws_env, 'create_contact "bob@test.com" "Bob Jones" "personal"')

        result = run_bash(gws_env, "load_contacts")
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert len(data) == 2
        emails = [c["email"] for c in data]
        assert "jane@acme.com" in emails
        assert "bob@test.com" in emails

    def test_print_memory_summary(self, gws_env: dict) -> None:
        run_bash(gws_env, 'create_contact "jane@acme.com" "Jane Smith" "work"')
        run_bash(gws_env, 'log_action "reply" "work" "jane@acme.com"')

        result = run_bash(gws_env, "print_memory_summary")
        assert result.returncode == 0
        assert "1 contacts" in result.stdout
        assert "actions logged" in result.stdout
