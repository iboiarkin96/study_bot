"""HTTP handlers for user-related endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserRegisterRequest, UserRegisterResponse
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.post(
    "/register",
    response_model=UserRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register user",
    description=(
        "Creates a new user by `telegram_user_id` or updates existing profile fields. "
        "All input fields are validated via Pydantic schemas."
    ),
)
def register_user(
    payload: UserRegisterRequest,
    session: Annotated[Session, Depends(get_db_session)],
) -> UserRegisterResponse:
    """Register or update user and return stored record."""
    service = UserService(UserRepository(session))
    user = service.register(payload)
    return UserRegisterResponse.model_validate(user)
