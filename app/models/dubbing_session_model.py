"""
Dubbing Session Pydantic models for user dubbing sessions.

Models:
- `DialogueRecorded` : individual recorded dialogue
- `DubbingSessionBase` : shared fields
- `DubbingSessionCreate` : request model
- `DubbingSessionUpdate` : fields allowed to update
- `DubbingSessionDB` : DB representation
- `DubbingSessionResponse` : response model
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId


class DialogueRecorded(BaseModel):
    """Individual recorded dialogue by user."""

    dialogue_id: str = Field(..., description="ID of the dialogue from transcription")
    audio_url: str = Field(..., description="URL of the user's recorded audio")
    duration: float = Field(..., description="Duration of the recording in seconds")
    uploaded_at: str = Field(..., description="Upload timestamp in ISO format")


class DubbingSessionBase(BaseModel):
    """Shared fields for dubbing sessions."""

    user_id: str = Field(..., description="ID of the user doing the dubbing")
    transcription_id: str = Field(..., description="ID of the transcription being dubbed")
    clip_scene_id: str = Field(..., description="ID of the clip/scene")
    character_id: str = Field(..., description="ID of the character being dubbed")
    character_name: str = Field(..., description="Name of the character")
    dialogues_recorded: List[DialogueRecorded] = Field(
        default_factory=list, description="List of recorded dialogues"
    )
    final_dubbed_audio_url: Optional[str] = Field(
        None, description="URL of the final mixed audio"
    )
    final_dubbed_video_url: Optional[str] = Field(
        None, description="URL of the final dubbed video"
    )
    status: str = Field(
        default="recording",
        description="Status: recording, processing, completed, error"
    )


class DubbingSessionCreate(BaseModel):
    """Request model when creating a dubbing session."""

    transcription_id: str = Field(...)
    character_id: str = Field(...)


class DubbingSessionUpdate(BaseModel):
    """Model for update requests. All fields optional."""

    dialogues_recorded: Optional[List[DialogueRecorded]] = None
    final_dubbed_audio_url: Optional[str] = None
    status: Optional[str] = None


class DubbingSessionDB(DubbingSessionBase):
    """Internal DB model."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: Optional[ObjectId] = Field(None, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class DubbingSessionResponse(BaseModel):
    """Response model returned by API endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="_id", description="Dubbing session ID")
    user_id: str
    transcription_id: str
    clip_scene_id: str
    character_id: str
    character_name: str
    dialogues_recorded: List[DialogueRecorded] = Field(default_factory=list)
    final_dubbed_audio_url: Optional[str] = None
    final_dubbed_video_url: Optional[str] = None
    status: str
    created_at: str
    completed_at: Optional[str] = None

    @classmethod
    def from_db(cls, data: Dict[str, Any]) -> "DubbingSessionResponse":
        """Build a DubbingSessionResponse from a MongoDB document dictionary."""
        dialogues = []
        for dlg in data.get("dialogues_recorded", []):
            dialogue_dict = dlg.copy() if isinstance(dlg, dict) else dlg
            if isinstance(dialogue_dict, dict) and "uploaded_at" in dialogue_dict:
                if isinstance(dialogue_dict["uploaded_at"], datetime):
                    dialogue_dict["uploaded_at"] = dialogue_dict["uploaded_at"].isoformat()
            dialogues.append(dialogue_dict)

        return cls(
            _id=str(data.get("_id")),
            user_id=data.get("user_id"),
            transcription_id=data.get("transcription_id"),
            clip_scene_id=data.get("clip_scene_id"),
            character_id=data.get("character_id"),
            character_name=data.get("character_name"),
            dialogues_recorded=dialogues,
            final_dubbed_audio_url=data.get("final_dubbed_audio_url"),
            final_dubbed_video_url=data.get("final_dubbed_video_url"),
            status=data.get("status", "recording"),
            created_at=(data.get("created_at") or datetime.utcnow()).isoformat(),
            completed_at=(
                data.get("completed_at").isoformat() if data.get("completed_at") else None
            ),
        )
