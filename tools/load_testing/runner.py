"""
Load-testing runner: collects scenarios from ``tools/load_testing/scenarios/**/*.py``.

  python -m tools.load_testing.runner --dry-run
  python -m tools.load_testing.runner --total-requests 200

Optional environment:
  LOAD_TEST_BASE_URL   (default http://127.0.0.1:8000)
  LOAD_TEST_API_KEY    (default local-dev-key)
  LOAD_TEST_VERBOSE=1  — log skipped modules when group weight is zero (same as --verbose)

Docs: tools/load_testing/README.html
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import random
import sys
import time
import uuid
from collections import Counter
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx

from tools.load_testing.request import BuiltRequest, RunContext

SCENARIO_BUILD = Callable[[RunContext], BuiltRequest]
DELAY_MS = 10


def _scenario_modules() -> Iterator[str]:
    """Yield import paths for each ``scenarios/**/*.py`` module except helpers.

    Yields:
        Dotted module names such as ``tools.load_testing.scenarios.user.create``.
    """
    root = Path(__file__).resolve().parent / "scenarios"
    for path in sorted(root.rglob("*.py")):
        if path.name == "__init__.py" or path.name == "weights.py" or path.name.startswith("_"):
            continue
        rel = path.relative_to(root).with_suffix("")
        yield "tools.load_testing.scenarios." + ".".join(rel.parts)


def _load_module(name: str):
    """Import a package module by dotted path (used for scenarios and weights).

    Args:
        name: Fully qualified module name.

    Returns:
        Loaded module object.
    """
    return importlib.import_module(name)


def _abs_sum(weights: dict[str, float]) -> float:
    """Sum weight values (must be ~1.0 for normalized mixture dicts).

    Args:
        weights: Mapping of scenario or group name to non-negative weight.

    Returns:
        Sum of all values.
    """
    return sum(weights.values())


def collect(
    *, verbose: bool = False
) -> tuple[
    dict[str, float],
    dict[str, SCENARIO_BUILD],
    dict[str, str],
]:
    """Discover scenario modules, validate weights, and build the global mixture.

    Args:
        verbose: If True, log to stderr when a group weight is zero and modules are skipped.

    Returns:
        Tuple of ``(scenario_weights, scenario_builders, scenario_source_module)`` where
        weights sum to ~1.0 and keys are unique across all files.

    Raises:
        SystemExit: On invalid ``GROUP_WEIGHTS``, ``MIX``, ``SHARE_OF_GROUP``, or duplicate keys.
    """
    wmod = _load_module("tools.load_testing.scenarios.weights")
    group_weights: dict[str, float] = dict(wmod.GROUP_WEIGHTS)

    if abs(_abs_sum(group_weights) - 1.0) > 0.02:
        raise SystemExit(f"GROUP_WEIGHTS must sum to ~1.0, got {_abs_sum(group_weights)}")

    final: dict[str, float] = {}
    builders: dict[str, SCENARIO_BUILD] = {}
    sources: dict[str, str] = {}
    share_by_group: dict[str, list[tuple[str, float]]] = {}

    for mod_name in _scenario_modules():
        mod = _load_module(mod_name)
        mix = getattr(mod, "MIX", None)
        scenarios = getattr(mod, "SCENARIOS", None)
        if not mix or not scenarios:
            continue
        if abs(_abs_sum(mix) - 1.0) > 0.02:
            raise SystemExit(f"{mod_name}: MIX must sum to ~1.0, got {_abs_sum(mix)}")

        group = getattr(mod, "GROUP", None)
        if not group or group not in group_weights:
            raise SystemExit(
                f"{mod_name}: set GROUP to one of GROUP_WEIGHTS: {sorted(group_weights)}"
            )

        gw = float(group_weights[group])
        if gw <= 0.0:
            if verbose:
                print(
                    f"Skip {mod_name}: group weight {group!r} in GROUP_WEIGHTS is 0 (scenarios disabled).",
                    file=sys.stderr,
                )
            continue

        share = float(getattr(mod, "SHARE_OF_GROUP", 1.0))
        share_by_group.setdefault(group, []).append((mod_name, share))
        for key, frac in mix.items():
            if key in final:
                raise SystemExit(
                    f"Duplicate scenario key {key!r} ({mod_name} vs {sources.get(key)})"
                )
            if key not in scenarios:
                raise SystemExit(f"{mod_name}: key {key!r} in MIX but missing in SCENARIOS")
            fn = scenarios[key]
            if not callable(fn):
                raise SystemExit(f"{mod_name}: SCENARIOS[{key!r}] must be callable")
            w = gw * share * float(frac)
            final[key] = w
            builders[key] = fn  # type: ignore[assignment]
            sources[key] = mod_name

    for group, shares in share_by_group.items():
        s = sum(sh for _, sh in shares)
        if abs(s - 1.0) > 0.02:
            raise SystemExit(
                f"Group {group!r}: SHARE_OF_GROUP across files must sum to ~1.0, got {s}. "
                f"Files: {shares}"
            )

    if abs(_abs_sum(final) - 1.0) > 0.02:
        raise SystemExit(f"Final scenario weights must sum to ~1.0, got {_abs_sum(final)}")

    return final, builders, sources


def split_counts(total: int, weights: dict[str, float]) -> dict[str, int]:
    """Split ``total`` into integer counts per key using largest-remainder allocation.

    Args:
        total: Number of requests to distribute (must be >= 1).
        weights: Non-negative weights (typically sum to 1.0).

    Returns:
        Mapping of scenario name to integer count; values sum to ``total``.

    Raises:
        ValueError: If ``total`` is less than 1.
    """
    if total < 1:
        raise ValueError("total_requests >= 1")
    keys = list(weights.keys())
    raw = [total * weights[k] for k in keys]
    counts = [int(x) for x in raw]
    rest = total - sum(counts)
    frac = sorted(
        enumerate([raw[i] - counts[i] for i in range(len(keys))]), key=lambda t: t[1], reverse=True
    )
    for i in range(rest):
        counts[frac[i][0]] += 1
    return dict(zip(keys, counts, strict=True))


def join_url(base: str, path: str) -> str:
    """Join base URL and path with exactly one slash between them.

    Args:
        base: Origin without trailing slash (e.g. ``http://127.0.0.1:8000``).
        path: Absolute path starting with ``/``.

    Returns:
        Full URL string.
    """
    return base.rstrip("/") + "/" + path.lstrip("/")


def _mask_api_key(value: str) -> str:
    """Redact API key for logs (keep last four characters when long enough).

    Args:
        value: Raw header value.

    Returns:
        Masked string safe to print.
    """
    if len(value) <= 4:
        return "***"
    return f"***{value[-4:]}"


def format_request_for_log(
    *,
    method: str,
    url: str,
    headers: dict[str, str],
    json_body: object | None,
    params: dict[str, str] | None,
) -> str:
    """Format a multi-line representation of an HTTP request for stderr logging.

    Args:
        method: HTTP method.
        url: Full URL including query string if applicable.
        headers: Request headers (``X-API-Key`` is masked).
        json_body: Parsed JSON body or ``None``.
        params: Query parameters if sent separately from URL.

    Returns:
        Human-readable block suitable for ``print(..., file=sys.stderr)``.
    """
    lines: list[str] = [f"{method} {url}"]
    if params:
        lines.append(f"query_string: {params!r}")
    lines.append("headers:")
    for hk in sorted(headers.keys(), key=str.lower):
        val = headers[hk]
        if hk.lower() == "x-api-key":
            val = _mask_api_key(val)
        lines.append(f"  {hk}: {val}")
    if json_body is not None:
        lines.append("body (JSON):")
        lines.append(json.dumps(json_body, ensure_ascii=False, indent=2))
    else:
        lines.append("body: <none>")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: parse args, build scenario plan, execute HTTP requests or dry-run.

    Args:
        argv: Argument list; defaults to :data:`sys.argv` when ``None``.

    Returns:
        Process exit code (0 on success, non-zero on usage or request failures).
    """
    p = argparse.ArgumentParser(
        description="Load test via scenarios under tools/load_testing/scenarios/"
    )
    p.add_argument("--total-requests", type=int, default=100)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--delay-ms",
        type=float,
        default=None,
        help="Delay between requests (ms). Default from LOAD_TEST_DELAY_MS or ~1s — with ~60 req/60s per client "
        "you often get 429. For stress without delay: --delay-ms 0.",
    )
    p.add_argument("--seed", type=int, default=None, help="RNG seed for reproducible shuffle")
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Log modules skipped due to zero group weight (or set LOAD_TEST_VERBOSE=1).",
    )
    p.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Do not print progress to stdout during the run (summary still prints at the end).",
    )
    args = p.parse_args(argv)

    base_url = os.environ.get("LOAD_TEST_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    api_key = os.environ.get("LOAD_TEST_API_KEY", "local-dev-key")

    if args.delay_ms is None:
        raw = os.environ.get("LOAD_TEST_DELAY_MS", "").strip()
        args.delay_ms = float(raw) if raw else DELAY_MS

    verbose = args.verbose or os.environ.get("LOAD_TEST_VERBOSE", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    weights, builders, _sources = collect(verbose=verbose)
    if args.seed is not None:
        random.seed(args.seed)

    counts = split_counts(args.total_requests, weights)
    plan: list[str] = []
    for name, n in counts.items():
        plan.extend([name] * n)
    random.shuffle(plan)

    if args.dry_run:
        print(f"base_url={base_url}")
        print(f"total_requests={args.total_requests}")
        print(f"per_scenario_counts: {counts}")
        print(f"plan_slots: {len(plan)}")
        return 0

    default_headers = {
        "X-API-Key": api_key,
        "Accept": "application/json",
    }
    delay = max(0.0, float(args.delay_ms) / 1000.0)
    stats: Counter[int] = Counter()
    wrong = 0
    run_in_scenario: dict[str, int] = {k: 0 for k in counts}

    total = args.total_requests
    progress_every = max(1, min(50, total // 20))
    if not args.quiet:
        print(
            f"Start: {total} requests → {base_url}, delay {float(args.delay_ms):g} ms between requests",
            flush=True,
        )

    with httpx.Client(timeout=60.0) as client:
        for seq, key in enumerate(plan):
            ri = run_in_scenario[key]
            run_in_scenario[key] = ri + 1

            nonce = uuid.uuid4().hex
            ctx = RunContext(seq=seq, run_in_scenario=ri, nonce=nonce)
            built: BuiltRequest = builders[key](ctx)

            hdrs = {**default_headers, **built.headers}
            url = join_url(base_url, built.path)

            try:
                if built.method == "GET":
                    r = client.get(url, headers=hdrs, params=built.params)
                elif built.method == "POST":
                    r = client.post(url, headers=hdrs, json=built.json, params=built.params)
                else:
                    raise RuntimeError(f"Unsupported HTTP method {built.method}")
            except httpx.HTTPError as e:
                print(f"[{seq + 1}/{args.total_requests}] {key}: network: {e}", file=sys.stderr)
                stats[-1] += 1
                continue

            stats[r.status_code] += 1
            if r.status_code != built.expect_status:
                wrong += 1
                hint = ""
                if (
                    built.expect_status == 500
                    and r.status_code == 404
                    and "/__loadtest/http500" in url
                ):
                    hint = " (set LOADTEST_HTTP_500=true on the server)"
                print(
                    f"[{seq + 1}/{args.total_requests}] {key}: expected HTTP {built.expect_status}, "
                    f"got {r.status_code}{hint}",
                    file=sys.stderr,
                )
                if r.status_code == 429:
                    print(
                        format_request_for_log(
                            method=built.method,
                            url=url,
                            headers=hdrs,
                            json_body=built.json,
                            params=built.params,
                        ),
                        file=sys.stderr,
                    )
                    try:
                        detail = r.json()
                    except Exception:
                        detail = r.text
                    print(f"server response (429): {detail!r}", file=sys.stderr)
                    print("---", file=sys.stderr)

            if not args.quiet:
                done = seq + 1
                if done in (1, total) or (total > 1 and done % progress_every == 0):
                    print(f"[{done}/{total}] {key} -> HTTP {r.status_code}", flush=True)

            if delay:
                time.sleep(delay)

    print("---")
    print(f"Done, requests: {args.total_requests}")
    net_errors = int(stats.get(-1, 0))
    if net_errors:
        # -1 reserved in Counter for failures before any HTTP response (see except in loop).
        stats_for_print = Counter(stats)
        del stats_for_print[-1]
        print(f"HTTP status counts: {dict(sorted(stats_for_print.items()))}")
        print(f"Network failures (no HTTP response): {net_errors}", file=sys.stderr)
    else:
        print(f"HTTP status counts: {dict(sorted(stats.items()))}")

    if wrong:
        print(f"Mismatches vs expect_status: {wrong}", file=sys.stderr)
        if stats.get(429, 0) > 0:
            print(
                "Hint: 429 responses mean API rate limit (~60 requests per window per client by default). "
                "Options: increase --delay-ms; for local load use `make run-loadtest-api` (see Makefile) "
                "or raise API_RATE_LIMIT_REQUESTS in .env only for the run.",
                file=sys.stderr,
            )
        return 2
    if net_errors:
        print(
            "Hint: Connection refused / network errors mean nothing is listening on base_url or the API "
            "process exited before the run finished. Ensure the server is up on LOAD_TEST_BASE_URL, check "
            "uvicorn logs and the port; on long runs verify the API terminal did not exit.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
