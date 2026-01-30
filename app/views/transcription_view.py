"""
FastAPI views for transcription endpoints.

Endpoints:
 - POST /transcriptions/transcribe-only -> transcribe audio with OpenAI (no save)
 - POST /transcriptions/        -> create transcription with manual data
 - PUT /transcriptions/{id}     -> edit transcription by _id
 - GET /transcriptions/{id}     -> get transcription by _id
 - DELETE /transcriptions/{id}  -> delete transcription by _id
"""
# pylint: disable=R0913,R0917

import json
from fastapi import APIRouter, Depends, UploadFile, Form, Body
from fastapi.responses import JSONResponse
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.controllers.transcription_controller import TranscriptionController
from app.controllers.auth_controller import AuthController
from app.utils.logger import get_logger, log_info, log_error
from app.utils.dependencies import get_current_admin

logger = get_logger(__name__)

router = APIRouter()


@router.post("/transcriptions/transcribe-only", response_class=JSONResponse)
async def transcribe_audio_only(
    audio_file: UploadFile,
    current_user: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """Transcribe audio using OpenAI without saving to database.

    Accepts multipart form: `audio_file` (.mp3)
    Returns only the transcribed text.
    Requires authentication.
    """
    try:
        log_info(logger, f"User {current_user.get('email')} requested audio transcription")
        return await TranscriptionController.transcribe_audio_only(audio_file)
    except (RuntimeError, OSError) as e:
        log_error(logger, "transcribe_audio_only endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500, content={"detail": "Failed to transcribe audio", "error": str(e)})


@router.post("/transcriptions/", response_class=JSONResponse)
async def create_transcription(
    background_audio_file: UploadFile = None,
    voices_audio_file: UploadFile = None,
    movie_id: str = Form(...),
    clip_scene_id: str = Form(...),
    duration: float = Form(...),
    characters: str = Form(None),
    status: str = Form("pending"),
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """Create a transcription with audio files uploaded to R2 Storage.

    Accepts multipart form data:
    - background_audio_file: Audio file with background/music only (.mp3)
    - voices_audio_file: Audio file with all character voices (.mp3)
    - movie_id: ID of the movie
    - clip_scene_id: ID of the clip/scene
    - duration: Duration in seconds
    - characters: JSON string with character dialogues (optional)
    - status: Status (default: pending)

    Returns the created transcription document.
    Requires admin role.
    """
    try:
        parsed_characters = None
        if characters:
            try:
                parsed_characters = json.loads(characters)
            except json.JSONDecodeError:
                return JSONResponse(
                    status_code=400, content={"detail": "Invalid JSON format for characters"})

        log_info(logger, f"Creating transcription for clip {clip_scene_id}")
        return await TranscriptionController.create_transcription(
            background_audio_file, voices_audio_file, movie_id, clip_scene_id,
            duration, parsed_characters, status)
    except (RuntimeError, OSError, PyMongoError) as e:
        log_error(logger, "create_transcription endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500, content={"detail": "Failed to create transcription", "error": str(e)})


@router.put("/transcriptions/{transcription_id}", response_class=JSONResponse)
async def update_transcription(
    transcription_id: str,
    updates: dict = Body(...),
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """Update fields on an existing transcription.

    Body may include: `movie_id`, `clip_scene_id`, `background_audio_url`,
    `voices_audio_url`, `characters`, `duration`, `status`.
    Requires admin role.
    """
    try:
        log_info(logger, f"Update request for transcription {transcription_id}")
        return await TranscriptionController.edit_transcription(transcription_id, updates)
    except (InvalidId, RuntimeError, OSError, PyMongoError) as e:
        log_error(logger, "update_transcription endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500, content={"detail": "Failed to update transcription", "error": str(e)})


@router.get("/transcriptions/{transcription_id}", response_class=JSONResponse)
async def get_transcription(
    transcription_id: str,
    _: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """Retrieve a transcription by its ObjectId `_id`.

    Requires authentication.
    """
    try:
        log_info(logger, f"Fetch transcription {transcription_id}")
        return await TranscriptionController.get_transcription(transcription_id)
    except (InvalidId, RuntimeError, OSError, PyMongoError) as e:
        log_error(logger, "get_transcription endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500, content={"detail": "Failed to fetch transcription", "error": str(e)})


@router.delete("/transcriptions/{transcription_id}", response_class=JSONResponse)
async def delete_transcription(
    transcription_id: str,
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """Delete a transcription by its ObjectId `_id`.

    Requires admin role.
    """
    try:
        log_info(logger, f"Delete transcription {transcription_id}")
        return await TranscriptionController.delete_transcription(transcription_id)
    except (InvalidId, RuntimeError, OSError, PyMongoError) as e:
        log_error(logger, "delete_transcription endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500, content={"detail": "Failed to delete transcription", "error": str(e)})


@router.get("/transcriptions/by-clip/{clip_scene_id}", response_class=JSONResponse)
async def get_transcriptions_by_clip(
    clip_scene_id: str,
    _: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """Get all transcriptions for a specific clip_scene.

    This endpoint allows you to find all available transcriptions for a clip,
    which is useful for starting a dubbing session.

    Returns:
        - clip_scene_id: The clip ID
        - total_transcriptions: Number of transcriptions found
        - transcriptions: List of all transcriptions for this clip

    Use this to:
    1. Check if a clip has transcriptions available
    2. Get the transcription_id needed for dubbing
    3. See all character dialogues available to dub

    Requires authentication.
    """
    try:
        log_info(logger, f"Fetching transcriptions for clip_scene {clip_scene_id}")
        return await TranscriptionController.get_transcriptions_by_clip(clip_scene_id)
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "get_transcriptions_by_clip endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to fetch transcriptions", "error": str(e)}
        )
