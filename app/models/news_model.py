"""
News Pydantic models for carousel/news items.

Models:
- `NewsBase`: shared fields
- `NewsCreate`: request model for creating a news item
- `NewsUpdate`: request model for partial updates
- `NewsDB`: DB representation
- `NewsResponse`: response model
"""
# pylint: disable=R0801
from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId


class NewsBase(BaseModel):
    """Shared fields for news/carousel items."""

    title: str = Field(..., description="Short title displayed in the carousel")
    description: str = Field(..., description="Short description text")
    image_url: str = Field(..., description="URL of the main image")
    link: str = Field(..., description="Redirection URL when item is clicked")
    label: Literal["popular", "novedad", "trending"] = Field(
        ..., description="Label for the carousel item"
    )


class NewsCreate(NewsBase):
    """Request model used when creating a news item."""


class NewsUpdate(BaseModel):
    """Model for update requests. All fields optional."""

    title: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    link: Optional[str] = None
    label: Optional[Literal["popular", "novedad", "trending"]]


class NewsDB(NewsBase):
    """Internal DB model."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(default_factory=ObjectId, alias="_id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class NewsResponse(BaseModel):
    """Response model for news items."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: str = Field(alias="_id", description="News item ID")
    title: str
    description: str
    image_url: str
    link: str
    label: Literal["popular", "novedad", "trending"]
    timestamp: str

    @classmethod
    def from_mongo(cls, doc: dict) -> "NewsResponse":
        """Transform MongoDB doc into response model."""
        if not doc:
            return None
        doc["_id"] = str(doc["_id"])
        if "timestamp" in doc and isinstance(doc["timestamp"], datetime):
            doc["timestamp"] = doc["timestamp"].isoformat()
        return cls(**doc)
