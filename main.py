"""Production-ready direct Claude OAuth client.

This module sends direct POST requests to Anthropic's Messages API using the
Claude Code OAuth token stored in ``~/.claude/.credentials.json``.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Protocol, Sequence, TextIO

import requests

__version__ = "0.2.2"

DEFAULT_CREDENTIALS_PATH = Path("~/.claude/.credentials.json").expanduser()
DEFAULT_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_API_PARAMS = {"beta": "true"}
DEFAULT_MODEL = "claude-sonnet-4-6"
ANTHROPIC_VERSION = "2023-06-01"
ANTHROPIC_BETA = "prompt-caching-2024-07-31,claude-code-20250219,oauth-2025-04-20"
BILLING_HEADER = "x-anthropic-billing-header: cc_version=2.1.81; cc_entrypoint=cli; cch=a9fc8;"
CLAUDE_CODE_USER_AGENT = "claude-code/2.1.81"
OAUTH_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
OAUTH_TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
OAUTH_SCOPES = "user:inference user:profile user:sessions:claude_code user:mcp_servers"
TOKEN_REFRESH_BUFFER_SECONDS = 300
DEFAULT_REPO_MAX_FILES = 40
DEFAULT_REPO_MAX_BYTES = 120_000

MODEL_ALIASES = {
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-7",
    "haiku": "claude-haiku-4-5-20251001",
}
MODELS_WITHOUT_SAMPLING_PARAMETERS = {"claude-opus-4-7"}

DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BASE_DELAY = 1.0


class ClaudeAPIError(Exception):
    """Base exception for Claude API errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(ClaudeAPIError):
    """Raised on HTTP 401 — invalid or expired credentials."""


class RateLimitError(ClaudeAPIError):
    """Raised on HTTP 429 — too many requests."""


class ServerError(ClaudeAPIError):
    """Raised on HTTP 5xx — server-side failure."""


class BadRequestError(ClaudeAPIError):
    """Raised on HTTP 400 — malformed request."""


class PermissionDeniedError(ClaudeAPIError):
    """Raised on HTTP 403 — forbidden."""


class NotFoundError(ClaudeAPIError):
    """Raised on HTTP 404 — resource not found."""


