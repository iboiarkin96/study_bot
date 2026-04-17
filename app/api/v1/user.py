"""HTTP handlers for user-related endpoints."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Path, Security, status
from fastapi.security.api_key import APIKeyHeader
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.core.idempotency import build_payload_hash
from app.errors.common import COMMON_400, COMMON_409
from app.openapi.examples import (
    USER_CREATE_REQUEST_EXAMPLES,
    USER_CREATE_VALIDATION_ERROR_EXAMPLES,
    USER_EXISTS_ERROR_EXAMPLE,
    USER_NOT_FOUND_ERROR_EXAMPLE,
)
from app.openapi.examples.errors import (
    USER_PATCH_BODY_EMPTY_EXAMPLE,
    USER_PATCH_VALIDATION_ERROR_EXAMPLES,
    USER_UPDATE_VALIDATION_ERROR_EXAMPLES,
)
from app.openapi.examples.users import USER_PATCH_REQUEST_EXAMPLES, USER_UPDATE_REQUEST_EXAMPLES
from app.openapi.responses import (
    COMMON_BODY_TOO_LARGE_413_RESPONSE,
    COMMON_IDEMPOTENCY_CONFLICT_409_RESPONSE,
    build_common_business_400_response,
    common_protected_route_responses,
)
from app.repositories.idempotency_repository import IdempotencyRepository
from app.repositories.user_repository import UserRepository
from app.schemas.errors import ApiErrorResponse, ValidationErrorResponse
from app.schemas.user import (
    UserCreateRequest,
    UserCreateResponse,
    UserPatchRequest,
    UserUpdateRequest,
)
from app.services.user_service import UserService

logger = logging.getLogger(__name__)
api_key_security = APIKeyHeader(name="X-API-Key", auto_error=False)

router = APIRouter(prefix="/user", tags=["User"])

# Public path for this router: in main, include_router(..., prefix="/api/v1").
# Use in clients and load tests to avoid duplicating the "/api/v1/user" string.
USER_HTTP_BASE_PATH = "/api/v1/user"


@router.post(
    "",
    response_model=UserCreateResponse,
    status_code=status.HTTP_201_CREATED,
    operation_id="createUser",
    summary="Create user",
    description=(
        "Creates a new user; uniqueness is `(system_user_id, system_uuid)`. "
        "Requires `Idempotency-Key` header for safe retry semantics.\n\n"
        "### Example request (curl)\n"
        "```bash\n"
        "curl -X POST 'http://127.0.0.1:8000/api/v1/user' \\\n"
        "  -H 'accept: application/json' \\\n"
        "  -H 'Content-Type: application/json' \\\n"
        "  -H 'X-API-Key: ....' \\\n"
        "  -H 'Idempotency-Key: create-user-sample-1' \\\n"
        '  -d \'{"system_user_id":"2","system_uuid":"b2c3d4e5-0002-4000-8000-000000000002",'
        '"full_name":"Ivan Petrov"}\'\n'
        "```\n"
    ),
    responses={
        status.HTTP_201_CREATED: {
            "description": "User created successfully.",
        },
        status.HTTP_400_BAD_REQUEST: build_common_business_400_response(
            extra_examples={
                "user_exists": {
                    "summary": "User already exists",
                    "value": USER_EXISTS_ERROR_EXAMPLE,
                }
            }
        ),
        status.HTTP_409_CONFLICT: COMMON_IDEMPOTENCY_CONFLICT_409_RESPONSE,
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": ValidationErrorResponse,
            "description": "Request validation errors for all supported user create field rules.",
            "content": {"application/json": {"examples": USER_CREATE_VALIDATION_ERROR_EXAMPLES}},
        },
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: COMMON_BODY_TOO_LARGE_413_RESPONSE,
        **common_protected_route_responses(),
    },
)
def create_user(
    payload: Annotated[UserCreateRequest, Body(openapi_examples=USER_CREATE_REQUEST_EXAMPLES)],
    session: Annotated[Session, Depends(get_db_session)],
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=128,
            pattern=r"^[ -~]+$",
            description=(
                "Required idempotency key for write deduplication. "
                "Use printable ASCII only (no Cyrillic/Unicode)."
            ),
        ),
    ],
    api_key: Annotated[str | None, Security(api_key_security)] = None,
) -> UserCreateResponse:
    """Handle POST ``/api/v1/user`` with idempotent replay semantics.

    Args:
        payload: Validated JSON body.
        session: Database session from :func:`app.core.database.get_db_session`.
        idempotency_key: Dedup token from ``Idempotency-Key`` header.
        api_key: Declared for OpenAPI; auth is enforced by middleware.

    Returns:
        Created user payload, or replayed body from a prior successful call.

    Raises:
        fastapi.HTTPException: 400 if idempotency header is missing, 409 on key/body mismatch.
    """
    _ = api_key  # represented in OpenAPI; runtime validation is handled by middleware
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail=COMMON_400.as_detail("business"),
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
                detail=COMMON_409.as_detail("business"),
            )
        logger.info("create_user_idempotent_replay key=%s", idempotency_key)
        return UserCreateResponse.model_validate(record.response_body)

    logger.info(
        "create_user_requested system_user_id=%s system_uuid=%s",
        payload.system_user_id,
        payload.system_uuid,
    )
    service = UserService(UserRepository(session))
    user = service.create(payload)
    response_model = UserCreateResponse.model_validate(user)
    idempotency_repository.save(
        endpoint_path=endpoint_path,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        status_code=status.HTTP_201_CREATED,
        response_body=response_model.model_dump(mode="json"),
    )
    logger.info(
        "create_user_succeeded system_user_id=%s client_uuid=%s",
        user.system_user_id,
        user.client_uuid,
    )
    return response_model


@router.get(
    "/{system_uuid}/{system_user_id}",
    response_model=UserCreateResponse,
    operation_id="getUserBySystemUserId",
    summary="Get user by system_uuid and system_user_id",
    description=(
        "Returns user profile by composite key `(system_uuid, system_user_id)`.\n\n"
        "### Example request (curl)\n"
        "```bash\n"
        "curl -X GET 'http://127.0.0.1:8000/api/v1/user/b2c3d4e5-0002-4000-8000-000000000002/2' \\\n"
        "  -H 'accept: application/json' \\\n"
        "  -H 'X-API-Key: ....'\n"
        "```\n"
    ),
    responses={
        status.HTTP_404_NOT_FOUND: {
            "model": ApiErrorResponse,
            "description": "User not found.",
            "content": {
                "application/json": {
                    "examples": {
                        "user_not_found": {
                            "summary": "No user with given system_user_id",
                            "value": USER_NOT_FOUND_ERROR_EXAMPLE,
                        }
                    }
                }
            },
        },
        **common_protected_route_responses(),
    },
)
def get_user(
    system_uuid: Annotated[UUID, Path(description="Source system UUID (`systems.system_uuid`).")],
    system_user_id: Annotated[str, Path(min_length=1, max_length=36)],
    session: Annotated[Session, Depends(get_db_session)],
    api_key: Annotated[str | None, Security(api_key_security)] = None,
) -> UserCreateResponse:
    """Return a user by path parameters ``system_uuid`` and ``system_user_id``.

    Args:
        system_uuid: Source system UUID from the path.
        system_user_id: External user id from the path.
        session: Database session.
        api_key: Declared for OpenAPI; auth is enforced by middleware.

    Returns:
        User payload with HTTP 200.

    Raises:
        fastapi.HTTPException: 404 when no user matches the composite key.
    """
    _ = api_key  # represented in OpenAPI; runtime validation is handled by middleware
    service = UserService(UserRepository(session))
    user = service.get_or_404(
        system_user_id=system_user_id,
        system_uuid=str(system_uuid),
    )
    return UserCreateResponse.model_validate(user)


@router.put(
    "/{system_uuid}/{system_user_id}",
    response_model=UserCreateResponse,
    operation_id="updateUserBySystemUserId",
    summary="Update user by system_uuid and system_user_id",
    description=(
        "Updates mutable profile fields for an existing user. "
        "Requires `Idempotency-Key` for safe retry semantics.\n\n"
        "### Example request (curl)\n"
        "```bash\n"
        "curl -X PUT 'http://127.0.0.1:8000/api/v1/user/b2c3d4e5-0002-4000-8000-000000000002/2' \\\n"
        "  -H 'accept: application/json' \\\n"
        "  -H 'Content-Type: application/json' \\\n"
        "  -H 'X-API-Key: ....' \\\n"
        "  -H 'Idempotency-Key: update-user-sample-1' \\\n"
        '  -d \'{"full_name":"Ivan Petrov","timezone":"Europe/Moscow","is_row_invalid":0}\'\n'
        "```\n"
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "User updated successfully.",
        },
        status.HTTP_404_NOT_FOUND: {
            "model": ApiErrorResponse,
            "description": "User not found.",
            "content": {
                "application/json": {
                    "examples": {
                        "user_not_found": {
                            "summary": "No user with given system_user_id",
                            "value": USER_NOT_FOUND_ERROR_EXAMPLE,
                        }
                    }
                }
            },
        },
        status.HTTP_409_CONFLICT: COMMON_IDEMPOTENCY_CONFLICT_409_RESPONSE,
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": ValidationErrorResponse,
            "description": "Request validation errors for user update body rules.",
            "content": {"application/json": {"examples": USER_UPDATE_VALIDATION_ERROR_EXAMPLES}},
        },
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: COMMON_BODY_TOO_LARGE_413_RESPONSE,
        **common_protected_route_responses(),
    },
)
def update_user(
    system_uuid: Annotated[UUID, Path(description="Source system UUID (`systems.system_uuid`).")],
    system_user_id: Annotated[str, Path(min_length=1, max_length=36)],
    payload: Annotated[UserUpdateRequest, Body(openapi_examples=USER_UPDATE_REQUEST_EXAMPLES)],
    session: Annotated[Session, Depends(get_db_session)],
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=128,
            pattern=r"^[ -~]+$",
            description=(
                "Required idempotency key for write deduplication. "
                "Use printable ASCII only (no Cyrillic/Unicode)."
            ),
        ),
    ],
    api_key: Annotated[str | None, Security(api_key_security)] = None,
) -> UserCreateResponse:
    """Handle PUT with idempotent replay semantics (same pattern as :func:`create_user`).

    Args:
        system_uuid: Source system UUID from the path.
        system_user_id: External user id from the path.
        payload: Full replacement body for mutable fields.
        session: Database session.
        idempotency_key: Dedup token from ``Idempotency-Key``.
        api_key: Declared for OpenAPI; auth is enforced by middleware.

    Returns:
        Updated user, or replayed JSON from a prior successful call with the same key.

    Raises:
        fastapi.HTTPException: 400 if idempotency header is missing, 409 on key/body mismatch, 404 if user missing.
    """
    _ = api_key
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail=COMMON_400.as_detail("business"),
        )

    payload_dump = payload.model_dump(mode="json")
    payload_hash = build_payload_hash(payload_dump)
    idempotency_repository = IdempotencyRepository(session)
    su_str = str(system_uuid)
    endpoint_path = f"/api/v1/user/{su_str}/{system_user_id}"
    record = idempotency_repository.get(
        endpoint_path=endpoint_path, idempotency_key=idempotency_key
    )
    if record is not None:
        if record.payload_hash != payload_hash:
            raise HTTPException(
                status_code=409,
                detail=COMMON_409.as_detail("business"),
            )
        logger.info("update_user_idempotent_replay key=%s", idempotency_key)
        return UserCreateResponse.model_validate(record.response_body)

    logger.info(
        "update_user_requested system_user_id=%s system_uuid=%s",
        system_user_id,
        su_str,
    )
    service = UserService(UserRepository(session))
    user = service.update(
        system_user_id=system_user_id,
        system_uuid=su_str,
        payload=payload,
    )
    response_model = UserCreateResponse.model_validate(user)
    idempotency_repository.save(
        endpoint_path=endpoint_path,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        status_code=status.HTTP_200_OK,
        response_body=response_model.model_dump(mode="json"),
    )
    return response_model


@router.patch(
    "/{system_uuid}/{system_user_id}",
    response_model=UserCreateResponse,
    operation_id="patchUserBySystemUserId",
    summary="Partially update user by system_uuid and system_user_id",
    description=(
        "Updates only the fields present in the JSON body; omitted fields stay unchanged. "
        "Requires `Idempotency-Key`. Use `PUT` for a full replacement of mutable fields.\n\n"
        "### Example request (curl)\n"
        "```bash\n"
        "curl -X PATCH 'http://127.0.0.1:8000/api/v1/user/b2c3d4e5-0002-4000-8000-000000000002/2' \\\n"
        "  -H 'accept: application/json' \\\n"
        "  -H 'Content-Type: application/json' \\\n"
        "  -H 'X-API-Key: ....' \\\n"
        "  -H 'Idempotency-Key: patch-user-sample-1' \\\n"
        '  -d \'{"full_name":"Maria Petrova"}\'\n'
        "```\n"
    ),
    responses={
        status.HTTP_200_OK: {
            "description": "User updated successfully.",
        },
        status.HTTP_400_BAD_REQUEST: build_common_business_400_response(
            extra_examples={
                "patch_body_empty": {
                    "summary": "No fields to patch",
                    "value": USER_PATCH_BODY_EMPTY_EXAMPLE,
                },
            }
        ),
        status.HTTP_404_NOT_FOUND: {
            "model": ApiErrorResponse,
            "description": "User not found.",
            "content": {
                "application/json": {
                    "examples": {
                        "user_not_found": {
                            "summary": "No user with given system_user_id",
                            "value": USER_NOT_FOUND_ERROR_EXAMPLE,
                        }
                    }
                }
            },
        },
        status.HTTP_409_CONFLICT: COMMON_IDEMPOTENCY_CONFLICT_409_RESPONSE,
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "model": ValidationErrorResponse,
            "description": "Request validation errors for user patch body rules.",
            "content": {"application/json": {"examples": USER_PATCH_VALIDATION_ERROR_EXAMPLES}},
        },
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: COMMON_BODY_TOO_LARGE_413_RESPONSE,
        **common_protected_route_responses(),
    },
)
def patch_user(
    system_uuid: Annotated[UUID, Path(description="Source system UUID (`systems.system_uuid`).")],
    system_user_id: Annotated[str, Path(min_length=1, max_length=36)],
    payload: Annotated[UserPatchRequest, Body(openapi_examples=USER_PATCH_REQUEST_EXAMPLES)],
    session: Annotated[Session, Depends(get_db_session)],
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=128,
            pattern=r"^[ -~]+$",
            description=(
                "Required idempotency key for write deduplication. "
                "Use printable ASCII only (no Cyrillic/Unicode)."
            ),
        ),
    ],
    api_key: Annotated[str | None, Security(api_key_security)] = None,
) -> UserCreateResponse:
    """Handle PATCH with idempotent replay semantics; partial field updates only.

    Args:
        system_uuid: Source system UUID from the path.
        system_user_id: External user id from the path.
        payload: Partial body; unset fields remain unchanged.
        session: Database session.
        idempotency_key: Dedup token from ``Idempotency-Key``.
        api_key: Declared for OpenAPI; auth is enforced by middleware.

    Returns:
        Updated user, or replayed JSON from a prior successful call with the same key.

    Raises:
        fastapi.HTTPException: 400 if idempotency header is missing or body is empty, 409 on conflict, 404 if user missing.
    """
    _ = api_key
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail=COMMON_400.as_detail("business"),
        )

    payload_dump = payload.model_dump(mode="json", exclude_unset=True)
    payload_hash = build_payload_hash(payload_dump)
    idempotency_repository = IdempotencyRepository(session)
    su_str = str(system_uuid)
    endpoint_path = f"PATCH {USER_HTTP_BASE_PATH}/{su_str}/{system_user_id}"
    record = idempotency_repository.get(
        endpoint_path=endpoint_path, idempotency_key=idempotency_key
    )
    if record is not None:
        if record.payload_hash != payload_hash:
            raise HTTPException(
                status_code=409,
                detail=COMMON_409.as_detail("business"),
            )
        logger.info("patch_user_idempotent_replay key=%s", idempotency_key)
        return UserCreateResponse.model_validate(record.response_body)

    logger.info(
        "patch_user_requested system_user_id=%s system_uuid=%s",
        system_user_id,
        su_str,
    )
    service = UserService(UserRepository(session))
    user = service.patch(
        system_user_id=system_user_id,
        system_uuid=su_str,
        payload=payload,
    )
    response_model = UserCreateResponse.model_validate(user)
    idempotency_repository.save(
        endpoint_path=endpoint_path,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        status_code=status.HTTP_200_OK,
        response_body=response_model.model_dump(mode="json"),
    )
    return response_model
