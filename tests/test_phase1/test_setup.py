"""Phase 1 tests: Setup script validation."""

from pathlib import Path

import pytest


class TestSetupScript:
    """Validate the setup script exists and is well-formed."""

    def test_setup_exists(self) -> None:
        setup_path = Path(__file__).parent.parent.parent / "setup"
        assert setup_path.exists(), "setup script must exist"

    def test_setup_is_executable_bash(self) -> None:
        setup_path = Path(__file__).parent.parent.parent / "setup"
        content = setup_path.read_text()
        assert content.startswith("#!/usr/bin/env bash"), "setup must have bash shebang"

    def test_setup_checks_gws(self) -> None:
        setup_path = Path(__file__).parent.parent.parent / "setup"
        content = setup_path.read_text()
        assert "command -v gws" in content or "which gws" in content, (
            "setup must check for gws CLI"
        )

    def test_setup_checks_jq(self) -> None:
        setup_path = Path(__file__).parent.parent.parent / "setup"
        content = setup_path.read_text()
        assert "jq" in content, "setup must check for jq"

    def test_setup_creates_registry(self) -> None:
        setup_path = Path(__file__).parent.parent.parent / "setup"
        content = setup_path.read_text()
        assert "registry.json" in content, "setup must create registry.json"

    def test_setup_is_idempotent(self) -> None:
        """Setup should detect existing installation."""
        setup_path = Path(__file__).parent.parent.parent / "setup"
        content = setup_path.read_text()
        assert "--add" in content, "setup must support --add for existing installations"


class TestDirectoryStructure:
    """Validate the expected directory structure exists."""

    @pytest.fixture
    def repo_root(self) -> Path:
        return Path(__file__).parent.parent.parent

    def test_required_dirs(self, repo_root: Path) -> None:
        required = [
            "accounts",
            "accounts/personas",
            "memory",
            "memory/contacts",
            "memory/topics",
            "memory/actions",
            "skills",
            "hooks",
            "tests",
            "docs",
        ]
        for d in required:
            assert (repo_root / d).is_dir(), f"Missing directory: {d}"

    def test_required_files(self, repo_root: Path) -> None:
        required = [
            "CLAUDE.md",
            "SKILL.md",
            "setup",
            ".gitignore",
            "skills/onboard.md",
            "skills/triage.md",
            "hooks/post-action.sh",
            "hooks/pattern-detect.sh",
        ]
        for f in required:
            assert (repo_root / f).is_file(), f"Missing file: {f}"
