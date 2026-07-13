"""Icon design lab for Rosu — exports the concept icons and generates the
geometric-rose variations (the direction picked from round 1: concept #15).

Run:  python -m osu_archiver.assets.icon_lab
Outputs (all vector SVG, plus PNG for the pure-path round-2 set):
    docs/icons/round1/*.svg          the 20 round-1 concepts (archived, not lost)
    docs/icons/round1.html           the round-1 gallery (self-contained)
    docs/icons/round2/*.svg + *.png  20 geometric-rose variations to choose from
    docs/icons/round2.html           the round-2 gallery (self-contained)

Vector SVG is the master format; the chosen icon is later rasterised to the
multi-size .ico/.png + splash by make_icon.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRATCH_HTML = None  # optional: a round-1 gallery html to harvest concepts from
OUT = REPO / "docs" / "icons"

RECT = '<rect x="2" y="2" width="96" height="96" rx="24"'

# ---- gradients shared by every icon ---------------------------------------
GRADS = """
<linearGradient id="gPink" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#ff8ab5"/><stop offset="1" stop-color="#ff3d86"/></linearGradient>
<linearGradient id="gRose" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#8f2455"/><stop offset="1" stop-color="#3d1230"/></linearGradient>
<linearGradient id="gInk" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#2a1019"/><stop offset="1" stop-color="#120810"/></linearGradient>
<linearGradient id="gGeo" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="#ffa0c6"/><stop offset="1" stop-color="#ff2f7d"/></linearGradient>
<radialGradient id="gGlass" cx="0.38" cy="0.32" r="0.85">
  <stop offset="0" stop-color="#ffe0ec"/><stop offset="0.5" stop-color="#ff77ac"/>
  <stop offset="1" stop-color="#ff2f7d"/></radialGradient>
<linearGradient id="gSoft" x1="0" y1="0" x2="0" y2="1">
  <stop offset="0" stop-color="#ffe9f2"/><stop offset="1" stop-color="#ffd0e2"/></linearGradient>
"""

# petal + bloom used by the round-1 concepts (kept so their SVGs stand alone)
BLOOM_DEFS = """
<path id="petal" d="M0 0 C 13 -9 13 -33 0 -43 C -13 -33 -13 -9 0 0 Z"/>
<symbol id="bloom" viewBox="-50 -50 100 100"><g fill="currentColor">
  <g opacity="0.95"><use href="#petal"/><use href="#petal" transform="rotate(72)"/>
    <use href="#petal" transform="rotate(144)"/><use href="#petal" transform="rotate(216)"/>
    <use href="#petal" transform="rotate(288)"/></g>
  <g opacity="0.72" transform="rotate(36) scale(.6)"><use href="#petal"/>
    <use href="#petal" transform="rotate(72)"/><use href="#petal" transform="rotate(144)"/>
    <use href="#petal" transform="rotate(216)"/><use href="#petal" transform="rotate(288)"/></g>
  <circle r="6.5" opacity="0.9"/></g></symbol>
