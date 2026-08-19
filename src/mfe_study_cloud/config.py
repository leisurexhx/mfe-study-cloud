"""Validated server and worker settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from mfe_study_cloud.branding import PRODUCT_NAME

Environment = Literal["development", "test", "production"]
ProviderName = Literal["fake", "disabled", "openai"]
PdfDetail = Literal["auto", "low", "high"]
ObjectSse = Literal["none", "AES256"]
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]


class Settings(BaseSettings):
    """Configuration shared by web and worker processes.

    Secrets stay as ``SecretStr`` and are never represented in templates or log fields.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Environment = Field("development", validation_alias="MFE_ENV")
    app_name: str = Field(PRODUCT_NAME, validation_alias="MFE_APP_NAME")
    public_base_url: str = Field(
        "http://localhost:8080", validation_alias="MFE_PUBLIC_BASE_URL"
    )
    session_secret: SecretStr = Field(
        SecretStr("development-session-secret-change-me"),
        validation_alias="MFE_SESSION_SECRET",
    )
    database_url: str = Field(
        "postgresql+psycopg://mfe:mfe-development-only@localhost:5432/mfe",
        validation_alias="MFE_DATABASE_URL",
    )

    object_endpoint: str = Field(
        "http://localhost:9000", validation_alias="MFE_OBJECT_ENDPOINT"
    )
    object_region: str = Field("us-east-1", validation_alias="MFE_OBJECT_REGION")
    object_bucket: str = Field("mfe-study", validation_alias="MFE_OBJECT_BUCKET")
    object_access_key: SecretStr = Field(
        SecretStr("mfe-development-only"), validation_alias="MFE_OBJECT_ACCESS_KEY"
    )
    object_secret_key: SecretStr = Field(
        SecretStr("mfe-development-only-secret"),
        validation_alias="MFE_OBJECT_SECRET_KEY",
    )
    object_secure: bool = Field(False, validation_alias="MFE_OBJECT_SECURE")
    object_sse: ObjectSse = Field("none", validation_alias="MFE_OBJECT_SSE")

    analysis_provider: ProviderName = Field(
        "fake", validation_alias="MFE_ANALYSIS_PROVIDER"
    )
    openai_api_key: SecretStr | None = Field(None, validation_alias="OPENAI_API_KEY")
    openai_model: str | None = Field(None, validation_alias="OPENAI_MODEL")
    openai_reasoning_effort: ReasoningEffort = Field(
        "medium", validation_alias="MFE_OPENAI_REASONING_EFFORT"
    )
    openai_pdf_detail: PdfDetail = Field(
        "high", validation_alias="MFE_OPENAI_PDF_DETAIL"
    )
    analysis_batch_pages: int = Field(
        5, ge=1, le=20, validation_alias="MFE_ANALYSIS_BATCH_PAGES"
    )
    analysis_max_document_pages: int = Field(
        500, ge=1, le=5000, validation_alias="MFE_ANALYSIS_MAX_DOCUMENT_PAGES"
    )
    analysis_max_concurrent_jobs: int = Field(
        2, ge=1, le=32, validation_alias="MFE_ANALYSIS_MAX_CONCURRENT_JOBS"
    )
    analysis_max_output_tokens: int = Field(
        20_000, ge=1000, le=128_000, validation_alias="MFE_ANALYSIS_MAX_OUTPUT_TOKENS"
    )
    analysis_job_max_output_tokens: int = Field(
        200_000,
        ge=1000,
        le=10_000_000,
        validation_alias="MFE_ANALYSIS_JOB_MAX_OUTPUT_TOKENS",
    )
    analysis_requests_per_minute: int = Field(
        60,
        ge=1,
        le=10_000,
        validation_alias="MFE_ANALYSIS_REQUESTS_PER_MINUTE",
    )
    analysis_max_input_bytes: int = Field(
        50 * 1024 * 1024,
        ge=1024,
        le=50 * 1024 * 1024,
        validation_alias="MFE_ANALYSIS_MAX_INPUT_BYTES",
    )
    analysis_job_lease_seconds: int = Field(
        300, ge=30, le=3600, validation_alias="MFE_ANALYSIS_JOB_LEASE_SECONDS"
    )
    analysis_max_attempts: int = Field(
        3, ge=1, le=10, validation_alias="MFE_ANALYSIS_MAX_ATTEMPTS"
    )
    worker_poll_seconds: float = Field(
        2.0, ge=0.1, le=60.0, validation_alias="MFE_WORKER_POLL_SECONDS"
    )

    # Container ingress is restricted by Compose and the reverse proxy.
    web_host: str = Field(
        "0.0.0.0",  # nosec B104
        validation_alias="MFE_WEB_HOST",
    )
    web_port: int = Field(8080, ge=1, le=65535, validation_alias="MFE_WEB_PORT")
    max_upload_bytes: int = Field(
        50 * 1024 * 1024,
        ge=1024,
        le=50 * 1024 * 1024,
        validation_alias="MFE_MAX_UPLOAD_BYTES",
    )
    secure_cookies: bool = Field(False, validation_alias="MFE_SECURE_COOKIES")
    allowed_hosts: str = Field(
        "localhost,127.0.0.1,testserver", validation_alias="MFE_ALLOWED_HOSTS"
    )
    log_level: str = Field("INFO", validation_alias="MFE_LOG_LEVEL")

    @field_validator("app_name", "object_bucket")
    @classmethod
    def nonempty_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("must not be empty")
        return cleaned

    @field_validator("openai_model")
    @classmethod
    def normalize_optional_model(cls, value: str | None) -> str | None:
        cleaned = value.strip() if value else ""
        return cleaned or None

    @model_validator(mode="after")
    def production_safety(self) -> Settings:
        secret = self.session_secret.get_secret_value()
        if self.environment == "production":
            if len(secret) < 32 or "development" in secret or "replace" in secret:
                raise ValueError("production requires a unique session secret of at least 32 chars")
            if not self.secure_cookies:
                raise ValueError("production requires MFE_SECURE_COOKIES=true")
            if not self.public_base_url.startswith("https://"):
                raise ValueError("production requires an https public base URL")
            if "*" in self.allowed_host_list:
                raise ValueError("production does not allow wildcard trusted hosts")
            if self.object_sse != "AES256":
                raise ValueError("production requires MFE_OBJECT_SSE=AES256")
        if self.analysis_provider == "openai":
            if not self.openai_api_key or not self.openai_api_key.get_secret_value().strip():
                raise ValueError("OpenAI provider requires OPENAI_API_KEY")
            if not self.openai_model:
                raise ValueError("OpenAI provider requires OPENAI_MODEL")
        if self.analysis_job_max_output_tokens < self.analysis_max_output_tokens:
            raise ValueError(
                "MFE_ANALYSIS_JOB_MAX_OUTPUT_TOKENS must be at least "
                "MFE_ANALYSIS_MAX_OUTPUT_TOKENS"
            )
        return self

    @property
    def provider_ready(self) -> bool:
        if self.analysis_provider == "fake":
            return True
        if self.analysis_provider == "disabled":
            return False
        return bool(self.openai_api_key and self.openai_model)

    @property
    def allowed_host_list(self) -> list[str]:
        hosts = {item.strip() for item in self.allowed_hosts.split(",") if item.strip()}
        public_host = urlsplit(self.public_base_url).hostname
        if public_host:
            hosts.add(public_host)
        return sorted(hosts)

    @property
    def public_origin(self) -> str:
        parsed = urlsplit(self.public_base_url)
        return f"{parsed.scheme}://{parsed.netloc}"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
