"""
Plan/Package models for admin-managed payment plans.

Models:
- `PlanBase` : Base plan model
- `PlanCreate` : Create plan
- `PlanUpdate` : Update plan
- `PlanDB` : DB representation
- `PlanResponse` : Response model
"""
# pylint: disable=R0801
from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class PlanFeature(BaseModel):
    """Individual feature of a plan."""

    title: str = Field(..., description="Feature title")
    description: Optional[str] = Field(None, description="Feature description")
    is_highlighted: bool = Field(default=False, description="Whether feature is highlighted")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class PlanBase(BaseModel):
    """Base model for payment plans."""

    name: str = Field(..., description="Plan name (e.g., 'Starter', 'Pro', 'Ultimate')")
    display_name: Optional[str] = Field(None, description="Display name for frontend")
    description: Optional[str] = Field(None, description="Plan description")
    credits: int = Field(..., description="Number of credits in the plan", ge=1)
    price_usd: float = Field(..., description="Price in USD", ge=0)
    stripe_price_id: Optional[str] = Field(None, description="Stripe Price ID")
    features: List[PlanFeature] = Field(default_factory=list, description="Plan features")
    is_active: bool = Field(default=True, description="Whether plan is available for purchase")
    is_featured: bool = Field(default=False, description="Whether plan is featured/highlighted")
    sort_order: int = Field(default=0, description="Display order (lower = first)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict,
                                               description="Additional metadata")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class PlanCreate(PlanBase):
    """Model for creating a plan."""


class PlanUpdate(BaseModel):
    """Model for updating a plan."""

    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    credits: Optional[int] = Field(None, ge=1)
    price_usd: Optional[float] = Field(None, ge=0)
    stripe_price_id: Optional[str] = None
    features: Optional[List[PlanFeature]] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None
    sort_order: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class PlanDB(PlanBase):
    """Database representation of a plan."""

    id: str = Field(default="", alias="_id", description="MongoDB document ID")
    created_at: datetime = Field(default_factory=datetime.utcnow,
                                 description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow,
                                 description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="User ID who created the plan")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class PlanResponse(BaseModel):
    """Response model for plans."""

    id: str = Field(..., alias="_id", description="MongoDB document ID")
    name: str
    display_name: str
    description: Optional[str] = None
    credits: int
    price_usd: float
    stripe_price_id: Optional[str] = None
    features: List[PlanFeature]
    is_active: bool
    is_featured: bool
    sort_order: int
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )
