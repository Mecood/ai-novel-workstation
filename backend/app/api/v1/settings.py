from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
import httpx

from app.core.database import get_db
from app.models.app_config import AppConfig

router = APIRouter(prefix="/settings", tags=["settings"])

DEFAULT_CONFIG = {
    "providers": [],
    "active_provider": None,
}


# === Schemas ===

class SettingsResponse(BaseModel):
    config: dict
    updated_at: Optional[str] = None


class ProviderConfig(BaseModel):
    name: str
    url: str
    api_key: str
    format: str = "openai"
    selected_model: Optional[str] = None
    models: list[str] = []


class UpdateSettingsRequest(BaseModel):
    config: dict


class TestConnectionRequest(BaseModel):
    url: str
    api_key: str
    format: str = "openai"


class FetchModelsRequest(BaseModel):
    url: str
    api_key: str
    format: str = "openai"


class TestModelRequest(BaseModel):
    url: str
    api_key: str
    model: str
    format: str = "openai"


class TestConnectionResponse(BaseModel):
    success: bool
    message: str


class FetchModelsResponse(BaseModel):
    success: bool
    models: list[str] = []
    message: str = ""


# === Helpers ===

async def get_or_create_config(db: AsyncSession) -> AppConfig:
    result = await db.execute(select(AppConfig).where(AppConfig.id == 1))
    config = result.scalar_one_or_none()
    if not config:
        config = AppConfig(id=1, config=DEFAULT_CONFIG)
        db.add(config)
        await db.commit()
        await db.refresh(config)
    return config


def build_headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


# === API Endpoints ===

@router.get("", response_model=SettingsResponse)
async def get_settings(db: AsyncSession = Depends(get_db)):
    config = await get_or_create_config(db)
    return SettingsResponse(
        config=config.config,
        updated_at=config.updated_at.isoformat() if config.updated_at else None,
    )


@router.put("", response_model=SettingsResponse)
async def update_settings(
    data: UpdateSettingsRequest,
    db: AsyncSession = Depends(get_db),
):
    config = await get_or_create_config(db)
    config.config = data.config
    await db.commit()
    await db.refresh(config)
    return SettingsResponse(
        config=config.config,
        updated_at=config.updated_at.isoformat() if config.updated_at else None,
    )


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_connection(data: TestConnectionRequest):
    """Test basic connectivity to the API base URL."""
    try:
        # For OpenAI-compatible APIs, list models is a good connectivity test
        url = data.url.rstrip("/")
        if data.format == "openai":
            test_url = f"{url}/models"
        elif data.format == "anthropic":
            test_url = f"{url}/v1/models"
        else:
            test_url = f"{url}/models"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                test_url,
                headers=build_headers(data.api_key),
            )
            if resp.status_code == 200:
                return TestConnectionResponse(success=True, message="连接成功")
            elif resp.status_code == 401:
                return TestConnectionResponse(success=False, message="API Key 无效（401）")
            else:
                return TestConnectionResponse(
                    success=False,
                    message=f"连接失败 (HTTP {resp.status_code})",
                )
    except httpx.TimeoutException:
        return TestConnectionResponse(success=False, message="连接超时，请检查 URL")
    except Exception as e:
        return TestConnectionResponse(success=False, message=f"连接失败: {str(e)[:100]}")


@router.post("/fetch-models", response_model=FetchModelsResponse)
async def fetch_models(data: FetchModelsRequest):
    """Fetch available models from the API."""
    try:
        url = data.url.rstrip("/")
        if data.format == "openai":
            models_url = f"{url}/models"
        elif data.format == "anthropic":
            models_url = f"{url}/v1/models"
        else:
            models_url = f"{url}/models"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(models_url, headers=build_headers(data.api_key))
            if resp.status_code != 200:
                return FetchModelsResponse(
                    success=False,
                    models=[],
                    message=f"获取失败 (HTTP {resp.status_code})",
                )

            body = resp.json()
            model_list = []

            if data.format == "openai" and "data" in body:
                # OpenAI format: { data: [{ id: "gpt-4", ... }, ...] }
                model_list = [m["id"] for m in body["data"] if "id" in m]
            elif isinstance(body, list):
                model_list = [m.get("id") or m.get("name") for m in body if m]
            else:
                # Try Anthropic or other formats
                model_list = [m.get("id") or m.get("name") for m in body.get("data", [])]

            # Sort and deduplicate
            model_list = sorted(set(m for m in model_list if m))

            return FetchModelsResponse(
                success=True,
                models=model_list,
                message=f"获取到 {len(model_list)} 个模型",
            )
    except httpx.TimeoutException:
        return FetchModelsResponse(success=False, models=[], message="请求超时")
    except Exception as e:
        return FetchModelsResponse(success=False, models=[], message=f"获取失败: {str(e)[:100]}")


@router.post("/test-model", response_model=TestConnectionResponse)
async def test_model(data: TestModelRequest):
    """Test a specific model by sending a minimal chat request."""
    try:
        url = data.url.rstrip("/")
        async with httpx.AsyncClient(timeout=30.0) as client:
            if data.format == "openai":
                payload = {
                    "model": data.model,
                    "messages": [{"role": "user", "content": "回复一个字：好"}],
                    "max_tokens": 10,
                }
                chat_url = f"{url}/chat/completions"
            elif data.format == "anthropic":
                payload = {
                    "model": data.model,
                    "messages": [{"role": "user", "content": "回复一个字：好"}],
                    "max_tokens": 10,
                }
                chat_url = f"{url}/v1/messages"
            else:
                payload = {
                    "model": data.model,
                    "messages": [{"role": "user", "content": "回复一个字：好"}],
                    "max_tokens": 10,
                }
                chat_url = f"{url}/chat/completions"

            resp = await client.post(
                chat_url,
                headers=build_headers(data.api_key),
                json=payload,
            )
            if resp.status_code == 200:
                return TestConnectionResponse(success=True, message="模型响应正常")
            else:
                return TestConnectionResponse(
                    success=False,
                    message=f"测试失败 (HTTP {resp.status_code})",
                )
    except httpx.TimeoutException:
        return TestConnectionResponse(success=False, message="模型响应超时")
    except Exception as e:
        return TestConnectionResponse(success=False, message=f"测试失败: {str(e)[:100]}")