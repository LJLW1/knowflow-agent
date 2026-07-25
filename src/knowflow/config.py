"""Environment-backed application settings."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="KNOWFLOW_",
        env_file=".env",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = "sqlite:///data/runtime/knowflow.db"
    chroma_path: str = "data/chroma"
    upload_path: str = "data/uploads"
    report_path: str = "reports/runtime"
    embedding_backend: str = "bge"
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    vector_backend: str = "chroma"
    openai_base_url: str | None = None
    openai_api_key: str | None = None
    openai_model: str | None = None
    log_level: str = "INFO"
    github_repository: str = "LJLW1/knowflow-agent"
    internal_api_token: SecretStr | None = None
