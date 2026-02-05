"""
Transcription Pydantic models (Pydantic v2) for the transcriptions domain.

Models:
- `Dialogue` : individual dialogue within a character
- `CharacterDialogues` : character with their dialogues
- `TranscriptionBase` : shared fields
- `TranscriptionCreate` : request model (without _id, timestamp)
- `TranscriptionUpdate` : fields allowed to update
- `TranscriptionDB` : DB representation (id alias for _id)
- `TranscriptionResponse` : response model (serializes dates)
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId


class Dialogue(BaseModel):
    """Individual dialogue model with timestamps (no audio URL needed)."""

    dialogue_id: str = Field(..., description="Unique identifier for the dialogue")
    text: str = Field(..., description="Dialogue text")
    start_time: float = Field(..., description="Start time in seconds")
    end_time: float = Field(..., description="End time in seconds")


class CharacterDialogues(BaseModel):
    """Character with their associated dialogues."""

    character_name: str = Field(..., description="Name of the character")
    character_id: str = Field(..., description="Unique identifier for the character")
    dialogues: List[Dialogue] = Field(default_factory=list, description="List of dialogues")


class TranscriptionBase(BaseModel):
    """Shared fields for transcriptions."""

    movie_id: str = Field(..., description="ID of the associated movie")
    clip_scene_id: str = Field(..., description="ID of the associated clip/scene")
    video_url: Optional[str] = Field(None, description="URL of the original video")
    background_audio_url: Optional[str] = Field(None,
                                                description="URL of the background audio")
    voices_audio_url: Optional[str] = Field(None,
                                            description="URL of the voices audio (all characters)")
    characters: List[CharacterDialogues] = Field(default_factory=list,
                                                 description="List of characters with dialogues")
    duration: float = Field(..., description="Duration in seconds")
    status: str = Field(default="pending",
                        description="Status: pending, processing, completed, error")


class TranscriptionCreate(BaseModel):
    """Request model used when creating a transcription.

    Note: audio file is uploaded via multipart form; this model documents
    the non-file fields expected alongside the upload.
    """

    movie_id: str = Field(...)
    clip_scene_id: str = Field(...)
    duration: float = Field(...)


class TranscriptionUpdate(BaseModel):
    """Model for update requests. All fields optional."""

    movie_id: Optional[str] = None
    clip_scene_id: Optional[str] = None
    background_audio_url: Optional[str] = None
    voices_audio_url: Optional[str] = None
    characters: Optional[List[CharacterDialogues]] = None
    duration: Optional[float] = None
    status: Optional[str] = None


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
    movie_id: str
    clip_scene_id: str
    background_audio_url: Optional[str] = None
    voices_audio_url: Optional[str] = None
    characters: List[CharacterDialogues] = Field(default_factory=list)
    duration: float
    status: str
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
            movie_id=data.get("movie_id"),
            clip_scene_id=data.get("clip_scene_id"),
            background_audio_url=data.get("background_audio_url"),
            voices_audio_url=data.get("voices_audio_url"),
            characters=data.get("characters", []),
            duration=float(data.get("duration")),
            status=data.get("status", "pending"),
            timestamp=(data.get("timestamp") or datetime.utcnow()).isoformat(),
            updated_at=(data.get("updated_at").isoformat() if data.get("updated_at") else None),
        )
