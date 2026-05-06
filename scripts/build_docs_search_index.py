"""Build an inverted client-side search index for docs HTML pages.

The script scans ``docs/**/*.html`` and writes ``docs/assets/search-index.json``.
The artifact contains:
    - docs metadata (title, url, section, preview)
    - an inverted index with per-field term frequencies
    - document frequency map for IDF scoring in the browser
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
OUTPUT_PATH = DOCS_DIR / "assets" / "search-index.json"
MAX_CONTENT_CHARS = 3200
PREVIEW_CHARS = 240
TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)

_RE_TITLE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_RE_MAIN = re.compile(r"<main\b[^>]*>(.*?)</main>", re.IGNORECASE | re.DOTALL)
_RE_BODY = re.compile(r"<body\b[^>]*>(.*?)</body>", re.IGNORECASE | re.DOTALL)
_RE_REMOVE_BLOCKS = re.compile(
    r"<(script|style|noscript|svg|template)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_RE_TAGS = re.compile(r"<[^>]+>")
_RE_WHITESPACE = re.compile(r"\s+")


@dataclass(slots=True)
class IndexedDoc:
    """Normalized metadata and field token frequencies for one page."""

    title: str
    url: str
    section: str
    preview: str
    content_len: int
    title_tf: Counter[str]
    url_tf: Counter[str]
    section_tf: Counter[str]
    content_tf: Counter[str]


def _extract_title(html_text: str, fallback: str) -> str:
    """Extract and normalize the page title.

    Args:
        html_text: Full page source.
        fallback: Default title when ``<title>`` is missing.

    Returns:
        Cleaned title string.
    """
    match = _RE_TITLE.search(html_text)
    if not match:
        return fallback
    title = _RE_WHITESPACE.sub(" ", match.group(1)).strip()
    return title or fallback


def _extract_main_html(html_text: str) -> str:
    """Prefer `<main>` content and fallback to `<body>`.

    Args:
        html_text: Full page source.

    Returns:
        HTML fragment for text extraction.
    """
    main_match = _RE_MAIN.search(html_text)
    if main_match:
        return main_match.group(1)
    body_match = _RE_BODY.search(html_text)
    if body_match:
        return body_match.group(1)
    return html_text


def _html_to_text(html_text: str) -> str:
    """Convert HTML fragment to compact plain text.

    Args:
        html_text: HTML fragment.

    Returns:
        Normalized plain text.
    """
    text = _RE_REMOVE_BLOCKS.sub(" ", html_text)
    text = _RE_TAGS.sub(" ", text)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )
    return _RE_WHITESPACE.sub(" ", text).strip()


def _normalize_text(text: str) -> str:
    """Normalize text for indexing and search.

    Args:
        text: Arbitrary source text.

    Returns:
        Lower-cased whitespace-normalized text.
    """
    return _RE_WHITESPACE.sub(" ", text.lower()).strip()


def _tokenize(text: str) -> list[str]:
    """Tokenize normalized text into alphanumeric terms.

    Args:
        text: Normalized text.

    Returns:
        Ordered token list.
    """
    return TOKEN_PATTERN.findall(text)


def _iter_docs_html() -> list[Path]:
    """List HTML files under docs excluding static fragments.

    Restricted to git-tracked files so locally gitignored notes do not leak
    into the committed search index and trigger CI drift.

    Returns:
        Sorted file paths relative to docs root.
    """
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "-z", "--", "docs"],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
        )
        tracked = {ROOT / rel for rel in output.decode().split("\0") if rel.endswith(".html")}
    except (OSError, subprocess.CalledProcessError):
        tracked = None
    return sorted(
        path
        for path in DOCS_DIR.rglob("*.html")
        if "assets" not in path.parts and path.is_file() and (tracked is None or path in tracked)
    )


def _build_index_doc(path: Path) -> IndexedDoc:
    """Build one indexed document from an HTML page.

    Args:
        path: Absolute file path under ``docs/``.

    Returns:
        Indexed metadata with per-field term frequencies.
    """
    source = path.read_text(encoding="utf-8")
    rel = path.relative_to(DOCS_DIR).as_posix()
    title = _extract_title(source, fallback=path.stem)
    section = rel.split("/", 1)[0] if "/" in rel else "root"
    text = _html_to_text(_extract_main_html(source))
    if len(text) > MAX_CONTENT_CHARS:
        text = text[:MAX_CONTENT_CHARS].rsplit(" ", 1)[0].strip()

    title_norm = _normalize_text(title)
    url_norm = _normalize_text(rel.replace("/", " "))
    section_norm = _normalize_text(section)
    content_norm = _normalize_text(text)

    content_tokens = _tokenize(content_norm)
    return IndexedDoc(
        title=title,
        url=rel,
        section=section,
        preview=text[:PREVIEW_CHARS].strip(),
        content_len=max(len(content_tokens), 1),
        title_tf=Counter(_tokenize(title_norm)),
        url_tf=Counter(_tokenize(url_norm)),
        section_tf=Counter(_tokenize(section_norm)),
        content_tf=Counter(content_tokens),
    )


def _pack_postings(
    docs: list[IndexedDoc],
) -> tuple[dict[str, list[list[int]]], dict[str, int], int]:
    """Build token postings and document frequencies.

    Args:
        docs: Indexed documents.

    Returns:
        Tuple of:
            postings map token -> [[doc_id, tf_title, tf_url, tf_section, tf_content], ...],
            document frequency map token -> df,
            total unique token count.
    """
    postings_by_token: dict[str, list[list[int]]] = defaultdict(list)
    doc_freq: dict[str, int] = defaultdict(int)

    for doc_id, doc in enumerate(docs):
        merged_keys = (
            set(doc.title_tf) | set(doc.url_tf) | set(doc.section_tf) | set(doc.content_tf)
        )
        # Keep stable token order across runs so JSON output is deterministic.
        for token in sorted(merged_keys):
            t_title = doc.title_tf.get(token, 0)
            t_url = doc.url_tf.get(token, 0)
            t_section = doc.section_tf.get(token, 0)
            t_content = doc.content_tf.get(token, 0)
            postings_by_token[token].append([doc_id, t_title, t_url, t_section, t_content])
            doc_freq[token] += 1

    return (
        dict(sorted(postings_by_token.items())),
        dict(sorted(doc_freq.items())),
        len(postings_by_token),
    )


def build_search_index(output: Path) -> int:
    """Generate and persist docs search index.

    Args:
        output: JSON destination path.

    Returns:
        Number of indexed pages.
    """
    docs = [_build_index_doc(path) for path in _iter_docs_html()]
    postings, doc_freq, vocab_size = _pack_postings(docs)
    avg_content_len = sum(doc.content_len for doc in docs) / max(len(docs), 1)

    payload = {
        "version": 2,
        "meta": {
            "doc_count": len(docs),
            "vocab_size": vocab_size,
            "avg_content_len": round(avg_content_len, 3),
            "idf_formula": "log(1 + (N + 1) / (df + 0.5))",
            "tf_formula": "log(1 + tf)",
            "length_norm": "1 / (1 + 0.08 * max(0, content_len / avg_content_len - 1))",
        },
        "docs": [
            {
                "id": idx,
                "title": doc.title,
                "url": doc.url,
                "section": doc.section,
                "preview": doc.preview,
                "content_len": doc.content_len,
            }
            for idx, doc in enumerate(docs)
        ],
        "doc_freq": doc_freq,
        "postings": postings,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return len(docs)


def main() -> None:
    """CLI entrypoint for docs search index generation."""
    parser = argparse.ArgumentParser(description="Build docs search JSON index.")
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help="Output path for search-index.json (default: docs/assets/search-index.json).",
    )
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else (ROOT / args.output)
    count = build_search_index(output)
    print(f"Indexed {count} docs pages -> {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
