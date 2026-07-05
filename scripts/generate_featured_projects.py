#!/usr/bin/env python3
"""Regenerate the Featured Projects section of README.md and its SVG cards
from the single source of truth: data/featured-projects.json.

Outputs:
- assets/featured-projects-stats.svg — category gauge card (glassmorphism)
- assets/featured/<repo>.svg         — one glass tile per project, laid out
  as a two-column grid in the README with each tile wrapped in its own link
- README.md between FEATURED:START/END markers

Counts, gauge widths, numbering, and star counts are all derived, so adding
or removing a project only requires editing the JSON (CI does the rest).
Star counts are fetched from the GitHub API at generation time; on network
failure the star text is simply omitted. Stale tiles for removed projects
are deleted automatically.

GitHub strips <style>/style attributes from README HTML, but CSS inside an
SVG file served as an image survives — including animations. backdrop-filter
does not work in SVG-as-image, so the glass look is built from blurred color
blobs behind translucent rgba() panels instead. Per-tile entrance delays are
baked into each SVG so the grid still rises in a stagger.
"""

import html
import json
import os
import pathlib
import re
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "featured-projects.json"
STATS_SVG = ROOT / "assets" / "featured-projects-stats.svg"
TILES_DIR = ROOT / "assets" / "featured"
README = ROOT / "README.md"

WIDTH = 820
TILE_W = 400
TILE_H = 84

FONT_STACK = (
    '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", '
    'Roboto, "Helvetica Neue", Arial, sans-serif'
)


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def plain_title(title: str) -> str:
    """Strip the leading emoji from a category title for alt/aria text."""
    return title.split(" ", 1)[1]


def fetch_stars(name: str) -> int | None:
    req = urllib.request.Request(f"https://api.github.com/repos/gunh0/{name}")
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.load(resp).get("stargazers_count")
    except Exception:
        return None


def wrap_desc(desc: str, widths: tuple[int, ...] = (55, 42)) -> list[str]:
    """Wrap to at most len(widths) lines; the last line is shorter to leave
    room for the category tag pill in the tile's bottom-right corner."""
    lines: list[str] = []
    current = ""
    words = desc.split()
    for i, word in enumerate(words):
        width = widths[min(len(lines), len(widths) - 1)]
        if not current or len(current) + 1 + len(word) <= width:
            current = f"{current} {word}".strip()
        else:
            lines.append(current)
            current = word
    lines.append(current)
    if len(lines) > len(widths):
        lines = lines[: len(widths)]
        last_w = widths[-1]
        lines[-1] = lines[-1][: last_w - 1].rstrip() + "…"
    return lines


def glass_scaffold(height: int, accents: list[str], uid: str) -> tuple[str, str]:
    """Shared glassmorphism scaffold for full-width cards: aurora blobs,
    glass panel, sheen sweep. Returns (defs_and_background, sheen_overlay).
    """
    blob_geometry = [
        (120, 60, 170), (700, 40, 150), (90, height - 60, 160), (740, height - 50, 180),
    ]
    blobs = "\n".join(
        f'    <circle class="blob b{i + 1}" cx="{cx}" cy="{cy}" r="{r}" '
        f'fill="{accents[i % len(accents)]}" opacity="0.30" filter="url(#{uid}-blur)"/>'
        for i, (cx, cy, r) in enumerate(blob_geometry)
    )
    head = f"""  <defs>
    <filter id="{uid}-blur" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDeviation="55"/>
    </filter>
    <filter id="{uid}-shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="10" stdDeviation="14" flood-color="#1f2328" flood-opacity="0.10"/>
    </filter>
    <linearGradient id="{uid}-sheen-grad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0"/>
      <stop offset="0.5" stop-color="#ffffff" stop-opacity="0.35"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
    <linearGradient id="{uid}-glass-edge" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.35"/>
      <stop offset="0.12" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
    <clipPath id="{uid}-panel-clip">
      <rect x="16" y="16" width="{WIDTH - 32}" height="{height - 32}" rx="24"/>
    </clipPath>
  </defs>

  <!-- backdrop: soft base + drifting aurora blobs (the "behind the glass" layer) -->
  <rect width="{WIDTH}" height="{height}" rx="28" fill="#f2f4f8"/>
  <g clip-path="url(#{uid}-panel-clip)">
{blobs}
  </g>

  <!-- glass panel -->
  <rect x="16" y="16" width="{WIDTH - 32}" height="{height - 32}" rx="24"
        fill="rgba(255,255,255,0.58)" stroke="rgba(255,255,255,0.95)" stroke-width="1.5"
        filter="url(#{uid}-shadow)"/>
  <rect x="16" y="16" width="{WIDTH - 32}" height="{height - 32}" rx="24"
        fill="url(#{uid}-glass-edge)"/>"""
    sheen = f"""  <!-- one-shot sheen sweep across the glass -->
  <g clip-path="url(#{uid}-panel-clip)">
    <rect class="sheen" x="-260" y="0" width="200" height="{height}" fill="url(#{uid}-sheen-grad)"/>
  </g>"""
    return head, sheen


