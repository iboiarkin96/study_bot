"""HTTP handlers for user-related endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.openapi.examples import (
    REGISTER_REQUIRED_FIELD_ERROR_EXAMPLE,
    TIMEZONE_VALIDATION_ERROR_EXAMPLE,
    USER_EXISTS_ERROR_EXAMPLE,
    USER_REGISTER_REQUEST_EXAMPLES,
)
from app.repositories.user_repository import UserRepository
from app.schemas.errors import ApiErrorResponse, ValidationErrorResponse
from app.schemas.user import UserRegisterRequest, UserRegisterResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])

@router.post(
    "/register",
    response_model=UserRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register user",
    description=(
        "Creates a new user by `system_user_id`. "
        "Timezone is validated against IANA timezone names via `zoneinfo`. "
        "Validation and business errors are returned with stable codes."
    ),
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
                            "value": REGISTER_REQUIRED_FIELD_ERROR_EXAMPLE,
                        },
                        "invalid_timezone": {
                            "summary": "Invalid timezone name",
                            "value": TIMEZONE_VALIDATION_ERROR_EXAMPLE,
                        }
                    }
                }
            },
        },
    },
)
def register_user(
    payload: Annotated[UserRegisterRequest, Body(openapi_examples=USER_REGISTER_REQUEST_EXAMPLES)],
    session: Annotated[Session, Depends(get_db_session)],
) -> UserRegisterResponse:
    """Register user and return stored record."""
    service = UserService(UserRepository(session))
    user = service.register(payload)
    return UserRegisterResponse.model_validate(user)
