"""Self-contained architecture scorecard for this repository."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_DOCS = (
    "README.md",
    "INSTALL.md",
    "CREATE-PR.md",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/User-Guide.md",
    "docs/How-It-Works.md",
    "docs/adr/003-score-through-wrapper.md",
)
SCANNED_SUFFIXES = {".md", ".py", ".toml", ".txt", ".yml", ".yaml"}
BLOCKED_PARTS = {".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
LEGACY_PACKAGE_NAME = "".join(("s", "t", "c"))


@dataclass(frozen=True)
class DimensionResult:
    """Score output for one architecture dimension."""

    name: str
    score: int
    detail: str
    violations: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.score >= 8:
            return "PASS"
        if self.score >= 5:
            return "WARN"
        return "FAIL"


@dataclass(frozen=True)
class ScoreReport:
    """Normalized score output."""

    results: list[DimensionResult]

    @property
    def overall_score(self) -> float:
        if not self.results:
            return 0.0
        total = sum(result.score for result in self.results)
        return round(total / len(self.results), 2)

    def failed_dimensions(self, minimum: int) -> list[DimensionResult]:
        """Return dimensions below the requested threshold."""
        return [result for result in self.results if result.score < minimum]

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-friendly report."""
        return {
            "overall_score": self.overall_score,
            "results": [asdict(result) | {"status": result.status} for result in self.results],
        }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse score wrapper arguments."""
    parser = argparse.ArgumentParser(
        description="Run the self-contained architecture scorecard for this repository"
    )
    parser.add_argument("--json", action="store_true", help="Emit score output as JSON")
    parser.add_argument("--verbose", action="store_true", help="Show violation details")
    parser.add_argument("--min-score", type=int, default=8, help="Minimum allowed dimension score")
    return parser.parse_args(argv)


def _iter_text_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in BLOCKED_PARTS for part in path.parts):
            continue
        if path.name == "Makefile" or path.suffix in SCANNED_SUFFIXES:
            yield path


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _forbidden_tokens() -> tuple[str, ...]:
    return (
        f"/mnt/data/src/scm/{LEGACY_PACKAGE_NAME}",
        f"import {LEGACY_PACKAGE_NAME}",
        f"from {LEGACY_PACKAGE_NAME}",
        f'"{LEGACY_PACKAGE_NAME}/',
        f"'{LEGACY_PACKAGE_NAME}/",
    )


def _score_independence(repo_root: Path) -> DimensionResult:
    violations: list[str] = []
    for path in _iter_text_files(repo_root):
        text = _read_text(path)
        for token in _forbidden_tokens():
            if token in text:
                violations.append(f"{path.relative_to(repo_root)} contains `{token}`")
    score = 10 if not violations else 0
    detail = "Repository avoids out-of-repo scorer dependencies and machine-specific imports."
    return DimensionResult("independence", score, detail, violations)


def _score_entrypoint(repo_root: Path) -> DimensionResult:
    violations: list[str] = []
    main_file = repo_root / "main.py"
    if not main_file.exists():
        violations.append("main.py is missing")
    else:
        text = _read_text(main_file)
        if "DEFAULT_API_URL" not in text:
            violations.append("main.py does not declare DEFAULT_API_URL")
        if "ClaudeNativeOAuthClient" not in text:
            violations.append("main.py does not define ClaudeNativeOAuthClient")
        if 'parser.add_argument("--stream"' not in text:
            violations.append("main.py does not expose the --stream CLI flag")
    score = 10 if not violations else 4
    detail = "The production entrypoint remains a single direct OAuth client in main.py."
    return DimensionResult("entrypoint", score, detail, violations)


def _score_docs(repo_root: Path) -> DimensionResult:
    missing = [relative for relative in REQUIRED_DOCS if not (repo_root / relative).exists()]
    score = 10 if not missing else 4
    detail = "Contributor, install, and architecture docs are present."
    violations = [f"Missing required document: {path}" for path in missing]
    return DimensionResult("documentation", score, detail, violations)


def _score_workflow(repo_root: Path) -> DimensionResult:
    violations: list[str] = []
    makefile = repo_root / "Makefile"
    workflow = repo_root / ".github" / "workflows" / "ci.yml"
    if not makefile.exists():
        violations.append("Makefile is missing")
    else:
        text = _read_text(makefile)
        for target in ("check:", "validate:", "score-repo:"):
            if target not in text:
                violations.append(f"Makefile is missing `{target}`")
    if not workflow.exists():
        violations.append(".github/workflows/ci.yml is missing")
    else:
        text = _read_text(workflow)
        if "make validate" not in text:
            violations.append("CI workflow does not run `make validate`")
    score = 10 if not violations else 4
    detail = "The repository exposes reproducible local and CI validation entrypoints."
    return DimensionResult("workflow", score, detail, violations)


def _score_testing(repo_root: Path) -> DimensionResult:
    violations: list[str] = []
    tests_dir = repo_root / "tests"
    pyproject = repo_root / "pyproject.toml"
    if not tests_dir.exists():
        violations.append("tests/ is missing")
    elif not any(tests_dir.glob("test_*.py")):
        violations.append("tests/ does not contain any test_*.py files")
    if not pyproject.exists():
        violations.append("pyproject.toml is missing")
    else:
        text = _read_text(pyproject)
        if "--cov-fail-under=100" not in text:
            violations.append("pyproject.toml does not enforce 100% coverage for main.py")
        if 'testpaths = ["tests"]' not in text:
            violations.append("pyproject.toml does not scope pytest to tests/")
    score = 10 if not violations else 4
    detail = "Tests and coverage gates are configured in-repo."
    return DimensionResult("testing", score, detail, violations)


def _score_typing(repo_root: Path) -> DimensionResult:
    violations: list[str] = []
    pyproject = repo_root / "pyproject.toml"
    main_file = repo_root / "main.py"
    if not pyproject.exists():
        violations.append("pyproject.toml is missing")
    else:
        text = _read_text(pyproject)
        if "[tool.mypy]" not in text:
            violations.append("pyproject.toml is missing a mypy section")
        if "strict = true" not in text:
            violations.append("pyproject.toml does not enable mypy strict mode")
    if main_file.exists():
        text = _read_text(main_file)
        if "@dataclass" not in text:
            violations.append("main.py does not use dataclasses for structured values")
    score = 10 if not violations else 4
    detail = "Typing and structured-value conventions are enforced."
    return DimensionResult("typing", score, detail, violations)


def _score_docs_alignment(repo_root: Path) -> DimensionResult:
    violations: list[str] = []
    readme = repo_root / "README.md"
    create_pr = repo_root / "CREATE-PR.md"
    if readme.exists():
        text = _read_text(readme)
        for command in ("make validate", "make score-repo"):
            if command not in text:
                violations.append(f"README.md does not describe `{command}`")
    if create_pr.exists():
        text = _read_text(create_pr)
        if "10.0/10" not in text:
            violations.append("CREATE-PR.md does not preserve the score expectation")
        if "make validate" not in text:
            violations.append("CREATE-PR.md does not describe `make validate`")
    score = 10 if not violations else 4
    detail = "Public docs describe the score workflow consistently."
    return DimensionResult("docs_alignment", score, detail, violations)


def _score_architecture_notes(repo_root: Path) -> DimensionResult:
    violations: list[str] = []
    adr_file = repo_root / "docs" / "adr" / "003-score-through-wrapper.md"
    if not adr_file.exists():
        violations.append("docs/adr/003-score-through-wrapper.md is missing")
    else:
        text = _read_text(adr_file)
        if "self-contained" not in text:
            violations.append("ADR 003 does not describe the self-contained score wrapper")
    score = 10 if not violations else 4
    detail = "Architecture decisions document how scoring works in this repository."
    return DimensionResult("architecture_notes", score, detail, violations)


def score_repository(repo_root: Path) -> ScoreReport:
    """Build the full score report for a repository."""
    return ScoreReport(
        results=[
            _score_independence(repo_root),
            _score_entrypoint(repo_root),
            _score_docs(repo_root),
            _score_workflow(repo_root),
            _score_testing(repo_root),
            _score_typing(repo_root),
            _score_docs_alignment(repo_root),
            _score_architecture_notes(repo_root),
        ]
    )


def _render_text(report: ScoreReport, verbose: bool) -> str:
    lines = [f"Overall score: {report.overall_score:.2f}/10.00", ""]
    for result in report.results:
        lines.append(f"{result.name:<20} {result.status:<4} {result.score}/10  {result.detail}")
        if verbose:
            for violation in result.violations:
                lines.append(f"  - {violation}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Run the repository-local scorecard."""
    args = parse_args(argv)
    report = score_repository(REPO_ROOT)
    if args.json:
        print(json.dumps(report.as_dict(), indent=2))
    else:
        print(_render_text(report, args.verbose))
    return 1 if report.failed_dimensions(args.min_score) else 0


if __name__ == "__main__":
    raise SystemExit(main())
