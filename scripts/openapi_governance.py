"""OpenAPI governance checks and baseline management."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "docs" / "openapi" / "openapi-baseline.json"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}


def _ensure_minimal_env_for_app_import() -> None:
    """Set ``SQLITE_DB_PATH`` to a temp SQLite file if unset so ``app.main`` can import.

    Side effects:
        Mutates ``os.environ`` when ``SQLITE_DB_PATH`` is empty.
    """
    if os.environ.get("SQLITE_DB_PATH", "").strip():
        return
    tmp_db = Path(tempfile.gettempdir()) / "study_app_openapi_governance.sqlite"
    os.environ["SQLITE_DB_PATH"] = str(tmp_db)


def _load_current_openapi() -> dict[str, Any]:
    """Import the FastAPI app and return its live OpenAPI schema dict.

    Returns:
        JSON-serializable OpenAPI document from :meth:`fastapi.FastAPI.openapi`.

    Note:
        Inserts :data:`ROOT` at the front of ``sys.path`` temporarily.
    """
    _ensure_minimal_env_for_app_import()
    sys.path.insert(0, str(ROOT))
    from app.main import app  # noqa: WPS433

    return app.openapi()


def _load_baseline() -> dict[str, Any]:
    """Read the committed OpenAPI baseline JSON from disk.

    Returns:
        Parsed baseline document.

    Raises:
        FileNotFoundError: If :data:`BASELINE_PATH` does not exist.
    """
    if not BASELINE_PATH.exists():
        raise FileNotFoundError(
            f"Baseline not found: {BASELINE_PATH}. Run: make openapi-accept-changes"
        )
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def _write_baseline(spec: dict[str, Any]) -> None:
    """Write ``spec`` to :data:`BASELINE_PATH` with stable JSON formatting.

    Args:
        spec: Full OpenAPI document to persist.
    """
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(
        json.dumps(spec, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _iter_operations(spec: dict[str, Any]):
    """Yield ``(path, method, operation_dict)`` for each HTTP operation in ``spec``.

    Args:
        spec: OpenAPI document containing a ``paths`` object.

    Yields:
        Path string, lowercased method name, and operation object.
    """
    for path, path_item in spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            yield path, method.lower(), operation


def _resolve_schema(schema: dict[str, Any] | None, spec: dict[str, Any]) -> dict[str, Any]:
    """Inline ``$ref`` and merge simple ``allOf`` fragments into one schema dict.

    Args:
        schema: Possibly partial schema object from OpenAPI.
        spec: Full root document for resolving internal ``#/`` references.

    Returns:
        Resolved schema dict, or empty dict if resolution fails.
    """
    if not isinstance(schema, dict):
        return {}
    resolved = dict(schema)
    while "$ref" in resolved:
        ref = resolved["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            return resolved
        node: Any = spec
        for part in ref[2:].split("/"):
            node = node.get(part) if isinstance(node, dict) else None
            if node is None:
                return {}
        if not isinstance(node, dict):
            return {}
        resolved = {**node, **{k: v for k, v in resolved.items() if k != "$ref"}}
    if "allOf" in resolved and isinstance(resolved["allOf"], list):
        merged: dict[str, Any] = {k: v for k, v in resolved.items() if k != "allOf"}
        required: set[str] = set(merged.get("required", []))
        properties: dict[str, Any] = dict(merged.get("properties", {}))
        for part in resolved["allOf"]:
            child = _resolve_schema(part if isinstance(part, dict) else {}, spec)
            required.update(child.get("required", []))
            properties.update(child.get("properties", {}))
        if required:
            merged["required"] = sorted(required)
        if properties:
            merged["properties"] = properties
        return merged
    return resolved


def _json_request_schema(operation: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Resolve ``application/json`` request body schema for an operation.

    Args:
        operation: OpenAPI operation object.
        spec: Full document for ``$ref`` resolution.

    Returns:
        Resolved JSON Schema object, or empty dict if none.
    """
    body = operation.get("requestBody")
    if not isinstance(body, dict):
        return {}
    content = body.get("content")
    if not isinstance(content, dict):
        return {}
    app_json = content.get("application/json")
    if not isinstance(app_json, dict):
        return {}
    return _resolve_schema(app_json.get("schema"), spec)


def _json_response_schema(
    operation: dict[str, Any], status: str, spec: dict[str, Any]
) -> dict[str, Any]:
    """Resolve ``application/json`` response schema for a given HTTP status code.

    Args:
        operation: OpenAPI operation object.
        status: Response key (e.g. ``"200"``, ``"422"``).
        spec: Full document for ``$ref`` resolution.

    Returns:
        Resolved JSON Schema for the response body, or empty dict.
    """
    responses = operation.get("responses", {})
    if not isinstance(responses, dict):
        return {}
    payload = responses.get(status)
    if not isinstance(payload, dict):
        return {}
    content = payload.get("content")
    if not isinstance(content, dict):
        return {}
    app_json = content.get("application/json")
    if not isinstance(app_json, dict):
        return {}
    return _resolve_schema(app_json.get("schema"), spec)


