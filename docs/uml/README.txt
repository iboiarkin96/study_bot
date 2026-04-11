PlantUML sources for documentation (single source of truth)

Policy and conventions (C4 mapping, palette, file layout): ../adr/0020-c4-plantuml-diagram-style-and-conventions.html

Layout
  architecture/*.puml     C4-style views (context, container, component)
  sequences/*.puml        Sequence diagrams
  include/style.puml      Shared skin — injected after @startuml by scripts/regenerate_docs.py
                          (Kroki needs one file; !include is not expanded server-side.)
  rendered/*.png          Generated — do not edit by hand

Regenerate PNGs (requires network, curl → kroki.io)
  make docs-fix
  # or:
  .venv/bin/python scripts/regenerate_docs.py

Verify committed PNGs match sources (no writes)
  make uml-check
  # or:
  .venv/bin/python scripts/regenerate_docs.py --check

HTML pages (e.g. docs/system-analysis.html) reference ./uml/rendered/<name>.png only.
