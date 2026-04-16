"""Post-process pdoc HTML under docs/api/.

Strip unstable memory addresses from HTML and ``search.js`` (function reprs) so
``make api-docs`` output is diff-stable across machines and runs.

pdoc output is otherwise left unchanged — no site chrome or ``docs-nav.js``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_API = ROOT / "docs" / "api"

# e.g. ``<function foo at 0x10ab02c40>`` in HTML-escaped form or plain text
_AT_ADDR = re.compile(r" at 0x[0-9a-f]{8,16}")


def main() -> int:
    if not DOCS_API.is_dir():
        print("docs/api missing; skip pdoc normalization", file=sys.stderr)
        return 0
    changed = 0
    for path in list(DOCS_API.rglob("*.html")) + [DOCS_API / "search.js"]:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        new = _AT_ADDR.sub("", text)
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed += 1

    if changed:
        print(f"Normalized unstable pdoc reprs in {changed} file(s) under docs/api/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
