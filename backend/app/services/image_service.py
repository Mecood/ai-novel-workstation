"""Image generation service — wraps OpenAI-compatible image generation API."""
import os
import uuid
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.app_config import AppConfig

# Directory for saving generated images locally
STORAGE_DIR = Path(settings.STORAGE_DIR) / "images"
STATIC_URL_PREFIX = "/static/images"


class ImageService:
    """Encapsulates image generation API calls using the configured AI provider."""

    async def _get_image_config(self, db: AsyncSession) -> dict:
        """Read the active image provider from AppConfig.

        Returns: dict with base_url, api_key, model.
        Uses active_image_provider if set; otherwise falls back to active_provider.
        """
        result = await db.execute(select(AppConfig).where(AppConfig.id == 1))
        app_config = result.scalar_one_or_none()
        config = (app_config.config if app_config else None) or {}

        providers = config.get("providers") or []
        if not providers:
            raise ValueError("未配置 AI 提供商")

        # Prefer active_image_provider, fallback to active_provider
        active_idx = config.get("active_image_provider", config.get("active_provider"))

        if isinstance(active_idx, int):
            provider = providers[active_idx] if 0 <= active_idx < len(providers) else None
        else:
            provider = next((p for p in providers if p.get("name") == active_idx), None)
        if not provider:
            provider = providers[0]  # last-resort fallback

        url = provider.get("url")
        api_key = provider.get("api_key")
        if not url or not api_key:
            raise ValueError("AI 提供商配置不完整（缺少 url 或 api_key）")

        model = provider.get("image_model") or provider.get("selected_model") or "agnes-image-2.1-flash"

        return {"base_url": url.rstrip("/"), "api_key": api_key, "model": model}

    async def generate_image(
        self,
        db: AsyncSession,
        prompt: str,
        size: str = "2K",
    ) -> dict:
        """Call image generation API and save the result locally.

        Returns: dict with keys `url` (relative URL path), `prompt`, `local_path`
        """
        provider = await self._get_image_config(db)
        base_url = provider["base_url"]
        api_key = provider["api_key"]
        model = provider["model"]

        # Ensure the image storage directory exists
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)

        # Build the full prompt with style prefix
        styled_prompt = f"中国古风，玄幻小说场景，{prompt}"

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{base_url}/v1/images/generations",
                json={
                    "model": model,
                    "prompt": styled_prompt,
                    "size": size,
                    "extra_body": {"response_format": "url"},
                },
                headers={"Authorization": f"Bearer {api_key}"},
            )

            if resp.status_code != 200:
                error_text = resp.text[:500]
                raise ValueError(
                    f"图像生成失败 (HTTP {resp.status_code}): {error_text}"
                )

            data = resp.json()

            # Parse the response — OpenAI format returns data[0].url (a URL) or data[0].b64_json
            image_url_from_api = None
            if "data" in data and len(data["data"]) > 0:
                img_data = data["data"][0]
                image_url_from_api = img_data.get("url")
                b64_json = img_data.get("b64_json")
            else:
                raise ValueError(f"图像生成返回格式异常: {data}")

            # Strategy: try to download the image from the returned URL and save locally.
            # If no URL (b64_json only), decode and save.
            filename = f"{uuid.uuid4().hex}.png"
            local_path = STORAGE_DIR / filename

            if image_url_from_api:
                # Download from the returned URL
                dl_resp = await client.get(image_url_from_api)
                if dl_resp.status_code == 200:
                    local_path.write_bytes(dl_resp.content)
                else:
                    # Fallback: if download fails, store the URL as-is
                    raise ValueError(
                        f"无法下载生成的图片 (HTTP {dl_resp.status_code}): {dl_resp.text[:200]}"
                    )
            elif b64_json:
                import base64
                local_path.write_bytes(base64.b64decode(b64_json))
            else:
                raise ValueError("API 未返回图片 URL 或 base64 数据")

        relative_url = f"{STATIC_URL_PREFIX}/{filename}"
        return {
            "url": relative_url,
            "file_path": str(local_path),
        }