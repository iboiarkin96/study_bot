"""OpenAPI governance checks and baseline management."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PATH = ROOT / "docs" / "openapi" / "openapi-baseline.json"
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}


def _load_current_openapi() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT))
    from app.main import app  # noqa: WPS433

    return app.openapi()


def _load_baseline() -> dict[str, Any]:
    if not BASELINE_PATH.exists():
        raise FileNotFoundError(
            f"Baseline not found: {BASELINE_PATH}. Run: make openapi-baseline-update"
        )
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def _write_baseline(spec: dict[str, Any]) -> None:
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(
        json.dumps(spec, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _iter_operations(spec: dict[str, Any]):
    for path, path_item in spec.get("paths", {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            yield path, method.lower(), operation


def _resolve_schema(schema: dict[str, Any] | None, spec: dict[str, Any]) -> dict[str, Any]:
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
    required = schema.get("required", [])
    if not isinstance(required, list):
        return set()
    return {item for item in required if isinstance(item, str)}


def run_lint(spec: dict[str, Any]) -> list[str]:
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
    return str(parameter.get("name", "")), str(parameter.get("in", ""))


def _required_parameters(operation: dict[str, Any]) -> dict[tuple[str, str], bool]:
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


def _print_issues(title: str, issues: list[str]) -> None:
    if not issues:
        print(f"✓ {title}: passed")
        return
    print(f"✗ {title}: {len(issues)} issue(s)")
    for item in issues:
        print(f"  - {item}")


def command_check() -> int:
    current = _load_current_openapi()
    baseline = _load_baseline()

    lint_issues = run_lint(current)
    breaking_issues = run_breaking_check(baseline, current)

    _print_issues("OpenAPI lint", lint_issues)
    _print_issues("OpenAPI breaking change guard", breaking_issues)

    return 1 if lint_issues or breaking_issues else 0


def command_update_baseline() -> int:
    current = _load_current_openapi()
    _write_baseline(current)
    print(f"✓ OpenAPI baseline updated: {BASELINE_PATH}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="OpenAPI governance checks and baseline update.")
    parser.add_argument(
        "command",
        choices=["check", "update-baseline"],
        help="Run checks or update baseline from current app.openapi() output.",
    )
    args = parser.parse_args()

    if args.command == "check":
        raise SystemExit(command_check())
    raise SystemExit(command_update_baseline())


if __name__ == "__main__":
    main()
