"""HTTP handlers for user-related endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.core.idempotency import build_payload_hash
from app.openapi.examples import (
    IDEMPOTENCY_KEY_CONFLICT_ERROR_EXAMPLE,
    IDEMPOTENCY_KEY_REQUIRED_ERROR_EXAMPLE,
    SECURITY_AUTH_REQUIRED_ERROR_EXAMPLE,
    SECURITY_BODY_TOO_LARGE_ERROR_EXAMPLE,
    SECURITY_RATE_LIMIT_EXCEEDED_ERROR_EXAMPLE,
    TIMEZONE_VALIDATION_ERROR_EXAMPLE,
    USER_CREATE_REQUEST_EXAMPLES,
    USER_CREATE_REQUIRED_FIELD_ERROR_EXAMPLE,
    USER_EXISTS_ERROR_EXAMPLE,
)
from app.repositories.idempotency_repository import IdempotencyRepository
from app.repositories.user_repository import UserRepository
from app.schemas.errors import ApiErrorResponse, ValidationErrorResponse
from app.schemas.user import UserCreateRequest, UserCreateResponse
from app.services.user_service import UserService

logger = logging.getLogger(__name__)
api_key_security = APIKeyHeader(name="X-API-Key", auto_error=False)

router = APIRouter(prefix="/user", tags=["User"])


@router.post(
    "",
    response_model=UserCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description=(
        "Creates a new user by `system_user_id`. "
        "Requires `Idempotency-Key` header for safe retry semantics."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ApiErrorResponse,
            "description": "Business validation failure.",
            "content": {
                "application/json": {
                    "examples": {
                        "user_exists": {
                            "summary": "User already exists",
                            "value": USER_EXISTS_ERROR_EXAMPLE,
                        },
                        "idempotency_key_missing": {
                            "summary": "Missing Idempotency-Key header",
                            "value": IDEMPOTENCY_KEY_REQUIRED_ERROR_EXAMPLE,
                        },
                    }
                }
            },
        },
        status.HTTP_409_CONFLICT: {
            "model": ApiErrorResponse,
            "description": "Idempotency key was reused with different payload.",
            "content": {
                "application/json": {
                    "examples": {
                        "idempotency_conflict": {
                            "summary": "Idempotency key conflict",
                            "value": IDEMPOTENCY_KEY_CONFLICT_ERROR_EXAMPLE,
                        }
                    }
                }
            },
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": ValidationErrorResponse,
            "description": (
                "Request validation error (for example invalid timezone like `Europe/Mscow`)."
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "missing_system_user_id": {
                            "summary": "Missing required field",
                            "value": USER_CREATE_REQUIRED_FIELD_ERROR_EXAMPLE,
                        },
                        "invalid_timezone": {
                            "summary": "Invalid timezone name",
                            "value": TIMEZONE_VALIDATION_ERROR_EXAMPLE,
                        },
                    }
                }
            },
        },
        status.HTTP_401_UNAUTHORIZED: {
            "model": ApiErrorResponse,
            "description": "Missing or invalid API key header.",
            "content": {
                "application/json": {
                    "examples": {
                        "auth_required": {
                            "summary": "Auth header required",
                            "value": SECURITY_AUTH_REQUIRED_ERROR_EXAMPLE,
                        }
                    }
                }
            },
        },
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {
            "model": ApiErrorResponse,
            "description": "Request body exceeds configured maximum size.",
            "content": {
                "application/json": {
                    "examples": {
                        "body_too_large": {
                            "summary": "Body size limit exceeded",
                            "value": SECURITY_BODY_TOO_LARGE_ERROR_EXAMPLE,
                        }
                    }
                }
            },
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "model": ApiErrorResponse,
            "description": "Per-client request rate limit exceeded.",
            "content": {
                "application/json": {
                    "examples": {
                        "rate_limit_exceeded": {
                            "summary": "Too many requests",
                            "value": SECURITY_RATE_LIMIT_EXCEEDED_ERROR_EXAMPLE,
                        }
                    }
                }
            },
        },
    },
)
def create_user(
    payload: Annotated[UserCreateRequest, Body(openapi_examples=USER_CREATE_REQUEST_EXAMPLES)],
    session: Annotated[Session, Depends(get_db_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    api_key: Annotated[str | None, Security(api_key_security)] = None,
) -> UserCreateResponse:
    """Create user and return stored record."""
    _ = api_key  # represented in OpenAPI; runtime validation is handled by middleware
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "COMMON_400",
                "key": "IDEMPOTENCY_KEY_REQUIRED",
                "message": "Missing required `Idempotency-Key` header for write operation.",
                "source": "business",
            },
        )

    payload_dump = payload.model_dump(mode="json")
    payload_hash = build_payload_hash(payload_dump)
    idempotency_repository = IdempotencyRepository(session)
    endpoint_path = "/api/v1/user"
    record = idempotency_repository.get(
        endpoint_path=endpoint_path, idempotency_key=idempotency_key
    )
    if record is not None:
        if record.payload_hash != payload_hash:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "COMMON_409",
                    "key": "IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_PAYLOAD",
                    "message": "Idempotency key was already used with another payload.",
                    "source": "business",
                },
            )
        logger.info("create_user_idempotent_replay key=%s", idempotency_key)
        return UserCreateResponse.model_validate(record.response_body)

    logger.info("create_user_requested system_user_id=%s", payload.system_user_id)
    service = UserService(UserRepository(session))
    user = service.create(payload)
    response = UserCreateResponse.model_validate(user)
    idempotency_repository.save(
        endpoint_path=endpoint_path,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        status_code=status.HTTP_201_CREATED,
        response_body=response.model_dump(mode="json"),
    )
    logger.info(
        "create_user_succeeded system_user_id=%s client_uuid=%s",
        user.system_user_id,
        user.client_uuid,
    )
    return response
