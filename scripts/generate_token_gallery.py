#!/usr/bin/env python3
"""Auto-generate the docs frontend token gallery page.

Parses CSS custom properties (--vars) from `docs/assets/docs.css`
(light) and `docs/assets/docs-theme.css` (dark) and renders an HTML
reference page with side-by-side light/dark swatches grouped by family.

Output: `docs/internal/front/docs-frontend-token-gallery.html`.

Run from project root:
    python3 scripts/generate_token_gallery.py
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parent.parent
DOCS_ASSETS = ROOT / "docs" / "assets"
OUT_PATH = ROOT / "docs" / "internal" / "front" / "docs-frontend-token-gallery.html"

LIGHT_CSS = DOCS_ASSETS / "docs.css"
DARK_CSS = DOCS_ASSETS / "docs-theme.css"

# Token: --name: value;  inside any :root or @media :root block.
TOKEN_RE = re.compile(r"--([a-z0-9_-]+)\s*:\s*([^;]+?);", re.IGNORECASE)


def collect_tokens_from_block(text: str, block_re: re.Pattern) -> dict[str, str]:
    """Return {name: value} for every --token in any block matching block_re."""
    out: dict[str, str] = {}
    for block_match in block_re.finditer(text):
        body = block_match.group(1)
        for m in TOKEN_RE.finditer(body):
            name, value = m.group(1).strip(), m.group(2).strip()
            # Last write wins — matches CSS cascade.
            out[name] = value
    return out


def parse_root_blocks(path: Path, mode: str) -> dict[str, str]:
    """Extract tokens from :root blocks (light) or @media (dark) blocks."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")

    if mode == "light":
        block_re = re.compile(
            r":root\s*(?:\[[^\]]+\])?\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}",
            re.DOTALL,
        )
        return collect_tokens_from_block(text, block_re)

    # Dark: only :root blocks inside @media (prefers-color-scheme: dark) or under [data-theme=dark].
    dark_blocks: dict[str, str] = {}
    media_re = re.compile(
        r"@media\s*\([^)]*prefers-color-scheme\s*:\s*dark[^)]*\)\s*\{(.*?)\n\}",
        re.DOTALL,
    )
    for media_match in media_re.finditer(text):
        inner = media_match.group(1)
        root_re = re.compile(r":root\s*\{([^}]*)\}", re.DOTALL)
        for rm in root_re.finditer(inner):
            for m in TOKEN_RE.finditer(rm.group(1)):
                dark_blocks[m.group(1).strip()] = m.group(2).strip()
    # Also capture explicit :root[data-theme="dark"] {...} blocks.
    explicit_re = re.compile(
        r':root\[data-theme=["\']dark["\']\]\s*\{([^}]*)\}',
        re.DOTALL,
    )
    for em in explicit_re.finditer(text):
        for m in TOKEN_RE.finditer(em.group(1)):
            # Light-block wins if both target same token; only fill missing.
            dark_blocks.setdefault(m.group(1).strip(), m.group(2).strip())
    return dark_blocks


# Token family rules — first matching prefix/family wins.
FAMILY_RULES: list[tuple[str, str]] = [
    ("Surfaces & text", r"^(bg|card|text|muted|accent|line|pre-bg|table|callout|code-)"),
    ("Status badges", r"^badge-"),
    ("Top navigation", r"^nav-"),
    ("Internal layout", r"^internal-"),
    ("Premium components", r"^docs-premium-"),
    ("Search", r"^search-"),
    ("ADR / lifecycle", r"^adr-|^docs-lifecycle-"),
    ("Audit scoring", r"^audit-"),
    ("Workflow status", r"^status-"),
    ("Syntax tokens", r"^st-"),
    ("Spacing", r"^space-|^gap-"),
    ("Radius", r"^radius-"),
    ("Motion", r"^motion-"),
    ("Typography", r"^font-|^line-height-|^letter-"),
    ("Breakpoints", r"^bp-"),
    ("Focus", r"^focus-"),
    ("Home page", r"^home-"),
]


def classify(name: str) -> str:
    for label, pattern in FAMILY_RULES:
        if re.match(pattern, name):
            return label
    return "Other"


