"""Generate an anonymous, copyright-safe two-page visual PDF fixture."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter


def demo_page(page_number: int) -> Image.Image:
    image = Image.new("RGB", (1240, 1754), "#fffdf8")
    draw = ImageDraw.Draw(image)
    eyebrow = ImageFont.load_default(size=24)
    title = ImageFont.load_default(size=62)
    body = ImageFont.load_default(size=32)
    small = ImageFont.load_default(size=25)
    draw.rectangle((0, 0, 1240, 28), fill="#16352d")
    draw.text(
        (110, 125),
        f"ANONYMOUS DEMO  /  PAGE {page_number}",
        font=eyebrow,
        fill="#d56636",
    )
    if page_number == 1:
        draw.text((110, 210), "A Small Study Fixture", font=title, fill="#16352d")
        lines = [
            "This document contains project-owned sample content.",
            "It is designed to verify upload, rendering, analysis,",
            "search, notes, progress, and tenant isolation.",
        ]
        callout = "Safe default: the fake provider makes no network request."
    else:
        draw.text((110, 210), "Duration: A Tiny Example", font=title, fill="#16352d")
        lines = [
            "Modified duration approximates price sensitivity",
            "for a small parallel change in yield.",
            "Example notation: dP / P is approximately -D x dy",
        ]
        callout = "The numbers are illustrative, anonymous, and not financial advice."
    y = 360
    for line in lines:
        draw.text((110, y), line, font=body, fill="#263530")
        y += 62
    draw.rounded_rectangle((110, 650, 1130, 880), radius=34, fill="#e8eee5")
    draw.text((165, 715), "STUDY PROMPT", font=eyebrow, fill="#486b55")
    draw.text((165, 775), callout, font=small, fill="#16352d")
    draw.line((110, 1540, 1130, 1540), fill="#d8d1c5", width=3)
    draw.text(
        (110, 1580),
        "MFE Study Cloud contributors  |  generated fixture",
        font=small,
        fill="#66736e",
    )
    return image


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    fixtures = root / "tests" / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    pages = [demo_page(1), demo_page(2)]
    buffer = BytesIO()
    pages[0].save(
        buffer,
        format="PDF",
        save_all=True,
        append_images=pages[1:],
        resolution=150,
    )
    reader = PdfReader(BytesIO(buffer.getvalue()))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
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