def _required_fields(schema: dict[str, Any]) -> set[str]:
    """Return the set of required property names declared on a JSON Schema object.

    Args:
        schema: Object schema with optional ``required`` list.

    Returns:
        Set of field names; empty if ``required`` is missing or invalid.
    """
    required = schema.get("required", [])
    if not isinstance(required, list):
        return set()
    return {item for item in required if isinstance(item, str)}


def run_lint(spec: dict[str, Any]) -> list[str]:
    """Validate OpenAPI conventions: unique ``operationId``, summaries, 422 examples for writes.

    Args:
        spec: OpenAPI document to lint.

    Returns:
        Human-readable issue strings (empty if no problems).
    """
    issues: list[str] = []
    operation_ids: set[str] = set()
    for path, method, operation in _iter_operations(spec):
        op_id = operation.get("operationId")
        if not isinstance(op_id, str) or not op_id.strip():
            issues.append(f"{method.upper()} {path}: missing operationId")
        elif op_id in operation_ids:
            issues.append(f"{method.upper()} {path}: duplicate operationId '{op_id}'")
        else:
            operation_ids.add(op_id)

        summary = operation.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            issues.append(f"{method.upper()} {path}: missing summary")

        responses = operation.get("responses")
        if not isinstance(responses, dict) or not responses:
            issues.append(f"{method.upper()} {path}: missing responses")
            continue

        if method in {"post", "put", "patch", "delete"}:
            if "422" not in responses:
                issues.append(f"{method.upper()} {path}: missing 422 response")
            else:
                content = responses.get("422", {}).get("content", {})
                examples = (
                    content.get("application/json", {}).get("examples", {})
                    if isinstance(content, dict)
                    else {}
                )
                if not isinstance(examples, dict) or not examples:
                    issues.append(f"{method.upper()} {path}: 422 response should include examples")
    return issues


def _param_key(parameter: dict[str, Any]) -> tuple[str, str]:
    """Stable tuple identity for an OpenAPI parameter (name + location).

    Args:
        parameter: Parameter object from ``operation["parameters"]``.

    Returns:
        ``(name, location)`` strings.
    """
    return str(parameter.get("name", "")), str(parameter.get("in", ""))


def _required_parameters(operation: dict[str, Any]) -> dict[tuple[str, str], bool]:
    """Map each parameter (name, in) to whether it is required.

    Args:
        operation: OpenAPI operation object.

    Returns:
        Dict keyed by :func:`_param_key` with boolean required flags.
    """
    result: dict[tuple[str, str], bool] = {}
    params = operation.get("parameters", [])
    if not isinstance(params, list):
        return result
    for item in params:
        if not isinstance(item, dict):
            continue
        result[_param_key(item)] = bool(item.get("required", False))
    return result


