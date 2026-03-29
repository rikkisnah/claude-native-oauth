"""Unit tests for the production direct OAuth client."""

from __future__ import annotations

import io
import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Iterator, cast

import pytest
import requests

import main
from tests.helpers import sse_data


class FakeResponse:
    """Minimal response stub for streaming tests."""

    def __init__(self, lines: list[bytes]) -> None:
        self._lines = lines

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self) -> Iterator[bytes]:
        return iter(self._lines)


class FakeSession:
    """Minimal requests-compatible session stub."""

    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return self.response


class RefreshResponse:
    """Response stub for OAuth refresh tests."""

    def __init__(self, status_code: int, payload: object | None = None) -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            error = requests.HTTPError(f"HTTP {self.status_code}")
            error.response = SimpleNamespace(status_code=self.status_code)
            raise error

    def json(self) -> object:
        return self._payload


class OneTime401Response(FakeResponse):
    """Response stub that fails once with 401 and succeeds on retry."""

    def __init__(self, lines: list[bytes], should_fail: bool) -> None:
        super().__init__(lines)
        self._should_fail = should_fail

    def raise_for_status(self) -> None:
        if self._should_fail:
            error = requests.HTTPError("HTTP 401")
            error.response = SimpleNamespace(status_code=401)
            raise error


