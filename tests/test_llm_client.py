"""Tests for src.llm.client — message building and streaming (mocked, no network)."""

import base64
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.llm.client import Client


@pytest.fixture
def client(monkeypatch):
    """A Client instance built with fake credentials (no network access)."""
    monkeypatch.setenv("EXPLAINV_API_KEY", "test-key")
    monkeypatch.setenv("EXPLAINV_API_URL", "https://api.example.test/v1")
    return Client(system_prompt="SYSTEM")


def _chunk(content):
    """Build a fake streaming chunk carrying *content* in its delta."""
    delta = SimpleNamespace(content=content)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def _usage_chunk():
    """Final chunk with no choices (usage-only)."""
    return SimpleNamespace(choices=[])


class TestInitRequiresEnv:
    def test_missing_env_raises(self, monkeypatch):
        monkeypatch.delenv("EXPLAINV_API_KEY", raising=False)
        monkeypatch.delenv("EXPLAINV_API_URL", raising=False)
        with pytest.raises(RuntimeError, match="missing"):
            Client(system_prompt="s")

    def test_default_model_name(self, client):
        assert client.model_name == "Kimi-k3"

    def test_custom_model_name(self, monkeypatch):
        monkeypatch.setenv("EXPLAINV_API_KEY", "k")
        monkeypatch.setenv("EXPLAINV_API_URL", "https://api.example.test/v1")
        monkeypatch.setenv("EXPLAINV_USE_MODEL", "gpt-x")
        assert Client(system_prompt="s").model_name == "gpt-x"


class TestBuildMessages:
    def test_without_image(self, client):
        messages = client.build_messages_without_image("hello")
        assert messages[0] == {"role": "system", "content": "SYSTEM"}
        assert messages[1] == {"role": "user", "content": "hello"}

    def test_system_prompt_override(self, client):
        messages = client.build_messages_without_image("hi", system_prompt="OTHER")
        assert messages[0]["content"] == "OTHER"

    def test_with_image(self, client, tmp_path):
        img = tmp_path / "problem.png"
        payload = b"fake-image-bytes"
        img.write_bytes(payload)

        messages = client.build_messages_with_image("solve this", str(img))

        assert messages[0]["role"] == "system"
        text_part, image_part = messages[1]["content"]
        assert text_part == {"type": "text", "text": "solve this"}
        expected_b64 = base64.b64encode(payload).decode("utf-8")
        assert image_part["type"] == "image_url"
        assert image_part["image_url"]["url"] == f"data:image/jpeg;base64,{expected_b64}"


class TestStreamingCall:
    def _install_stream(self, monkeypatch, client, chunks):
        create = MagicMock(return_value=iter(chunks))
        monkeypatch.setattr(client.client.chat.completions, "create", create)
        return create

    def test_accumulates_content(self, monkeypatch, client):
        self._install_stream(
            monkeypatch,
            client,
            [_chunk("Hello"), _chunk(", "), _usage_chunk(), _chunk("world")],
        )
        result = client._streaming_call([{"role": "user", "content": "x"}])
        assert result == "Hello, world"

    def test_empty_stream_returns_none(self, monkeypatch, client):
        self._install_stream(monkeypatch, client, [])
        assert client._streaming_call([{"role": "user", "content": "x"}]) is None

    def test_html_response_raises(self, monkeypatch, client):
        self._install_stream(
            monkeypatch, client, [_chunk("<html><body>Gateway error</body></html>")]
        )
        with pytest.raises(RuntimeError, match="HTML"):
            client._streaming_call([{"role": "user", "content": "x"}])

    def test_doctype_response_raises(self, monkeypatch, client):
        self._install_stream(monkeypatch, client, [_chunk("<!DOCTYPE html><html>")])
        with pytest.raises(RuntimeError, match="HTML"):
            client._streaming_call([{"role": "user", "content": "x"}])

    def test_request_parameters(self, monkeypatch, client):
        create = self._install_stream(monkeypatch, client, [_chunk("ok")])
        messages = [{"role": "user", "content": "x"}]
        client._streaming_call(messages)

        kwargs = create.call_args.kwargs
        assert kwargs["model"] == client.model_name
        assert kwargs["messages"] is messages
        assert kwargs["stream"] is True
        assert kwargs["extra_body"] == {"enable_thinking": True}
