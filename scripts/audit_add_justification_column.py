"""Insert Table 2 \"Justification\" column before Score cells in audit HTML (audit-score-table)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DX_PATH = ROOT / "docs/audit/docs/2026-04-14-documentation-experience-assessment.html"
API_PATH = ROOT / "docs/audit/api/2026-04-14-rest-api-assessment.html"

# One line per Table 2 row (25 DX rows)
DX_JUSTIFICATIONS = [
    "Folders imply roles; explicit Diátaxis labels would raise confidence.",
    "Quality depends on author habit; no uniform “basics first” pattern.",
    "Strong pieces exist; no single end-to-end golden path with checkpoints.",
    "ADR 0001 + pipeline: reviewable, automated — reference-tier for PET.",
    "OpenAPI + generation limit hand drift; narrative still manual.",
    "Changelog + tags; not separate versioned doc subsites.",
    "Drift checks and OpenAPI gates; prose lint not universal.",
    "Examples not executed as a dedicated docs CI job.",
    "Errors covered across matrix, OpenAPI, runbooks — not one catalog site.",
    "Baseline + governance: contract is enforced in repo.",
    "Swagger UI + static explorer; env risk stays with the operator.",
    "HTTP-only scope; no multi-SDK tabs — intentional at this scale.",
    "Client-side index exists; ranking/tuning remain iterative (see ADR 0027).",
    "No in-repo RAG assistant — acceptable until prioritized.",
    "Static HTML/CSS; CWV not measured in this assessment.",
    "Stable paths and anchors; copy-link affordance not everywhere.",
    "Semantic patterns; full WCAG 2.2 AA not claimed for every template.",
    "English-first; translation workflow out of scope unless product asks.",
    "Precise engineering tone; inclusive glossary not centralized.",
    "Changelog gate + format — strong trust signal.",
    "Env templates and placeholder discipline match good practice.",
    "Issues/PR path exists; in-page thumbs not required.",
    "No default first-party docs analytics pipeline.",
    "Runbooks under docs/runbooks; on-call roster outside repo.",
    "PET-appropriate: docs site, not a billing portal.",
]

# 24 API rows
API_JUSTIFICATIONS = [
    "Request id wired through logs and responses — strong fit.",
    "Idempotency keys + storage + 409 — reference implementation for writes.",
    "Optimistic concurrency not implemented — score reflects absence.",
    "Conditional GET not implemented for current reads.",
    "No list route yet; pagination N/A until collections exist.",
    "/api/v1 + ADR policy; servers skew local — documented.",
    "Spectral/Redocly-style governance via scripts and baseline.",
    "Problem details + stable codes in governance path.",
    "HSTS and baseline headers where applicable — verify deployment.",
    "Rate limiting present for the service shape.",
    "Auth model matches product; external SSO out of scope here.",
    "OpenAPI drives UI and tests — SSOT for HTTP contract.",
    "Trace context reserved; full OTel rollout future work.",
    "Structured logs with request id — good operability.",
    "SLO/error budget docs exist; enforcement is process-dependent.",
    "Contract tests in CI — high confidence vs drift.",
    "Deprecation policy documented; few deprecated surfaces yet.",
    "Version in URL; sunset headers when sunsetting appears.",
    "Changelog discipline with gate — aligns with integrators’ needs.",
    "Container + GHCR path documented — not Heroku-specific.",
    "No separate AsyncAPI artifact — sync-only surface for now.",
    "Errors spread across matrix/docs vs single catalog — PET trade-off.",
    "Lifecycle docs + HTTP deprecation story evolving with API.",
    "One pipeline from code to OpenAPI to tests — strong alignment.",
]


def _insert_justifications(html: str, justifications: list[str]) -> str:
    pattern = re.compile(
        r"\n[ \t]*<td class=\"score-(?:excellent|good|needs-attention|neutral)\">\d+</td>",
    )
    matches = list(pattern.finditer(html))
    if len(matches) != len(justifications):
        raise SystemExit(
            f"Expected {len(justifications)} score cells, found {len(matches)}",
        )
    out: list[str] = []
    pos = 0
    for m, text in zip(matches, justifications, strict=True):
        out.append(html[pos : m.start()])
        esc = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        out.append(
            f'\n                  <td class="audit-table-justification">{esc}</td>{m.group(0)}',
        )
        pos = m.end()
    out.append(html[pos:])
    return "".join(out)


def _patch_dx() -> None:
    text = DX_PATH.read_text(encoding="utf-8")
    text = text.replace(
        '<th scope="col">Study App evidence / notes</th>\n'
        '                  <th scope="col">Score</th>',
        '<th scope="col">Study App evidence / notes</th>\n'
        '                  <th scope="col">Justification</th>\n'
        '                  <th scope="col">Score</th>',
        1,
    )
    text = _insert_justifications(text, DX_JUSTIFICATIONS)
    DX_PATH.write_text(text, encoding="utf-8")


def _patch_api() -> None:
    text = API_PATH.read_text(encoding="utf-8")
    text = text.replace(
        '<th scope="col">What exists in the project (code)</th>\n'
        '                  <th scope="col">Score</th>',
        '<th scope="col">What exists in the project (code)</th>\n'
        '                  <th scope="col">Justification</th>\n'
        '                  <th scope="col">Score</th>',
        1,
    )
    text = _insert_justifications(text, API_JUSTIFICATIONS)
    API_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    _patch_dx()
    _patch_api()
    print("Patched:", DX_PATH.relative_to(ROOT))
    print("Patched:", API_PATH.relative_to(ROOT))


if __name__ == "__main__":
    main()
