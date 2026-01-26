"""
User model for authentication.
"""
# pylint: disable=R0903

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict


class UserBase(BaseModel):
    """Base user model with common fields."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
    )

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)


class UserLogin(BaseModel):
    """User login request model."""

    email: EmailStr
    password: str


class ChangePassword(BaseModel):
    """Model for password change requests using email and current password."""

    email: EmailStr
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=72)


class UserResponse(BaseModel):
    """User response model (without password)."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
    )

    id: str = Field(alias="_id")
    email: EmailStr
    created_at: str


class UserInDB(BaseModel):
    """Internal user model in database."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
    )

    id: Optional[str] = Field(default=None, alias="_id")
    email: EmailStr
    password_hash: str
    created_at: datetime
