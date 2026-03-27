"""Phase 4 tests: metamemory index (print, structure, consolidation)."""

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
        "bin",
    ]:
        (tmp_path / d).mkdir(parents=True, exist_ok=True)

    # Copy gws-common.sh
    lib_src = Path(__file__).parent.parent.parent / "lib" / "gws-common.sh"
    lib_dst = tmp_path / "lib" / "gws-common.sh"
    lib_dst.write_text(lib_src.read_text())
    lib_dst.chmod(0o755)

    # Copy gws-graph.py
    graph_src = Path(__file__).parent.parent.parent / "bin" / "gws-graph.py"
    graph_dst = tmp_path / "bin" / "gws-graph.py"
    graph_dst.write_text(graph_src.read_text())
    graph_dst.chmod(0o755)

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


class TestMetamemory:
    """Test metamemory index generation and printing."""

    def test_print_metamemory_no_index(self, phase4_env: dict) -> None:
        """Without metamemory-index.json, prints guidance message."""
        result = run_bash(phase4_env, "print_metamemory")
        assert result.returncode == 0
        assert "No metamemory index yet" in result.stdout

    def test_print_metamemory_with_index(self, phase4_env: dict) -> None:
        """With metamemory-index.json present, prints its contents."""
        index_data = {
            "generated": "2026-03-27T10:00:00Z",
            "contacts": [
                {
                    "file": "jane-smith.md",
                    "email": "jane@acme.com",
                    "name": "Jane Smith",
                    "observations": 5,
                    "last_contact": "2026-03-25",
                },
            ],
            "topics": [
                {
                    "slug": "quarterly-reports",
                    "name": "Quarterly Reports",
                    "observations": 3,
                    "has_pattern": False,
                },
            ],
            "patterns_promoted": 0,
            "unanswered_topics": ["quarterly-reports"],
        }
        index_path = phase4_env["root"] / "memory" / "metamemory-index.json"
        index_path.write_text(json.dumps(index_data, indent=2))

        result = run_bash(phase4_env, "print_metamemory")
        assert result.returncode == 0
        output = json.loads(result.stdout.strip())
        assert output["contacts"][0]["email"] == "jane@acme.com"
        assert "quarterly-reports" in output["unanswered_topics"]

    def test_metamemory_index_structure(self, phase4_env: dict) -> None:
        """Running weekly consolidation creates metamemory-index.json with expected structure."""
        root = phase4_env["root"]

        # Create contact nodes via bash
        run_bash(
            phase4_env,
            'create_contact "jane@acme.com" "Jane Smith" "work"',
        )
        run_bash(
            phase4_env,
            'create_contact "bob@test.com" "Bob Test" "work"',
        )

        # Create topic nodes manually (frontmatter format)
        topics_dir = root / "memory" / "topics"
        (topics_dir / "quarterly-reports.md").write_text(
            """---
name: Quarterly Reports
observations: 4
confidence: 0.7
contacts: [jane@acme.com, bob@test.com]
actions: [reply, archive]
---
"""
        )
        (topics_dir / "project-alpha.md").write_text(
            """---
name: Project Alpha
observations: 2
confidence: 0.4
contacts: [bob@test.com]
actions: [reply]
---
"""
        )

        # Run weekly consolidation via gws-graph.py
        result = subprocess.run(
            [
                "python3",
                str(root / "bin" / "gws-graph.py"),
                "consolidate",
                "--mode",
                "weekly",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            env={
                **dict(__import__("os").environ),
                "GWS_OS_DIR": str(root),
                "GWS_MEMORY_DIR": str(root / "memory"),
            },
        )
        assert result.returncode == 0, f"consolidate failed: {result.stderr}"

        # Parse consolidation output
        consolidation_result = json.loads(result.stdout.strip())
        assert consolidation_result["mode"] == "weekly"
        assert consolidation_result["status"] == "ok"
        assert consolidation_result["contacts_indexed"] == 2
        assert consolidation_result["topics_analyzed"] == 2

        # Verify metamemory-index.json was created
        index_path = root / "memory" / "metamemory-index.json"
        assert index_path.exists(), "metamemory-index.json not created"

        index = json.loads(index_path.read_text())

        # Check top-level structure
        assert "generated" in index
        assert "contacts" in index
        assert "topics" in index
        assert "patterns_promoted" in index
        assert "unanswered_topics" in index

        # Check contacts
        assert len(index["contacts"]) == 2
        contact_emails = [c["email"] for c in index["contacts"]]
        assert "jane@acme.com" in contact_emails
        assert "bob@test.com" in contact_emails

        # Check topics
        assert len(index["topics"]) == 2
        topic_slugs = [t["slug"] for t in index["topics"]]
        assert "quarterly-reports" in topic_slugs
        assert "project-alpha" in topic_slugs

        # Check topic details
        qr_topic = next(t for t in index["topics"] if t["slug"] == "quarterly-reports")
        assert qr_topic["observations"] == 4
        assert qr_topic["name"] == "Quarterly Reports"

    def test_metamemory_index_unanswered_topics(self, phase4_env: dict) -> None:
        """Topics with observations but no pattern are flagged as unanswered."""
        root = phase4_env["root"]

        # Create a topic with observations but no pattern
        topics_dir = root / "memory" / "topics"
        (topics_dir / "mystery-topic.md").write_text(
            """---
name: Mystery Topic
observations: 3
confidence: 0.2
contacts: []
actions: []
---
"""
        )

        # Create a topic WITH a pattern
        (topics_dir / "known-topic.md").write_text(
            """---
name: Known Topic
observations: 5
confidence: 0.9
pattern: "weekly sync every Monday"
contacts: []
actions: []
---
"""
        )

        result = subprocess.run(
            [
                "python3",
                str(root / "bin" / "gws-graph.py"),
                "consolidate",
                "--mode",
                "weekly",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            env={
                **dict(__import__("os").environ),
                "GWS_OS_DIR": str(root),
                "GWS_MEMORY_DIR": str(root / "memory"),
            },
        )
        assert result.returncode == 0, f"consolidate failed: {result.stderr}"

        index_path = root / "memory" / "metamemory-index.json"
        index = json.loads(index_path.read_text())

        # mystery-topic has observations but no pattern -> unanswered
        assert "mystery-topic" in index["unanswered_topics"]
        # known-topic has a pattern -> NOT unanswered
        assert "known-topic" not in index["unanswered_topics"]
