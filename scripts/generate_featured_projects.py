#!/usr/bin/env python3
"""Regenerate the Featured Projects section of README.md and its SVG cards
from the single source of truth: data/featured-projects.json.

Outputs:
- assets/featured-projects-stats.svg  — category gauge card (glassmorphism)
- assets/featured-projects-list.svg   — animated project index card (glassmorphism)
- README.md between FEATURED:START/END markers (images + collapsible text list)

Counts, gauge widths, numbering, and star counts are all derived, so adding
or removing a project only requires editing the JSON (CI does the rest).
Star counts are fetched from the GitHub API at generation time; on network
failure the star text is simply omitted.

GitHub strips <style>/style attributes from README HTML, but CSS inside an
SVG file served as an image survives — including animations. backdrop-filter
does not work in SVG-as-image, so the glass look is built from blurred color
blobs behind translucent rgba() panels instead.
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
LIST_SVG = ROOT / "assets" / "featured-projects-list.svg"
README = ROOT / "README.md"

WIDTH = 820
DESC_MAX = 104

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


def glass_scaffold(height: int, accents: list[str], uid: str) -> tuple[str, str]:
    """Shared glassmorphism scaffold: aurora blobs, glass panel, sheen sweep.

    Returns (defs_and_background, panel_and_sheen) to wrap card content.
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


def build_list_svg(categories: list[dict], total: int, stars: dict[str, int | None]) -> str:
    aria = f"Project index: {total} featured repositories with descriptions"
    accents = [c.get("accent", c["svg_color"]) for c in categories]

    body = []
    y = 108
    slot = 0
    number = 0
    for ci, cat in enumerate(categories):
        accent = accents[ci]
        count = len(cat["projects"])
        delay = 0.3 + slot * 0.06
        body.append(
            f"""  <g class="cat" style="animation-delay: {delay:.2f}s">
    <circle cx="54" cy="{y - 5}" r="5" fill="{accent}"/>
    <text x="70" y="{y}" class="cat-label">{esc(plain_title(cat['title']).upper())}</text>
    <text x="772" y="{y}" text-anchor="end" class="cat-count" fill="{accent}">{count}<tspan class="dim" font-weight="400">/{total}</tspan></text>
  </g>"""
        )
        slot += 1
        y += 30

        for project in cat["projects"]:
            number += 1
            name = project["name"]
            desc = project["description"]
            if len(desc) > DESC_MAX:
                desc = desc[: DESC_MAX - 1].rstrip() + "…"
            star_text = ""
            if stars.get(name) is not None:
                star_text = (
                    f'\n    <text x="772" y="{y}" text-anchor="end" class="star" '
                    f'fill="{accent}">&#9733; {stars[name]}</text>'
                )
            delay = 0.3 + slot * 0.06
            body.append(
                f"""  <g class="row" style="animation-delay: {delay:.2f}s">
    <rect x="48" y="{y - 15}" width="34" height="21" rx="7" fill="rgba(255,255,255,0.75)" stroke="rgba(31,35,40,0.10)"/>
    <text x="65" y="{y}" text-anchor="middle" class="num" fill="{accent}">{number:02d}</text>
    <text x="94" y="{y}" class="name">{esc(name)}</text>{star_text}
    <text x="94" y="{y + 18}" class="desc">{esc(desc)}</text>
  </g>"""
            )
            slot += 1
            y += 46

        y += 16

    height = y + 6
    body_svg = "\n\n".join(body)
    head, sheen = glass_scaffold(height, accents, "ix")

    return f"""<svg width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{esc(aria)}">
  <style>
{GLASS_CSS}
    .cat-label {{ font-size: 13px; font-weight: 700; letter-spacing: 1.5px; fill: #57606a; }}
    .cat-count {{ font-size: 13px; font-weight: 700; }}
    .num {{ font-size: 11px; font-weight: 700; font-family: "SFMono-Regular", Consolas, Menlo, monospace; }}
    .name {{ font-size: 14.5px; font-weight: 700; }}
    .star {{ font-size: 12px; font-weight: 700; }}
    .desc {{ font-size: 12px; fill: #6e7781; }}
    .row {{ animation: slide-left 0.5s cubic-bezier(0.22, 1, 0.36, 1) backwards; }}
    .cat {{ animation: slide-right 0.5s cubic-bezier(0.22, 1, 0.36, 1) backwards; }}
    @keyframes slide-left {{ from {{ opacity: 0; transform: translateX(-18px); }} }}
    @keyframes slide-right {{ from {{ opacity: 0; transform: translateX(18px); }} }}
  </style>

{head}

  <!-- header -->
  <text x="48" y="62" class="header">Project Index<tspan class="cursor" fill="#6e7781">_</tspan></text>

{body_svg}

{sheen}
</svg>
"""


def build_readme_section(categories: list[dict], total: int) -> str:
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
        '  <a href="https://github.com/gunh0?tab=repositories">',
        '    <img src="./assets/featured-projects-list.svg" '
        f'alt="Project index: {total} featured repositories"/>',
        "  </a>",
        "</p>",
        "",
        "<details>",
        "<summary><b>&#128209; Text version with clickable links</b></summary>",
        "<br/>",
    ]

    number = 0
    for cat in categories:
        count = len(cat["projects"])
        unit = "repo" if count == 1 else "repos"
        badge = (
            f"![{count} {unit}](https://img.shields.io/badge/"
            f"-{count}%2F{total}-{cat['badge_color']}?style=flat-square)"
        )
        parts.append("")
        parts.append(f"#### {cat['title']} {badge}")
        for project in cat["projects"]:
            number += 1
            stars_badge = (
                f"https://img.shields.io/github/stars/gunh0/{project['name']}"
                f"?style=flat-square&label=%E2%98%85&color={cat['badge_color']}"
            )
            parts.append("")
            parts.append(
                f'<kbd>&nbsp;{number:02d}&nbsp;</kbd>&ensp;'
                f'<a href="https://github.com/gunh0/{project["name"]}"><b>{project["name"]}</b></a>&ensp;'
                f'<img src="{stars_badge}" alt="GitHub stars" align="top"/>\n'
                f'<br/>\n'
                f'<sub>&emsp;&emsp;{esc(project["description"])}</sub>'
            )
    parts.append("")
    parts.append("</details>")
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
    LIST_SVG.write_text(build_list_svg(categories, total, stars), encoding="utf-8")

    readme = README.read_text(encoding="utf-8")
    section = build_readme_section(categories, total)
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
