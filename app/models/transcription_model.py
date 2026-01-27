"""
Transcription Pydantic models (Pydantic v2) for the transcriptions domain.

Models:
- `TranscriptionBase` : shared fields
- `TranscriptionCreate` : request model (without _id, timestamp)
- `TranscriptionUpdate` : fields allowed to update
- `TranscriptionDB` : DB representation (id alias for _id)
- `TranscriptionResponse` : response model (serializes dates)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId


class TranscriptionBase(BaseModel):
    """Shared fields for transcriptions."""

    movie_name: str = Field(..., description="Name of the movie")
    transcription: str = Field(..., description="Transcribed text")
    duration: float = Field(..., description="Duration in seconds")


class TranscriptionCreate(BaseModel):
    """Request model used when creating a transcription.

    Note: audio file is uploaded via multipart form; this model documents
    the non-file fields expected alongside the upload.
    """

    movie_name: str = Field(...)
    duration: float = Field(...)


class TranscriptionUpdate(BaseModel):
    """Model for update requests. All fields optional."""

    movie_name: Optional[str] = None
    transcription: Optional[str] = None
    duration: Optional[float] = None


class TranscriptionDB(TranscriptionBase):
    """Internal DB model. Uses `id` alias for MongoDB `_id`."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: Optional[ObjectId] = Field(None, alias="_id")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class TranscriptionResponse(BaseModel):
    """Response model returned by API endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="_id", description="Transcription id")
    movie_name: str
    transcription: str
    duration: float
    timestamp: str
    updated_at: Optional[str] = None

    @classmethod
    def from_db(cls, data: Dict[str, Any]) -> "TranscriptionResponse":
        """Build a `TranscriptionResponse` from a MongoDB document dictionary.

        Args:
            data: The raw document returned from the database.

        Returns:
            A populated `TranscriptionResponse` instance with stringified id and
            ISO-formatted timestamps.
        """
        return cls(
            _id=str(data.get("_id")),
            movie_name=data.get("movie_name"),
            transcription=data.get("transcription"),
            duration=float(data.get("duration")),
            timestamp=(data.get("timestamp") or datetime.utcnow()).isoformat(),
            updated_at=(data.get("updated_at").isoformat() if data.get("updated_at") else None),
        )
