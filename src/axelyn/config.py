from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AXELYN_", env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./axelyn.db"
    api_key: str = Field(min_length=32)
    tenant_id: str = Field(default="local", min_length=1, max_length=128)
    embedding_provider: Literal["demo", "ollama"] = "demo"
    embedding_model: str = "demo-hash-v1"
    ollama_url: str = "http://localhost:11434"
    minimum_score: float = Field(default=0.25, gt=0, le=1)

    @model_validator(mode="after")
    def validate_model(self) -> "Settings":
        if self.embedding_provider == "ollama" and self.embedding_model == "demo-hash-v1":
            raise ValueError("Set AXELYN_EMBEDDING_MODEL to a pinned Ollama model")
        return self
