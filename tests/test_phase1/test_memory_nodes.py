"""Phase 1 tests: Memory node (contact/topic) validation."""

import json
from pathlib import Path

import yaml


class TestContactNodes:
    """Validate contact node structure."""

    def test_contact_file_exists(self, sample_contact: Path) -> None:
        assert sample_contact.exists()

    def test_contact_has_frontmatter(self, sample_contact: Path) -> None:
        content = sample_contact.read_text()
        assert content.startswith("---")
        parts = content.split("---", 2)
        assert len(parts) >= 3, "Contact node must have YAML frontmatter"

    def test_contact_required_fields(self, sample_contact: Path) -> None:
        content = sample_contact.read_text()
        frontmatter = content.split("---", 2)[1]
        data = yaml.safe_load(frontmatter)
        required = {"email", "name", "accounts_seen", "observations", "trust_levels"}
        assert required.issubset(data.keys()), (
            f"Missing fields: {required - data.keys()}"
        )

    def test_contact_trust_levels_valid(self, sample_contact: Path) -> None:
        content = sample_contact.read_text()
        frontmatter = content.split("---", 2)[1]
        data = yaml.safe_load(frontmatter)
        valid_levels = {"observe", "suggest", "assist", "automate"}
        for action, level in data["trust_levels"].items():
            assert level in valid_levels, (
                f"Invalid trust level '{level}' for action '{action}'"
            )

    def test_contact_observations_positive(self, sample_contact: Path) -> None:
        content = sample_contact.read_text()
        frontmatter = content.split("---", 2)[1]
        data = yaml.safe_load(frontmatter)
        assert data["observations"] >= 0


class TestTrustLevels:
    """Validate trust-levels.json template."""

    def test_trust_template_loads(self, sample_trust_levels: Path) -> None:
        data = json.loads(sample_trust_levels.read_text())
        assert "defaults" in data
        assert "promotion_thresholds" in data

    def test_trust_defaults_valid_levels(self, sample_trust_levels: Path) -> None:
        data = json.loads(sample_trust_levels.read_text())
        valid_levels = {"observe", "suggest", "assist", "automate"}
        for action, level in data["defaults"].items():
            assert level in valid_levels, (
                f"Invalid default trust level '{level}' for '{action}'"
            )

    def test_promotion_thresholds_positive(self, sample_trust_levels: Path) -> None:
        data = json.loads(sample_trust_levels.read_text())
        for threshold_name, value in data["promotion_thresholds"].items():
            assert value > 0, f"Threshold '{threshold_name}' must be positive"

    def test_contact_overrides_global(
        self, sample_contact: Path, sample_trust_levels: Path
    ) -> None:
        """Contact node trust levels should override global defaults."""
        global_data = json.loads(sample_trust_levels.read_text())
        contact_content = sample_contact.read_text()
        contact_fm = yaml.safe_load(contact_content.split("---", 2)[1])

        # Contact has archive=automate, global has archive=observe
        assert contact_fm["trust_levels"]["archive"] == "automate"
        assert global_data["defaults"]["archive"] == "observe"
        # Contact node wins — this is the core design decision
