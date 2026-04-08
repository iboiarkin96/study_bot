"""HTTP handlers for user-related endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.openapi.examples import (
    TIMEZONE_VALIDATION_ERROR_EXAMPLE,
    USER_CREATE_REQUEST_EXAMPLES,
    USER_CREATE_REQUIRED_FIELD_ERROR_EXAMPLE,
    USER_EXISTS_ERROR_EXAMPLE,
)
from app.repositories.user_repository import UserRepository
from app.schemas.errors import ApiErrorResponse, ValidationErrorResponse
from app.schemas.user import UserCreateRequest, UserCreateResponse
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["User"])


@router.post(
    "",
    response_model=UserCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create user",
    description=("Creates a new user by `system_user_id`. "),
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ApiErrorResponse,
            "description": "User with this `system_user_id` already exists.",
            "content": {
                "application/json": {
                    "examples": {
                        "user_exists": {
                            "summary": "User already exists",
                            "value": USER_EXISTS_ERROR_EXAMPLE,
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
    },
)
def create_user(
    payload: Annotated[UserCreateRequest, Body(openapi_examples=USER_CREATE_REQUEST_EXAMPLES)],
    session: Annotated[Session, Depends(get_db_session)],
) -> UserCreateResponse:
    """Create user and return stored record."""
    logger.info("create_user_requested system_user_id=%s", payload.system_user_id)
    service = UserService(UserRepository(session))
    user = service.create(payload)
    logger.info(
        "create_user_succeeded system_user_id=%s client_uuid=%s",
        user.system_user_id,
        user.client_uuid,
    )
    return UserCreateResponse.model_validate(user)
