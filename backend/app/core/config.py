from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os


class Settings(BaseSettings):
    APP_NAME: str = "AI Novel Workstation"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/novel_workstation"
    CHROMA_URL: str = "http://localhost:8001"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIM: int = 1024
    SILICONFLOW_API_KEY: Optional[str] = None
    DEEPSEEK_API_KEY: Optional[str] = None
    STORAGE_DIR: str = "./storage"

    @property
    def storage_path(self) -> str:
        return os.path.join(self.STORAGE_DIR, "vectorstore")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()