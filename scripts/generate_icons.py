"""Generate deterministic project-owned PWA icons without third-party assets."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "mfe_study_cloud" / "web" / "static"


def icon(size: int) -> None:
    image = Image.new("RGB", (size, size), "#16352d")
    draw = ImageDraw.Draw(image)
    margin = round(size * 0.14)
    draw.rounded_rectangle(
        (margin, margin, size - margin, size - margin),
        radius=round(size * 0.12),
        fill="#f4f0e8",
    )
    draw.rectangle(
        (round(size * 0.24), round(size * 0.25), round(size * 0.31), round(size * 0.75)),
        fill="#d56636",
    )
    draw.line(
        [
            (round(size * 0.39), round(size * 0.69)),
            (round(size * 0.39), round(size * 0.36)),
            (round(size * 0.50), round(size * 0.54)),
            (round(size * 0.61), round(size * 0.36)),
            (round(size * 0.61), round(size * 0.69)),
        ],
        fill="#16352d",
        width=round(size * 0.055),
        joint="curve",
    )
    image.save(STATIC / f"icon-{size}.png", optimize=True)


if __name__ == "__main__":
    STATIC.mkdir(parents=True, exist_ok=True)
    icon(192)
    icon(512)
