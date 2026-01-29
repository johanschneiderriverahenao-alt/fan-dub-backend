"""
Pydantic models for clip_scene entity.
Handles data validation and serialization for scene clips.
"""
# pylint: disable=R0801
from datetime import datetime
from typing import List, Optional

from bson import ObjectId
from pydantic import BaseModel, Field, ConfigDict


class ClipSceneBase(BaseModel):
    """Base model with common fields."""

    scene_name: str = Field(..., description="Name of the scene")
    description: str = Field(..., description="Description of the scene")
    movie_id: str = Field(..., description="ID of the movie this scene belongs to")
    characters: List[str] = Field(default_factory=list,
                                  description="List of characters in the scene")
    image_url: Optional[str] = Field(None, description="URL of the scene thumbnail image")
    video_url: Optional[str] = Field(None, description="URL of the scene video")
    transcription: Optional[str] = Field(None, description="Transcription of the scene dialogue")


class ClipSceneCreate(ClipSceneBase):
    """Request model used when creating a clip scene."""


class ClipSceneUpdate(BaseModel):
    """Model for update requests. All fields optional."""

    scene_name: Optional[str] = None
    description: Optional[str] = None
    movie_id: Optional[str] = None
    characters: Optional[List[str]] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    transcription: Optional[str] = None


class ClipSceneDB(ClipSceneBase):
    """Internal DB model."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(default_factory=ObjectId, alias="_id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ClipSceneResponse(BaseModel):
    """Response model for ClipScene."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: str = Field(alias="_id", description="ClipScene ID")
    scene_name: str
    description: str
    movie_id: str
    characters: List[str]
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    transcription: Optional[str] = None
    timestamp: str

    @classmethod
    def from_mongo(cls, doc: dict) -> "ClipSceneResponse":
        """Transform MongoDB doc into response model."""
        if not doc:
            return None
        doc["_id"] = str(doc["_id"])
        if "timestamp" in doc and isinstance(doc["timestamp"], datetime):
            doc["timestamp"] = doc["timestamp"].isoformat()
        return cls(**doc)
