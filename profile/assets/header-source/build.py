"""Builds the MK Global org profile header as two flat SVGs (light, dark).

All text is converted to outlines so the header renders the same everywhere,
including GitHub, which loads README images without external fonts.

Needs fontTools and hb-shape (HarfBuzz). Put static instances of Plus Jakarta Sans 800,
Geist Mono 500 and 700 and Cairo 600 from Google Fonts in fonts/ as jakarta-800.ttf,
geistmono-500.ttf, geistmono-700.ttf and cairo-600.ttf, then run:

    python3 build.py ..
"""

import json
import re
import subprocess
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).parent
FONTS = HERE / "fonts"
LOGO = HERE
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "out"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 1600, 440

THEMES = {
    "light": {
        "bg": "#ffffff",
        "frame": "#d9dee7",
        "ink": "#1a3057",
        "muted": "#5b6b85",
        "faint": "#d5dbe5",
        "meta": "#8c99ae",
        "accent": "#f07c10",
        "mark_navy": "#1a3057",
        "node_fill": "#ffffff",
    },
    "dark": {
        "bg": "#1a3057",
        "frame": "#1a3057",
        "ink": "#ffffff",
        "muted": "#a9b6cc",
        "faint": "#314a73",
        "meta": "#7d90b0",
        "accent": "#f7892a",
        "mark_navy": "#ffffff",
        "node_fill": "#1a3057",
    },
}

_fonts: dict[str, TTFont] = {}


def font(name: str) -> TTFont:
    if name not in _fonts:
        _fonts[name] = TTFont(FONTS / name)
    return _fonts[name]


