"""Validated environment configuration with safe secret representations."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Environment(StrEnum):
    """Supported runtime environments."""

    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class AuthMode(StrEnum):
    """Supported authentication modes."""

    DEVELOPMENT = "development"
    API_KEY = "api_key"


class Settings(BaseSettings):
    """Application settings loaded from ``EVAL_`` environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="EVAL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Environment.DEVELOPMENT
    auth_mode: AuthMode = AuthMode.DEVELOPMENT
    log_level: str = "INFO"
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    api_base_url: str = "http://localhost:8000"

    database_url: SecretStr = SecretStr(
        "postgresql+asyncpg://eval:eval-local-only@localhost:5432/eval"
    )
    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")
    celery_broker_url: SecretStr = SecretStr("redis://localhost:6379/1")
    s3_endpoint_url: str = "http://localhost:9000"
    s3_region: str = "us-east-1"
    s3_bucket: str = "llm-eval-artifacts"
    s3_access_key_id: SecretStr = SecretStr("eval-local-access")
    s3_secret_access_key: SecretStr = SecretStr("eval-local-secret-change-me")
    api_key_pepper: SecretStr = SecretStr("development-pepper-change-before-production")

    max_upload_bytes: int = Field(default=100 * 1024 * 1024, ge=1024)
    max_import_records: int = Field(default=1_000_000, ge=1)
    max_response_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)
    rate_limit_enabled: bool = False
    rate_limit_requests_per_minute: int = Field(default=600, ge=1, le=1_000_000)
    dispatch_window: int = Field(default=500, ge=1, le=100_000)
    outbox_relay_interval_seconds: float = Field(default=5.0, ge=1.0, le=60.0)
    provider_timeout_seconds: float = Field(default=60.0, gt=0, le=600)
    provider_max_attempts: int = Field(default=4, ge=1, le=10)
    default_project_concurrency: int = Field(default=8, ge=1, le=10_000)
    default_budget_usd: Decimal = Field(default=Decimal("100"), ge=0)

    otlp_endpoint: str = ""
    service_version: str = "0.1.0"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        """Accept comma-separated environment values as well as JSON arrays."""

        if isinstance(value, str) and not value.lstrip().startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    def validate_secure_runtime(self) -> None:
        """Reject unsafe development controls in production."""

        if self.environment is Environment.PRODUCTION:
            if self.auth_mode is AuthMode.DEVELOPMENT:
                raise ValueError("development authentication is forbidden in production")
            if "development-pepper" in self.api_key_pepper.get_secret_value():
                raise ValueError("production requires a unique API-key pepper")
            if not self.rate_limit_enabled:
                raise ValueError("production requires distributed API rate limiting")
