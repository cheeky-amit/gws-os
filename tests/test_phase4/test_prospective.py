"""Phase 4 tests: prospective triggers (create, check, expire)."""

import json
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def phase4_env(tmp_path: Path) -> dict:
    """Create a temporary GWS OS environment for Phase 4 testing."""
    for d in [
        "accounts/personas",
        "memory/contacts",
        "memory/topics",
        "memory/actions",
        "lib",
    ]:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)

    # Copy gws-common.sh
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
    }
    (tmp_path / "memory" / "trust-levels.json").write_text(json.dumps(trust, indent=2))

    return {"root": tmp_path}


def run_bash(env_dict: dict, script: str) -> subprocess.CompletedProcess:
    """Run a bash script that sources gws-common.sh in the test environment."""
    root = env_dict["root"]
    full_script = f"""
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
export GWS_OS_DIR="{root}"
export GWS_REGISTRY="{root}/accounts/registry.json"
export GWS_MEMORY_DIR="{root}/memory"
export GWS_PROFILES_DIR="{root}/profiles"
source "{root}/lib/gws-common.sh"
{script}
"""
    return subprocess.run(
        ["bash", "-c", full_script],
        capture_output=True,
        text=True,
        timeout=10,
    )


class TestProspectiveTriggers:
    """Test prospective trigger creation, matching, and expiration."""

    def test_create_trigger(self, phase4_env: dict) -> None:
        """Creating a trigger appends an entry to prospective.jsonl."""
        result = run_bash(
            phase4_env,
            """create_trigger "Follow up on Acme proposal" '["mentions Acme"]' "2099-12-31" """,
        )
        assert result.returncode == 0
        assert "Trigger created" in result.stdout

        trigger_file = phase4_env["root"] / "memory" / "prospective.jsonl"
        assert trigger_file.exists()
        entry = json.loads(trigger_file.read_text().strip())
        assert entry["content"] == "Follow up on Acme proposal"
        assert entry["conditions"] == ["mentions Acme"]
        assert entry["expires"] == "2099-12-31"
        assert entry["fired"] is False

    def test_check_triggers_match(self, phase4_env: dict) -> None:
        """Triggers fire when all conditions match the context."""
        # Create a trigger
        run_bash(
            phase4_env,
            """create_trigger "Remind about Acme deal" '["mentions Acme"]' """,
        )

        # Check with matching context
        result = run_bash(
            phase4_env,
            'check_triggers "Email from Bob mentions Acme quarterly review"',
        )
        assert result.returncode == 0
        assert "TRIGGER MATCH" in result.stdout
        assert "Remind about Acme deal" in result.stdout

        # Verify the trigger was marked as fired
        trigger_file = phase4_env["root"] / "memory" / "prospective.jsonl"
        entry = json.loads(trigger_file.read_text().strip())
        assert entry["fired"] is True

    def test_check_triggers_no_match(self, phase4_env: dict) -> None:
        """Triggers do not fire when conditions do not match."""
        # Create a trigger
        run_bash(
            phase4_env,
            """create_trigger "Follow up on Acme" '["mentions Acme"]' """,
        )

        # Check with non-matching context
        result = run_bash(
            phase4_env,
            'check_triggers "Email from Carol about lunch plans"',
        )
        assert "TRIGGER MATCH" not in result.stdout

        # Verify trigger is still unfired
        trigger_file = phase4_env["root"] / "memory" / "prospective.jsonl"
        entry = json.loads(trigger_file.read_text().strip())
        assert entry["fired"] is False

    def test_check_triggers_expired(self, phase4_env: dict) -> None:
        """Expired triggers are removed from prospective.jsonl."""
        # Create a trigger with a past expiry date
        run_bash(
            phase4_env,
            """create_trigger "Old reminder" '["mentions test"]' "2020-01-01" """,
        )

        trigger_file = phase4_env["root"] / "memory" / "prospective.jsonl"
        assert trigger_file.exists()
        # File has one entry before check
        lines_before = [
            l for l in trigger_file.read_text().strip().split("\n") if l.strip()
        ]
        assert len(lines_before) == 1

        # Check triggers -- expired one should be removed
        run_bash(
            phase4_env,
            'check_triggers "mentions test"',
        )

        # Verify the expired trigger was removed from the file
        content = trigger_file.read_text().strip()
        if content:
            remaining = [l for l in content.split("\n") if l.strip()]
            # The expired trigger should have been dropped
            for line in remaining:
                entry = json.loads(line)
                assert entry.get("content") != "Old reminder"
        # If file is empty, that's also correct -- the only trigger was expired

    def test_create_trigger_no_expiry(self, phase4_env: dict) -> None:
        """Creating a trigger without expiry sets expires to null."""
        run_bash(
            phase4_env,
            """create_trigger "Persistent reminder" '["mentions quarterly"]' """,
        )

        trigger_file = phase4_env["root"] / "memory" / "prospective.jsonl"
        entry = json.loads(trigger_file.read_text().strip())
        assert entry["expires"] is None
        assert entry["fired"] is False

    def test_check_triggers_multi_condition(self, phase4_env: dict) -> None:
        """Triggers with multiple conditions require all to match."""
        run_bash(
            phase4_env,
            """create_trigger "Acme + budget" '["mentions Acme", "budget review"]' """,
        )

        # Only one condition matches -- should NOT fire
        result = run_bash(
            phase4_env,
            'check_triggers "Email mentions Acme partnership"',
        )
        assert "TRIGGER MATCH" not in result.stdout

        # Both conditions match -- should fire
        result = run_bash(
            phase4_env,
            'check_triggers "Email mentions Acme budget review for Q3"',
        )
        assert "TRIGGER MATCH" in result.stdout
        assert "Acme + budget" in result.stdout