def text(name, s, size, x, y, tracking=0.0, anchor="start", features=""):
    """Shape `s` with HarfBuzz and return (svg path d, width) at baseline y."""
    path = FONTS / name
    args = ["hb-shape", str(path), s, "--output-format=json", "--no-glyph-names"]
    if features:
        args.append(f"--features={features}")
    glyphs = json.loads(subprocess.check_output(args))
    f = font(name)
    upm = f["head"].unitsPerEm
    scale = size / upm
    track = tracking * size
    width = sum(g["ax"] for g in glyphs) * scale + track * (len(glyphs) - 1)
    if anchor == "end":
        x -= width
    elif anchor == "middle":
        x -= width / 2
    gs = f.getGlyphSet()
    order = f.getGlyphOrder()
    pen = SVGPathPen(gs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
    cx = x
    for g in glyphs:
        gx = cx + g["dx"] * scale
        gy = y - g["dy"] * scale
        tp = TransformPen(pen, (scale, 0, 0, -scale, gx, gy))
        gs[order[g["g"]]].draw(tp)
        cx += g["ax"] * scale + track
    return pen.getCommands(), width


def mark_paths():
    """The traced MK mark: navy (M and the tail of the swoosh) and orange (K and arrow)."""
    def read(n):
        return re.findall(r'<path d="([^"]+)"', (LOGO / f"{n}.svg").read_text())
    return read("navy"), read("orange")


# Mark bounding box in the 2048 px trace, found with `magick -trim`.
MARK_BOX = (457, 571, 1131, 661)

# Map projection for the route figure, from real coordinates.
PLACES = {
    "BEY": (35.50, 33.89),
    "DXB": (55.36, 25.25),
    "KSA": (46.70, 24.71),
}
MAP_X0, MAP_Y0, K = 1010, 118, 24.0


def project(lon, lat):
    return MAP_X0 + (lon - 35.50) * K, MAP_Y0 + (33.89 - lat) * K


def build(theme: str) -> str:
    t = THEMES[theme]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
        f'role="img" aria-labelledby="title">',
        "<title id=\"title\">MK Global. Shop Global. Deliver to Lebanon. By air from Dubai and by land from "
        "Saudi Arabia, into Beirut and on to your door.</title>",
        f'<defs><clipPath id="card"><rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="21"/></clipPath></defs>',
        f'<rect x="1" y="1" width="{W - 2}" height="{H - 2}" rx="22" fill="{t["bg"]}" '
        f'stroke="{t["frame"]}" stroke-width="2"/>',
        '<g clip-path="url(#card)">',
    ]

    # Lockup: the mark, then GLOBAL, as on the official horizontal logo.
    navy, orange = mark_paths()
    bx, by, bw, bh = MARK_BOX
    mark_h = 104
    s = mark_h / bh
    mx, my = 80, 78
    tr = f"translate({mx - bx * s:.2f},{my - by * s:.2f}) scale({s:.5f})"
    inner = "translate(0,2048) scale(0.1,-0.1)"
    parts.append(f'<g transform="{tr}"><g transform="{inner}">')
    parts.append(f'<path fill="{t["accent"]}" d="{" ".join(orange)}"/>')
    parts.append(f'<path fill="{t["mark_navy"]}" d="{" ".join(navy)}"/>')
    parts.append("</g></g>")
    word_x = mx + bw * s + 26
    d, _ = text("jakarta-800.ttf", "GLOBAL", 66, word_x, my + mark_h - 22, tracking=0.04)
    parts.append(f'<path fill="{t["ink"]}" d="{d}"/>')

    # Line and Arabic line.
    d, _ = text("jakarta-800.ttf", "Shop Global. Deliver to Lebanon.", 47, 80, 286, tracking=-0.02)
    parts.append(f'<path fill="{t["ink"]}" d="{d}"/>')
    d, _ = text("cairo-600.ttf", "تسوّق عالميًا. منوصّل عَ لبنان.", 32, 80, 348)
    parts.append(f'<path fill="{t["muted"]}" d="{d}"/>')

    # Route figure.
    bey = project(*PLACES["BEY"])
    dxb = project(*PLACES["DXB"])
    ksa = project(*PLACES["KSA"])

    # Land: a transit-map line with 45 degree bends, north out of Saudi Arabia, then west.
    rise = 84
    land = [ksa, (ksa[0], ksa[1] - rise), (ksa[0] - (ksa[1] - rise - bey[1]), bey[1]), bey]
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in land)
    parts.append(
        f'<polyline points="{pts}" fill="none" stroke="{t["ink"]}" stroke-width="5" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
    )

    # Air: an arc from Dubai over the top, landing on Beirut.
    c1 = (dxb[0] - 30, bey[1] - 96)
    c2 = (bey[0] + 190, bey[1] - 92)
    parts.append(
        f'<path d="M{dxb[0]:.1f},{dxb[1]:.1f} C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} '
        f'{bey[0]:.1f},{bey[1]:.1f}" fill="none" stroke="{t["accent"]}" stroke-width="5" '
        f'stroke-linecap="round" stroke-dasharray="1 14"/>'
    )

    # Stubs off the edge of the map: orders arrive from stores around the world.
    parts.append(
        f'<line x1="{W}" y1="{dxb[1]:.1f}" x2="{dxb[0]:.1f}" y2="{dxb[1]:.1f}" stroke="{t["faint"]}" stroke-width="5"/>'
        f'<line x1="{ksa[0]:.1f}" y1="{H}" x2="{ksa[0]:.1f}" y2="{ksa[1]:.1f}" stroke="{t["faint"]}" stroke-width="5"/>'
    )

    # Nodes.
    for (x, y), color in ((dxb, t["accent"]), (ksa, t["ink"])):
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" fill="{t["node_fill"]}" stroke="{color}" stroke-width="5"/>'
        )
    parts.append(f'<circle cx="{bey[0]:.1f}" cy="{bey[1]:.1f}" r="22" fill="{t["accent"]}"/>')
    parts.append(f'<circle cx="{bey[0]:.1f}" cy="{bey[1]:.1f}" r="8" fill="{t["node_fill"]}"/>')

    # Labels.
    def label(code, sub, x, y, anchor="middle", extra=None):
        d1, _ = text("geistmono-700.ttf", code, 22, x, y, tracking=0.08, anchor=anchor)
        d2, _ = text("geistmono-500.ttf", sub, 14, x, y + 24, tracking=0.12, anchor=anchor)
        parts.append(f'<path fill="{t["ink"]}" d="{d1}"/>')
        parts.append(f'<path fill="{t["muted"]}" d="{d2}"/>')
        if extra:
            d3, _ = text("geistmono-500.ttf", extra, 13, x, y + 46, tracking=0.08, anchor=anchor)
            parts.append(f'<path fill="{t["meta"]}" d="{d3}"/>')

    label("DXB", "BY AIR", dxb[0], dxb[1] + 46)
    label("KSA", "BY LAND", ksa[0] - 30, ksa[1] + 8, anchor="end")
    label("BEY", "TO YOUR DOOR", bey[0] - 42, bey[1] - 4, anchor="end", extra="33.89N 35.50E")

    # Parcels travelling each route. Without SMIL they rest off the canvas.
    off = 100
    def shift(points):
        return " ".join(f"{x + off:.1f},{y + off:.1f}" for x, y in points)
    air_motion = (
        f"M{W + 20 + off},{dxb[1] + off:.1f} L{shift([dxb])} "
        f"C{shift([c1])} {shift([c2])} {shift([bey])}"
    )
    land_motion = "M" + shift([(ksa[0], H + 20), *land])
    parts.append(
        "<style>@media (prefers-reduced-motion: reduce){.parcel{display:none}}</style>"
    )
    for motion, color, dur, begin in ((air_motion, t["accent"], 5, 0), (land_motion, t["ink"], 7, 1.5)):
        parts.append(
            f'<g class="parcel" transform="translate({-off},{-off})">'
            f'<rect x="-8" y="-8" width="16" height="16" rx="3" fill="{color}">'
            f'<animateMotion dur="{dur}s" begin="{begin}s" repeatCount="indefinite" '
            f'keyPoints="0;1;1" keyTimes="0;0.8;1" calcMode="linear" path="{motion}"/>'
            f'<animate attributeName="opacity" dur="{dur}s" begin="{begin}s" repeatCount="indefinite" '
            f'values="1;1;0;0" keyTimes="0;0.78;0.82;1"/>'
            "</rect></g>"
        )

    parts.append("</g></svg>")
    return "".join(parts)


for name in THEMES:
    (OUT / f"header-{name}.svg").write_text(build(name))
    print("wrote", OUT / f"header-{name}.svg")
