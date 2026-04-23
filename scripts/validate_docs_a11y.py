"""Baseline accessibility validation for docs HTML pages."""

from __future__ import annotations

import re
from pathlib import Path

import html5lib

ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = ROOT / "docs"
DOCS_CSS = DOCS_ROOT / "assets" / "docs.css"


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _iter_docs_pages() -> list[Path]:
    pages: list[Path] = []
    for path in sorted(DOCS_ROOT.glob("**/*.html")):
        rel = path.relative_to(DOCS_ROOT)
        if rel.parts and rel.parts[0] in {"api", "assets", "pdoc"}:
            continue
        pages.append(path)
    return pages


def _is_redirect_stub(root_el, text: str) -> bool:
    for node in root_el.iter():
        if not isinstance(node.tag, str):
            continue
        if _local_name(node.tag) != "meta":
            continue
        equiv = (node.attrib.get("http-equiv") or "").lower()
        if equiv == "refresh":
            return True
    lowered = text.lower()
    if "window.location.replace(" in lowered and 'rel="canonical"' in lowered:
        return True
    if "<title>moved" in lowered:
        return True
    return False


def _extract_headings(root_el) -> list[int]:
    levels: list[int] = []
    for node in root_el.iter():
        if not isinstance(node.tag, str):
            continue
        name = _local_name(node.tag)
        if len(name) == 2 and name.startswith("h") and name[1].isdigit():
            levels.append(int(name[1]))
    return levels


def _has_top_nav_mount(root_el) -> bool:
    for node in root_el.iter():
        if not isinstance(node.tag, str):
            continue
        if _local_name(node.tag) != "div":
            continue
        if node.attrib.get("id") == "docs-top-nav":
            return True
    return False


def _find_landmarks(root_el) -> tuple[bool, bool]:
    has_main = False
    has_nav = False
    for node in root_el.iter():
        if not isinstance(node.tag, str):
            continue
        name = _local_name(node.tag)
        if name == "main":
            has_main = True
        elif name in {"nav", "header", "footer", "aside"}:
            has_nav = True
    return has_main, has_nav


def _is_natively_interactive(name: str) -> bool:
    return name in {"a", "button", "input", "select", "textarea", "summary"}


def _check_keyboard(root_el) -> list[str]:
    errors: list[str] = []
    for node in root_el.iter():
        if not isinstance(node.tag, str):
            continue
        name = _local_name(node.tag)
        tabindex = node.attrib.get("tabindex")
        if tabindex:
            try:
                if int(tabindex) > 0:
                    errors.append(f"positive tabindex on <{name}>")
            except ValueError:
                errors.append(f"invalid tabindex='{tabindex}' on <{name}>")

        if "onclick" in node.attrib and not _is_natively_interactive(name):
            if not any(key in node.attrib for key in ("onkeydown", "onkeyup", "onkeypress")):
                errors.append(f"onclick without keyboard handler on <{name}>")
    return errors


def _hex_to_rgb(value: str) -> tuple[int, int, int] | None:
    v = value.strip().lower()
    if not v.startswith("#"):
        return None
    v = v[1:]
    if len(v) == 3:
        v = "".join(ch * 2 for ch in v)
    if len(v) != 6 or any(ch not in "0123456789abcdef" for ch in v):
        return None
    r = int(v[0:2], 16)
    g = int(v[2:4], 16)
    b = int(v[4:6], 16)
    return (r, g, b)


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    l1 = _relative_luminance(a)
    l2 = _relative_luminance(b)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _extract_css_vars(css_text: str) -> dict[str, str]:
    vars_found: dict[str, str] = {}
    for name, value in re.findall(r"(--[a-zA-Z0-9_-]+)\s*:\s*([^;]+);", css_text):
        vars_found[name] = value.strip()
    return vars_found


def _check_css_baseline() -> list[str]:
    errors: list[str] = []
    css = DOCS_CSS.read_text(encoding="utf-8")
    vars_found = _extract_css_vars(css)

    required_vars = ["--bg", "--card", "--text", "--muted", "--accent"]
    for var_name in required_vars:
        if var_name not in vars_found:
            errors.append(f"missing CSS variable {var_name} in docs.css")

    pairs = [
        ("--text", "--bg", 4.5),
        ("--text", "--card", 4.5),
        ("--muted", "--bg", 4.5),
        ("--accent", "--bg", 4.5),
    ]
    for fg_name, bg_name, min_ratio in pairs:
        fg = _hex_to_rgb(vars_found.get(fg_name, ""))
        bg = _hex_to_rgb(vars_found.get(bg_name, ""))
        if fg is None or bg is None:
            errors.append(f"cannot compute contrast for {fg_name} vs {bg_name}")
            continue
        ratio = _contrast_ratio(fg, bg)
        if ratio < min_ratio:
            errors.append(f"contrast {fg_name}/{bg_name}={ratio:.2f} is below {min_ratio:.1f}")

    if ":focus" not in css and ":focus-visible" not in css:
        errors.append("docs.css does not define :focus / :focus-visible styles")

    return errors


def main() -> None:
    parser = html5lib.HTMLParser(tree=html5lib.getTreeBuilder("etree"))
    failures: list[str] = []

    failures.extend(_check_css_baseline())

    for path in _iter_docs_pages():
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        doc = parser.parse(text)
        if parser.errors:
            failures.append(f"{rel}: HTML5 parse errors ({len(parser.errors)})")
            parser.errors.clear()
            continue

        redirect_stub = _is_redirect_stub(doc, text)
        headings = _extract_headings(doc)
        has_main, has_landmark_nav = _find_landmarks(doc)
        has_top_nav = _has_top_nav_mount(doc)

        if not redirect_stub:
            if not headings:
                failures.append(f"{rel}: no headings found")
            else:
                if headings.count(1) != 1:
                    failures.append(f"{rel}: expected exactly one h1, found {headings.count(1)}")
                prev = headings[0]
                for level in headings[1:]:
                    if level - prev > 1:
                        failures.append(f"{rel}: heading jump h{prev}->h{level}")
                        break
                    prev = level

            if not has_main:
                failures.append(f"{rel}: missing <main> landmark")
            if not has_landmark_nav and not has_top_nav:
                failures.append(f"{rel}: missing navigation landmark/mount")

        kb_errors = _check_keyboard(doc)
        for err in kb_errors:
            failures.append(f"{rel}: {err}")

    if failures:
        print("Docs A11y baseline check failed:")
        for item in failures:
            print(f" - {item}")
        raise SystemExit(1)

    print("Docs A11y baseline check passed")


if __name__ == "__main__":
    main()