"""

DEFS_FULL = GRADS + BLOOM_DEFS


def _svg_file(inner: str, defs: str = DEFS_FULL) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" '
            f'width="256" height="256"><defs>{defs}</defs>{inner}</svg>')


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# =====================================================================
# Round 1 — the 20 concepts (inner SVG, so their .svg files stand alone)
# =====================================================================
def round1_icons() -> list[tuple[str, str]]:
    R = RECT
    return [
        ("Bloom pink", f'{R} fill="url(#gPink)"/><g transform="translate(50 50) scale(.86)" style="color:#fff"><use href="#bloom" x="-50" y="-50" width="100" height="100"/></g>'),
        ("Bloom deep rose", f'{R} fill="url(#gRose)"/><g transform="translate(50 50) scale(.86)" style="color:#ffd7e6"><use href="#bloom" x="-50" y="-50" width="100" height="100"/></g>'),
        ("Bloom midnight", f'{R} fill="url(#gInk)"/><g transform="translate(50 50) scale(.86)" style="color:#ff5aa2"><use href="#bloom" x="-50" y="-50" width="100" height="100"/></g>'),
        ("Bloom outline", f'{R} fill="#fff2f8" stroke="#ffcfe1" stroke-width="1.5"/><g transform="translate(50 50) scale(.86)" style="color:#ff3d86"><use href="#bloom" x="-50" y="-50" width="100" height="100"/></g>'),
        ("Hit-circle rose", f'{R} fill="url(#gPink)"/><circle cx="50" cy="50" r="31" fill="none" stroke="#fff" stroke-width="9"/><g transform="translate(50 50) scale(.4)" style="color:#fff"><use href="#bloom" x="-50" y="-50" width="100" height="100"/></g>'),
        ("Approach circle", f'{R} fill="url(#gInk)"/><circle cx="50" cy="50" r="38" fill="none" stroke="#ff5aa2" stroke-width="2.5" opacity="0.55"/><circle cx="50" cy="50" r="27" fill="none" stroke="#ff5aa2" stroke-width="2.5" opacity="0.8"/><g transform="translate(50 50) scale(.44)" style="color:#ff5aa2"><use href="#bloom" x="-50" y="-50" width="100" height="100"/></g>'),
        ("r monogram", f'{R} fill="url(#gPink)"/><circle cx="50" cy="50" r="33" fill="#fff2f8"/><path d="M40 34 v32 M40 45 q6 -12 20 -9" fill="none" stroke="#ff2f7d" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>'),
        ("r petal dot", f'{R} fill="#fff2f8" stroke="#ffcfe1" stroke-width="1.5"/><path d="M36 40 v30 M36 50 q7 -13 20 -11" fill="none" stroke="#ff2f7d" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/><g transform="translate(66 34) scale(.2)" style="color:#ff5aa2"><use href="#bloom" x="-50" y="-50" width="100" height="100"/></g>'),
        ("Question rose", f'{R} fill="url(#gPink)"/><path d="M38 40 a12 12 0 1 1 15 12 c-4 3 -4 6 -4 9" fill="none" stroke="#fff" stroke-width="8" stroke-linecap="round"/><g transform="translate(49 72) scale(.22)" style="color:#fff"><use href="#bloom" x="-50" y="-50" width="100" height="100"/></g>'),
        ("Petal mandala", f'{R} fill="url(#gRose)"/><g transform="translate(50 50)" fill="#ffd7e6"><g opacity=".95"><use href="#petal" transform="scale(.78)"/><use href="#petal" transform="rotate(45) scale(.78)"/><use href="#petal" transform="rotate(90) scale(.78)"/><use href="#petal" transform="rotate(135) scale(.78)"/><use href="#petal" transform="rotate(180) scale(.78)"/><use href="#petal" transform="rotate(225) scale(.78)"/><use href="#petal" transform="rotate(270) scale(.78)"/><use href="#petal" transform="rotate(315) scale(.78)"/></g><circle r="7" fill="#ff5aa2"/></g>'),
        ("Heart rose", f'{R} fill="#fff2f8" stroke="#ffcfe1" stroke-width="1.5"/><path d="M50 74 C 24 56 26 34 40 32 C 47 31 50 37 50 41 C 50 37 53 31 60 32 C 74 34 76 56 50 74 Z" fill="url(#gPink)"/><g transform="translate(50 47) scale(.34)" style="color:#fff"><use href="#bloom" x="-50" y="-50" width="100" height="100"/></g>'),
        ("Vinyl rose", f'{R} fill="url(#gInk)"/><circle cx="50" cy="50" r="34" fill="none" stroke="#3a2130" stroke-width="1.5"/><circle cx="50" cy="50" r="28" fill="none" stroke="#3a2130" stroke-width="1.5"/><circle cx="50" cy="50" r="22" fill="none" stroke="#3a2130" stroke-width="1.5"/><g transform="translate(50 50) scale(.34)" style="color:#ff5aa2"><use href="#bloom" x="-50" y="-50" width="100" height="100"/></g>'),
        ("Spiral swirl", f'{R} fill="#fff2f8" stroke="#ffcfe1" stroke-width="1.5"/><path d="M50 50 a4 4 0 1 1 4 -4 a11 11 0 1 1 -14 3 a19 19 0 1 1 26 -6 a27 27 0 1 1 -35 9" fill="none" stroke="#ff2f7d" stroke-width="6.5" stroke-linecap="round"/>'),
        ("Line rosebud", f'{R} fill="url(#gSoft)"/><path d="M50 30 c-9 4 -12 14 -6 20 c4 4 10 4 12 -1 c-4 8 -12 9 -18 4 c8 12 22 10 24 -3 M50 52 v18" fill="none" stroke="#c0246a" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>'),
        ("Geometric rose", f'{R} fill="#fff2f8" stroke="#ffcfe1" stroke-width="1.5"/><g transform="translate(50 50)"><path d="M0 -26 L14 -8 L0 6 L-14 -8 Z" fill="#ff8fbf"/><path d="M0 6 L18 2 L10 22 Z" fill="#ff5f9c"/><path d="M0 6 L-18 2 L-10 22 Z" fill="#ff5f9c"/><path d="M0 6 L10 22 L-10 22 Z" fill="#ff2f7d"/><circle cy="-6" r="5" fill="#b0225f"/></g>'),
        ("Spinner rose", f'{R} fill="url(#gInk)"/><g transform="translate(50 50)" stroke="#ff5aa2" stroke-width="4" stroke-linecap="round"><line y2="-34"/><line y2="-34" transform="rotate(45)"/><line y2="-34" transform="rotate(90)"/><line y2="-34" transform="rotate(135)"/><line y2="-34" transform="rotate(180)"/><line y2="-34" transform="rotate(225)"/><line y2="-34" transform="rotate(270)"/><line y2="-34" transform="rotate(315)"/></g><g transform="translate(50 50) scale(.34)" style="color:#ffd7e6"><use href="#bloom" x="-50" y="-50" width="100" height="100"/></g>'),
        ("Question hit-circle", f'{R} fill="url(#gPink)"/><circle cx="50" cy="50" r="31" fill="none" stroke="#fff" stroke-width="8"/><path d="M42 42 a8 8 0 1 1 10 8 c-3 2 -3 4 -3 6 M49 62 v.5" fill="none" stroke="#fff" stroke-width="6.5" stroke-linecap="round"/>'),
        ("Droplet rose", f'{R} fill="url(#gSoft)"/><path d="M50 24 C 66 44 70 54 70 62 a20 20 0 1 1 -40 0 C 30 54 34 44 50 24 Z" fill="url(#gPink)"/><g transform="translate(50 60) scale(.32)" style="color:#fff"><use href="#bloom" x="-50" y="-50" width="100" height="100"/></g>'),
        ("Rose play", f'{R} fill="url(#gRose)"/><g transform="translate(46 50) scale(.8)" style="color:#ffd7e6"><use href="#bloom" x="-50" y="-50" width="100" height="100"/></g><path d="M60 42 L74 50 L60 58 Z" fill="#fff"/>'),
        ("Glass bloom", f'{R} fill="#fff2f8" stroke="#ffcfe1" stroke-width="1.5"/><g transform="translate(50 50) scale(.82)" fill="url(#gGlass)"><g opacity=".95"><use href="#petal"/><use href="#petal" transform="rotate(72)"/><use href="#petal" transform="rotate(144)"/><use href="#petal" transform="rotate(216)"/><use href="#petal" transform="rotate(288)"/></g><g opacity=".72" transform="rotate(36) scale(.6)"><use href="#petal"/><use href="#petal" transform="rotate(72)"/><use href="#petal" transform="rotate(144)"/><use href="#petal" transform="rotate(216)"/><use href="#petal" transform="rotate(288)"/></g><circle r="6.5" fill="#b0225f"/></g>'),
    ]


# =====================================================================
# Round 2 — 20 geometric-rose variations (pure paths, the picked #15 look)
# =====================================================================
def _kite(H, w, h):
    return f"M0 0 L{w} {-h} L0 {-H} L{-w} {-h} Z"


def geo_bloom(n, colors, H=30, w=11, h=13, inner=None, rot0=0.0,
              center="#b0225f", cr=5, stroke=None):
    """n kite-petals radiating from the centre, colours cycling, optional inner ring."""
    step = 360 / n
    parts = []
    sattr = f' stroke="{stroke}" stroke-width="1.6" stroke-linejoin="round"' if stroke else ""
    for i in range(n):
        parts.append(f'<path d="{_kite(H, w, h)}" fill="{colors[i % len(colors)]}"{sattr} '
                     f'transform="rotate({rot0 + i * step:.1f})"/>')
    if inner:
        icolors, iscale, irot = inner
        for i in range(n):
            parts.append(f'<path d="{_kite(H * iscale, w * iscale, h * iscale)}" '
                         f'fill="{icolors[i % len(icolors)]}"{sattr} '
                         f'transform="rotate({rot0 + irot + i * step:.1f})"/>')
    parts.append(f'<circle r="{cr}" fill="{center}"/>')
    return "".join(parts)


# base concept #15 recoloured (the exact faceted layout the user liked)
def orig(c1, c2, c3, c4, stroke=None):
    s = f' stroke="{stroke}" stroke-width="1.4" stroke-linejoin="round"' if stroke else ""
    return (f'<path d="M0 -26 L14 -8 L0 6 L-14 -8 Z" fill="{c1}"{s}/>'
            f'<path d="M0 6 L18 2 L10 22 Z" fill="{c2}"{s}/>'
            f'<path d="M0 6 L-18 2 L-10 22 Z" fill="{c2}"{s}/>'
            f'<path d="M0 6 L10 22 L-10 22 Z" fill="{c3}"{s}/>'
            f'<circle cy="-6" r="5" fill="{c4}"/>')


LIGHT = ["#ffe0ec", "#ff9ec4", "#ff6aa2", "#ff3d86"]
PINK = ["#ff9ec4", "#ff6aa2", "#ff3d86", "#d81b64"]
WHITE = ["#ffffff", "#ffe0ec", "#ffb3d1", "#ff8fbf"]
DEEP = ["#ff6aa2", "#ff3d86", "#d81b64", "#a5175a"]


def round2_icons() -> list[tuple[str, str, str]]:
    """(name, note, inner-svg) — pure-path geometric roses."""
    R = RECT
    bg = {
        "pink": f'{R} fill="url(#gPink)"/>',
        "rose": f'{R} fill="url(#gRose)"/>',
        "ink": f'{R} fill="url(#gInk)"/>',
        "soft": f'{R} fill="#fff2f8" stroke="#ffcfe1" stroke-width="1.5"/>',
        "geo": f'{R} fill="url(#gGeo)"/>',
    }

    def C(inner, scale=0.9, tx=50, ty=50):
        return f'<g transform="translate({tx} {ty}) scale({scale})">{inner}</g>'

    ring = '<circle cx="50" cy="50" r="32" fill="none" stroke="#fff" stroke-width="8"/>'
    approach = ('<circle cx="50" cy="50" r="40" fill="none" stroke="#ff6aa2" stroke-width="2" opacity=".5"/>'
                '<circle cx="50" cy="50" r="30" fill="none" stroke="#ff6aa2" stroke-width="2" opacity=".8"/>')

    items = [
        ("Original · soft", "the #15 look, on soft pink",
         bg["soft"] + C(orig("#ff8fbf", "#ff5f9c", "#ff2f7d", "#b0225f"))),
        ("Original · pink", "light facets on pink",
         bg["pink"] + C(orig("#ffffff", "#ffd0e2", "#ffb3d1", "#a5175a"))),
        ("Original · midnight", "glowing facets on near-black",
         bg["ink"] + C(orig("#ff8fbf", "#ff5f9c", "#ff2f7d", "#ffd0e2"))),
        ("Original · rose", "light facets on deep rose",
         bg["rose"] + C(orig("#ffd0e2", "#ff9ec4", "#ff6aa2", "#ffe0ec"))),
        ("Original · outlined", "line-art facets",
         bg["soft"] + C(orig("#ffe0ec", "#ffc2da", "#ff9ec4", "#ff2f7d", stroke="#c0246a"))),
        ("5-fold · pink", "five-petal geometric bloom",
         bg["soft"] + C(geo_bloom(5, PINK), 0.92)),
        ("6-fold · midnight", "six petals, glow",
         bg["ink"] + C(geo_bloom(6, DEEP, H=28), 0.92)),
        ("4-fold · pink bg", "four white petals on pink",
         bg["pink"] + C(geo_bloom(4, WHITE, center="#a5175a"), 0.92)),
        ("5-fold · layered", "outer + inner ring, on rose",
         bg["rose"] + C(geo_bloom(5, LIGHT, inner=(["#ffe0ec"], 0.55, 36), center="#ffe0ec"), 0.92)),
        ("6-fold · layered", "double ring bloom",
         bg["soft"] + C(geo_bloom(6, PINK, H=27, inner=(["#ff2f7d"], 0.5, 30)), 0.92)),
        ("5-fold · gradient", "gradient-filled petals",
         bg["soft"] + C(geo_bloom(5, ["url(#gGeo)"], center="#b0225f"), 0.92)),
        ("8-fold · crystal", "eight sharp facets",
         bg["ink"] + C(geo_bloom(8, DEEP, H=30, w=7, h=10), 0.92)),
        ("5-fold · hit-circle", "bloom inside an osu! ring",
         bg["pink"] + ring + C(geo_bloom(5, WHITE, center="#a5175a"), 0.5)),
        ("6-fold · approach", "approach-circle framing",
         bg["ink"] + approach + C(geo_bloom(6, DEEP, H=22), 0.5)),
        ("5-fold · spiky", "elongated petals",
         bg["rose"] + C(geo_bloom(5, LIGHT, H=38, w=8, h=16, center="#ffe0ec"), 0.86)),
        ("6-fold · rounded", "short, soft petals",
         bg["soft"] + C(geo_bloom(6, PINK, H=22, w=13, h=12), 0.96)),
        ("4-fold · two-tone", "alternating pink/magenta",
         bg["soft"] + C(geo_bloom(8, ["#ff8fbf", "#ff2f7d"], H=30, w=9, h=12), 0.92)),
        ("5-fold · outlined", "light petals, deep outline",
         bg["soft"] + C(geo_bloom(5, ["#ffe0ec"], stroke="#ff2f7d", center="#ff2f7d"), 0.92)),
        ("5-fold · pinwheel", "rotated rings, motion",
         bg["pink"] + C(geo_bloom(5, WHITE, inner=(["#ffd0e2"], 0.6, 20), center="#a5175a"), 0.92)),
        ("3-fold · minimal", "bold three-facet mark",
         bg["geo"] + C(geo_bloom(3, ["#ffffff", "#ffd0e2", "#ffb3d1"], H=32, w=15, h=15,
                                  center="#a5175a"), 0.9)),
    ]
    return items


# =====================================================================
# Rasterise (best effort) + gallery
# =====================================================================
def _render_png(svg: str, path: Path, size: int = 256) -> bool:
    try:
        from PySide6.QtCore import QByteArray, Qt
        from PySide6.QtGui import QGuiApplication, QImage, QPainter
        from PySide6.QtSvg import QSvgRenderer
    except Exception:
        return False
    if QGuiApplication.instance() is None:
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        _render_png._app = QGuiApplication([])  # keep a ref alive
    r = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not r.isValid():
        return False
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    r.render(p)
    p.end()
    return bool(img.save(str(path)))


def _gallery(title: str, items: list[tuple], out: Path, numbered_from: int = 1) -> None:
    tiles = []
    for i, it in enumerate(items):
        name = it[0]
        note = it[1] if len(it) > 2 else ""
        inner = it[-1]
        n = f"{numbered_from + i:02d}"
        tiles.append(
            f'<div class="card"><span class="num">{n}</span>'
            f'<div class="stage"><svg class="lg" viewBox="0 0 100 100"><defs>{DEFS_FULL}</defs>{inner}</svg>'
            f'<div class="minis"><svg class="sm" viewBox="0 0 100 100"><defs>{DEFS_FULL}</defs>{inner}</svg>'
            f'<svg class="xs" viewBox="0 0 100 100"><defs>{DEFS_FULL}</defs>{inner}</svg>'
            f'<span>40·22</span></div></div>'
            f'<div class="meta"><span class="name">{n} · {name}</span>'
            f'<span class="desc">{note}</span></div></div>')
    html = f"""<title>{title}</title><style>