class SequencedSession:
    """Session stub that returns responses in sequence."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = responses
        self.calls: list[dict[str, object]] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return self._responses.pop(0)


@pytest.mark.parametrize(
    ("alias", "expected"),
    [("sonnet", "claude-sonnet-4-6"), ("opus", "claude-opus-4-6"), ("custom", "custom")],
)
def test_resolve_model(alias: str, expected: str) -> None:
    """Model aliases should resolve predictably."""
    assert main.resolve_model(alias) == expected


def test_version_is_defined() -> None:
    """The module should expose a project version."""
    assert main.__version__ == "0.1.1"


def test_get_token_status(credentials_path: Path) -> None:
    """Token status should report expiry and refresh metadata."""
    credentials_path.write_text(
        json.dumps(
            {
                "claudeAiOauth": {
                    "accessToken": "token-123",
                    "refreshToken": "refresh-123",
                    "expiresAt": int(time.time() * 1000) + 60_000,
                    "subscriptionType": "max",
                }
            }
        ),
        encoding="utf-8",
    )
    status = main.get_token_status(credentials_path)
    assert status.token_present is True
    assert status.refresh_token_present is True
    assert status.is_expired is False
    assert status.should_refresh is True
    assert status.subscription_type == "max"


def test_get_token_status_rejects_invalid_oauth_payload(credentials_path: Path) -> None:
    """Token status requires an object-shaped OAuth payload."""
    credentials_path.write_text(json.dumps({"claudeAiOauth": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        main.get_token_status(credentials_path)


def test_load_claude_code_token(credentials_path: Path) -> None:
    """The OAuth token loader should read the expected field."""
    credentials_path.write_text(
        json.dumps({"claudeAiOauth": {"accessToken": "token-123"}}),
        encoding="utf-8",
    )
    assert main.load_claude_code_token(credentials_path) == "token-123"


def test_load_credentials_rejects_non_object(credentials_path: Path) -> None:
    """Credential loading should reject non-object JSON payloads."""
    credentials_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError):
        main.load_credentials(credentials_path)


def test_save_credentials_round_trips(credentials_path: Path) -> None:
    """Saving credentials should persist JSON to disk."""
    payload: dict[str, object] = {"claudeAiOauth": {"accessToken": "token-123"}}
    main.save_credentials(payload, credentials_path)
    assert main.load_credentials(credentials_path) == payload


def test_load_claude_code_token_rejects_missing_field(credentials_path: Path) -> None:
    """Missing OAuth token fields should fail loudly."""
    credentials_path.write_text(json.dumps({"claudeAiOauth": {}}), encoding="utf-8")
    with pytest.raises(ValueError):
        main.load_claude_code_token(credentials_path)


def test_load_claude_code_token_rejects_invalid_oauth_payload(credentials_path: Path) -> None:
    """OAuth payloads must be JSON objects."""
    credentials_path.write_text(json.dumps({"claudeAiOauth": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        main.load_claude_code_token(credentials_path)


def test_build_headers() -> None:
    """Header construction should match the direct OAuth contract."""
    headers = main.build_headers("secret")
    assert headers["Authorization"] == "Bearer secret"
    assert headers["x-app"] == "cli"
    assert "oauth-2025-04-20" in headers["anthropic-beta"]


def test_supported_models() -> None:
    """Supported model listing should include the known aliases."""
    assert ("sonnet", "claude-sonnet-4-6") in main.supported_models()


def test_refresh_claude_code_token_updates_credentials(
    monkeypatch: pytest.MonkeyPatch,
    credentials_path: Path,
) -> None:
    """Refreshing the token should persist the new access token."""
    credentials_path.write_text(
        json.dumps({"claudeAiOauth": {"refreshToken": "refresh-123", "accessToken": "old"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "main.requests.post",
        lambda *args, **kwargs: RefreshResponse(
            200,
            {"access_token": "new-token", "refresh_token": "new-refresh", "expires_in": 60},
        ),
    )
    token = main.refresh_claude_code_token(credentials_path)
    saved = main.load_credentials(credentials_path)
    oauth = saved["claudeAiOauth"]
    assert token == "new-token"
    assert isinstance(oauth, dict)
    assert oauth["accessToken"] == "new-token"
    assert oauth["refreshToken"] == "new-refresh"


def test_refresh_claude_code_token_rejects_invalid_oauth_payload(credentials_path: Path) -> None:
    """Refresh requires a JSON-object OAuth payload."""
    credentials_path.write_text(json.dumps({"claudeAiOauth": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        main.refresh_claude_code_token(credentials_path)


def test_refresh_claude_code_token_rejects_missing_refresh_token(credentials_path: Path) -> None:
    """Refresh requires a stored refresh token."""
    credentials_path.write_text(json.dumps({"claudeAiOauth": {"accessToken": "old"}}), encoding="utf-8")
    with pytest.raises(ValueError):
        main.refresh_claude_code_token(credentials_path)


def test_refresh_claude_code_token_handles_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
    credentials_path: Path,
) -> None:
    """Refresh should raise a clear error when all attempts are rate-limited."""
    credentials_path.write_text(
        json.dumps({"claudeAiOauth": {"refreshToken": "refresh-123", "accessToken": "old"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr("main.requests.post", lambda *args, **kwargs: RefreshResponse(429))
    monkeypatch.setattr("main.time.sleep", lambda seconds: None)
    with pytest.raises(RuntimeError):
        main.refresh_claude_code_token(credentials_path)


def test_refresh_claude_code_token_rejects_non_object_response(
    monkeypatch: pytest.MonkeyPatch,
    credentials_path: Path,
) -> None:
    """Refresh responses must be JSON objects."""
    credentials_path.write_text(
        json.dumps({"claudeAiOauth": {"refreshToken": "refresh-123", "accessToken": "old"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr("main.requests.post", lambda *args, **kwargs: RefreshResponse(200, ["bad"]))
    with pytest.raises(ValueError):
        main.refresh_claude_code_token(credentials_path)


def test_refresh_claude_code_token_rejects_missing_access_token(
    monkeypatch: pytest.MonkeyPatch,
    credentials_path: Path,
) -> None:
    """Refresh responses must include an access token."""
    credentials_path.write_text(
        json.dumps({"claudeAiOauth": {"refreshToken": "refresh-123", "accessToken": "old"}}),
        encoding="utf-8",
    )
    monkeypatch.setattr("main.requests.post", lambda *args, **kwargs: RefreshResponse(200, {}))
    with pytest.raises(ValueError):
        main.refresh_claude_code_token(credentials_path)


def test_load_fresh_claude_code_token_refreshes_when_expired(
    monkeypatch: pytest.MonkeyPatch,
    credentials_path: Path,
) -> None:
    """Expired access tokens should trigger refresh."""
    credentials_path.write_text(
        json.dumps(
            {
                "claudeAiOauth": {
                    "accessToken": "old-token",
                    "refreshToken": "refresh-123",
                    "expiresAt": 0,
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "refresh_claude_code_token", lambda path: "fresh-token")
    assert main.load_fresh_claude_code_token(credentials_path) == "fresh-token"


def test_load_fresh_claude_code_token_rejects_invalid_oauth_payload(credentials_path: Path) -> None:
    """Fresh token loading requires an object-shaped OAuth payload."""
    credentials_path.write_text(json.dumps({"claudeAiOauth": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        main.load_fresh_claude_code_token(credentials_path)


def test_build_system_blocks() -> None:
    """System blocks should include the billing header and environment block."""
    config = main.ClientConfig(model="claude-sonnet-4-6", system_prompt="Act carefully.")
    blocks = main.build_system_blocks(config, Path("/repo"))
    assert blocks[0]["text"] == main.BILLING_HEADER
    assert blocks[1]["text"] == "Act carefully."
    assert "Working directory: /repo" in str(blocks[2]["text"])


def test_build_repo_context(tmp_path: Path) -> None:
    """Repository context should include readable text files."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("hello repo", encoding="utf-8")
    (repo / ".git").mkdir()
    (repo / ".git" / "ignored.txt").write_text("ignore me", encoding="utf-8")
    context = main.build_repo_context(repo, max_files=5, max_bytes=500)
    assert "# Repository Snapshot:" in context
    assert "README.md" in context
    assert "hello repo" in context
    assert "ignored.txt" not in context


