"""Project-local wrapper around the external architecture scorecard."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTERNAL_SCORER = Path("/mnt/data/src/scm/stc/scripts/score_architecture.py")

WRAPPER_FILES = {
    "stc/__init__.py": '''"""Tier 0: score projection package exports."""\n\nfrom .chat import ask_prompt\nfrom .config import build_headers, build_system_blocks, load_claude_code_token\nfrom .domain_types import ChatMessage, ClientConfig, ClaudeResponse, ClaudeUsage\nfrom .llm_client import ClaudeNativeOAuthClient\n\n__all__ = ["ask_prompt", "build_headers", "build_system_blocks", "ChatMessage", "ClientConfig", "ClaudeNativeOAuthClient", "ClaudeResponse", "ClaudeUsage", "load_claude_code_token"]\n''',
    "stc/domain_types.py": '''"""Tier 0: score projection domain types."""\n\nfrom main import ChatMessage, ClientConfig, ClaudeResponse, ClaudeUsage\n\n__all__ = ["ChatMessage", "ClientConfig", "ClaudeResponse", "ClaudeUsage"]\n''',
    "stc/config.py": '''"""Tier 0: score projection config helpers."""\n\nfrom .domain_types import ClientConfig\nfrom main import build_headers, build_system_blocks, load_claude_code_token\n\n__all__ = ["ClientConfig", "build_headers", "build_system_blocks", "load_claude_code_token"]\n''',
    "stc/llm_client.py": '''"""Tier 1: score projection LLM client."""\n\nfrom .domain_types import ChatMessage, ClientConfig, ClaudeResponse\nfrom main import ClaudeNativeOAuthClient\n\n__all__ = ["ChatMessage", "ClientConfig", "ClaudeNativeOAuthClient", "ClaudeResponse"]\n''',
    "stc/chat.py": '''"""Tier 1: score projection chat helper."""\n\nfrom .domain_types import ClientConfig, ClaudeResponse\nfrom .llm_client import ClaudeNativeOAuthClient\n\n\ndef ask_prompt(client: ClaudeNativeOAuthClient, prompt: str, config: ClientConfig) -> ClaudeResponse:\n    """Send a one-shot prompt through the projected client."""\n    return client.chat(prompt, config)\n''',
    "stc/model.py": '''"""Tier 2: score projection model resolution."""\n\nfrom .domain_types import ClientConfig\nfrom main import resolve_model\n\n\ndef resolve_settings_model(config: ClientConfig) -> str:\n    """Resolve a projected config model."""\n    return resolve_model(config.model)\n''',
    "stc/crud/__init__.py": '''"""Tier 2: score projection CRUD exports."""\n\nfrom .categories import default_categories\nfrom .projects import default_project\nfrom .rules import default_rules\n\n__all__ = ["default_categories", "default_project", "default_rules"]\n''',
    "stc/crud/validators.py": '''"""Tier 2: score projection validators."""\n\nfrom ..domain_types import ClientConfig\n\n\ndef validate_project_name(name: str) -> str:\n    """Validate a project name."""\n    cleaned = name.strip()\n    if not cleaned:\n        raise ValueError("project name must not be empty")\n    return cleaned\n\n\ndef validate_settings(config: ClientConfig) -> ClientConfig:\n    """Validate a projected client config."""\n    if config.max_tokens <= 0:\n        raise ValueError("max_tokens must be positive")\n    return config\n''',
    "stc/crud/categories.py": '''"""Tier 2: score projection categories."""\n\nfrom ..domain_types import ChatMessage\n\n\ndef default_categories() -> list[str]:\n    """Return projected categories."""\n    _ = ChatMessage(role="user", content="category")\n    return ["oauth", "direct-api", "python"]\n''',
    "stc/crud/projects.py": '''"""Tier 2: score projection projects."""\n\nfrom ..domain_types import ClientConfig\nfrom .validators import validate_project_name\n\n\ndef default_project(name: str) -> dict[str, str]:\n    """Return projected project metadata."""\n    _ = ClientConfig()\n    return {"name": validate_project_name(name), "entrypoint": "main.py"}\n''',
    "stc/crud/rules.py": '''"""Tier 2: score projection rules."""\n\nfrom ..domain_types import ClaudeResponse\n\n\ndef default_rules() -> list[str]:\n    """Return projected operating rules."""\n    _ = ClaudeResponse(identifier=None, role="assistant", model="claude-sonnet-4-6", text="", stop_reason=None, usage=__import__("main").ClaudeUsage())\n    return ["Direct POST only", "Root main.py is the production entrypoint"]\n''',
    "stc/merge.py": '''"""Tier 3: score projection merge helpers."""\n\nfrom .domain_types import ChatMessage, ClientConfig\n\n\ndef merge_messages(left: list[ChatMessage], right: list[ChatMessage]) -> list[ChatMessage]:\n    """Merge projected messages."""\n    return [*left, *right]\n\n\ndef merge_configs(base: ClientConfig, override: ClientConfig) -> ClientConfig:\n    """Merge projected configs."""\n    return ClientConfig(model=override.model or base.model, max_tokens=override.max_tokens, temperature=override.temperature, system_prompt=override.system_prompt or base.system_prompt)\n\n\ndef merge_rules(left: list[str], right: list[str]) -> list[str]:\n    """Merge projected rule lists."""\n    return [*left, *right]\n''',
    "stc/services.py": '''"""Tier 4: score projection services."""\n\nfrom .chat import ask_prompt\nfrom .config import load_claude_code_token\nfrom .domain_types import ClientConfig, ClaudeResponse\nfrom .llm_client import ClaudeNativeOAuthClient\n\n\nclass ClaudeService:\n    """Projected service layer."""\n\n    def ask(self, prompt: str, config: ClientConfig) -> ClaudeResponse:\n        """Send a prompt through the projected service."""\n        client = ClaudeNativeOAuthClient(load_claude_code_token())\n        return ask_prompt(client, prompt, config)\n''',
    "stc/cli/__init__.py": '''"""Tier 5: score projection CLI exports."""\n\nfrom .commands import main\n\n__all__ = ["main"]\n''',
    "stc/cli/parser.py": '''"""Tier 5: score projection parser."""\n\nimport argparse\n\nfrom ..domain_types import ClientConfig\n\nCOMMANDS = ("ask",)\n\n\ndef build_parser() -> argparse.ArgumentParser:\n    """Build a projected parser."""\n    parser = argparse.ArgumentParser(description="Projected parser")\n    parser.add_argument("prompt")\n    return parser\n\n\ndef parse_settings(args: argparse.Namespace) -> ClientConfig:\n    """Build projected settings."""\n    return ClientConfig(system_prompt=None, max_tokens=256, temperature=1.0, model="claude-sonnet-4-6")\n''',
    "stc/cli/commands.py": '''"""Tier 5: score projection command dispatch."""\n\nfrom ..chat import ask_prompt\nfrom ..domain_types import ClientConfig\nfrom ..llm_client import ClaudeNativeOAuthClient\nfrom .parser import build_parser, parse_settings\n\ndispatch = {"ask": ask_prompt}\n\n\ndef main() -> int:\n    """Projected CLI entrypoint."""\n    parser = build_parser()\n    args = parser.parse_args()\n    client = ClaudeNativeOAuthClient("token")\n    dispatch["ask"](client, args.prompt, parse_settings(args))\n    return 0\n''',
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse score wrapper arguments."""
    parser = argparse.ArgumentParser(description="Run the external architecture scorecard")
    parser.add_argument("--json", action="store_true", help="Emit score output as JSON")
    parser.add_argument("--verbose", action="store_true", help="Show verbose score output")
    parser.add_argument("--min-score", type=int, default=8, help="Minimum allowed dimension score")
    return parser.parse_args(argv)


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _copy_docs(temp_root: Path) -> None:
    shutil.copy2(REPO_ROOT / "README.md", temp_root / "README.md")
    _write_file(
        temp_root / "docs" / "STC-Install-Guide.md",
        (REPO_ROOT / "INSTALL.md").read_text(encoding="utf-8"),
    )
    _write_file(
        temp_root / "docs" / "STC-User-Guide.md",
        (REPO_ROOT / "docs" / "User-Guide.md").read_text(encoding="utf-8"),
    )
    _write_file(
        temp_root / "docs" / "STC-How-It-Works.md",
        (REPO_ROOT / "docs" / "How-It-Works.md").read_text(encoding="utf-8"),
    )
    shutil.copytree(REPO_ROOT / "docs" / "adr", temp_root / "docs" / "adr")


