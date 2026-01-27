"""
Transcription data models for storing audio transcriptions.

Defines Pydantic models compatible with project conventions.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId


class TranscriptionBase(BaseModel):
    """Base fields for transcription input and storage."""

    movie_name: str = Field(..., description="Name of the movie")
    transcription: str = Field(..., description="Generated transcription text")
    duration: float = Field(..., description="Duration in seconds")


class Transcription(TranscriptionBase):
    """Internal model used when writing to MongoDB."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)
    id: Optional[ObjectId] = Field(None, alias="_id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(None)


class TranscriptionResponse(BaseModel):
    """Response model returned by the API."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="id", description="Transcription id")
    movie_name: str
    transcription: str
    duration: float
    timestamp: str
    updated_at: Optional[str] = None

    @classmethod
    def from_db(cls, data: Dict[str, Any]):
        return cls(
            id=str(data.get("_id")),
            movie_name=data.get("movie_name"),
            transcription=data.get("transcription"),
            duration=float(data.get("duration")),
            timestamp=(data.get("timestamp") or datetime.utcnow()).isoformat(),
            updated_at=(data.get("updated_at").isoformat() if data.get("updated_at") else None)
        )
