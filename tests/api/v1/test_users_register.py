"""Tests for POST /api/v1/users/register."""

from __future__ import annotations


def test_register_user_success(client) -> None:
    payload = {
        "system_user_id": "a1b2c3d4-0001-4000-8000-000000000001",
        "full_name": "Ivan Petrov",
        "username": "ipetrov",
        "timezone": "UTC",
    }

    response = client.post("/api/v1/users/register", json=payload)

    assert response.status_code == 201
    body = response.json()
    assert body["system_user_id"] == payload["system_user_id"]
    assert body["full_name"] == payload["full_name"]
    assert body["timezone"] == payload["timezone"]
    assert "client_uuid" in body


def test_register_user_duplicate_returns_business_error(client) -> None:
    payload = {
        "system_user_id": "a1b2c3d4-0001-4000-8000-000000000002",
        "full_name": "Ivan Petrov",
        "timezone": "UTC",
    }

    first = client.post("/api/v1/users/register", json=payload)
    second = client.post("/api/v1/users/register", json=payload)

    assert first.status_code == 201
    assert second.status_code == 400
    detail = second.json()["detail"]
    assert detail["code"] == "101"
    assert detail["key"] == "USR_REG_ALREADY_EXISTS"
    assert detail["source"] == "business"


def test_register_user_invalid_timezone_returns_code_based_422(client) -> None:
    payload = {
        "system_user_id": "a1b2c3d4-0001-4000-8000-000000000003",
        "full_name": "Ivan Petrov",
        "timezone": "Europe/Mscow",
    }

    response = client.post("/api/v1/users/register", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error_type"] == "validation_error"
    assert body["endpoint"] == "POST /api/v1/users/register"
    assert body["errors"][0]["code"] == "007"
    assert body["errors"][0]["field"] == "timezone"
    assert body["errors"][0]["source"] == "validation"

