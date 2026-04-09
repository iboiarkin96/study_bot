"""Tests for POST /api/v1/user."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_create_user_success(client) -> None:
    payload = {
        "system_user_id": "a1b2c3d4-0001-4000-8000-000000000001",
        "full_name": "Ivan Petrov",
        "username": "ipetrov",
        "timezone": "UTC",
    }

    response = client.post(
        "/api/v1/user",
        json=payload,
        headers={"Idempotency-Key": "create-user-success-1"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["system_user_id"] == payload["system_user_id"]
    assert body["full_name"] == payload["full_name"]
    assert body["timezone"] == payload["timezone"]
    assert "client_uuid" in body


def test_create_user_duplicate_returns_business_error(client) -> None:
    payload = {
        "system_user_id": "a1b2c3d4-0001-4000-8000-000000000002",
        "full_name": "Ivan Petrov",
        "timezone": "UTC",
    }

    first = client.post(
        "/api/v1/user",
        json=payload,
        headers={"Idempotency-Key": "create-user-dup-1"},
    )
    second = client.post(
        "/api/v1/user",
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
    payload = {
        "system_user_id": "a1b2c3d4-0001-4000-8000-000000000003",
        "full_name": "Ivan Petrov",
        "timezone": "Europe/123",
    }

    response = client.post(
        "/api/v1/user",
        json=payload,
        headers={"Idempotency-Key": "create-user-timezone-1"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_type"] == "validation_error"
    assert body["endpoint"] == "POST /api/v1/user"
    assert body["errors"][0]["code"] == "USER_007"
    assert body["errors"][0]["field"] == "timezone"
    assert body["errors"][0]["source"] == "validation"


def test_create_user_short_system_user_id_is_valid(client) -> None:
    payload = {
        "system_user_id": "1",
        "full_name": "Ivan Petrov",
        "timezone": "UTC",
    }

    response = client.post(
        "/api/v1/user",
        json=payload,
        headers={"Idempotency-Key": "create-user-system-user-id-short-valid-1"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["system_user_id"] == payload["system_user_id"]


def test_create_user_requires_api_key() -> None:
    client = TestClient(app)
    payload = {
        "system_user_id": "a1b2c3d4-0001-4000-8000-000000000099",
        "full_name": "Ivan Petrov",
        "timezone": "UTC",
    }

    response = client.post(
        "/api/v1/user",
        json=payload,
        headers={"Idempotency-Key": "create-user-auth-required-1"},
    )

    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail["code"] == "COMMON_401"
    assert detail["key"] == "SECURITY_AUTH_REQUIRED"
    assert detail["source"] == "security"


def test_create_user_idempotent_replay_returns_same_result(client) -> None:
    payload = {
        "system_user_id": "a1b2c3d4-0001-4000-8000-000000000004",
        "full_name": "Ivan Petrov",
        "timezone": "UTC",
    }
    headers = {"Idempotency-Key": "create-user-idempotent-replay-1"}

    first = client.post("/api/v1/user", json=payload, headers=headers)
    second = client.post("/api/v1/user", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()


def test_create_user_idempotency_key_conflict_returns_409(client) -> None:
    base_headers = {"Idempotency-Key": "create-user-idempotent-conflict-1"}
    first_payload = {
        "system_user_id": "a1b2c3d4-0001-4000-8000-000000000005",
        "full_name": "Ivan Petrov",
        "timezone": "UTC",
    }
    second_payload = {
        "system_user_id": "a1b2c3d4-0001-4000-8000-000000000006",
        "full_name": "Petr Ivanov",
        "timezone": "UTC",
    }

    first = client.post("/api/v1/user", json=first_payload, headers=base_headers)
    second = client.post("/api/v1/user", json=second_payload, headers=base_headers)

    assert first.status_code == 201
    assert second.status_code == 409
    detail = second.json()["detail"]
    assert detail["code"] == "COMMON_409"
    assert detail["key"] == "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD"


def test_create_user_without_idempotency_key_returns_422(client) -> None:
    payload = {
        "system_user_id": "a1b2c3d4-0001-4000-8000-000000000007",
        "full_name": "Ivan Petrov",
        "timezone": "UTC",
    }

    response = client.post("/api/v1/user", json=payload)

    assert response.status_code == 422


def test_create_user_with_empty_idempotency_key_returns_422(client) -> None:
    payload = {
        "system_user_id": "a1b2c3d4-0001-4000-8000-000000000008",
        "full_name": "Ivan Petrov",
        "timezone": "UTC",
    }

    response = client.post(
        "/api/v1/user",
        json=payload,
        headers={"Idempotency-Key": ""},
    )

    assert response.status_code == 422


def test_get_user_by_system_user_id_success(client) -> None:
    payload = {
        "system_user_id": "42",
        "full_name": "Ivan Petrov",
        "timezone": "UTC",
    }
    create = client.post(
        "/api/v1/user",
        json=payload,
        headers={"Idempotency-Key": "get-user-success-seed-1"},
    )
    assert create.status_code == 201

    response = client.get("/api/v1/user/42")

    assert response.status_code == 200
    body = response.json()
    assert body["system_user_id"] == "42"
    assert body["full_name"] == "Ivan Petrov"


def test_get_user_by_system_user_id_not_found_returns_404(client) -> None:
    response = client.get("/api/v1/user/not-existing")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "USER_404"
    assert detail["key"] == "USER_NOT_FOUND"
    assert detail["source"] == "business"


def test_create_user_unknown_validation_shape_falls_back_to_common_code(client) -> None:
    response = client.post(
        "/api/v1/user",
        json=[],
        headers={"Idempotency-Key": "create-user-validation-fallback-1"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error_type"] == "validation_error"
    assert body["endpoint"] == "POST /api/v1/user"
    assert body["errors"][0]["code"] == "COMMON_000"
    assert body["errors"][0]["key"] == "COMMON_VALIDATION_ERROR"