GLASS_CSS = f"""    text {{
      font-family: {FONT_STACK};
      fill: #1f2328;
    }}
    .header {{ font-size: 19px; font-weight: 700; letter-spacing: 0.5px; }}
    .dim {{ fill: #6e7781; }}
    .cursor {{ animation: blink 1.1s step-end infinite; }}
    .blob {{ animation: drift 16s ease-in-out infinite alternate; }}
    .b2 {{ animation-duration: 19s; animation-delay: -6s; }}
    .b3 {{ animation-duration: 22s; animation-delay: -11s; }}
    .b4 {{ animation-duration: 17s; animation-delay: -3s; }}
    .sheen {{ animation: sweep 2.4s ease-in-out 0.5s 1 both; }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
    @keyframes drift {{ to {{ transform: translate(46px, 26px); }} }}
    @keyframes sweep {{ to {{ transform: translateX(1300px) skewX(-16deg); }} }}"""


def build_stats_svg(categories: list[dict], total: int) -> str:
    summary = ", ".join(
        f"{plain_title(c['title'])} {len(c['projects'])}" for c in categories
    )
    aria = f"Featured Projects: {total} total — {summary}"
    n = len(categories)
    height = 104 + 47 * n + 20
    accents = [c.get("accent", c["svg_color"]) for c in categories]
    head, sheen = glass_scaffold(height, accents, "st")

    delay_css = "\n".join(
        f"    .d{i + 1} {{ animation-delay: {0.2 + 0.2 * i:.2f}s; }}" for i in range(n)
    )
    fade_css = "\n".join(
        f"    .f{i + 1} {{ animation-delay: {0.9 + 0.2 * i:.1f}s; }}" for i in range(n)
    )

    rows = []
    for i, cat in enumerate(categories):
        count = len(cat["projects"])
        accent = accents[i]
        bar_y = 104 + 47 * i
        text_y = bar_y + 13
        bar_w = round(380 * count / total)
        rows.append(
            f"""  <!-- {plain_title(cat['title'])} {count}/{total} -->
  <text x="48" y="{text_y}" class="label">{esc(cat['svg_label'])}</text>
  <rect x="340" y="{bar_y}" width="380" height="14" rx="7" fill="rgba(31,35,40,0.07)"/>
  <rect x="340" y="{bar_y}" width="{bar_w}" height="14" rx="7" fill="{accent}" class="bar d{i + 1}"/>
  <text x="772" y="{text_y}" text-anchor="end" class="count fade f{i + 1}" fill="{accent}">{count}</text>"""
        )
    rows_svg = "\n\n".join(rows)

    return f"""<svg width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{esc(aria)}">
  <style>
{GLASS_CSS}
    .label {{ font-size: 15px; font-weight: 600; }}
    .count {{ font-size: 15px; font-weight: 700; }}
    .total {{ font-size: 18px; font-weight: 700; }}
    .bar {{
      transform-box: fill-box;
      transform-origin: left;
      animation: grow 1.1s cubic-bezier(0.22, 1, 0.36, 1) backwards;
    }}
{delay_css}
    .fade {{ animation: fadein 0.5s ease-out backwards; }}
{fade_css}
    @keyframes grow {{ from {{ transform: scaleX(0); }} }}
    @keyframes fadein {{ from {{ opacity: 0; }} }}
  </style>

{head}

  <!-- header -->
  <text x="48" y="62" class="header">Featured Projects<tspan class="cursor" fill="#6e7781">_</tspan></text>
  <text x="772" y="62" text-anchor="end" class="total"><tspan class="dim">TOTAL </tspan>{total}</text>

{rows_svg}

{sheen}
</svg>
"""


