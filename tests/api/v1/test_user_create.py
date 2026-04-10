"""Tests for POST /api/v1/user and GET/PUT/PATCH /api/v1/user/{system_uuid}/{system_user_id}."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.api.v1.user_test_utils import (
    TEST_INVALIDATION_REASON_UUID,
    TEST_SYSTEM_UUID,
    TEST_SYSTEM_UUID_ALT,
    USER_CREATE_OPERATION,
    USER_HTTP_BASE_PATH,
    user_create_body,
    user_patch_body,
    user_resource_path,
    user_update_body,
)


def test_create_user_success(client) -> None:
    payload = user_create_body(
        "a1b2c3d4-0001-4000-8000-000000000001",
        username="ipetrov",
    )

    response = client.post(
        USER_HTTP_BASE_PATH,
        json=payload,
        headers={"Idempotency-Key": "create-user-success-1"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["system_user_id"] == payload["system_user_id"]
    assert body["system_uuid"] == str(payload["system_uuid"])
    assert body["full_name"] == payload["full_name"]
    assert body["timezone"] == payload["timezone"]
    assert "client_uuid" in body


def test_create_user_duplicate_returns_business_error(client) -> None:
    payload = user_create_body("a1b2c3d4-0001-4000-8000-000000000002")

    first = client.post(
        USER_HTTP_BASE_PATH,
        json=payload,
        headers={"Idempotency-Key": "create-user-dup-1"},
    )
    second = client.post(
        USER_HTTP_BASE_PATH,
        json=payload,
        headers={"Idempotency-Key": "create-user-dup-2"},
    )

    assert first.status_code == 201
    assert second.status_code == 400
    detail = second.json()["detail"]
    assert detail["code"] == "USER_101"
    assert detail["key"] == "USER_CREATE_ALREADY_EXISTS"
    assert detail["source"] == "business"


def test_create_user_invalid_timezone_returns_code_based_422(client) -> None:
    payload = user_create_body("a1b2c3d4-0001-4000-8000-000000000003")
    payload["timezone"] = "Europe/123"

    response = client.post(
        USER_HTTP_BASE_PATH,
        json=payload,
        headers={"Idempotency-Key": "create-user-timezone-1"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_type"] == "validation_error"
    assert body["endpoint"] == USER_CREATE_OPERATION
    assert body["errors"][0]["code"] == "USER_007"
    assert body["errors"][0]["field"] == "timezone"
    assert body["errors"][0]["source"] == "validation"


def test_create_user_short_system_user_id_is_valid(client) -> None:
    payload = user_create_body("1")

    response = client.post(
        USER_HTTP_BASE_PATH,
        json=payload,
        headers={"Idempotency-Key": "create-user-system-user-id-short-valid-1"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["system_user_id"] == payload["system_user_id"]
    assert body["system_uuid"] == TEST_SYSTEM_UUID


def test_create_user_requires_api_key() -> None:
    client = TestClient(app)
    payload = user_create_body("a1b2c3d4-0001-4000-8000-000000000099")

    response = client.post(
        USER_HTTP_BASE_PATH,
        json=payload,
        headers={"Idempotency-Key": "create-user-auth-required-1"},
    )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["code"] == "COMMON_401"
    assert detail["key"] == "SECURITY_AUTH_REQUIRED"
    assert detail["source"] == "security"


def test_create_user_idempotent_replay_returns_same_result(client) -> None:
    payload = user_create_body("a1b2c3d4-0001-4000-8000-000000000004")
    headers = {"Idempotency-Key": "create-user-idempotent-replay-1"}

    first = client.post(USER_HTTP_BASE_PATH, json=payload, headers=headers)
    second = client.post(USER_HTTP_BASE_PATH, json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()


def test_create_user_idempotency_key_conflict_returns_409(client) -> None:
    base_headers = {"Idempotency-Key": "create-user-idempotent-conflict-1"}
    first_payload = user_create_body("a1b2c3d4-0001-4000-8000-000000000005")
    second_payload = user_create_body(
        "a1b2c3d4-0001-4000-8000-000000000006",
        full_name="Petr Ivanov",
    )

    first = client.post(USER_HTTP_BASE_PATH, json=first_payload, headers=base_headers)
    second = client.post(USER_HTTP_BASE_PATH, json=second_payload, headers=base_headers)

    assert first.status_code == 201
    assert second.status_code == 409
    detail = second.json()["detail"]
    assert detail["code"] == "COMMON_409"
    assert detail["key"] == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"


def test_create_user_without_idempotency_key_returns_422(client) -> None:
    payload = user_create_body("a1b2c3d4-0001-4000-8000-000000000007")

    response = client.post(USER_HTTP_BASE_PATH, json=payload)

    assert response.status_code == 422


def test_create_user_with_empty_idempotency_key_returns_422(client) -> None:
    payload = user_create_body("a1b2c3d4-0001-4000-8000-000000000008")

    response = client.post(
        USER_HTTP_BASE_PATH,
        json=payload,
        headers={"Idempotency-Key": ""},
    )

    assert response.status_code == 422


def test_get_user_by_system_user_id_success(client) -> None:
    payload = user_create_body("42")
    create = client.post(
        USER_HTTP_BASE_PATH,
        json=payload,
        headers={"Idempotency-Key": "get-user-success-seed-1"},
    )
    assert create.status_code == 201

    response = client.get(user_resource_path("42"))

    assert response.status_code == 200
    body = response.json()
    assert body["system_user_id"] == "42"
    assert body["full_name"] == "Ivan Petrov"


def test_get_user_by_system_user_id_not_found_returns_404(client) -> None:
    response = client.get(user_resource_path("not-existing"))

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "USER_404"
    assert detail["key"] == "USER_NOT_FOUND"
    assert detail["source"] == "business"


def test_put_user_by_system_user_id_success(client) -> None:
    sid = "put-user-ok-1"
    create = client.post(
        USER_HTTP_BASE_PATH,
        json=user_create_body(sid),
        headers={"Idempotency-Key": "put-user-seed-1"},
    )
    assert create.status_code == 201

    upd = user_update_body(full_name="Updated Name", timezone="Europe/Moscow")
    response = client.put(
        user_resource_path(sid),
        json=upd,
        headers={"Idempotency-Key": "put-user-ok-1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["system_user_id"] == sid
    assert body["full_name"] == "Updated Name"
    assert body["timezone"] == "Europe/Moscow"


def test_put_user_not_found_returns_404(client) -> None:
    response = client.put(
        user_resource_path("missing-put-1"),
        json=user_update_body(),
        headers={"Idempotency-Key": "put-user-missing-1"},
    )
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "USER_404"
    assert detail["key"] == "USER_NOT_FOUND"


def test_put_user_idempotent_replay_returns_same_result(client) -> None:
    sid = "put-user-idem-1"
    assert (
        client.post(
            USER_HTTP_BASE_PATH,
            json=user_create_body(sid),
            headers={"Idempotency-Key": "put-user-idem-seed"},
        ).status_code
        == 201
    )
    payload = user_update_body(full_name="Same Every Time")
    headers = {"Idempotency-Key": "put-user-idem-key"}
    first = client.put(user_resource_path(sid), json=payload, headers=headers)
    second = client.put(user_resource_path(sid), json=payload, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


def test_put_user_idempotency_key_conflict_returns_409(client) -> None:
    sid = "put-user-conflict-1"
    assert (
        client.post(
            USER_HTTP_BASE_PATH,
            json=user_create_body(sid),
            headers={"Idempotency-Key": "put-user-conflict-seed"},
        ).status_code
        == 201
    )
    headers = {"Idempotency-Key": "put-user-conflict-key"}
    first = client.put(
        user_resource_path(sid),
        json=user_update_body(full_name="A"),
        headers=headers,
    )
    second = client.put(
        user_resource_path(sid),
        json=user_update_body(full_name="B"),
        headers=headers,
    )
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["detail"]["key"] == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"


def test_put_user_invalid_timezone_returns_code_based_422(client) -> None:
    sid = "put-user-tz-1"
    assert (
        client.post(
            USER_HTTP_BASE_PATH,
            json=user_create_body(sid),
            headers={"Idempotency-Key": "put-user-tz-seed"},
        ).status_code
        == 201
    )
    # Invalid timezone must bypass UserUpdateRequest construction (client validates body).
    bad = {
        "full_name": "Petr Ivanov",
        "timezone": "Europe/123",
        "username": "ipetrov_updated",
        "is_row_invalid": 0,
    }
    response = client.put(
        user_resource_path(sid),
        json=bad,
        headers={"Idempotency-Key": "put-user-tz-bad"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error_type"] == "validation_error"
    assert body["endpoint"] == f"PUT {user_resource_path(sid)}"
    assert body["errors"][0]["code"] == "USER_018"
    assert body["errors"][0]["field"] == "timezone"


def test_patch_user_updates_timezone_only(client) -> None:
    sid = "patch-user-tz-only"
    assert (
        client.post(
            USER_HTTP_BASE_PATH,
            json=user_create_body(sid, timezone="UTC"),
            headers={"Idempotency-Key": "patch-tz-only-seed"},
        ).status_code
        == 201
    )
    response = client.patch(
        user_resource_path(sid),
        json={"timezone": "Europe/Moscow"},
        headers={"Idempotency-Key": "patch-tz-only-1"},
    )
    assert response.status_code == 200
    assert response.json()["timezone"] == "Europe/Moscow"


def test_patch_user_by_system_user_id_success(client) -> None:
    sid = "patch-user-ok-1"
    assert (
        client.post(
            USER_HTTP_BASE_PATH,
            json=user_create_body(sid),
            headers={"Idempotency-Key": "patch-user-seed-1"},
        ).status_code
        == 201
    )
    response = client.patch(
        user_resource_path(sid),
        json=user_patch_body(full_name="Patched Name"),
        headers={"Idempotency-Key": "patch-user-ok-1"},
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Patched Name"
    assert response.json()["system_user_id"] == sid


def test_patch_user_empty_body_returns_400(client) -> None:
    sid = "patch-user-empty-1"
    assert (
        client.post(
            USER_HTTP_BASE_PATH,
            json=user_create_body(sid),
            headers={"Idempotency-Key": "patch-user-empty-seed"},
        ).status_code
        == 201
    )
    response = client.patch(
        user_resource_path(sid),
        json={},
        headers={"Idempotency-Key": "patch-user-empty-1"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "USER_102"
    assert detail["key"] == "USER_PATCH_BODY_EMPTY"


def test_patch_user_not_found_returns_404(client) -> None:
    response = client.patch(
        user_resource_path("patch-missing-1"),
        json=user_patch_body(),
        headers={"Idempotency-Key": "patch-user-missing-1"},
    )
    assert response.status_code == 404
    assert response.json()["detail"]["key"] == "USER_NOT_FOUND"


def test_patch_user_idempotent_replay_returns_same_result(client) -> None:
    sid = "patch-user-idem-1"
    assert (
        client.post(
            USER_HTTP_BASE_PATH,
            json=user_create_body(sid),
            headers={"Idempotency-Key": "patch-user-idem-seed"},
        ).status_code
        == 201
    )
    payload = user_patch_body(full_name="Idem Patch")
    headers = {"Idempotency-Key": "patch-user-idem-key"}
    first = client.patch(user_resource_path(sid), json=payload, headers=headers)
    second = client.patch(user_resource_path(sid), json=payload, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


def test_patch_user_idempotency_key_conflict_returns_409(client) -> None:
    sid = "patch-user-conflict-1"
    assert (
        client.post(
            USER_HTTP_BASE_PATH,
            json=user_create_body(sid),
            headers={"Idempotency-Key": "patch-user-conflict-seed"},
        ).status_code
        == 201
    )
    headers = {"Idempotency-Key": "patch-user-conflict-key"}
    first = client.patch(
        user_resource_path(sid),
        json=user_patch_body(full_name="A"),
        headers=headers,
    )
    second = client.patch(
        user_resource_path(sid),
        json=user_patch_body(full_name="B"),
        headers=headers,
    )
    assert first.status_code == 200
    assert second.status_code == 409


def test_patch_user_invalid_timezone_returns_code_based_422(client) -> None:
    sid = "patch-user-tz-1"
    assert (
        client.post(
            USER_HTTP_BASE_PATH,
            json=user_create_body(sid),
            headers={"Idempotency-Key": "patch-user-tz-seed"},
        ).status_code
        == 201
    )
    bad = {"timezone": "Europe/123"}
    response = client.patch(
        user_resource_path(sid),
        json=bad,
        headers={"Idempotency-Key": "patch-user-tz-bad"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["endpoint"] == f"PATCH {user_resource_path(sid)}"
    assert body["errors"][0]["code"] == "USER_018"


def test_create_user_unknown_validation_shape_falls_back_to_common_code(client) -> None:
    response = client.post(
        USER_HTTP_BASE_PATH,
        json=[],
        headers={"Idempotency-Key": "create-user-validation-fallback-1"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_type"] == "validation_error"
    assert body["endpoint"] == USER_CREATE_OPERATION
    assert body["errors"][0]["code"] == "COMMON_000"
    assert body["errors"][0]["key"] == "COMMON_VALIDATION_ERROR"


def test_create_user_persists_invalidation_reason_uuid(client) -> None:
    payload = user_create_body(
        "user-with-ir-1",
        invalidation_reason_uuid=TEST_INVALIDATION_REASON_UUID,
    )
    response = client.post(
        USER_HTTP_BASE_PATH,
        json=payload,
        headers={"Idempotency-Key": "create-user-ir-1"},
    )
    assert response.status_code == 201
    assert response.json()["invalidation_reason_uuid"] == TEST_INVALIDATION_REASON_UUID


def test_patch_user_updates_username(client) -> None:
    sid = "patch-username-1"
    assert (
        client.post(
            USER_HTTP_BASE_PATH,
            json=user_create_body(sid),
            headers={"Idempotency-Key": "patch-username-seed"},
        ).status_code
        == 201
    )
    response = client.patch(
        user_resource_path(sid),
        json={"username": "new_username"},
        headers={"Idempotency-Key": "patch-username-1"},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "new_username"


def test_put_user_body_may_set_system_uuid(client) -> None:
    sid = "put-body-sysuuid-1"
    assert (
        client.post(
            USER_HTTP_BASE_PATH,
            json=user_create_body(sid),
            headers={"Idempotency-Key": "put-body-sysuuid-seed"},
        ).status_code
        == 201
    )
    body = user_update_body(full_name="Name", timezone="UTC")
    body["system_uuid"] = TEST_SYSTEM_UUID
    response = client.put(
        user_resource_path(sid),
        json=body,
        headers={"Idempotency-Key": "put-body-sysuuid-1"},
    )
    assert response.status_code == 200
    assert response.json()["system_uuid"] == TEST_SYSTEM_UUID


def test_patch_user_may_change_system_uuid(client) -> None:
    sid = "patch-sysuuid-1"
    assert (
        client.post(
            USER_HTTP_BASE_PATH,
            json=user_create_body(sid),
            headers={"Idempotency-Key": "patch-sysuuid-seed"},
        ).status_code
        == 201
    )
    response = client.patch(
        user_resource_path(sid),
        json={"system_uuid": TEST_SYSTEM_UUID_ALT},
        headers={"Idempotency-Key": "patch-sysuuid-1"},
    )
    assert response.status_code == 200
    assert response.json()["system_uuid"] == TEST_SYSTEM_UUID_ALT