def test_build_repo_context_rejects_invalid_path(tmp_path: Path) -> None:
    """Repository context requires an existing directory."""
    with pytest.raises(ValueError):
        main.build_repo_context(tmp_path / "missing")


def test_read_repo_file_handles_oserror(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Unreadable files should be skipped."""
    path = tmp_path / "file.txt"
    path.write_text("data", encoding="utf-8")
    monkeypatch.setattr(Path, "read_bytes", lambda self: (_ for _ in ()).throw(OSError("boom")))
    assert main._read_repo_file(path, 10) is None


def test_read_repo_file_rejects_binary(tmp_path: Path) -> None:
    """Binary files should be ignored."""
    path = tmp_path / "file.bin"
    path.write_bytes(b"\x00abc")
    assert main._read_repo_file(path, 10) is None


def test_read_repo_file_rejects_invalid_utf8(tmp_path: Path) -> None:
    """Invalid UTF-8 files should be ignored."""
    path = tmp_path / "file.txt"
    path.write_bytes(b"\xff\xfe\xfd")
    assert main._read_repo_file(path, 10) is None


def test_read_repo_file_truncates(tmp_path: Path) -> None:
    """Oversized text files should be truncated."""
    path = tmp_path / "file.txt"
    path.write_text("abcdefghijklmnopqrstuvwxyz", encoding="utf-8")
    text = main._read_repo_file(path, 5)
    assert text == "abcde\n... [truncated]"


def test_build_repo_context_rejects_empty_repo(tmp_path: Path) -> None:
    """A repo with no readable files should fail clearly."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / ".git" / "config").write_text("ignored", encoding="utf-8")
    with pytest.raises(ValueError):
        main.build_repo_context(repo)


def test_build_repo_context_respects_file_limit(tmp_path: Path) -> None:
    """The repo snapshot should stop at the configured file limit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    for index in range(3):
        (repo / f"file{index}.txt").write_text(f"file-{index}", encoding="utf-8")
    context = main.build_repo_context(repo, max_files=1, max_bytes=500)
    assert context.count("## ") == 1


def test_build_repo_context_stops_when_byte_budget_is_exhausted(tmp_path: Path) -> None:
    """The repo snapshot should stop when no bytes remain."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "file1.txt").write_text("abcdef", encoding="utf-8")
    (repo / "file2.txt").write_text("ghijkl", encoding="utf-8")
    context = main.build_repo_context(repo, max_files=10, max_bytes=1)
    assert context.count("## ") == 1


def test_build_repo_context_skips_unreadable_entries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Files returning None from _read_repo_file should be skipped."""
    repo = tmp_path / "repo"
    repo.mkdir()
    readable = repo / "a.txt"
    skipped = repo / "b.txt"
    readable.write_text("alpha", encoding="utf-8")
    skipped.write_text("beta", encoding="utf-8")
    original = main._read_repo_file

    def fake_read_repo_file(path: Path, max_bytes: int) -> str | None:
        if path == skipped:
            return None
        return original(path, max_bytes)

    monkeypatch.setattr(main, "_read_repo_file", fake_read_repo_file)
    context = main.build_repo_context(repo, max_files=10, max_bytes=500)
    assert "a.txt" in context
    assert "b.txt" not in context


def test_build_prompt_with_repo_context(tmp_path: Path) -> None:
    """Prompt building should append repository context."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "main.py").write_text("print('hi')", encoding="utf-8")
    prompt = main.build_prompt_with_repo_context("Explain this repo.", repo)
    assert "Explain this repo." in prompt
    assert "main.py" in prompt


def test_decode_sse_events_skips_invalid_lines() -> None:
    """SSE parsing should ignore non-data and invalid JSON lines."""
    lines = [b"", b"event: message_start", b"data: not-json", sse_data({"type": "ping"})]
    assert list(main.decode_sse_events(lines)) == [{"type": "ping"}]


def test_usage_from_payload_ignores_non_dict() -> None:
    """Usage merging should leave the current value unchanged for non-dicts."""
    current = main.ClaudeUsage(input_tokens=5)
    assert main._usage_from_payload(None, current) == current


def test_response_from_stream_aggregates_events() -> None:
    """Streaming responses should be normalized into a ClaudeResponse."""
    events: list[dict[str, object]] = [
        {
            "type": "message_start",
            "message": {"id": "msg_123", "role": "assistant", "usage": {"input_tokens": 4}},
        },
        {"type": "content_block_delta", "delta": {"text": "Hello"}},
        {"type": "content_block_delta", "delta": {"text": " world"}},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 2}},
        {"type": "message_stop"},
    ]
    response = main.response_from_stream(events, "claude-sonnet-4-6")
    assert response.identifier == "msg_123"
    assert response.text == "Hello world"
    assert response.stop_reason == "end_turn"
    assert response.usage.input_tokens == 4
    assert response.usage.output_tokens == 2