def run_breaking_check(baseline: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Detect backward-incompatible changes between two OpenAPI documents.

    Args:
        baseline: Previously accepted API description.
        current: Newly generated API description.

    Returns:
        List of issue strings describing removals or new requirements; empty if safe.
    """
    issues: list[str] = []

    base_paths = baseline.get("paths", {})
    curr_paths = current.get("paths", {})
    if not isinstance(base_paths, dict) or not isinstance(curr_paths, dict):
        return ["Invalid OpenAPI document structure: paths must be objects"]

    for path, base_path_item in base_paths.items():
        if path not in curr_paths:
            issues.append(f"Removed path: {path}")
            continue
        curr_path_item = curr_paths[path]
        if not isinstance(base_path_item, dict) or not isinstance(curr_path_item, dict):
            continue

        for method, base_op in base_path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(base_op, dict):
                continue
            curr_op = curr_path_item.get(method)
            if not isinstance(curr_op, dict):
                issues.append(f"Removed operation: {method.upper()} {path}")
                continue

            base_params = _required_parameters(base_op)
            curr_params = _required_parameters(curr_op)
            for param_key, was_required in base_params.items():
                if was_required and param_key not in curr_params:
                    issues.append(
                        f"Removed required parameter {param_key[0]} in {param_key[1]} for "
                        f"{method.upper()} {path}"
                    )
            for param_key, is_required in curr_params.items():
                if is_required and not base_params.get(param_key, False):
                    issues.append(
                        f"New required parameter {param_key[0]} in {param_key[1]} for "
                        f"{method.upper()} {path}"
                    )

            base_req_schema = _json_request_schema(base_op, baseline)
            curr_req_schema = _json_request_schema(curr_op, current)
            base_required_fields = _required_fields(base_req_schema)
            curr_required_fields = _required_fields(curr_req_schema)
            newly_required = sorted(curr_required_fields - base_required_fields)
            for field in newly_required:
                issues.append(f"New required request field '{field}' in {method.upper()} {path}")

            base_responses = base_op.get("responses", {})
            curr_responses = curr_op.get("responses", {})
            if isinstance(base_responses, dict) and isinstance(curr_responses, dict):
                for status_code in base_responses.keys():
                    if status_code not in curr_responses:
                        issues.append(
                            f"Removed response status {status_code} for {method.upper()} {path}"
                        )

                for status_code in sorted(base_responses.keys()):
                    if not str(status_code).startswith("2"):
                        continue
                    if status_code not in curr_responses:
                        continue
                    base_resp_required = _required_fields(
                        _json_response_schema(base_op, str(status_code), baseline)
                    )
                    curr_resp_required = _required_fields(
                        _json_response_schema(curr_op, str(status_code), current)
                    )
                    dropped_required = sorted(base_resp_required - curr_resp_required)
                    for field in dropped_required:
                        issues.append(
                            f"Required response field '{field}' removed for "
                            f"{method.upper()} {path} [{status_code}]"
                        )

    return issues


def run_snapshot_check(baseline: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Return issues when ``current`` is not byte-identical to ``baseline`` (sorted JSON diff).

    Args:
        baseline: Accepted snapshot document.
        current: Live document from the app.

    Returns:
        Empty list if equal; otherwise headers plus a truncated unified diff.
    """
    if baseline == current:
        return []

    baseline_json = json.dumps(baseline, ensure_ascii=True, indent=2, sort_keys=True).splitlines()
    current_json = json.dumps(current, ensure_ascii=True, indent=2, sort_keys=True).splitlines()
    diff_lines = list(
        difflib.unified_diff(
            baseline_json,
            current_json,
            fromfile="openapi-baseline.json",
            tofile="current-openapi.json",
            lineterm="",
        )
    )

    issues = [
        "OpenAPI snapshot differs from baseline.",
        "If changes are intentional, run: make openapi-accept-changes",
    ]
    max_diff_lines = 40
    if diff_lines:
        issues.append(f"Snapshot diff (first {max_diff_lines} lines):")
        issues.extend(diff_lines[:max_diff_lines])
    return issues


def _print_issues(title: str, issues: list[str]) -> None:
    """Print a pass/fail summary and bullet list of issues to stdout.

    Args:
        title: Short name of the check (e.g. ``OpenAPI lint``).
        issues: Non-empty to print failures; empty prints a checkmark line.
    """
    if not issues:
        print(f"✓ {title}: passed")
        return
    print(f"✗ {title}: {len(issues)} issue(s)")
    for item in issues:
        print(f"  - {item}")


def command_check() -> int:
    """Run lint + breaking-change checks against the stored baseline.

    Returns:
        ``0`` if both pass, ``1`` if either reports issues.
    """
    current = _load_current_openapi()
    baseline = _load_baseline()

    lint_issues = run_lint(current)
    breaking_issues = run_breaking_check(baseline, current)

    _print_issues("OpenAPI lint", lint_issues)
    _print_issues("OpenAPI breaking change guard", breaking_issues)

    return 1 if lint_issues or breaking_issues else 0


def command_contract_test() -> int:
    """Run full JSON snapshot equality check (stricter than breaking-only guard).

    Returns:
        ``0`` if current matches baseline exactly, else ``1``.
    """
    current = _load_current_openapi()
    baseline = _load_baseline()
    snapshot_issues = run_snapshot_check(baseline, current)
    _print_issues("OpenAPI snapshot contract", snapshot_issues)
    return 1 if snapshot_issues else 0


def command_update_baseline() -> int:
    """Overwrite the baseline file with the current app OpenAPI JSON.

    Returns:
        Always ``0`` after a successful write.
    """
    current = _load_current_openapi()
    _write_baseline(current)
    print(f"✓ OpenAPI baseline updated: {BASELINE_PATH}")
    return 0


def main() -> None:
    """Dispatch ``check``, ``contract-test``, or ``update-baseline`` subcommands."""
    parser = argparse.ArgumentParser(description="OpenAPI governance checks and baseline update.")
    parser.add_argument(
        "command",
        choices=["check", "contract-test", "update-baseline"],
        help="Run checks or update baseline from current app.openapi() output.",
    )
    args = parser.parse_args()

    if args.command == "check":
        raise SystemExit(command_check())
    if args.command == "contract-test":
        raise SystemExit(command_contract_test())
    raise SystemExit(command_update_baseline())


if __name__ == "__main__":
    main()