:root{{--bg:#fff4f9;--panel:#fff;--line:#f3c6db;--text:#2a1420;--muted:#9a5b7a;--accent:#ff3d86}}
@media(prefers-color-scheme:dark){{:root{{--bg:#140a10;--panel:#1e0f18;--line:#3a1c2c;--text:#ffe3ef;--muted:#c48fa9;--accent:#ff5aa2}}}}
:root[data-theme=light]{{--bg:#fff4f9;--panel:#fff;--line:#f3c6db;--text:#2a1420;--muted:#9a5b7a;--accent:#ff3d86}}
:root[data-theme=dark]{{--bg:#140a10;--panel:#1e0f18;--line:#3a1c2c;--text:#ffe3ef;--muted:#c48fa9;--accent:#ff5aa2}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--text);font-family:"Segoe UI",system-ui,sans-serif}}
.wrap{{max-width:1160px;margin:0 auto;padding:44px 26px 72px}}
h1{{font-size:34px;margin:0 0 6px;letter-spacing:-.02em;background:linear-gradient(120deg,var(--accent),#ff8fbf);-webkit-background-clip:text;background-clip:text;color:transparent}}
.lede{{color:var(--muted);max-width:64ch;margin:0 0 30px}}
.grid{{display:grid;gap:18px;grid-template-columns:repeat(auto-fill,minmax(210px,1fr))}}
.card{{position:relative;background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:18px;display:flex;flex-direction:column;gap:10px;box-shadow:0 10px 26px rgba(255,61,134,.12)}}
.num{{position:absolute;top:12px;left:14px;font-size:12px;font-weight:800;color:var(--muted)}}
.stage{{display:flex;align-items:center;gap:14px}}
.lg{{width:104px;height:104px;border-radius:24px;box-shadow:0 6px 16px rgba(0,0,0,.18)}}
.minis{{display:flex;flex-direction:column;gap:8px;align-items:center}}
.sm{{width:40px;height:40px;border-radius:11px}}.xs{{width:22px;height:22px;border-radius:7px}}
.minis span{{font-size:10px;color:var(--muted)}}
.name{{font-weight:700;font-size:15px}}.desc{{font-size:12.5px;color:var(--muted)}}
</style><div class="wrap"><h1>{title}</h1>
<p class="lede">Geometric-rose variations of concept&nbsp;#15 for <b>Rosu</b> — rose · osu&nbsp;pink · round.
Each is a complete app icon (large + 40&nbsp;px + 22&nbsp;px). Tell me the number and I'll finalise it into the .ico/.png + splash.</p>
<div class="grid">{''.join(tiles)}</div></div>"""
    out.write_text(html, encoding="utf-8")


def main() -> None:
    (OUT / "round1").mkdir(parents=True, exist_ok=True)
    (OUT / "round2").mkdir(parents=True, exist_ok=True)

    r1 = round1_icons()
    for i, (name, inner) in enumerate(r1, 1):
        (OUT / "round1" / f"{i:02d}-{_slug(name)}.svg").write_text(
            _svg_file(inner), encoding="utf-8")
    _gallery("Rosu — round 1 concepts", [(n, "", s) for n, s in r1],
             OUT / "round1.html")

    r2 = round2_icons()
    png_ok = 0
    for i, (name, note, inner) in enumerate(r2, 1):
        svg = _svg_file(inner)
        stem = f"{i:02d}-{_slug(name)}"
        (OUT / "round2" / f"{stem}.svg").write_text(svg, encoding="utf-8")
        if _render_png(svg, OUT / "round2" / f"{stem}.png"):
            png_ok += 1
    _gallery("Rosu — geometric rose (round 2)", r2, OUT / "round2.html")

    print(f"round1: {len(r1)} svg  ->  {OUT/'round1'}")
    print(f"round2: {len(r2)} svg, {png_ok} png  ->  {OUT/'round2'}")
    print(f"galleries: {OUT/'round1.html'} , {OUT/'round2.html'}")


if __name__ == "__main__":
    main()
