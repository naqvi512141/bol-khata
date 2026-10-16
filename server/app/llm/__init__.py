"""LLM fallback module for Bol Khata.

Pipeline stage (h): LLM repair.
Invoked ONLY when validation.requires_llm is True.
LLM output is re-run through the FULL validation gate — it never bypasses it.
"""

from app.llm.providers import LLMProvider, get_llm_provider
from app.llm.repair import llm_repair

__all__ = [
    "LLMProvider",
    "get_llm_provider",
    "llm_repair",
]
