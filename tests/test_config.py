from __future__ import annotations

import pytest
from pydantic import ValidationError

from mfe_study_cloud.config import Settings


def test_fake_provider_is_safe_default() -> None:
    settings = Settings(MFE_ENV="test")

    assert settings.analysis_provider == "fake"
    assert settings.provider_ready is True
    assert "session" not in repr(settings.session_secret).lower()


def test_openai_provider_requires_server_credentials() -> None:
    with pytest.raises(ValidationError, match="OPENAI_API_KEY"):
        Settings(
            MFE_ENV="test",
            MFE_ANALYSIS_PROVIDER="openai",
            OPENAI_MODEL="configured-model",
            OPENAI_API_KEY="",
        )


def test_production_rejects_development_security_values() -> None:
    with pytest.raises(ValidationError, match="session secret"):
        Settings(
            MFE_ENV="production",
            MFE_PUBLIC_BASE_URL="https://study.example.invalid",
            MFE_SECURE_COOKIES=True,
        )


def test_job_budget_must_cover_one_provider_request() -> None:
    with pytest.raises(ValidationError, match="JOB_MAX_OUTPUT_TOKENS"):
        Settings(
            MFE_ENV="test",
            MFE_ANALYSIS_MAX_OUTPUT_TOKENS=2000,
            MFE_ANALYSIS_JOB_MAX_OUTPUT_TOKENS=1000,
        )


def test_production_requires_object_server_side_encryption() -> None:
    with pytest.raises(ValidationError, match="OBJECT_SSE"):
        Settings(
            MFE_ENV="production",
            MFE_PUBLIC_BASE_URL="https://study.example.invalid",
            MFE_ALLOWED_HOSTS="study.example.invalid",
            MFE_SESSION_SECRET="a-unique-example-session-secret-longer-than-32-characters",
            MFE_SECURE_COOKIES=True,
            MFE_ANALYSIS_PROVIDER="disabled",
        )
