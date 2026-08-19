from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from mfe_study_cloud.analysis.errors import ProviderDisabledError, ProviderSchemaError
from mfe_study_cloud.analysis.models import BatchAnalysisOutput
from mfe_study_cloud.analysis.provider import (
    AnalysisRequest,
    DisabledProvider,
    FakeAnalysisProvider,
    OpenAIResponsesProvider,
    build_provider,
)
from mfe_study_cloud.config import Settings


def request(first_page: int = 1, last_page: int = 2) -> AnalysisRequest:
    return AnalysisRequest(
        document_id="00000000-0000-0000-0000-000000000001",
        document_title="Anonymous demo",
        pdf_bytes=b"%PDF-anonymous",
        first_page=first_page,
        last_page=last_page,
    )


def test_fake_provider_is_deterministic_and_network_free() -> None:
    first = FakeAnalysisProvider().analyze(request())
    second = FakeAnalysisProvider().analyze(request())

    assert first.output == second.output
    assert [page.page_number for page in first.output.pages] == [1, 2]
    assert first.input_tokens == first.output_tokens == 0
    assert first.provider == "fake"


def test_disabled_provider_has_clear_failure() -> None:
    with pytest.raises(ProviderDisabledError, match="disabled"):
        DisabledProvider().analyze(request())


class _ResponsesProbe:
    def __init__(self, parsed: BatchAnalysisOutput) -> None:
        self.parsed = parsed
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(
            id="response_test",
            output_parsed=self.parsed,
            output=[],
            usage=SimpleNamespace(input_tokens=12, output_tokens=34),
        )


def test_openai_provider_keeps_key_server_side_and_uses_structured_pdf_input() -> None:
    fake_output = FakeAnalysisProvider().analyze(request()).output
    responses = _ResponsesProbe(fake_output)
    client = SimpleNamespace(responses=responses)
    settings = Settings(
        MFE_ENV="test",
        MFE_ANALYSIS_PROVIDER="openai",
        OPENAI_API_KEY="server-only-test-key",
        OPENAI_MODEL="configured-model",
    )

    result = OpenAIResponsesProvider(settings, client=client).analyze(request())

    assert result.response_id == "response_test"
    assert result.input_tokens == 12
    assert result.output_tokens == 34
    call = responses.calls[0]
    assert call["model"] == "configured-model"
    assert call["store"] is False
    assert call["text_format"] is BatchAnalysisOutput
    content = call["input"][1]["content"]
    assert content[0]["type"] == "input_file"
    assert content[0]["file_data"].startswith("data:application/pdf;base64,")
    serialized = json.dumps({key: value for key, value in call.items() if key != "text_format"})
    assert "server-only-test-key" not in serialized


def test_openai_provider_rejects_wrong_page_mapping() -> None:
    wrong = FakeAnalysisProvider().analyze(request(2, 2)).output
    client = SimpleNamespace(responses=_ResponsesProbe(wrong))
    settings = Settings(
        MFE_ENV="test",
        MFE_ANALYSIS_PROVIDER="openai",
        OPENAI_API_KEY="server-only-test-key",
        OPENAI_MODEL="configured-model",
    )

    with pytest.raises(ProviderSchemaError, match="expected"):
        OpenAIResponsesProvider(settings, client=client).analyze(request(1, 1))


def test_checked_in_schema_accepts_fake_output() -> None:
    root = Path(__file__).resolve().parents[1]
    schema_path = root / "src/mfe_study_cloud/schemas/page_analysis_v1.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    errors = list(
        Draft202012Validator(schema).iter_errors(
            FakeAnalysisProvider().analyze(request()).output.model_dump()
        )
    )
    assert errors == []


def test_provider_factory_never_falls_back_to_paid_provider() -> None:
    assert isinstance(build_provider(Settings(MFE_ENV="test")), FakeAnalysisProvider)
    assert isinstance(
        build_provider(Settings(MFE_ENV="test", MFE_ANALYSIS_PROVIDER="disabled")),
        DisabledProvider,
    )
