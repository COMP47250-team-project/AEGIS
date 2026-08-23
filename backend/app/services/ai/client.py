"""AI client factory for AEGIS.

Resolves the backend in priority order:
  1. Azure OpenAI  — when AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY are set.
  2. Ollama        — when OLLAMA_BASE_URL is set (OpenAI-compatible /v1 API).
  3. Dev stub      — always available; returns clearly-labelled placeholder responses
                     so the app boots and CI passes with no credentials.

Usage
-----
    from app.services.ai.client import get_ai_client, AIProvider

    client = get_ai_client()
    text   = await client.chat(system="...", user="...")
    vecs   = await client.embed(["answer one", "answer two"])

The same `openai` SDK (v3.x) is used for both Azure and Ollama paths because
Ollama exposes an OpenAI-compatible /v1 API.  Switching is just a base_url swap.

References
----------
- Azure OpenAI (gpt-4.1, text-embedding-3-large):
    https://learn.microsoft.com/azure/ai-services/openai/concepts/models
- openai Python SDK v3.x:
    https://github.com/openai/openai-python
- Ollama OpenAI-compatible API:
    https://github.com/ollama/ollama/blob/main/docs/openai.md
"""

from __future__ import annotations

import asyncio
import logging
from enum import Enum
from functools import lru_cache
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


class AIProvider(str, Enum):
    AZURE = "azure"
    OLLAMA = "ollama"
    STUB = "stub"


# ---------------------------------------------------------------------------
# Base interface
# ---------------------------------------------------------------------------


class _BaseAIClient:
    provider: AIProvider

    async def chat(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.0,
        max_tokens: int = 512,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        raise NotImplementedError

    async def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Azure OpenAI + Ollama (same SDK, different base_url / auth)
# ---------------------------------------------------------------------------


class _OpenAIClient(_BaseAIClient):
    """Wraps openai v3.x AsyncAzureOpenAI or AsyncOpenAI (for Ollama)."""

    def __init__(
        self,
        provider: AIProvider,
        chat_model: str,
        embed_model: str,
        **client_kwargs: Any,
    ) -> None:
        self.provider = provider
        self._chat_model = chat_model
        self._embed_model = embed_model
        self._kwargs = client_kwargs
        self._client: Any = None  # lazy-init inside the event loop

    def _get_client(self) -> Any:
        if self._client is None:
            if self.provider == AIProvider.AZURE:
                from openai import AsyncAzureOpenAI

                self._client = AsyncAzureOpenAI(**self._kwargs)
            else:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(**self._kwargs)
        return self._client

    async def chat(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.0,
        max_tokens: int = 512,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        client = self._get_client()
        kwargs: dict[str, Any] = {
            "model": self._chat_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format
        resp = await client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._get_client()
        resp = await client.embeddings.create(
            model=self._embed_model,
            input=texts,
        )
        # Sort by index to preserve input order
        items = sorted(resp.data, key=lambda x: x.index)
        return [item.embedding for item in items]


# ---------------------------------------------------------------------------
# Dev stub — always boots, clearly labelled
# ---------------------------------------------------------------------------


class _StubAIClient(_BaseAIClient):
    provider = AIProvider.STUB

    async def chat(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.0,
        max_tokens: int = 512,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        return (
            "[AI STUB — no credentials configured] "
            "This is a placeholder response. "
            "Set AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY "
            "or OLLAMA_BASE_URL to enable real AI features."
        )

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Return zero vectors of dimension 768 (nomic-embed-text dim)
        return [[0.0] * 768 for _ in texts]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def get_ai_client() -> _BaseAIClient:
    """Return the best available AI client (cached for the process lifetime).

    Priority: Azure OpenAI -> Ollama -> dev stub.
    """
    if not settings.ai_features_enabled:
        logger.info("AI features disabled (AI_FEATURES_ENABLED=false) — using stub")
        return _StubAIClient()

    # 1. Azure OpenAI
    if settings.azure_openai_endpoint and settings.azure_openai_api_key:
        logger.info(
            "AI client: Azure OpenAI endpoint=%s chat=%s embed=%s",
            settings.azure_openai_endpoint,
            settings.azure_openai_chat_deployment,
            settings.azure_openai_embed_deployment,
        )
        return _OpenAIClient(
            provider=AIProvider.AZURE,
            chat_model=settings.azure_openai_chat_deployment,
            embed_model=settings.azure_openai_embed_deployment,
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )

    # 2. Ollama (OpenAI-compatible)
    if settings.ollama_base_url:
        logger.info(
            "AI client: Ollama base_url=%s chat=%s embed=%s",
            settings.ollama_base_url,
            settings.ollama_chat_model,
            settings.ollama_embed_model,
        )
        return _OpenAIClient(
            provider=AIProvider.OLLAMA,
            chat_model=settings.ollama_chat_model,
            embed_model=settings.ollama_embed_model,
            base_url=settings.ollama_base_url,
            api_key="ollama",  # Ollama ignores the key but the SDK requires one
        )

    # 3. Dev stub
    logger.warning(
        "AI client: no credentials found — using dev stub. "
        "Set AZURE_OPENAI_ENDPOINT+AZURE_OPENAI_API_KEY or OLLAMA_BASE_URL."
    )
    return _StubAIClient()
