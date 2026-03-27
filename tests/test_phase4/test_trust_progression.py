"""Phase 4 tests: trust progression (promote / demote / streak)."""

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

    # Create trust-levels.json with thresholds
    trust = {
        "defaults": {
            "reply": "observe",
            "archive": "observe",
            "schedule": "observe",
        },
        "thresholds": {
            "default": {
                "observe": 5,
                "suggest": 3,
                "assist": 5,
            },
        },
        "promotion_thresholds": {
            "observe_to_suggest": 5,
            "suggest_to_assist": 3,
            "assist_to_automate": 5,
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


class TestTrustProgression:
    """Test trust promotion and demotion functions."""

    def test_promote_trust_observe_to_suggest(self, phase4_env: dict) -> None:
        """Promote a contact from observe to suggest for an action."""
        run_bash(phase4_env, 'create_contact "jane@acme.com" "Jane Smith" "work"')
        # Verify starting at observe
        result = run_bash(phase4_env, 'resolve_trust "jane@acme.com" "reply"')
        assert result.stdout.strip() == "observe"

        # Promote
        result = run_bash(phase4_env, 'promote_trust "jane@acme.com" "reply"')
        assert result.returncode == 0
        assert "observe" in result.stdout
        assert "suggest" in result.stdout

        # Verify new level
        result = run_bash(phase4_env, 'resolve_trust "jane@acme.com" "reply"')
        assert result.stdout.strip() == "suggest"

    def test_promote_trust_assist_to_automate(self, phase4_env: dict) -> None:
        """Promote a contact from assist to automate."""
        run_bash(phase4_env, 'create_contact "jane@acme.com" "Jane Smith" "work"')
        # Set trust to assist manually
        contact_file = phase4_env["root"] / "memory" / "contacts" / "jane-smith.md"
        content = contact_file.read_text()
        content = content.replace("reply: observe", "reply: assist")
        contact_file.write_text(content)

        # Promote
        result = run_bash(phase4_env, 'promote_trust "jane@acme.com" "reply"')
        assert result.returncode == 0
        assert "assist" in result.stdout
        assert "automate" in result.stdout

        # Verify
        result = run_bash(phase4_env, 'resolve_trust "jane@acme.com" "reply"')
        assert result.stdout.strip() == "automate"

    def test_promote_trust_already_at_max(self, phase4_env: dict) -> None:
        """Promoting a contact already at automate returns a message and no change."""
        run_bash(phase4_env, 'create_contact "jane@acme.com" "Jane Smith" "work"')
        # Set to automate
        contact_file = phase4_env["root"] / "memory" / "contacts" / "jane-smith.md"
        content = contact_file.read_text()
        content = content.replace("reply: observe", "reply: automate")
        contact_file.write_text(content)

        result = run_bash(phase4_env, 'promote_trust "jane@acme.com" "reply"')
        assert result.returncode == 0
        assert "Already at maximum" in result.stdout

        # Verify still automate
        result = run_bash(phase4_env, 'resolve_trust "jane@acme.com" "reply"')
        assert result.stdout.strip() == "automate"

    def test_demote_trust_assist_to_suggest(self, phase4_env: dict) -> None:
        """Demote a contact from assist to suggest."""
        run_bash(phase4_env, 'create_contact "jane@acme.com" "Jane Smith" "work"')
        # Set to assist
        contact_file = phase4_env["root"] / "memory" / "contacts" / "jane-smith.md"
        content = contact_file.read_text()
        content = content.replace("reply: observe", "reply: assist")
        contact_file.write_text(content)

        result = run_bash(
            phase4_env,
            'demote_trust "jane@acme.com" "reply" "user disagreed with draft"',
        )
        assert result.returncode == 0
        assert "assist" in result.stdout
        assert "suggest" in result.stdout

        # Verify
        result = run_bash(phase4_env, 'resolve_trust "jane@acme.com" "reply"')
        assert result.stdout.strip() == "suggest"

    def test_demote_trust_resets_streak(self, phase4_env: dict) -> None:
        """Demoting trust resets the action streak to 0."""
        run_bash(phase4_env, 'create_contact "jane@acme.com" "Jane Smith" "work"')
        # Set to assist and add a streak
        contact_file = phase4_env["root"] / "memory" / "contacts" / "jane-smith.md"
        content = contact_file.read_text()
        content = content.replace("reply: observe", "reply: assist")
        contact_file.write_text(content)

        run_bash(
            phase4_env,
            'update_contact "jane@acme.com" "reply_streak" "4"',
        )

        # Verify streak was set
        content = contact_file.read_text()
        assert "reply_streak: 4" in content

        # Demote
        run_bash(
            phase4_env,
            'demote_trust "jane@acme.com" "reply" "override"',
        )

        # Verify streak is reset to 0
        content = contact_file.read_text()
        assert "reply_streak: 0" in content

    def test_demote_logs_disagreement(self, phase4_env: dict) -> None:
        """Demoting trust logs an entry to disagreements.jsonl."""
        run_bash(phase4_env, 'create_contact "jane@acme.com" "Jane Smith" "work"')
        # Set to suggest so demotion goes to observe
        contact_file = phase4_env["root"] / "memory" / "contacts" / "jane-smith.md"
        content = contact_file.read_text()
        content = content.replace("reply: observe", "reply: suggest")
        contact_file.write_text(content)

        run_bash(
            phase4_env,
            'demote_trust "jane@acme.com" "reply" "user rewrote the reply"',
        )

        disagreements_file = (
            phase4_env["root"] / "memory" / "actions" / "disagreements.jsonl"
        )
        assert disagreements_file.exists()
        entry = json.loads(disagreements_file.read_text().strip().split("\n")[-1])
        assert entry["action"] == "reply"
        assert entry["system_recommendation"] == "suggest"
        assert entry["user_override"] == "observe"
        assert "rewrote" in entry["reason"]

    def test_promote_suggest_to_assist(self, phase4_env: dict) -> None:
        """Promote from suggest to assist covers the middle step."""
        run_bash(phase4_env, 'create_contact "bob@test.com" "Bob Test" "work"')
        contact_file = phase4_env["root"] / "memory" / "contacts" / "bob-test.md"
        content = contact_file.read_text()
        content = content.replace("reply: observe", "reply: suggest")
        contact_file.write_text(content)

        result = run_bash(phase4_env, 'promote_trust "bob@test.com" "reply"')
        assert result.returncode == 0
        assert "suggest" in result.stdout
        assert "assist" in result.stdout

        result = run_bash(phase4_env, 'resolve_trust "bob@test.com" "reply"')
        assert result.stdout.strip() == "assist"
