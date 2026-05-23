"""Unified AI client supporting multiple LLM and Embedding providers."""
import json
from typing import AsyncGenerator, Optional

import httpx


class AIClient:
    """AI client that takes runtime config (url + api_key + model)."""

    def __init__(
        self,
        url: str,
        api_key: str,
        model: Optional[str] = None,
    ):
        if not url:
            raise ValueError("Missing AI provider URL")
        if not api_key:
            raise ValueError("Missing AI provider API key")
        self.base_url = url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self):
        """Lazily initialize the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=120.0)

    async def chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> str | AsyncGenerator[str, None]:
        """Call chat completion API."""
        await self._ensure_client()
        selected_model = model or self._model
        if not selected_model:
            raise ValueError("Missing model name")
        payload = {
            "model": selected_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        if stream:
            return self._stream_chat(payload)

        resp = await self._client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]

    async def _stream_chat(self, payload: dict) -> AsyncGenerator[str, None]:
        """Stream chat completion."""
        await self._ensure_client()
        async with self._client.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self._api_key}"},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if content := data["choices"][0].get("delta", {}).get("content"):
                            yield content
                    except json.JSONDecodeError:
                        continue

    async def embed(self, text: str, model: Optional[str] = None) -> list[float]:
        """Get text embedding vector."""
        await self._ensure_client()
        selected_model = model or self._model
        if not selected_model:
            raise ValueError("Missing embedding model name")
        payload = {
            "model": selected_model,
            "input": text,
        }
        resp = await self._client.post(
            f"{self.base_url}/embeddings",
            json=payload,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["data"][0]["embedding"]

    async def close(self):
        if self._client:
            await self._client.aclose()
