"""Bounded PDF validation and page-range splitting for provider calls."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader, PdfWriter


@dataclass(frozen=True, slots=True)
class PdfBatch:
    first_page: int
    last_page: int
    pdf_bytes: bytes


def validate_pdf(raw: bytes, *, max_bytes: int, max_pages: int) -> int:
    if not raw or len(raw) > max_bytes:
        raise ValueError("PDF is empty or exceeds the configured upload limit.")
    if not raw.startswith(b"%PDF-"):
        raise ValueError("Uploaded file is not a PDF.")
    try:
        reader = PdfReader(BytesIO(raw), strict=True)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported.")
        page_count = len(reader.pages)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("PDF is damaged or cannot be parsed.") from exc
    if page_count < 1:
        raise ValueError("PDF has no readable pages.")
    if page_count > max_pages:
        raise ValueError(f"PDF has {page_count} pages; configured maximum is {max_pages}.")
    return page_count


def split_pdf(raw: bytes, *, batch_pages: int, max_bytes: int, max_pages: int) -> list[PdfBatch]:
    page_count = validate_pdf(raw, max_bytes=max_bytes, max_pages=max_pages)
    reader = PdfReader(BytesIO(raw), strict=True)
    batches: list[PdfBatch] = []
    for offset in range(0, page_count, batch_pages):
        writer = PdfWriter()
        stop = min(offset + batch_pages, page_count)
        for page_index in range(offset, stop):
            writer.add_page(reader.pages[page_index])
        buffer = BytesIO()
        writer.write(buffer)
        batches.append(
            PdfBatch(first_page=offset + 1, last_page=stop, pdf_bytes=buffer.getvalue())
        )
    return batches

