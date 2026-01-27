"""
FastAPI views for transcription endpoints.

Endpoints:
 - POST /transcriptions/        -> create transcription (audio + movie_name + duration)
 - PUT /transcriptions/{id}     -> edit transcription by _id
 - GET /transcriptions/{id}     -> get transcription by _id
 - DELETE /transcriptions/{id}  -> delete transcription by _id
"""

from fastapi import APIRouter, Depends, UploadFile, Form, Body
from fastapi.responses import JSONResponse
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.controllers.transcription_controller import TranscriptionController
from app.controllers.auth_controller import AuthController
from app.utils.logger import get_logger, log_info, log_error

logger = get_logger(__name__)

router = APIRouter()


@router.post("/transcriptions/", response_class=JSONResponse)
async def create_transcription(
    audio_file: UploadFile,
    movie_name: str = Form(...),
    duration: float = Form(...),
    _: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """Create a transcription from uploaded audio.

    Accepts multipart form: `audio_file`, `movie_name`, `duration`.
    Returns the created transcription document.
    """
    try:
        log_info(logger, f"Received request to transcribe movie {movie_name}")
        return await TranscriptionController.create_transcription(audio_file, movie_name, duration)
    except (RuntimeError, OSError, PyMongoError) as e:
        log_info(logger, "create_transcription endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500, content={"detail": "Failed to create transcription", "error": str(e)})


@router.put("/transcriptions/{transcription_id}", response_class=JSONResponse)
async def update_transcription(
    transcription_id: str,
    updates: dict = Body(...),
    _: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """Update fields on an existing transcription.

    Body may include: `movie_name`, `transcription`, `duration`.
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
    """Retrieve a transcription by its ObjectId `_id`."""
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
    _: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """Delete a transcription by its ObjectId `_id`."""
    try:
        log_info(logger, f"Delete transcription {transcription_id}")
        return await TranscriptionController.delete_transcription(transcription_id)
    except (InvalidId, RuntimeError, OSError, PyMongoError) as e:
        log_error(logger, "delete_transcription endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500, content={"detail": "Failed to delete transcription", "error": str(e)})
