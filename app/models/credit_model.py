"""
Credit and Usage Limit models for user dubbing limitations.

Models:
- `UserCredits` : User credits and daily limits tracking
- `UserCreditsDB` : DB representation
- `UserCreditsResponse` : Response model
- `DailyUsage` : Daily dubbing usage tracking
- `AdWatchRecord` : Ad watch tracking
"""
# pylint: disable=R0801
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class DailyUsage(BaseModel):
    """Daily dubbing usage tracking."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    free_dubbings_used: int = Field(default=0, description="Number of free dubbings used today")
    credits_used: int = Field(default=0, description="Number of credits used today")
    ads_watched: int = Field(default=0, description="Number of ads watched today")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class AdWatchRecord(BaseModel):
    """Record of an ad watch."""

    watched_at: datetime = Field(default_factory=datetime.utcnow,
                                 description="When the ad was watched")
    ad_provider: str = Field(default="", description="Ad provider name")
    dubbing_granted: bool = Field(default=True, description="Whether a dubbing was granted")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class UserCreditsBase(BaseModel):
    """Base model for user credits and limits."""

    user_id: str = Field(..., description="ID of the user")
    paid_credits: int = Field(default=0, description="Purchased credits (never expire)")
    daily_free_limit: int = Field(default=3, description="Daily free dubbing limit")
    daily_ad_limit: int = Field(default=3, description="Daily ad watch limit")
    current_daily_usage: Optional[DailyUsage] = Field(default=None, description="Current day usage")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class UserCreditsCreate(UserCreditsBase):
    """Model for creating user credits record."""
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class UserCreditsUpdate(BaseModel):
    """Model for updating user credits."""

    paid_credits: Optional[int] = None
    daily_free_limit: Optional[int] = None
    daily_ad_limit: Optional[int] = None
    current_daily_usage: Optional[DailyUsage] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class UserCreditsDB(UserCreditsBase):
    """Database representation of user credits."""

    id: str = Field(default="", alias="_id", description="MongoDB document ID")
    created_at: datetime = Field(default_factory=datetime.utcnow,
                                 description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow,
                                 description="Last update timestamp")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class UserCreditsResponse(BaseModel):
    """Response model for user credits."""

    id: str = Field(..., alias="_id", description="MongoDB document ID")
    user_id: str
    paid_credits: int
    daily_free_limit: int
    daily_ad_limit: int
    current_daily_usage: Optional[DailyUsage] = None
    available_free_dubbings: int = Field(..., description="Remaining free dubbings today")
    available_ad_dubbings: int = Field(..., description="Remaining ad-based dubbings today")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class CreditPackage(BaseModel):
    """Credit package for purchase."""

    name: str = Field(..., description="Package name (e.g., 'Starter', 'Pro', 'Ultimate')")
    credits: int = Field(..., description="Number of credits in the package")
    price_usd: float = Field(..., description="Price in USD")
    price_id: str = Field(..., description="Stripe Price ID")
    description: Optional[str] = Field(None, description="Package description")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )
