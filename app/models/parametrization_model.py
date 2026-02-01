"""
Parametrization models for system configuration.

Models:
- `ParametrizationBase` : Base configuration model
- `ParametrizationCreate` : Create configuration
- `ParametrizationUpdate` : Update configuration
- `ParametrizationDB` : DB representation
- `ParametrizationResponse` : Response model
"""
# pylint: disable=R0801
from __future__ import annotations

from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict


class ParametrizationBase(BaseModel):
    """Base model for system parametrization."""

    type: str = Field(..., description="Type identifier (e.g., 'credits_config', 'ads_config')")
    name: Optional[str] = Field(None, description="Human-readable name")
    description: Optional[str] = Field(None, description="Configuration description")
    config: Dict[str, Any] = Field(..., description="Configuration values")
    is_active: bool = Field(default=True, description="Whether this config is active")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class ParametrizationCreate(ParametrizationBase):
    """Model for creating parametrization."""


class ParametrizationUpdate(BaseModel):
    """Model for updating parametrization."""

    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class ParametrizationDB(ParametrizationBase):
    """Database representation of parametrization."""

    id: str = Field(default="", alias="_id", description="MongoDB document ID")
    created_at: datetime = Field(default_factory=datetime.utcnow,
                                 description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow,
                                 description="Last update timestamp")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class ParametrizationResponse(BaseModel):
    """Response model for parametrization."""

    id: str = Field(..., alias="_id", description="MongoDB document ID")
    type: str
    name: str
    description: Optional[str] = None
    config: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )
