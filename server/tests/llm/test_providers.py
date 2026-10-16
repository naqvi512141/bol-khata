"""Tests for server/app/llm/providers.py.

Rules:
- LLM_PROVIDER=none must be a valid configuration. The app runs with no LLM.
- temperature 0, JSON mode.
"""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from app.config import Settings
from app.llm.providers import (
    NoLLMProvider,
    OpenAICompatibleProvider,
    get_llm_provider,
)


def test_no_llm_provider_raises_on_chat() -> None:
    provider = NoLLMProvider()
    with pytest.raises(RuntimeError, match="LLM_PROVIDER is set to 'none'"):
        provider.chat([{"role": "user", "content": "hi"}])


def test_get_llm_provider_none() -> None:
    settings = Settings(LLM_PROVIDER="none")
    provider = get_llm_provider(settings)
    assert isinstance(provider, NoLLMProvider)


def test_get_llm_provider_groq_missing_key() -> None:
    settings = Settings(LLM_PROVIDER="groq", GROQ_API_KEY="")
    provider = get_llm_provider(settings)
    assert isinstance(provider, NoLLMProvider)


def test_get_llm_provider_groq_with_key() -> None:
    settings = Settings(LLM_PROVIDER="groq", GROQ_API_KEY="gsk_test123")
    provider = get_llm_provider(settings)
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider._api_key == "gsk_test123"
    assert provider._base_url == "https://api.groq.com/openai/v1"


def test_get_llm_provider_gemini_with_key() -> None:
    settings = Settings(LLM_PROVIDER="gemini", GEMINI_API_KEY="AIzaSyTest")
    provider = get_llm_provider(settings)
    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider._api_key == "AIzaSyTest"


def test_openai_compatible_provider_chat_payload() -> None:
    """Verify temperature 0 and json_object response format are sent."""
    secret = "secret_key_abc"

    def mock_transport_handler(request: httpx.Request) -> httpx.Response:
        import json
        body = json.loads(request.content.decode("utf-8"))
        assert body["temperature"] == 0
        assert body["response_format"] == {"type": "json_object"}
        assert request.headers["Authorization"] == f"Bearer {secret}"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"items": [], "computed_total": 0}'}}
                ]
            },
        )

    transport = httpx.MockTransport(mock_transport_handler)
    provider = OpenAICompatibleProvider(
        api_key=secret,
        base_url="https://mock.api/v1",
        model="test-model",
    )
    with patch("httpx.Client", return_value=httpx.Client(transport=transport)):
        result = provider.chat([{"role": "user", "content": "test"}])
    assert result == '{"items": [], "computed_total": 0}'
