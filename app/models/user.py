"""
User model for authentication.
"""
# pylint: disable=R0903

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator


class UserBase(BaseModel):
    """Base user model with common fields.

    Simple validations only: type checks and length constraints.
    Email is normalized to lowercase here.
    """

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
    )

    email: EmailStr = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=72)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v


class UserLogin(BaseModel):
    """User login request model.

    Normalizes email to lowercase.
    """

    email: EmailStr = Field(..., max_length=254)
    password: str

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v


class ChangePassword(BaseModel):
    """Model for password change requests using email and current password."""

    email: EmailStr = Field(..., max_length=254)
    current_password: str = Field(..., min_length=8, max_length=72)
    new_password: str = Field(..., min_length=8, max_length=72)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v


class ChangeEmail(BaseModel):
    """Model for email change requests requiring current password."""

    email: EmailStr = Field(..., max_length=254)
    new_email: EmailStr = Field(..., max_length=254)
    current_password: str = Field(..., min_length=8, max_length=72)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v

    @field_validator("new_email", mode="before")
    @classmethod
    def _normalize_new_email(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v


class VerificationRequest(BaseModel):
    """Model for requesting a verification code."""

    email: EmailStr = Field(..., max_length=254)
    purpose: str = Field(..., pattern="^(registration|password_change)$")

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v


class VerificationConfirm(BaseModel):
    """Model for confirming a verification code."""

    email: EmailStr = Field(..., max_length=254)
    code: str = Field(..., min_length=6, max_length=6, pattern="^[0-9]{6}$")
    purpose: str = Field(..., pattern="^(registration|password_change)$")

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v


class RegisterWithVerification(BaseModel):
    """Model for completing registration after verification."""

    email: EmailStr = Field(..., max_length=254)
    password: str = Field(..., min_length=8, max_length=72)
    verification_token: str = Field(..., min_length=32)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v


class ChangePasswordWithVerification(BaseModel):
    """Model for changing password after verification."""

    email: EmailStr = Field(..., max_length=254)
    new_password: str = Field(..., min_length=8, max_length=72)
    verification_token: str = Field(..., min_length=32)

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, v):
        if isinstance(v, str):
            return v.lower()
        return v


class UserResponse(BaseModel):
    """User response model (without password)."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
    )

    id: str = Field(alias="_id")
    email: EmailStr
    role: str = Field(default="user")
    image_profile_id: Optional[str] = None
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
    role: str = Field(default="user")
    image_profile_id: Optional[str] = None
    created_at: datetime
