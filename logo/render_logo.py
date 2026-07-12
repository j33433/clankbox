#!/usr/bin/env python3
"""Render logo.txt to a transparent PNG."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_SIZE = 18
FG_COLOR = (160, 160, 170, 255)  # grey
PADDING = 16


def main() -> None:
    logo_path = Path(__file__).resolve().parent / "logo.txt"
    text = logo_path.read_text().rstrip("\n")
    lines = text.splitlines()

    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)

    dummy = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(dummy)

    max_w = 0
    line_heights = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        max_w = max(max_w, w)
        line_heights.append(h)

    ascent, descent = font.getmetrics()
    row_h = ascent + descent
    img_w = max_w + PADDING * 2
    img_h = row_h * len(lines) + PADDING * 2

    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    y = PADDING
    for line in lines:
        draw.text((PADDING, y), line, font=font, fill=FG_COLOR)
        y += row_h

    out = Path(__file__).resolve().parent / "logo.png"
    img.save(out)
    print(f"wrote {out} ({img_w}x{img_h})")


if __name__ == "__main__":
    main()
