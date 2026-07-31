"""Render the Chip Orchestra header logo used by the IEEE Access report class.

The class pulls its running-header logo from ``Logo.png`` /
``notaglineLogo.png`` / ``jtehmLogo.png`` and its section bullet from
``bullet.png``. This script draws all four from the same brand mark as the
frontend favicon (``frontend/public/favicon.svg``): a rounded microchip glyph
in the sky-to-indigo gradient, plus the "CHIP ORCHESTRA" wordmark.

Regenerate after a branding change:

    python agent-service/reporting/templates/ieeeaccess/make_logo.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent

# Same geometry the header logo is scaled into by the class (width=7.61pc).
W, H = 981, 251
SS = 3  # supersampling factor — the glyph strokes are thin at 1x

# Brand palette, lifted from the favicon gradient.
SKY = (56, 189, 248)
BLUE = (14, 165, 233)
INDIGO = (29, 78, 216)
INK = (15, 23, 42)


def _lerp(a: tuple, b: tuple, t: float) -> tuple:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _gradient(size: tuple[int, int]) -> Image.Image:
    """Vertical sky → blue → indigo gradient, as in the favicon."""
    w, h = size
    grad = Image.new("RGB", (1, h))
    px = grad.load()
    for y in range(h):
        t = y / max(1, h - 1)
        px[0, y] = _lerp(SKY, BLUE, t / 0.52) if t <= 0.52 else _lerp(BLUE, INDIGO, (t - 0.52) / 0.48)
    return grad.resize((w, h))


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    names = (
        ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "Arial_Bold.ttf"]
        if bold
        else ["DejaVuSans.ttf", "LiberationSans-Regular.ttf", "Arial.ttf"]
    )
    for name in names:
        for root in ("/usr/share/fonts", "/usr/local/share/fonts"):
            hits = list(Path(root).rglob(name))
            if hits:
                return ImageFont.truetype(str(hits[0]), size)
    return ImageFont.load_default()


def _chip_glyph(box: int) -> Image.Image:
    """The microchip mark: gradient-filled rounded square with white pin/die
    strokes — the favicon's 64-unit artwork scaled to ``box`` pixels."""
    s = box * SS
    u = s / 64.0  # favicon user-unit → pixel
    glyph = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=int(16 * u), fill=255)
    body = _gradient((s, s)).convert("RGBA")
    body.putalpha(mask)
    glyph.alpha_composite(body)

    d = ImageDraw.Draw(glyph)
    stroke = max(1, int(3.5 * u))
    white = (255, 255, 255, 255)
    d.rounded_rectangle([21 * u, 21 * u, 43 * u, 43 * u], radius=int(4 * u),
                        outline=white, width=stroke)
    d.rectangle([27 * u, 28 * u, 37 * u, 36 * u], outline=white, width=stroke)
    for x in (25, 32, 39):  # top and bottom pins
        d.line([x * u, 14 * u, x * u, 21 * u], fill=white, width=stroke)
        d.line([x * u, 43 * u, x * u, 50 * u], fill=white, width=stroke)
    for y in (25, 32, 39):  # left and right pins
        d.line([14 * u, y * u, 21 * u, y * u], fill=white, width=stroke)
        d.line([43 * u, y * u, 50 * u, y * u], fill=white, width=stroke)

    return glyph.resize((box, box), Image.LANCZOS)


def build_logo() -> Image.Image:
    canvas = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))

    box = int(H * 0.86) * SS
    glyph = _chip_glyph(box)
    gy = (H * SS - box) // 2
    canvas.alpha_composite(glyph, (0, gy))

    d = ImageDraw.Draw(canvas)
    x = box + int(34 * SS)
    avail = W * SS - x - int(8 * SS)

    # Fit the wordmark to the space left of the glyph instead of assuming a
    # point size — a hard-coded size clipped "ORCHESTRA" off the canvas.
    def fit(text: str, start: int, bold: bool = True) -> ImageFont.FreeTypeFont:
        size = start
        while size > 8:
            font = _font(size, bold=bold)
            if d.textlength(text, font=font) <= avail:
                return font
            size -= 2
        return _font(8, bold=bold)

    gap = int(18 * SS)
    name_font = fit("CHIP ORCHESTRA", int(86 * SS))
    tagline = "AI-native RTL-to-GDSII orchestration"
    tag_font = fit(tagline, int(31 * SS), bold=False)

    chip_w = d.textlength("CHIP", font=name_font)
    name_h = name_font.getbbox("CHIP ORCHESTRA")[3]
    tag_h = tag_font.getbbox(tagline)[3]
    block = name_h + int(20 * SS) + tag_h
    top = (H * SS - block) // 2

    d.text((x, top), "CHIP", font=name_font, fill=(*INK, 255))
    d.text((x + chip_w + gap, top), "ORCHESTRA", font=name_font, fill=(*INDIGO, 255))
    d.text((x + int(3 * SS), top + name_h + int(20 * SS)), tagline,
           font=tag_font, fill=(100, 116, 139, 255))

    return canvas.resize((W, H), Image.LANCZOS)


def build_bullet(size: int = 64) -> Image.Image:
    """The class's section bullet — a brand-blue dot."""
    s = size * SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse([0, 0, s - 1, s - 1], fill=(*BLUE, 255))
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    logo = build_logo()
    # The class references three logo slots depending on mode; Chip Orchestra
    # uses one mark for all of them.
    for name in ("Logo.png", "notaglineLogo.png", "jtehmLogo.png"):
        logo.save(HERE / name)
    build_bullet().save(HERE / "bullet.png")
    print("wrote", ", ".join(sorted(p.name for p in HERE.glob("*.png"))))


if __name__ == "__main__":
    main()