def build_tile_svg(
    number: int, name: str, desc: str, accent: str, tag: str, star_count: int | None
) -> str:
    """One project = one compact glass tile, so each can carry its own link.
    The category is shown as a tag pill (bottom-right), not just by color."""
    alt = f"{number:02d} {name} [{tag}] — {desc}"
    delay = 0.1 + (number - 1) * 0.05
    lines = wrap_desc(desc)

    star_avail = 60 if star_count is not None else 0
    name_avail = TILE_W - 62 - 16 - star_avail
    name_attrs = ""
    if len(name) * 7.5 > name_avail:
        name_attrs = f' textLength="{name_avail}" lengthAdjust="spacingAndGlyphs"'

    star_text = ""
    if star_count is not None:
        star_text = (
            f'\n    <text x="{TILE_W - 16}" y="27" text-anchor="end" class="star" '
            f'fill="{accent}">&#9733; {star_count}</text>'
        )

    desc_lines = "\n".join(
        f'    <text x="20" y="{50 + 16 * i}" class="desc">{esc(line)}</text>'
        for i, line in enumerate(lines)
    )

    pill_w = round(len(tag) * 6.6) + 16
    pill_x = TILE_W - 16 - pill_w

    return f"""<svg width="{TILE_W}" height="{TILE_H}" viewBox="0 0 {TILE_W} {TILE_H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{esc(alt)}">
  <style>
    text {{
      font-family: {FONT_STACK};
      fill: #1f2328;
    }}
    .num {{ font-size: 11px; font-weight: 700; font-family: "SFMono-Regular", Consolas, Menlo, monospace; }}
    .name {{ font-size: 13.5px; font-weight: 700; }}
    .star {{ font-size: 11.5px; font-weight: 700; }}
    .desc {{ font-size: 11px; fill: #6e7781; }}
    .tag {{ font-size: 9px; font-weight: 700; letter-spacing: 1px; }}
    .blob {{ animation: drift 18s ease-in-out infinite alternate; }}
    .tile {{ animation: rise 0.55s cubic-bezier(0.22, 1, 0.36, 1) {delay:.2f}s backwards; }}
    @keyframes drift {{ to {{ transform: translate(-30px, 18px); }} }}
    @keyframes rise {{ from {{ opacity: 0; transform: translateY(12px); }} }}
  </style>

  <defs>
    <filter id="t-blur" x="-80%" y="-80%" width="260%" height="260%">
      <feGaussianBlur stdDeviation="28"/>
    </filter>
    <clipPath id="t-clip">
      <rect width="{TILE_W}" height="{TILE_H}" rx="14"/>
    </clipPath>
  </defs>

  <g class="tile">
    <rect width="{TILE_W}" height="{TILE_H}" rx="14" fill="#f2f4f8"/>
    <g clip-path="url(#t-clip)">
      <circle class="blob" cx="{TILE_W - 60}" cy="6" r="76" fill="{accent}" opacity="0.24" filter="url(#t-blur)"/>
    </g>
    <rect x="2" y="2" width="{TILE_W - 4}" height="{TILE_H - 4}" rx="12"
          fill="rgba(255,255,255,0.62)" stroke="rgba(255,255,255,0.95)" stroke-width="1.5"/>
    <rect x="8" y="10" width="5" height="{TILE_H - 20}" rx="2.5" fill="{accent}" opacity="0.85"/>

    <rect x="22" y="12" width="32" height="19" rx="6" fill="{accent}" opacity="0.13"/>
    <text x="38" y="26" text-anchor="middle" class="num" fill="{accent}">{number:02d}</text>
    <text x="62" y="26" class="name"{name_attrs}>{esc(name)}</text>{star_text}
{desc_lines}

    <rect x="{pill_x}" y="{TILE_H - 30}" width="{pill_w}" height="17" rx="8.5" fill="{accent}" opacity="0.13"/>
    <text x="{pill_x + pill_w / 2:.0f}" y="{TILE_H - 18}" text-anchor="middle" class="tag" fill="{accent}">{esc(tag)}</text>
  </g>
</svg>
"""


def build_readme_section(
    categories: list[dict], total: int, tiles: list[tuple[str, str]]
) -> str:
    summary = ", ".join(
        f"{plain_title(c['title'])} {len(c['projects'])}" for c in categories
    )
    alt = f"Featured Projects: {total} total — {summary}"
    parts = [
        '<p align="center">',
        f'  <img src="./assets/featured-projects-stats.svg" alt="{alt}"/>',
        "</p>",
        "",
        '<p align="center">',
    ]
    for name, tile_alt in tiles:
        parts.append(
            f'  <a href="https://github.com/gunh0/{name}">'
            f'<img src="./assets/featured/{name}.svg" width="49%" alt="{tile_alt}"/></a>'
        )
    parts.append("</p>")
    return "\n".join(parts)


def main() -> None:
    config = json.loads(DATA.read_text(encoding="utf-8"))
    categories = config["categories"]
    total = sum(len(c["projects"]) for c in categories)

    stars = {
        p["name"]: fetch_stars(p["name"])
        for c in categories
        for p in c["projects"]
    }
    fetched = sum(1 for v in stars.values() if v is not None)

    STATS_SVG.write_text(build_stats_svg(categories, total), encoding="utf-8")

    TILES_DIR.mkdir(parents=True, exist_ok=True)
    tiles: list[tuple[str, str]] = []
    number = 0
    for cat in categories:
        accent = cat.get("accent", cat["svg_color"])
        tag = cat.get("tag", plain_title(cat["title"]).upper())
        for project in cat["projects"]:
            number += 1
            name = project["name"]
            tile = build_tile_svg(
                number, name, project["description"], accent, tag, stars.get(name)
            )
            (TILES_DIR / f"{name}.svg").write_text(tile, encoding="utf-8")
            tiles.append((name, f"{number:02d} {name}"))

    current = {name for name, _ in tiles}
    for stale in TILES_DIR.glob("*.svg"):
        if stale.stem not in current:
            stale.unlink()

    readme = README.read_text(encoding="utf-8")
    section = build_readme_section(categories, total, tiles)
    updated, replaced = re.subn(
        r"(<!-- FEATURED:START -->\n).*?(\n<!-- FEATURED:END -->)",
        lambda m: m.group(1) + section + m.group(2),
        readme,
        count=1,
        flags=re.DOTALL,
    )
    if not replaced:
        raise SystemExit("FEATURED:START/END markers not found in README.md")
    README.write_text(updated, encoding="utf-8")

    print(
        f"Regenerated: {total} projects across {len(categories)} categories "
        f"(stars fetched for {fetched}/{total})"
    )


if __name__ == "__main__":
    main()
