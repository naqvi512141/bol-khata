"""LLM provider abstraction — Groq, Gemini, Model Studio, or none.

Selected by env LLM_PROVIDER. LLM_PROVIDER=none is a valid configuration —
the app runs with no LLM at all.

All providers use the OpenAI-compatible chat completions API with:
  response_format={"type": "json_object"}, temperature=0.
"""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    """Protocol for an LLM provider."""

    def chat(self, messages: list[dict[str, str]]) -> str:
        """Send a chat completion request and return the raw response text.

        Raises RuntimeError on failure.
        """
        ...


class NoLLMProvider:
    """Stub provider when LLM_PROVIDER=none.  Always raises."""

    def chat(self, messages: list[dict[str, str]]) -> str:
        raise RuntimeError("LLM_PROVIDER is set to 'none' — no LLM available")


class OpenAICompatibleProvider:
    """Provider for any OpenAI-compatible chat completions API (Groq, Gemini, DashScope)."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    def chat(self, messages: list[dict[str, str]]) -> str:
        """Send a chat completion request with JSON mode, temperature 0."""
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(url, headers=headers, json=payload)
        except Exception as e:
            raise RuntimeError(f"LLM request failed: {type(e).__name__}: {e}") from e

        if response.status_code != 200:
            # Never log API keys — redact them from body
            body = response.text.replace(self._api_key, "[REDACTED]") if self._api_key else response.text
            raise RuntimeError(
                f"LLM API returned HTTP {response.status_code}: {body[:500]}"
            )

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return str(content)
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(f"Unexpected LLM response structure: {e}") from e


def get_llm_provider(settings: Settings) -> LLMProvider:
    """Build the appropriate LLM provider from settings.

    Supported providers: groq, gemini, model_studio, none.
    """
    provider_name = settings.LLM_PROVIDER.lower().strip()

    if provider_name == "none":
        logger.info("LLM_PROVIDER=none — LLM fallback disabled")
        return NoLLMProvider()

    if provider_name == "groq":
        if not settings.GROQ_API_KEY or not settings.GROQ_API_KEY.strip():
            logger.warning("LLM_PROVIDER=groq but GROQ_API_KEY is empty — falling back to none")
            return NoLLMProvider()
        return OpenAICompatibleProvider(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1",
            model=settings.LLM_MODEL,
        )

    if provider_name == "gemini":
        if not settings.GEMINI_API_KEY or not settings.GEMINI_API_KEY.strip():
            logger.warning("LLM_PROVIDER=gemini but GEMINI_API_KEY is empty — falling back to none")
            return NoLLMProvider()
        return OpenAICompatibleProvider(
            api_key=settings.GEMINI_API_KEY,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            model="gemini-2.5-flash",
        )

    if provider_name == "model_studio":
        if not settings.DASHSCOPE_API_KEY or not settings.DASHSCOPE_API_KEY.strip():
            logger.warning(
                "LLM_PROVIDER=model_studio but DASHSCOPE_API_KEY is empty — falling back to none"
            )
            return NoLLMProvider()
        return OpenAICompatibleProvider(
            api_key=settings.DASHSCOPE_API_KEY,
            base_url=settings.DASHSCOPE_BASE_URL,
            model=settings.LLM_MODEL,
        )

    logger.warning("Unknown LLM_PROVIDER '%s' — falling back to none", provider_name)
    return NoLLMProvider()