_STATUS_TO_EXCEPTION: dict[int, type[ClaudeAPIError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    429: RateLimitError,
}


def _raise_api_error(status_code: int, message: str) -> None:
    """Raise the appropriate typed exception for an HTTP status code."""
    exc_class = _STATUS_TO_EXCEPTION.get(status_code)
    if exc_class is not None:
        raise exc_class(message, status_code=status_code)
    if status_code >= 500:
        raise ServerError(message, status_code=status_code)
    raise ClaudeAPIError(message, status_code=status_code)


@dataclass(frozen=True)
class ChatMessage:
    """Single user or assistant message."""

    role: str
    content: str


@dataclass(frozen=True)
class ClientConfig:
    """Runtime settings for a single request."""

    model: str = DEFAULT_MODEL
    max_tokens: int = 1024
    temperature: float | None = None
    system_prompt: str | None = None
    top_p: float | None = None
    top_k: int | None = None
    stop_sequences: list[str] | None = None
    metadata: dict[str, str] | None = None


@dataclass(frozen=True)
class ClaudeUsage:
    """Normalized Anthropic usage metadata."""

    input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    output_tokens: int = 0
    service_tier: str = ""
    inference_geo: str = ""


@dataclass(frozen=True)
class TokenStatus:
    """Normalized Claude OAuth token status."""

    token_present: bool
    refresh_token_present: bool
    expires_at: int | None
    seconds_remaining: float | None
    is_expired: bool
    should_refresh: bool
    subscription_type: str | None


@dataclass(frozen=True)
class ClaudeResponse:
    """Normalized Claude response payload."""

    identifier: str | None
    role: str
    model: str
    text: str
    stop_reason: str | None
    usage: ClaudeUsage

    def as_api_dict(self) -> dict[str, object]:
        """Return an API-like dictionary representation."""
        return {
            "id": self.identifier,
            "type": "message",
            "role": self.role,
            "model": self.model,
            "content": [{"type": "text", "text": self.text}],
            "stop_reason": self.stop_reason,
            "usage": asdict(self.usage),
        }


class HTTPResponse(Protocol):
    """Minimal streaming response protocol used by the client."""

    def raise_for_status(self) -> None:
        """Raise an exception for non-successful status codes."""

    def iter_lines(self) -> Iterator[bytes]:
        """Yield raw streaming response lines."""


class HTTPSession(Protocol):
    """Minimal session protocol used by the client for HTTP POSTs."""

    def post(self, url: str, **kwargs: object) -> HTTPResponse:
        """Submit an HTTP POST request."""


def load_credentials(credentials_path: Path = DEFAULT_CREDENTIALS_PATH) -> dict[str, object]:
    """Load raw Claude credentials JSON from disk."""
    payload = json.loads(credentials_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid credentials payload in {credentials_path}")
    return payload


def save_credentials(
    credentials: dict[str, object], credentials_path: Path = DEFAULT_CREDENTIALS_PATH
) -> None:
    """Persist updated Claude credentials back to disk with restricted permissions."""
    credentials_path.write_text(json.dumps(credentials), encoding="utf-8")
    credentials_path.chmod(0o600)


def resolve_model(model: str) -> str:
    """Resolve a model alias to a full Anthropic model identifier."""
    return MODEL_ALIASES.get(model, model)


def validate_sampling_parameters(config: ClientConfig) -> None:
    """Reject sampling parameters for models that do not accept them."""
    if config.model not in MODELS_WITHOUT_SAMPLING_PARAMETERS:
        return
    unsupported = [
        name
        for name, value in (
            ("temperature", config.temperature),
            ("top_p", config.top_p),
            ("top_k", config.top_k),
        )
        if value is not None
    ]
    if unsupported:
        parameters = ", ".join(unsupported)
        raise ValueError(f"{config.model} does not support sampling parameters: {parameters}")


def load_claude_code_token(credentials_path: Path = DEFAULT_CREDENTIALS_PATH) -> str:
    """Load the Claude Code OAuth access token from disk."""
    payload = load_credentials(credentials_path)
    oauth = payload.get("claudeAiOauth", {})
    if not isinstance(oauth, dict):
        raise ValueError(f"Invalid Claude OAuth payload in {credentials_path}")
    token = oauth.get("accessToken")
    if not isinstance(token, str) or not token:
        raise ValueError(f"No Claude access token found in {credentials_path}")
    return token


def get_token_status(credentials_path: Path = DEFAULT_CREDENTIALS_PATH) -> TokenStatus:
    """Inspect the Claude OAuth token state without making network calls."""
    payload = load_credentials(credentials_path)
    oauth = payload.get("claudeAiOauth", {})
    if not isinstance(oauth, dict):
        raise ValueError(f"Invalid Claude OAuth payload in {credentials_path}")
    token = oauth.get("accessToken")
    refresh_token = oauth.get("refreshToken")
    expires_at = oauth.get("expiresAt")
    seconds_remaining: float | None = None
    is_expired = False
    should_refresh = False
    if isinstance(expires_at, int):
        seconds_remaining = round((expires_at - time.time() * 1000) / 1000, 2)
        is_expired = seconds_remaining <= 0
        should_refresh = seconds_remaining <= TOKEN_REFRESH_BUFFER_SECONDS
    return TokenStatus(
        token_present=isinstance(token, str) and bool(token),
        refresh_token_present=isinstance(refresh_token, str) and bool(refresh_token),
        expires_at=expires_at if isinstance(expires_at, int) else None,
        seconds_remaining=seconds_remaining,
        is_expired=is_expired,
        should_refresh=should_refresh,
        subscription_type=oauth.get("subscriptionType")
        if isinstance(oauth.get("subscriptionType"), str)
        else None,
    )


def format_epoch_millis(epoch_millis: int | None) -> str | None:
    """Render epoch milliseconds as a human-friendly UTC timestamp."""
    if epoch_millis is None:
        return None
    return datetime.fromtimestamp(epoch_millis / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


def format_seconds_remaining(seconds: float | None) -> str | None:
    """Render a remaining-duration value as a human-friendly string."""
    if seconds is None:
        return None
    total_seconds = int(abs(seconds))
    days, remainder = divmod(total_seconds, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, secs = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if minutes or hours or days:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    formatted = " ".join(parts)
    return f"-{formatted}" if seconds < 0 else formatted


def refresh_claude_code_token(credentials_path: Path = DEFAULT_CREDENTIALS_PATH) -> str:
    """Refresh the Claude Code OAuth access token and persist the new credentials."""
    payload = load_credentials(credentials_path)
    oauth = payload.get("claudeAiOauth", {})
    if not isinstance(oauth, dict):
        raise ValueError(f"Invalid Claude OAuth payload in {credentials_path}")
    refresh_token = oauth.get("refreshToken")
    if not isinstance(refresh_token, str) or not refresh_token:
        raise ValueError(f"No Claude refresh token found in {credentials_path}")

    response: requests.Response | None = None
    for attempt in range(5):
        response = requests.post(
            OAUTH_TOKEN_URL,
            headers={
                "Content-Type": "application/json",
                "User-Agent": CLAUDE_CODE_USER_AGENT,
            },
            json={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": OAUTH_CLIENT_ID,
                "scope": OAUTH_SCOPES,
            },
            timeout=15,
        )
        if response.status_code != 429:
            break
        time.sleep(2**attempt)
    assert response is not None
    if response.status_code == 429:
        raise RuntimeError(
            "Claude OAuth token refresh is rate-limited by platform.claude.com. "
            "Wait and retry, or refresh the Claude login with the official client."
        )
    response.raise_for_status()
    refreshed = response.json()
    if not isinstance(refreshed, dict):
        raise ValueError("OAuth refresh response was not a JSON object")
    access_token = refreshed.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise ValueError("OAuth refresh response did not include access_token")

    expires_in = refreshed.get("expires_in")
    expires_at = (
        int(time.time() * 1000) + (expires_in if isinstance(expires_in, int) else 3600) * 1000
    )
    payload["claudeAiOauth"] = {
        **oauth,
        "accessToken": access_token,
        "refreshToken": refreshed.get("refresh_token", refresh_token),
        "expiresAt": expires_at,
    }
    save_credentials(payload, credentials_path)
    return access_token


def load_fresh_claude_code_token(credentials_path: Path = DEFAULT_CREDENTIALS_PATH) -> str:
    """Load a usable Claude Code OAuth token, refreshing it when near expiry."""
    payload = load_credentials(credentials_path)
    oauth = payload.get("claudeAiOauth", {})
    if not isinstance(oauth, dict):
        raise ValueError(f"Invalid Claude OAuth payload in {credentials_path}")
    token = oauth.get("accessToken")
    expires_at = oauth.get("expiresAt")
    if not isinstance(token, str) or not token:
        raise ValueError(f"No Claude access token found in {credentials_path}")
    if isinstance(expires_at, int):
        seconds_remaining = (expires_at - time.time() * 1000) / 1000
        if seconds_remaining <= TOKEN_REFRESH_BUFFER_SECONDS:
            return refresh_claude_code_token(credentials_path)
    return token


def build_headers(auth_token: str) -> dict[str, str]:
    """Build the HTTP headers required for direct Claude OAuth access."""
    return {
        "Authorization": f"Bearer {auth_token}",
        "anthropic-version": ANTHROPIC_VERSION,
        "anthropic-beta": ANTHROPIC_BETA,
        "anthropic-dangerous-direct-browser-access": "true",
        "x-app": "cli",
        "User-Agent": CLAUDE_CODE_USER_AGENT,
        "content-type": "application/json",
    }


def supported_models() -> list[tuple[str, str]]:
    """Return supported model aliases and their resolved identifiers."""
    return sorted(MODEL_ALIASES.items())


def build_request_kwargs(auth_token: str, payload: dict[str, object]) -> dict[str, object]:
    """Build the requests.post keyword arguments for a Claude API call."""
    return {
        "headers": build_headers(auth_token),
        "json": payload,
        "params": DEFAULT_API_PARAMS,
        "stream": True,
        "timeout": 300,
    }


def _should_skip_repo_entry(path: Path) -> bool:
    """Return True when a repository entry should not be included in prompt context."""
    blocked_parts = {".git", ".venv", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache"}
    return any(part in blocked_parts for part in path.parts)


def _read_repo_file(path: Path, max_bytes: int) -> str | None:
    """Read a repository file as UTF-8 text within a byte budget."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data:
        return None
    truncated = data[:max_bytes]
    try:
        text = truncated.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if len(data) > max_bytes:
        text += "\n... [truncated]"
    return text


def build_repo_context(
    repo_path: Path,
    max_files: int = DEFAULT_REPO_MAX_FILES,
    max_bytes: int = DEFAULT_REPO_MAX_BYTES,
) -> str:
    """Build a bounded textual snapshot of a repository for prompt context."""
    resolved = repo_path.resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"Repository path does not exist or is not a directory: {repo_path}")

    parts: list[str] = [f"# Repository Snapshot: {resolved}"]
    total_bytes = 0
    files_added = 0
    for path in sorted(resolved.rglob("*")):
        if not path.is_file() or _should_skip_repo_entry(path):
            continue
        if files_added >= max_files or total_bytes >= max_bytes:
            break
        remaining = max_bytes - total_bytes
        text = _read_repo_file(path, remaining)
        if text is None:
            continue
        rel = path.relative_to(resolved)
        parts.append(f"\n## {rel}\n```text\n{text}\n```")
        total_bytes += len(text.encode("utf-8"))
        files_added += 1
    if files_added == 0:
        raise ValueError(f"No readable text files found under {repo_path}")
    return "\n".join(parts)


def build_prompt_with_repo_context(
    prompt: str,
    repo_path: Path,
    max_files: int = DEFAULT_REPO_MAX_FILES,
    max_bytes: int = DEFAULT_REPO_MAX_BYTES,
) -> str:
    """Combine a user prompt with a repository snapshot."""
    repo_context = build_repo_context(repo_path, max_files=max_files, max_bytes=max_bytes)
    return f"{prompt}\n\n{repo_context}"


def build_system_blocks(config: ClientConfig, working_directory: Path) -> list[dict[str, object]]:
    """Build the minimum Claude Code-compatible system blocks."""
    prompt = config.system_prompt or "You are Claude."
    environment = (
        "# Environment\n"
        f"- Working directory: {working_directory}\n"
        f"- Platform: {platform.system().lower()}\n"
        f"- Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"
        f"- Model: {config.model}"
    )
    return [
        {"type": "text", "text": BILLING_HEADER},
        {
            "type": "text",
            "text": prompt,
            "cache_control": {"type": "ephemeral"},
        },
        {"type": "text", "text": environment},
    ]


def build_payload(
    messages: Sequence[ChatMessage],
    config: ClientConfig,
    working_directory: Path,
) -> dict[str, object]:
    """Build the direct Messages API payload."""
    validate_sampling_parameters(config)
    payload: dict[str, object] = {
        "model": config.model,
        "messages": [asdict(message) for message in messages],
        "max_tokens": config.max_tokens,
        "system": build_system_blocks(config, working_directory),
        "tools": [],
        "stream": True,
    }
    if config.temperature is not None:
        payload["temperature"] = config.temperature
    if config.top_p is not None:
        payload["top_p"] = config.top_p
    if config.top_k is not None:
        payload["top_k"] = config.top_k
    if config.stop_sequences is not None:
        payload["stop_sequences"] = config.stop_sequences
    if config.metadata is not None:
        payload["metadata"] = config.metadata
    return payload


def decode_sse_events(lines: Iterable[bytes]) -> Iterator[dict[str, object]]:
    """Yield parsed JSON SSE payloads from raw response lines."""
    for raw_line in lines:
        if not raw_line:
            continue
        line = raw_line.decode("utf-8")
        if not line.startswith("data: "):
            continue
        try:
            parsed = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            yield parsed


def _usage_from_payload(payload: object, current: ClaudeUsage) -> ClaudeUsage:
    """Merge partial usage payloads into a normalized usage object."""
    if not isinstance(payload, dict):
        return current
    return ClaudeUsage(
        input_tokens=payload["input_tokens"]
        if isinstance(payload.get("input_tokens"), int)
        else current.input_tokens,
        cache_creation_input_tokens=(
            payload["cache_creation_input_tokens"]
            if isinstance(payload.get("cache_creation_input_tokens"), int)
            else current.cache_creation_input_tokens
        ),
        cache_read_input_tokens=(
            payload["cache_read_input_tokens"]
            if isinstance(payload.get("cache_read_input_tokens"), int)
            else current.cache_read_input_tokens
        ),
        output_tokens=payload["output_tokens"]
        if isinstance(payload.get("output_tokens"), int)
        else current.output_tokens,
        service_tier=payload["service_tier"]
        if isinstance(payload.get("service_tier"), str)
        else current.service_tier,
        inference_geo=payload["inference_geo"]
        if isinstance(payload.get("inference_geo"), str)
        else current.inference_geo,
    )


def response_from_stream(events: Iterable[dict[str, object]], model: str) -> ClaudeResponse:
    """Aggregate Messages API stream events into a normalized response."""
    identifier: str | None = None
    role = "assistant"
    stop_reason: str | None = None
    text_parts: list[str] = []
    usage = ClaudeUsage()

    for event in events:
        event_type = event.get("type")
        if event_type == "message_start":
            message = event.get("message", {})
            if isinstance(message, dict):
                if isinstance(message.get("id"), str):
                    identifier = message["id"]
                if isinstance(message.get("role"), str):
                    role = message["role"]
                usage = _usage_from_payload(message.get("usage"), usage)
        elif event_type == "content_block_delta":
            delta = event.get("delta", {})
            if isinstance(delta, dict) and isinstance(delta.get("text"), str):
                text_parts.append(delta["text"])
        elif event_type == "message_delta":
            delta = event.get("delta", {})
            if isinstance(delta, dict) and isinstance(delta.get("stop_reason"), str):
                stop_reason = delta["stop_reason"]
            usage = _usage_from_payload(event.get("usage"), usage)
        elif event_type == "message_stop":
            break

    return ClaudeResponse(
        identifier=identifier,
        role=role,
        model=model,
        text="".join(text_parts),
        stop_reason=stop_reason,
        usage=usage,
    )


class ClaudeNativeOAuthClient:
    """Direct HTTP client for Anthropic's Messages API with Claude Code OAuth."""

    def __init__(
        self,
        auth_token: str,
        api_url: str = DEFAULT_API_URL,
        working_directory: Path | None = None,
        session: HTTPSession | None = None,
        credentials_path: Path = DEFAULT_CREDENTIALS_PATH,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_base_delay: float = DEFAULT_RETRY_BASE_DELAY,
    ) -> None:
        self._auth_token = auth_token
        self._api_url = api_url
        self._working_directory = working_directory or Path.cwd()
        self._session = session or requests
        self._credentials_path = credentials_path
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay

    def create_message(
        self,
        messages: Sequence[ChatMessage],
        config: ClientConfig | None = None,
    ) -> ClaudeResponse:
        """Send a direct POST request and aggregate the streamed response."""
        effective_config = config or ClientConfig()
        events = self._request_events(messages, effective_config)
        return response_from_stream(events, effective_config.model)

    def _post(self, payload: dict[str, object]) -> HTTPResponse:
        """POST the request payload with token refresh on 401 and retries on 429/5xx."""
        refreshed = False
        last_status: int | None = None

        for attempt in range(1 + self._max_retries):
            response = self._session.post(
                self._api_url, **build_request_kwargs(self._auth_token, payload)
            )
            try:
                response.raise_for_status()
                return response
            except requests.HTTPError as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if status_code is None:
                    raise

                if status_code == 401 and not refreshed:
                    refreshed = True
                    self._auth_token = refresh_claude_code_token(self._credentials_path)
                    continue

                if status_code == 429 or status_code >= 500:
                    last_status = status_code
                    if attempt < self._max_retries:
                        time.sleep(self._retry_base_delay * (2**attempt))
                        continue

                _raise_api_error(status_code, str(exc))

        _raise_api_error(last_status or 500, "Request failed after retries")  # pragma: no cover
        return response  # pragma: no cover

    def _request_events(
        self,
        messages: Sequence[ChatMessage],
        config: ClientConfig,
    ) -> Iterator[dict[str, object]]:
        """Submit a request and yield decoded SSE events."""
        payload = build_payload(messages, config, self._working_directory)
        response = self._post(payload)
        return decode_sse_events(response.iter_lines())

    def chat(
        self,
        prompt: str,
        config: ClientConfig | None = None,
    ) -> ClaudeResponse:
        """Send a single user prompt."""
        return self.create_message([ChatMessage(role="user", content=prompt)], config=config)

    def stream_text(
        self,
        prompt: str,
        config: ClientConfig | None = None,
    ) -> Iterator[str]:
        """Yield text deltas as they arrive."""
        effective_config = config or ClientConfig()
        for event in self._request_events(
            [ChatMessage(role="user", content=prompt)], effective_config
        ):
            if event.get("type") != "content_block_delta":
                continue
            delta = event.get("delta", {})
            if isinstance(delta, dict) and isinstance(delta.get("text"), str):
                yield delta["text"]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Direct Claude OAuth client")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--token-status", action="store_true", help="Print Claude OAuth token status and exit"
    )
    parser.add_argument(
        "--list-models", action="store_true", help="List supported model aliases and exit"
    )
    parser.add_argument("prompt", nargs="?", help="Prompt text.")
    parser.add_argument("--model", default="sonnet", help="Model alias or full model id")
    parser.add_argument("--max-tokens", type=int, default=256, help="Maximum output tokens")
    parser.add_argument("--temperature", type=float, default=None, help="Sampling temperature")
    parser.add_argument("--system-prompt", default=None, help="Optional system prompt override")
    parser.add_argument("--top-p", type=float, default=None, help="Nucleus sampling threshold")
    parser.add_argument("--top-k", type=int, default=None, help="Top-k sampling cutoff")
    parser.add_argument(
        "--stop-sequences", nargs="+", default=None, help="One or more stop sequences"
    )
    parser.add_argument(
        "--repo", type=Path, default=None, help="Repository directory to read into the prompt"
    )
    parser.add_argument(
        "--repo-max-files",
        type=int,
        default=DEFAULT_REPO_MAX_FILES,
        help="Maximum repository files to include",
    )
    parser.add_argument(
        "--repo-max-bytes",
        type=int,
        default=DEFAULT_REPO_MAX_BYTES,
        help="Maximum repository bytes to include",
    )
    parser.add_argument(
        "--credentials-path",
        type=Path,
        default=DEFAULT_CREDENTIALS_PATH,
        help="Path to Claude credentials JSON",
    )
    parser.add_argument("--json", action="store_true", help="Emit structured JSON output")
    parser.add_argument("--stream", action="store_true", help="Print streamed text deltas")
    return parser.parse_args(list(argv) if argv is not None else None)


def read_prompt(args: argparse.Namespace, stdin: TextIO) -> str:
    """Resolve prompt text from argv and fail fast when absent."""
    if isinstance(args.prompt, str) and args.prompt.strip():
        return args.prompt
    raise ValueError("A prompt argument is required")


def handle_token_status(args: argparse.Namespace, stdout: TextIO) -> int:
    """Print token status and exit."""
    status = get_token_status(args.credentials_path)
    payload = asdict(status)
    payload["expires_at"] = format_epoch_millis(status.expires_at)
    payload["seconds_remaining"] = format_seconds_remaining(status.seconds_remaining)
    stdout.write(json.dumps(payload, indent=2))
    stdout.write("\n")
    return 0


def handle_list_models(stdout: TextIO) -> int:
    """Print supported models and exit."""
    payload = {
        "default": DEFAULT_MODEL,
        "aliases": [{"alias": alias, "model": model} for alias, model in supported_models()],
    }
    stdout.write(json.dumps(payload, indent=2))
    stdout.write("\n")
    return 0


def main(
    argv: Sequence[str] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """CLI entrypoint."""
    out = stdout or sys.stdout
    err = stderr or sys.stderr
    args = parse_args(argv)

    try:
        if args.token_status:
            return handle_token_status(args, out)
        if args.list_models:
            return handle_list_models(out)

        prompt = read_prompt(args, sys.stdin)
        if args.repo is not None:
            prompt = build_prompt_with_repo_context(
                prompt,
                args.repo,
                max_files=args.repo_max_files,
                max_bytes=args.repo_max_bytes,
            )

        config = ClientConfig(
            model=resolve_model(args.model),
            max_tokens=args.max_tokens,
            temperature=args.temperature,
            system_prompt=args.system_prompt,
            top_p=args.top_p,
            top_k=args.top_k,
            stop_sequences=args.stop_sequences,
        )
        validate_sampling_parameters(config)
        token = load_fresh_claude_code_token(args.credentials_path)
        client = ClaudeNativeOAuthClient(token, credentials_path=args.credentials_path)
        if args.stream:
            for chunk in client.stream_text(prompt, config):
                out.write(chunk)
                out.flush()
            out.write("\n")
            return 0

        response = client.chat(prompt, config)
        if args.json:
            out.write(json.dumps(response.as_api_dict(), indent=2))
            out.write("\n")
            return 0

        out.write(response.text)
        out.write("\n")
        return 0
    except Exception as exc:
        err.write(f"Error: {exc}\n")
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
