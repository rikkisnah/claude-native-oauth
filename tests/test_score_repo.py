"""Tests for the self-contained architecture scorecard."""

from __future__ import annotations

from pathlib import Path

from scripts import score_repo


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_repo(root: Path) -> None:
    _write(
        root / "main.py",
        'from dataclasses import dataclass\n\nDEFAULT_API_URL = "https://api.anthropic.com/v1/messages"\n\n@dataclass(frozen=True)\nclass ClaudeNativeOAuthClient:\n    token: str\n\n\ndef build_parser(parser: object) -> object:\n    parser.add_argument("--stream")\n    return parser\n',
    )
    _write(root / "README.md", "Run `make validate` and `make score-repo` before opening a PR.\n")
    _write(root / "INSTALL.md", "# Install\n")
    _write(root / "CREATE-PR.md", "Run `make validate` and keep the score at 10.0/10.\n")
    _write(root / "AGENTS.md", "# Agents\n")
    _write(root / "CLAUDE.md", "# Claude\n")
    _write(root / "docs" / "User-Guide.md", "# User Guide\n")
    _write(root / "docs" / "How-It-Works.md", "# How It Works\n")
    _write(
        root / "docs" / "adr" / "003-score-through-wrapper.md",
        "# ADR\n\nThis is a self-contained score wrapper.\n",
    )
    _write(root / "tests" / "test_main.py", "def test_ok() -> None:\n    assert True\n")
    _write(
        root / ".github" / "workflows" / "ci.yml",
        "jobs:\n  check:\n    steps:\n      - run: make validate\n",
    )
    _write(
        root / "Makefile",
        "check:\n\t@true\n\nvalidate:\n\t@true\n\nscore-repo:\n\t@true\n",
    )
    _write(
        root / "pyproject.toml",
        '[tool.pytest.ini_options]\naddopts = "-q --cov=main --cov-fail-under=100"\ntestpaths = ["tests"]\n\n[tool.mypy]\nstrict = true\n',
    )


def test_score_repository_returns_perfect_score_for_clean_repo(tmp_path: Path) -> None:
    _make_repo(tmp_path)

    report = score_repo.score_repository(tmp_path)

    assert report.overall_score == 10.0
    assert report.failed_dimensions(8) == []
    assert all(result.score == 10 for result in report.results)


def test_score_repository_flags_legacy_package_references(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    legacy_name = score_repo.LEGACY_PACKAGE_NAME
    _write(tmp_path / "scripts" / "legacy.py", f"import {legacy_name}\n")

    report = score_repo.score_repository(tmp_path)
    independence = next(result for result in report.results if result.name == "independence")

    assert independence.score == 0
    assert independence.violations == [f"scripts/legacy.py contains `import {legacy_name}`"]


def test_score_repository_flags_machine_specific_scorer_paths(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    legacy_root = "/".join(("mnt", "data", "src", "scm", score_repo.LEGACY_PACKAGE_NAME))
    legacy_path = f"/{legacy_root}/scripts/score_architecture.py"
    _write(tmp_path / "docs" / "notes.md", f"Legacy path: {legacy_path}\n")

    report = score_repo.score_repository(tmp_path)
    independence = next(result for result in report.results if result.name == "independence")

    assert independence.score == 0
    assert independence.violations == [
        f"docs/notes.md contains `/{legacy_root}`"
    ]
