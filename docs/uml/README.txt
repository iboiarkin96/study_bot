PlantUML sources for documentation (single source of truth)

Policy and conventions (C4 mapping, palette, file layout):
  ../adr/0020-c4-plantuml-diagram-style-and-conventions.html

Layout
  architecture/*.puml     C4-style views (context, container, component)
  make/*.puml             Makefile composite / run-target overview (developer guide 0010)
  sequences/*.puml        Sequence diagrams (e.g. conspectus, review, error log)
  include/style.puml      Shared skin — injected after @startuml by scripts/regenerate_docs.py
                          (Kroki needs one file; !include is not expanded server-side.)
  rendered/*.svg          Generated — do not edit by hand
  input-hashes.json       Fingerprint cache (merged source + output SHA-256); commit it. Renders
                          skip Kroki when unchanged; use --bootstrap-manifest to fill offline.

----------------------------------------------------------------------------
Sizing and visual consistency (exports + HTML)
----------------------------------------------------------------------------

Global export cap (include/style.puml)
  - ``scale max 960 width`` caps how *wide* an SVG can get. It does **not** upscale narrow
    diagrams. That keeps font sizes consistent across diagram types.
  - Do **not** replace this with a fixed ``scale <N> width`` (without ``max``): PlantUML would
    scale every diagram to the same pixel width, so sparse / narrow diagrams get **upscaled**
    and their text looks larger than dense / wide ones.
  - After changing shared skin, regenerate all outputs: ``make docs-fix`` or
    ``python3 scripts/regenerate_docs.py --force``.

HTML (how SVGs are shown)
  - Pages such as ``docs/internal/analysis/system-design.html`` reference ``../../uml/rendered/<name>.svg``.
  - PlantUML SVGs are shown at **intrinsic** width (they must not be forced to ``width: 100%``
    of the text column, or narrow exports stretch and look like a bigger font). The rules live
    under ``.sys-diagram__canvas img`` / ``img.diagram`` in ``docs/assets/docs.css``.
  - For detail, readers use the in-page **expand** / lightbox control; do not “fix” small
    diagrams by stretching them in CSS.

Sequence diagrams shown together (same doc section)
  - **Goal:** When several sequence diagrams sit one after another, they should look like one
    family: same fonts (from shared skin), similar **frame width** so the column does not jump.
  - **Participant order:** Use the same left-to-right order for the same roles (e.g.
    Integrator → HTTP API → *Service* → SchedulePolicy → DB) so lifelines line up conceptually
    across diagrams.
  - **Fewer roles in one flow:** If a flow legitimately does not call a role (e.g. no schedule
    policy), you may still declare that participant so the layout matches sibling diagrams; the
    lifeline stays idle. Document in a comment above the diagram if it helps readers.
  - **Matching export width:** Shared ``skinparam ParticipantPadding`` in ``style.puml`` is the
    default. If one sequence still renders much narrower than its neighbours, override **only
    in that** ``*.puml`` file (after the injected style, so it wins), e.g.
    ``skinparam ParticipantPadding 71``. Re-render and compare the root SVG ``width="…px"``.
    Tune padding until the width is close to the reference diagram (see ``sequences/
    error_log_sequence.puml`` vs ``create_conspectus_sequence.puml``).
  - **What does *not* work** for widening sequence lifelines: ``skinparam nodesep`` and
    ``skinparam minClassWidth`` are unreliable here; prefer participant alignment + padding.

----------------------------------------------------------------------------
When something looks wrong after render (checklist)
----------------------------------------------------------------------------

  1. Regenerate and compare bytes: ``python3 scripts/regenerate_docs.py --force``, then
     ``scripts/regenerate_docs.py --check``. Commit ``rendered/*.svg`` and ``input-hashes.json`` when they change.
  2. Open the SVG and check the root element: ``width="…px"`` / ``viewBox``. Compare with another
     diagram that looks correct. Large width differences explain different “block” size in HTML.
  3. If **text** looks larger on one diagram only: ensure HTML is not stretching that image
     (inspect computed width; see ``docs/assets/docs.css``). Ensure you did not use a fixed
     PlantUML scale without ``max`` in ``style.puml``.
  4. If widths differ but fonts match: adjust the **source** (participants, labels, per-file
     ``ParticipantPadding``), not the global scale, unless you intentionally change policy for
     all diagrams.

----------------------------------------------------------------------------
Commands
----------------------------------------------------------------------------

Regenerate SVGs (requires network when a diagram actually changes, HTTPS → kroki.io)
  make docs-fix
  # or:
  .venv/bin/python scripts/regenerate_docs.py
  .venv/bin/python scripts/regenerate_docs.py --force   # ignore cache, re-render all

Verify committed SVGs match sources (no writes)
  .venv/bin/python scripts/regenerate_docs.py --check
  # or:
  .venv/bin/python scripts/regenerate_docs.py --check