# Heuristic: which tokens are visually rendered as color swatches.
def is_color_value(value: str) -> bool:
    s = value.strip().lower()
    if s.startswith("#") or s.startswith("rgb") or s.startswith("hsl"):
        return True
    if "color-mix(" in s:
        return True
    if "linear-gradient(" in s or "radial-gradient(" in s:
        return True
    # Named colors we actually use.
    if s in {"transparent", "currentcolor", "white", "black"}:
        return True
    return False


def html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def render() -> str:
    light = parse_root_blocks(LIGHT_CSS, "light")
    dark = parse_root_blocks(DARK_CSS, "dark")

    all_names = sorted(set(light) | set(dark))
    by_family: dict[str, list[str]] = {}
    for name in all_names:
        by_family.setdefault(classify(name), []).append(name)

    # Stable family order matching FAMILY_RULES, "Other" last.
    family_order = [label for label, _ in FAMILY_RULES] + ["Other"]
    families = [(f, by_family[f]) for f in family_order if f in by_family]

    today = date.today().isoformat()
    rows_count = sum(len(toks) for _, toks in families)

    parts: list[str] = []
    parts.append(
        '<!doctype html>\n<html lang="en"><head>\n'
        '  <script>(function(){try{var k="docs-theme-preference",v=localStorage.getItem(k);'
        'if(v==="dark")document.documentElement.setAttribute("data-theme","dark");'
        'else if(v==="light")document.documentElement.setAttribute("data-theme","light");}'
        "catch(e){}})();</script>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "  <title>Docs frontend token gallery</title>\n"
        '  <link rel="icon" type="image/svg+xml" href="../../assets/favicon.svg">\n'
        '  <link rel="stylesheet" href="../../assets/docs.css" />\n'
        '  <link rel="stylesheet" href="../../assets/docs-theme.css">\n'
        '  <script defer src="../../assets/internal-sidebar.js"></script>\n'
        '  <script defer src="../../assets/docs-nav.js"></script>\n'
        '  <script defer src="../../assets/docs-portal-data.js"></script>\n'
        '  <script defer src="../../assets/docs-internal-meta.js"></script>\n'
        "  <style>\n"
        "    .docs-token-row { display: grid; grid-template-columns: minmax(200px, 1.5fr) 1fr 1fr; gap: 8px 14px; padding: 8px 0; border-bottom: 1px solid var(--line); align-items: center; }\n"
        "    .docs-token-row:last-child { border-bottom: 0; }\n"
        "    .docs-token-name { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.82rem; color: var(--accent); word-break: break-all; }\n"
        "    .docs-token-cell { display: flex; align-items: center; gap: 8px; min-width: 0; }\n"
        "    .docs-token-swatch { width: 28px; height: 28px; border-radius: 6px; border: 1px solid var(--line); flex-shrink: 0; }\n"
        "    .docs-token-value { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.74rem; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }\n"
        "    .docs-token-missing { font-style: italic; color: var(--muted); opacity: 0.7; }\n"
        "    @media (max-width: 640px) { .docs-token-row { grid-template-columns: 1fr; } }\n"
        "  </style>\n"
        "</head>\n"
        '<body class="internal-layout" data-maintainer-ids="16fc8b78537109162984a2fdbef6e142">\n'
        '  <div class="internal-layout__shell">\n'
        '    <aside class="internal-layout__sidebar">\n'
        '      <div id="internal-sidebar-mount"></div>\n'
        "    </aside>\n"
        '    <div class="internal-layout__main">\n'
        '      <main class="container">\n'
        "        <h1>Docs frontend token gallery "
        '<span class="docs-page-type docs-page-type--reference">Reference</span></h1>\n'
        '        <div id="docs-top-nav"></div>\n'
        '        <div id="docs-page-meta-mount" hidden=""></div>\n'
    )

    parts.append(
        '        <section id="overview" class="card">\n'
        "          <h2>Overview</h2>\n"
        f"          <p>\n"
        f"            Visual lookup for every CSS custom property defined in the docs portal. {rows_count} tokens across\n"
        f"            {len(families)} families, with light and dark values side-by-side. Auto-generated from\n"
        "            <code>docs/assets/docs.css</code> (light) and <code>docs/assets/docs-theme.css</code> (dark) by\n"
        "            <code>scripts/generate_token_gallery.py</code> — do not edit this page by hand. Re-run the script\n"
        "            when tokens are added or renamed.\n"
        "          </p>\n"
        '          <p class="small">\n'
        f'            Last regenerated: <time datetime="{today}">{today}</time>.\n'
        '            Sister pages: <a href="./docs-frontend-css-architecture.html">CSS architecture</a>,\n'
        '            <a href="./docs-frontend-ui-kit.html">UI kit</a>,\n'
        '            <a href="./docs-frontend-ui-motion-and-adaptivity.html">UI / motion / adaptivity</a>.\n'
        "          </p>\n"
        "        </section>\n"
    )

    for family_label, tokens in families:
        anchor = re.sub(r"[^a-z0-9]+", "-", family_label.lower()).strip("-")
        parts.append(
            f'        <section id="family-{anchor}" class="card">\n'
            f'          <h2>{html_escape(family_label)} <span class="small">({len(tokens)} tokens)</span></h2>\n'
            f'          <div class="docs-token-grid" role="region" aria-label="{html_escape(family_label)} tokens">\n'
        )
        for name in sorted(tokens):
            light_v = light.get(name)
            dark_v = dark.get(name, light_v)  # Fall back to light if dark not redefined.
            light_is_color = light_v and is_color_value(light_v)
            dark_is_color = dark_v and is_color_value(dark_v)

            light_cell = ""
            if light_v is None:
                light_cell = '<span class="docs-token-missing">— not defined in light —</span>'
            else:
                if light_is_color:
                    swatch = (
                        '<span class="docs-token-swatch" '
                        f'style="background: {html_escape(light_v)};" aria-hidden="true"></span>'
                    )
                else:
                    swatch = ""
                light_cell = f'{swatch}<span class="docs-token-value">{html_escape(light_v)}</span>'

            dark_cell = ""
            if dark_v is None:
                dark_cell = '<span class="docs-token-missing">— not defined in dark —</span>'
            else:
                if dark_is_color:
                    swatch = (
                        '<span class="docs-token-swatch" '
                        f'style="background: {html_escape(dark_v)};" aria-hidden="true"></span>'
                    )
                else:
                    swatch = ""
                same = (dark_v == light_v) and light_v is not None
                value_html = html_escape(dark_v)
                if same:
                    value_html += ' <span class="small">(inherits light)</span>'
                dark_cell = f'{swatch}<span class="docs-token-value">{value_html}</span>'

            parts.append(
                '            <div class="docs-token-row">\n'
                f'              <div class="docs-token-name">--{html_escape(name)}</div>\n'
                f'              <div class="docs-token-cell">{light_cell}</div>\n'
                f'              <div class="docs-token-cell">{dark_cell}</div>\n'
                "            </div>\n"
            )
        parts.append("          </div>\n        </section>\n")

    parts.append(
        '        <section id="page-history" class="card">\n'
        "          <h2>Page history</h2>\n"
        '          <div class="docs-table-scroll" role="region" aria-label="Page history">\n'
        '            <table class="docs-page-history">\n'
        "              <thead>\n"
        '                <tr><th scope="col">Date</th><th scope="col">Change</th><th scope="col">Author</th></tr>\n'
        "              </thead>\n"
        "              <tbody>\n"
        "                <tr>\n"
        f'                  <td><time datetime="{today}">{today}</time></td>\n'
        f"                  <td>Auto-regenerated — {rows_count} tokens across {len(families)} families.</td>\n"
        "                  <td>scripts/generate_token_gallery.py</td>\n"
        "                </tr>\n"
        "              </tbody>\n"
        "            </table>\n"
        "          </div>\n"
        "        </section>\n"
        '        <div class="docs-inpage-toc-mount" data-inpage-toc="auto"></div>\n'
        "      </main>\n"
        "    </div>\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )
    return "".join(parts)


def main() -> int:
    html = render()
    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"✓ Wrote {OUT_PATH.relative_to(ROOT)} ({len(html):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
