"""
Movie Pydantic models for the movies domain.

Models:
- `MovieBase`: shared fields
- `MovieCreate`: request model for creating a movie
- `MovieUpdate`: fields allowed to update
- `MovieDB`: DB representation
- `MovieResponse`: response model
"""
# pylint: disable=R0801
from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId


class MovieBase(BaseModel):
    """Shared fields for movies."""

    movie_name: str = Field(..., description="Name of the movie")
    description: str = Field(..., description="Description of the movie")
    saga_id: str = Field(..., description="ID of the parent saga")
    characters_available: List[str] = Field(default_factory=list,
                                            description="Available characters")
    image_url: Optional[str] = Field(None, description="URL of the movie image")


class MovieCreate(MovieBase):
    """Request model used when creating a movie."""


class MovieUpdate(BaseModel):
    """Model for update requests. All fields optional."""

    movie_name: Optional[str] = None
    description: Optional[str] = None
    saga_id: Optional[str] = None
    characters_available: Optional[List[str]] = None
    image_url: Optional[str] = None


class MovieDB(MovieBase):
    """Internal DB model."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(default_factory=ObjectId, alias="_id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MovieResponse(BaseModel):
    """Response model for Movie."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: str = Field(alias="_id", description="Movie ID")
    movie_name: str
    description: str
    saga_id: str
    characters_available: List[str]
    image_url: Optional[str] = None
    timestamp: str

    @classmethod
    def from_mongo(cls, doc: dict) -> "MovieResponse":
        """Transform MongoDB doc into response model."""
        if not doc:
            return None
        doc["_id"] = str(doc["_id"])
        if "timestamp" in doc and isinstance(doc["timestamp"], datetime):
            doc["timestamp"] = doc["timestamp"].isoformat()
        return cls(**doc)
