#!/usr/bin/env python3
"""Regenerate the Featured Projects section of README.md and the stats SVG
from the single source of truth: data/featured-projects.json.

Counts, gauge bar widths, category badges, and <kbd> numbering are all
derived from the JSON, so adding/removing a project only requires editing
that file and re-running this script (CI does it automatically).
"""

import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "featured-projects.json"
SVG = ROOT / "assets" / "featured-projects-stats.svg"
README = ROOT / "README.md"

BAR_TRACK_WIDTH = 380
ROW_STEP = 43
FIRST_BAR_Y = 93


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def plain_title(title: str) -> str:
    """Strip the leading emoji from a category title for alt/aria text."""
    return title.split(" ", 1)[1]


def build_svg(categories: list[dict], total: int) -> str:
    summary = ", ".join(
        f"{plain_title(c['title'])} {len(c['projects'])}" for c in categories
    )
    aria = f"Featured Projects: {total} total — {summary}"
    n = len(categories)
    height = FIRST_BAR_Y + ROW_STEP * (n - 1) + 16 + 32

    delay_css = "\n".join(
        f"    .d{i + 1} {{ animation-delay: {0.15 + 0.2 * i:.2f}s; }}" for i in range(n)
    )
    fade_css = "\n".join(
        f"    .f{i + 1} {{ animation-delay: {0.9 + 0.2 * i:.1f}s; }}" for i in range(n)
    )

    rows = []
    for i, cat in enumerate(categories):
        count = len(cat["projects"])
        bar_y = FIRST_BAR_Y + ROW_STEP * i
        text_y = bar_y + 14
        bar_w = round(BAR_TRACK_WIDTH * count / total)
        color = cat["svg_color"]
        rows.append(
            f"""  <!-- row {i + 1}: {plain_title(cat['title'])} {count}/{total} -->
  <text x="32" y="{text_y}" class="label">{esc(cat['svg_label'])}</text>
  <rect x="330" y="{bar_y}" width="{BAR_TRACK_WIDTH}" height="16" rx="8" fill="#eaeef2"/>
  <rect x="330" y="{bar_y}" width="{bar_w}" height="16" rx="8" fill="{color}" class="bar d{i + 1}"/>
  <text x="726" y="{text_y}" class="count fade f{i + 1}" fill="{color}">{count}</text>"""
        )
    rows_svg = "\n\n".join(rows)

    return f"""<svg width="820" height="{height}" viewBox="0 0 820 {height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{esc(aria)}">
  <style>
    text {{
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
      fill: #24292f;
    }}
    .label {{ font-size: 15px; }}
    .count {{ font-size: 15px; font-weight: bold; }}
    .header {{ font-size: 18px; font-weight: bold; fill: #1f2328; letter-spacing: 2px; }}
    .total {{ font-size: 18px; font-weight: bold; }}
    .dim {{ fill: #6e7781; }}
    .bar {{
      transform-box: fill-box;
      transform-origin: left;
      animation: grow 1.1s cubic-bezier(0.22, 1, 0.36, 1) backwards;
    }}
{delay_css}
    .fade {{
      animation: fadein 0.5s ease-out backwards;
    }}
{fade_css}
    .cursor {{ animation: blink 1.1s step-end infinite; }}
    @keyframes grow {{ from {{ transform: scaleX(0); }} }}
    @keyframes fadein {{ from {{ opacity: 0; }} }}
    @keyframes blink {{ 50% {{ opacity: 0; }} }}
  </style>

  <!-- card -->
  <rect x="1" y="1" width="818" height="{height - 2}" rx="10" fill="#ffffff" stroke="#d0d7de" stroke-width="2"/>

  <!-- header -->
  <text x="32" y="48" class="header">&#9656; FEATURED PROJECTS<tspan class="cursor">_</tspan></text>
  <text x="788" y="48" text-anchor="end" class="total"><tspan class="dim">TOTAL </tspan><tspan fill="#1f2328">{total}</tspan></text>
  <line x1="32" y1="66" x2="788" y2="66" stroke="#d0d7de" stroke-width="1"/>

{rows_svg}
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
        parts.append(f"### {cat['title']} {badge}")
        parts.append("")
        parts.append("<table>")
        for project in cat["projects"]:
            number += 1
            parts.append(
                f"""  <tr>
    <td align="center"><kbd>&nbsp;{number:02d}&nbsp;</kbd></td>
    <td><a href="https://github.com/gunh0/{project['name']}"><b>{project['name']}</b></a></td>
    <td>{esc(project['description'])}</td>
  </tr>"""
            )
        parts.append("</table>")
    return "\n".join(parts)


def main() -> None:
    config = json.loads(DATA.read_text(encoding="utf-8"))
    categories = config["categories"]
    total = sum(len(c["projects"]) for c in categories)

    SVG.write_text(build_svg(categories, total), encoding="utf-8")

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

    print(f"Regenerated: {total} projects across {len(categories)} categories")


if __name__ == "__main__":
    main()