def test_create_message_posts_expected_payload() -> None:
    """The client should send a direct POST with streaming enabled."""
    fake_response = FakeResponse(
        [
            sse_data({"type": "message_start", "message": {"id": "m1", "role": "assistant", "usage": {}}}),
            sse_data({"type": "content_block_delta", "delta": {"text": "ok"}}),
            sse_data({"type": "message_stop"}),
        ]
    )
    session = FakeSession(fake_response)
    client = main.ClaudeNativeOAuthClient("secret", session=session)
    response = client.create_message([main.ChatMessage(role="user", content="Ping")])
    assert response.text == "ok"
    assert session.calls[0]["url"] == main.DEFAULT_API_URL
    assert session.calls[0]["stream"] is True
    assert isinstance(session.calls[0]["json"], dict)


def test_create_message_retries_after_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """The client should refresh and retry once after a 401 response."""
    session = SequencedSession(
        [
            OneTime401Response([], should_fail=True),
            FakeResponse(
                [
                    sse_data({"type": "message_start", "message": {"id": "m1", "role": "assistant", "usage": {}}}),
                    sse_data({"type": "content_block_delta", "delta": {"text": "ok"}}),
                    sse_data({"type": "message_stop"}),
                ]
            ),
        ]
    )
    monkeypatch.setattr(main, "refresh_claude_code_token", lambda path: "fresh-token")
    client = main.ClaudeNativeOAuthClient("secret", session=session)
    response = client.create_message([main.ChatMessage(role="user", content="Ping")])
    assert response.text == "ok"
    headers = cast(dict[str, str], session.calls[1]["headers"])
    assert headers["Authorization"] == "Bearer fresh-token"


def test_create_message_re_raises_non_401() -> None:
    """Non-401 HTTP failures should bubble out of create_message."""

    class Non401Response(FakeResponse):
        def raise_for_status(self) -> None:
            error = requests.HTTPError("HTTP 500")
            error.response = SimpleNamespace(status_code=500)
            raise error

    client = main.ClaudeNativeOAuthClient("secret", session=FakeSession(Non401Response([])))
    with pytest.raises(requests.HTTPError):
        client.create_message([main.ChatMessage(role="user", content="Ping")])


def test_chat_wraps_single_user_message() -> None:
    """The chat helper should wrap the prompt as a single user message."""
    fake_response = FakeResponse(
        [
            sse_data({"type": "message_start", "message": {"id": "m1", "role": "assistant", "usage": {}}}),
            sse_data({"type": "content_block_delta", "delta": {"text": "ok"}}),
            sse_data({"type": "message_stop"}),
        ]
    )
    session = FakeSession(fake_response)
    client = main.ClaudeNativeOAuthClient("secret", session=session)
    response = client.chat("Ping")
    payload = session.calls[0]["json"]
    assert isinstance(payload, dict)
    assert payload["messages"] == [{"role": "user", "content": "Ping"}]
    assert response.text == "ok"


