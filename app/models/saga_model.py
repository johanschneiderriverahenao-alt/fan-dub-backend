"""
Saga Pydantic models for the sagas domain.

Models:
- `SagaBase`: shared fields
- `SagaCreate`: request model for creating a saga
- `SagaUpdate`: fields allowed to update
- `SagaDB`: DB representation
- `SagaResponse`: response model
"""
# pylint: disable=R0801
from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId


class SagaBase(BaseModel):
    """Shared fields for sagas."""

    saga_name: str = Field(..., description="Name of the saga")
    description: str = Field(..., description="Description of the saga")
    company_id: str = Field(..., description="ID of the parent company")
    image_url: Optional[str] = Field(None, description="URL of the saga image")


class SagaCreate(SagaBase):
    """Request model used when creating a saga."""


class SagaUpdate(BaseModel):
    """Model for update requests. All fields optional."""

    saga_name: Optional[str] = None
    description: Optional[str] = None
    company_id: Optional[str] = None
    image_url: Optional[str] = None
    movies_list: Optional[List[str]] = None


class SagaDB(SagaBase):
    """Internal DB model."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(default_factory=ObjectId, alias="_id")
    movies_list: List[str] = Field(default_factory=list, description="List of movie IDs")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SagaResponse(BaseModel):
    """Response model for Saga."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: str = Field(alias="_id", description="Saga ID")
    saga_name: str
    description: str
    company_id: str
    image_url: Optional[str] = None
    movies_list: List[str]
    timestamp: str

    @classmethod
    def from_mongo(cls, doc: dict) -> "SagaResponse":
        """Transform MongoDB doc into response model."""
        if not doc:
            return None
        doc["_id"] = str(doc["_id"])
        if "timestamp" in doc and isinstance(doc["timestamp"], datetime):
            doc["timestamp"] = doc["timestamp"].isoformat()
        return cls(**doc)
