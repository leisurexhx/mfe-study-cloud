"""Generate anonymous, copyright-safe fixtures from blank pages."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfWriter


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    fixtures = root / "tests" / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    writer.add_blank_page(width=420, height=594)
    writer.add_blank_page(width=420, height=594)
    writer.add_metadata(
        {
            "/Title": "Anonymous MFE Study Cloud Demo",
            "/Author": "MFE Study Cloud contributors",
            "/Subject": "Generated fixture with no third-party course content",
        }
    )
    with (fixtures / "anonymous-demo.pdf").open("wb") as stream:
        writer.write(stream)


if __name__ == "__main__":
    main()

