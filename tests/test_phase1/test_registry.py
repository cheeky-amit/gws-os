"""Phase 1 tests: Account registry validation."""

import json
from pathlib import Path



class TestRegistrySchema:
    """Validate account registry JSON structure."""

    def test_registry_loads(self, sample_registry: Path) -> None:
        data = json.loads(sample_registry.read_text())
        assert "accounts" in data
        assert "default_account" in data

    def test_registry_has_accounts(self, sample_registry: Path) -> None:
        data = json.loads(sample_registry.read_text())
        assert len(data["accounts"]) >= 1

    def test_account_required_fields(self, sample_registry: Path) -> None:
        data = json.loads(sample_registry.read_text())
        required = {
            "id",
            "email",
            "label",
            "persona",
            "gws_profile",
            "is_default",
            "scan_window",
        }
        for account in data["accounts"]:
            assert required.issubset(account.keys()), (
                f"Missing fields in account {account.get('id')}"
            )

    def test_default_account_exists(self, sample_registry: Path) -> None:
        data = json.loads(sample_registry.read_text())
        account_ids = [a["id"] for a in data["accounts"]]
        assert data["default_account"] in account_ids

    def test_exactly_one_default(self, sample_registry: Path) -> None:
        data = json.loads(sample_registry.read_text())
        defaults = [a for a in data["accounts"] if a["is_default"]]
        assert len(defaults) == 1

    def test_scan_window_valid(self, sample_registry: Path) -> None:
        data = json.loads(sample_registry.read_text())
        valid_patterns = {"24h", "1w", "2w", "1m", "3m", "6m", "1y"}
        for account in data["accounts"]:
            assert account["scan_window"] in valid_patterns, (
                f"Invalid scan_window '{account['scan_window']}' for {account['id']}"
            )

    def test_unique_account_ids(self, sample_registry: Path) -> None:
        data = json.loads(sample_registry.read_text())
        ids = [a["id"] for a in data["accounts"]]
        assert len(ids) == len(set(ids)), "Duplicate account IDs found"

    def test_unique_emails(self, sample_registry: Path) -> None:
        data = json.loads(sample_registry.read_text())
        emails = [a["email"] for a in data["accounts"]]
        assert len(emails) == len(set(emails)), "Duplicate emails found"
