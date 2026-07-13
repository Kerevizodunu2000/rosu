"""Generate the app icon (concept D: 'o!' monogram) in osu!'s pink palette.

Run:  python -m osu_archiver.assets.make_icon
Outputs icon.png (256), icon.ico (multi-size), splash.png next to this file.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent

# osu!-flavoured pinks
PINK_TOP = (255, 124, 192)      # #ff7cc0
PINK_BOTTOM = (232, 62, 140)    # #e83e8c
WHITE = (255, 255, 255, 255)


def _vertical_gradient(size: int, top, bottom) -> Image.Image:
    grad = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        grad.putpixel((0, y), tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    return grad.resize((size, size))


def _rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def render(size: int = 256) -> Image.Image:
    s = size * 4  # supersample for smooth edges
    bg = _vertical_gradient(s, PINK_TOP, PINK_BOTTOM).convert("RGBA")
    bg.putalpha(_rounded_mask(s, int(s * 0.22)))
    d = ImageDraw.Draw(bg)

    # the 'o' — a thick white ring, left of centre
    cx, cy, r = int(s * 0.40), int(s * 0.52), int(s * 0.20)
    ring = int(s * 0.075)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=WHITE, width=ring)

    # the '!' — bar + dot, right of the ring
    bx = int(s * 0.66)
    bw = int(s * 0.075)
    d.rounded_rectangle([bx, int(s * 0.30), bx + bw, int(s * 0.60)],
                        radius=bw // 2, fill=WHITE)
    dot_r = int(s * 0.05)
    dcy = int(s * 0.70)
    d.ellipse([bx + bw // 2 - dot_r, dcy - dot_r,
               bx + bw // 2 + dot_r, dcy + dot_r], fill=WHITE)

    return bg.resize((size, size), Image.LANCZOS)


def make_splash() -> Image.Image:
    w, h = 520, 300
    img = _vertical_gradient(max(w, h), PINK_TOP, PINK_BOTTOM).convert("RGBA").resize((w, h))
    icon = render(140)
    img.alpha_composite(icon, (w // 2 - 70, 40))
    d = ImageDraw.Draw(img)
    d.text((w // 2, 210), "osu! Archive Manager", fill=WHITE, anchor="mm")
    return img


def main() -> None:
    icon = render(256)
    icon.save(HERE / "icon.png")
    icon.save(HERE / "icon.ico",
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                     (128, 128), (256, 256)])
    make_splash().save(HERE / "splash.png")
    print("wrote icon.png, icon.ico, splash.png to", HERE)


if __name__ == "__main__":
    main()