def test_stream_text_yields_deltas() -> None:
    """Streaming text mode should yield only content deltas."""
    fake_response = FakeResponse(
        [
            sse_data({"type": "ping"}),
            sse_data({"type": "content_block_delta", "delta": {"text": "a"}}),
            sse_data({"type": "content_block_delta", "delta": {"text": "b"}}),
        ]
    )
    session = FakeSession(fake_response)
    client = main.ClaudeNativeOAuthClient("secret", session=session)
    assert list(client.stream_text("hi")) == ["a", "b"]


def test_stream_text_retries_after_401(monkeypatch: pytest.MonkeyPatch) -> None:
    """Streaming mode should refresh and retry once after a 401 response."""
    session = SequencedSession(
        [
            OneTime401Response([], should_fail=True),
            FakeResponse([sse_data({"type": "content_block_delta", "delta": {"text": "ok"}})]),
        ]
    )
    monkeypatch.setattr(main, "refresh_claude_code_token", lambda path: "fresh-token")
    client = main.ClaudeNativeOAuthClient("secret", session=session)
    assert list(client.stream_text("hi")) == ["ok"]


def test_stream_text_re_raises_non_401() -> None:
    """Non-401 streaming failures should bubble out."""

    class Non401Response(FakeResponse):
        def raise_for_status(self) -> None:
            error = requests.HTTPError("HTTP 500")
            error.response = SimpleNamespace(status_code=500)
            raise error

    client = main.ClaudeNativeOAuthClient("secret", session=FakeSession(Non401Response([])))
    with pytest.raises(requests.HTTPError):
        list(client.stream_text("hi"))


def test_read_prompt_prefers_cli_value() -> None:
    """Prompt resolution should prefer the positional argument."""
    args = main.parse_args(["hello"])
    assert main.read_prompt(args, io.StringIO("ignored")) == "hello"


def test_read_prompt_reads_stdin() -> None:
    """Prompt resolution should no longer read stdin implicitly."""
    args = main.parse_args([])
    with pytest.raises(ValueError):
        main.read_prompt(args, io.StringIO("hello from stdin"))


def test_read_prompt_rejects_empty_input() -> None:
    """Prompt resolution should reject missing prompt input."""
    args = main.parse_args([])
    with pytest.raises(ValueError):
        main.read_prompt(args, io.StringIO(""))


def test_parse_args_version_flag() -> None:
    """The CLI should expose a version flag."""
    with pytest.raises(SystemExit) as exc_info:
        main.parse_args(["--version"])
    assert exc_info.value.code == 0


def test_parse_args_token_status_flag() -> None:
    """The CLI should parse the token status flag."""
    args = main.parse_args(["--token-status"])
    assert args.token_status is True


def test_parse_args_list_models_flag() -> None:
    """The CLI should parse the model listing flag."""
    args = main.parse_args(["--list-models"])
    assert args.list_models is True


def test_main_json_output(monkeypatch: pytest.MonkeyPatch, credentials_path: Path) -> None:
    """The CLI should emit JSON when requested."""
    credentials_path.write_text(
        json.dumps({"claudeAiOauth": {"accessToken": "token-123"}}),
        encoding="utf-8",
    )

    def fake_chat(self: main.ClaudeNativeOAuthClient, prompt: str, config: main.ClientConfig) -> main.ClaudeResponse:
        assert prompt == "hello"
        return main.ClaudeResponse(
            identifier="m1",
            role="assistant",
            model=config.model,
            text="hi",
            stop_reason="end_turn",
            usage=main.ClaudeUsage(output_tokens=1),
        )

    monkeypatch.setattr(main.ClaudeNativeOAuthClient, "chat", fake_chat)
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = main.main(
        ["--json", "--credentials-path", str(credentials_path), "hello"],
        stdout=stdout,
        stderr=stderr,
    )
    assert exit_code == 0
    assert json.loads(stdout.getvalue())["content"][0]["text"] == "hi"
    assert stderr.getvalue() == ""


def test_main_token_status_output(credentials_path: Path) -> None:
    """The CLI should print token status and exit."""
    credentials_path.write_text(
        json.dumps({"claudeAiOauth": {"accessToken": "token-123", "refreshToken": "refresh-123"}}),
        encoding="utf-8",
    )
    stdout = io.StringIO()
    exit_code = main.main(["--token-status", "--credentials-path", str(credentials_path)], stdout=stdout)
    assert exit_code == 0
    assert json.loads(stdout.getvalue())["token_present"] is True


