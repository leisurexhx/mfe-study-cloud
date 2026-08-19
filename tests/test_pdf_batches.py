from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader

from mfe_study_cloud.analysis.pdf_batches import split_pdf, validate_pdf

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "anonymous-demo.pdf"


def test_generated_fixture_is_bounded_and_splits_with_real_page_numbers() -> None:
    raw = FIXTURE.read_bytes()

    assert validate_pdf(raw, max_bytes=1_000_000, max_pages=10) == 2
    batches = split_pdf(raw, batch_pages=1, max_bytes=1_000_000, max_pages=10)

    assert [(item.first_page, item.last_page) for item in batches] == [(1, 1), (2, 2)]
    assert all(len(PdfReader(BytesIO(item.pdf_bytes)).pages) == 1 for item in batches)


def test_pdf_validation_rejects_signature_size_and_page_limits() -> None:
    raw = FIXTURE.read_bytes()

    with pytest.raises(ValueError, match="not a PDF"):
        validate_pdf(b"not-pdf", max_bytes=100, max_pages=10)
    with pytest.raises(ValueError, match="upload limit"):
        validate_pdf(raw, max_bytes=10, max_pages=10)
    with pytest.raises(ValueError, match="configured maximum"):
        validate_pdf(raw, max_bytes=1_000_000, max_pages=1)
