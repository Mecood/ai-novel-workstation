"""Unified AI client supporting multiple LLM and Embedding providers."""
import json
from typing import Any, AsyncGenerator, Callable, Mapping, Optional

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

    async def _chat_completion(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[str] = None,
    ) -> dict:
        """Internal chat completion returning the full message dict.

        Used by both *chat* (strips to content) and *agent_chat* (keeps the
        dict so tool_calls can be parsed).
        """
        await self._ensure_client()
        selected_model = model or self._model
        if not selected_model:
            raise ValueError("Missing model name")
        payload = {
            "model": selected_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        resp = await self._client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]

    async def agent_chat(
        self,
        messages: list[dict],
        tools: list[dict],
        tool_executor: Callable[[str, Mapping[str, Any]], Any],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        max_steps: int = 10,
    ) -> dict:
        """Run a tool-use loop (agent pattern)."""
        msgs = list(messages)
        try:
            for step in range(max_steps):
                response = await self._chat_completion(
                    msgs,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    tool_choice="auto",
                )
                msgs.append({"role": "assistant", "content": response.get("content")})
                tool_calls = response.get("tool_calls") or []
                if not tool_calls:
                    return response
                for tc in tool_calls:
                    func = tc.get("function", {})
                    name = func.get("name", "")
                    try:
                        kwargs = json.loads(func.get("arguments", "{}"))
                    except json.JSONDecodeError:
                        kwargs = {}
                    try:
                        result = tool_executor(name, kwargs)
                        import asyncio
                        if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                            result = await result
                    except Exception as exc:
                        result = f"ERROR calling {name}: {exc}"
                    msgs.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "name": name,
                        "content": str(result),
                    })
            return {
                "content": "Reached maximum tool-use steps; stopping the agent loop.",
                "tool_calls": [],
            }
        except Exception as exc:
            return {
                "content": f"Agent loop error: {type(exc).__name__}: {exc}",
                "tool_calls": [],
            }

    async def chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> str | AsyncGenerator[str, None]:
        """Call chat completion API.

        Legacy plain-text interface.  When *stream=True* returns a generator
        of content chunks; otherwise returns the assistant content string.
        """
        if stream:
            await self._ensure_client()
            selected_model = model or self._model
            if not selected_model:
                raise ValueError("Missing model name")
            return self._stream_chat(
                {
                    "model": selected_model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": stream,
                }
            )
        msg = await self._chat_completion(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return msg.get("content") or ""

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
            buffer = ""
            async for chunk in resp.aiter_bytes():
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            return
                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if not choices:
                                continue
                            delta = choices[0].get("delta", {})
                            if choices[0].get("finish_reason") is not None:
                                return
                            if content := delta.get("content"):
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