def test_main_list_models_output() -> None:
    """The CLI should print supported models and exit."""
    stdout = io.StringIO()
    exit_code = main.main(["--list-models"], stdout=stdout)
    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["default"] == "claude-sonnet-4-6"
    assert any(item["alias"] == "sonnet" for item in payload["aliases"])


def test_main_stream_output(monkeypatch: pytest.MonkeyPatch, credentials_path: Path) -> None:
    """The CLI should print streamed content when requested."""
    credentials_path.write_text(
        json.dumps({"claudeAiOauth": {"accessToken": "token-123"}}),
        encoding="utf-8",
    )

    def fake_stream_text(
        self: main.ClaudeNativeOAuthClient,
        prompt: str,
        config: main.ClientConfig,
    ) -> Iterator[str]:
        assert prompt == "hello"
        yield "a"
        yield "b"

    monkeypatch.setattr(main.ClaudeNativeOAuthClient, "stream_text", fake_stream_text)
    stdout = io.StringIO()
    exit_code = main.main(
        ["--stream", "--credentials-path", str(credentials_path), "hello"],
        stdout=stdout,
        stderr=io.StringIO(),
    )
    assert exit_code == 0
    assert stdout.getvalue() == "ab\n"


def test_main_plain_text_output(monkeypatch: pytest.MonkeyPatch, credentials_path: Path) -> None:
    """The CLI should print plain text in the default output mode."""
    credentials_path.write_text(
        json.dumps({"claudeAiOauth": {"accessToken": "token-123"}}),
        encoding="utf-8",
    )

    def fake_chat(self: main.ClaudeNativeOAuthClient, prompt: str, config: main.ClientConfig) -> main.ClaudeResponse:
        assert prompt == "hello"
        return main.ClaudeResponse(
            identifier="m1",
            role="assistant",
            model=config.model,
            text="plain output",
            stop_reason="end_turn",
            usage=main.ClaudeUsage(output_tokens=1),
        )

    monkeypatch.setattr(main.ClaudeNativeOAuthClient, "chat", fake_chat)
    stdout = io.StringIO()
    exit_code = main.main(
        ["--credentials-path", str(credentials_path), "hello"],
        stdout=stdout,
        stderr=io.StringIO(),
    )
    assert exit_code == 0
    assert stdout.getvalue() == "plain output\n"


def test_main_repo_prompt_uses_context(monkeypatch: pytest.MonkeyPatch, credentials_path: Path, tmp_path: Path) -> None:
    """The CLI should augment prompts with repository context when requested."""
    credentials_path.write_text(
        json.dumps({"claudeAiOauth": {"accessToken": "token-123"}}),
        encoding="utf-8",
    )
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("repo docs", encoding="utf-8")

    def fake_chat(self: main.ClaudeNativeOAuthClient, prompt: str, config: main.ClientConfig) -> main.ClaudeResponse:
        assert "Summarize this repo" in prompt
        assert "repo docs" in prompt
        return main.ClaudeResponse(
            identifier="m1",
            role="assistant",
            model=config.model,
            text="repo summary",
            stop_reason="end_turn",
            usage=main.ClaudeUsage(output_tokens=1),
        )

    monkeypatch.setattr(main.ClaudeNativeOAuthClient, "chat", fake_chat)
    stdout = io.StringIO()
    exit_code = main.main(
        [
            "--credentials-path",
            str(credentials_path),
            "--repo",
            str(repo),
            "Summarize this repo",
        ],
        stdout=stdout,
        stderr=io.StringIO(),
    )
    assert exit_code == 0
    assert stdout.getvalue() == "repo summary\n"


def test_main_error_path(credentials_path: Path) -> None:
    """CLI failures should return non-zero and write stderr."""
    credentials_path.write_text(json.dumps({"claudeAiOauth": {}}), encoding="utf-8")
    stderr = io.StringIO()
    exit_code = main.main(["--credentials-path", str(credentials_path), "hello"], stderr=stderr)
    assert exit_code == 1
    assert "Error:" in stderr.getvalue()


def test_main_requires_prompt_argument() -> None:
    """The CLI should fail fast without a positional prompt."""
    stderr = io.StringIO()
    exit_code = main.main([], stderr=stderr)
    assert exit_code == 1
    assert "prompt argument is required" in stderr.getvalue()