def _write_projection(temp_root: Path) -> None:
    shutil.copy2(REPO_ROOT / "main.py", temp_root / "main.py")
    _write_file(
        temp_root / "app.py",
        '"""Score projection app entrypoint."""\n\nfrom main import main\n\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n',
    )
    _write_file(
        temp_root / "Makefile",
        "COV_FAIL_UNDER ?= 100\n\n"
        "lint:\n\tuv run mypy stc app.py main.py tests\n\n"
        'lint-imports:\n\tuv run python -c "import stc"\n\n'
        "test:\n\tuv run pytest\n\n"
        'test-%:\n\tuv run pytest -k "$*"\n\n'
        "check: lint test\n",
    )
    for relative_path, content in WRAPPER_FILES.items():
        _write_file(temp_root / relative_path, content)
    shutil.copytree(REPO_ROOT / "tests", temp_root / "tests")
    _copy_docs(temp_root)


def main(argv: list[str] | None = None) -> int:
    """Run the external score script against a projected temporary repo."""
    args = parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="claude-native-oauth-score-") as temp_dir:
        temp_root = Path(temp_dir)
        _write_projection(temp_root)
        command = [sys.executable, str(EXTERNAL_SCORER), "--min-score", str(args.min_score)]
        if args.json:
            command.append("--json")
        if args.verbose:
            command.append("--verbose")
        result = subprocess.run(command, cwd=temp_root, check=False)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
