"""Unified AI client supporting multiple LLM and Embedding providers."""
import json
import os
from typing import AsyncGenerator, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()


class AIClient:
    """AI client with multiple provider support."""

    PROVIDERS = {
        "siliconflow": {
            "base_url": "https://api.siliconflow.cn/v1",
            "api_key_env": "SILICONFLOW_API_KEY",
        },
        "deepseek": {
            "base_url": "https://api.deepseek.com/v1",
            "api_key_env": "DEEPSEEK_API_KEY",
        },
    }

    def __init__(self, provider: str = "siliconflow"):
        if provider not in self.PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider}")
        self._provider = provider
        config = self.PROVIDERS[provider]
        self.base_url = config["base_url"]
        self._api_key_env = config["api_key_env"]
        self._api_key = os.getenv(config["api_key_env"])
        self._client: Optional[httpx.AsyncClient] = None

    async def _ensure_client(self):
        """Lazily initialize the HTTP client and verify API key."""
        if self._client is not None:
            return
        if not self._api_key:
            raise ValueError(
                f"Missing API key: {self._api_key_env}. "
                f"Set it in .env file or environment variables."
            )
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
        payload = {
            "model": model or "Qwen/Qwen2.5-7B-Instruct",
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
        payload = {
            "model": model or "BAAI/bge-m3",
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