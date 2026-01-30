"""
Transcription controller: business logic for creating, retrieving,
updating and deleting transcriptions. Uses OpenAI transcription endpoint
via curl and stores documents in MongoDB.
"""
# pylint: disable=R0913,R0917
# flake8: noqa: C901
from datetime import datetime
import os
import json
import tempfile
import asyncio
import subprocess
from typing import Dict, Any, Optional

from fastapi.responses import JSONResponse
from fastapi import UploadFile
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.config.database import database
from app.models.transcription_model import TranscriptionResponse
from app.services.r2_storage_service import R2StorageService
from app.utils.logger import get_logger, log_info, log_error

logger = get_logger(__name__)


open_ai_transcription = os.getenv("OPENAI_API_KEY")
_OPENAI_MODEL = "gpt-4o-transcribe"


class TranscriptionController:
    """Business logic for transcription CRUD operations."""

    @staticmethod
    async def transcribe_audio_only(audio_file: UploadFile) -> JSONResponse:
        """Transcribe audio using OpenAI without saving to database.

        Returns only the transcribed text.
        """
        filename = (audio_file.filename or "").strip()
        if not filename:
            return JSONResponse(status_code=400, content={"detail": "audio_file is required"})

        ext = os.path.splitext(filename)[1].lower()
        if ext != ".mp3":
            return JSONResponse(
                status_code=400, content={"detail": "Only .mp3 files are supported"})

        tmp_path: Optional[str] = None
        try:
            suffix = ext or ".mp3"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmpf:
                tmp_path = tmpf.name
                content = await audio_file.read()
                tmpf.write(content)

            text = await TranscriptionController._call_openai_curl(tmp_path)

            log_info(logger, "Audio transcribed successfully")
            return JSONResponse(
                status_code=200,
                content={"transcription": text}
            )

        except (RuntimeError, OSError) as e:
            log_error(logger, "Failed to transcribe audio", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to transcribe audio", "error": str(e)},
            )

        finally:
            try:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass

    @staticmethod
    async def _call_openai_curl(file_path: str) -> str:
        """Call OpenAI transcription endpoint via curl and return text."""
        cmd = [
            "curl", "-s", "-X", "POST",
            "https://api.openai.com/v1/audio/transcriptions",
            "-H", f"Authorization: Bearer {open_ai_transcription}",
            "-F", f"file=@{file_path}",
            "-F", f"model={_OPENAI_MODEL}"
        ]

        loop = asyncio.get_event_loop()

        def _run():
            return subprocess.run(cmd, capture_output=True, text=True, check=True)

        try:
            proc = await loop.run_in_executor(None, _run)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(e.stderr or "OpenAI curl call failed") from e

        try:
            payload = json.loads(proc.stdout)
            return payload.get("text") or payload.get("transcript") or ""
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid OpenAI response: {str(e)}") from e

    @staticmethod
    async def create_transcription(
        background_audio_file: Optional[UploadFile],
        voices_audio_file: Optional[UploadFile],
        movie_id: str,
        clip_scene_id: str,
        duration: float,
        characters: Optional[list] = None,
        status: str = "pending"
    ) -> JSONResponse:
        """Create a new transcription with audio files uploaded to R2.

        Args:
            background_audio_file: Audio file with background/music only
            voices_audio_file: Audio file with all character voices
            movie_id: Movie ID
            clip_scene_id: Clip/scene ID
            duration: Duration in seconds
            characters: List of characters with dialogues
            status: Status of the transcription

        Returns:
            JSONResponse with the created document fields.
        """
        if duration is None:
            return JSONResponse(status_code=400, content={"detail": "duration is required"})

        if not movie_id or not clip_scene_id:
            return JSONResponse(status_code=400,
                                content={"detail": "movie_id and clip_scene_id are required"})

        background_url = None
        voices_url = None
        r2_service = R2StorageService()

        try:
            if background_audio_file and background_audio_file.filename:
                log_info(logger, f"Uploading background audio: {background_audio_file.filename}")
                upload_result = await r2_service.upload_file(
                    background_audio_file,
                    folder="transcriptions/backgrounds"
                )
                background_url = upload_result["file_url"]
                log_info(logger, f"Background audio uploaded: {background_url}")

            if voices_audio_file and voices_audio_file.filename:
                log_info(logger, f"Uploading voices audio: {voices_audio_file.filename}")
                upload_result = await r2_service.upload_file(
                    voices_audio_file,
                    folder="transcriptions/voices"
                )
                voices_url = upload_result["file_url"]
                log_info(logger, f"Voices audio uploaded: {voices_url}")

            result = await database["transcriptions"].insert_one({
                "movie_id": movie_id,
                "clip_scene_id": clip_scene_id,
                "background_audio_url": background_url,
                "voices_audio_url": voices_url,
                "characters": characters or [],
                "duration": float(duration),
                "status": status,
                "timestamp": datetime.utcnow(),
                "updated_at": None,
            })

            log_info(logger, "Transcription created",
                     {"id": str(result.inserted_id),
                      "movie_id": movie_id, "clip_scene_id": clip_scene_id})

            return JSONResponse(
                status_code=201,
                content={
                    "transcription": TranscriptionResponse.from_db(
                        await database["transcriptions"].find_one({"_id": result.inserted_id})
                    ).dict()
                }
            )

        except PyMongoError as e:
            log_error(logger, "Failed to create transcription", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to create transcription", "error": str(e)},
            )

    @staticmethod
    async def get_transcription(transcription_id: str) -> JSONResponse:
        """Get transcription by ObjectId `_id`."""
        try:
            obj_id = ObjectId(transcription_id)
            doc = await database["transcriptions"].find_one({"_id": obj_id})
            if not doc:
                return JSONResponse(status_code=404, content={"detail": "Transcription not found"})

            return JSONResponse(status_code=200, content={
                "transcription": TranscriptionResponse.from_db(doc).dict()
            })
        except InvalidId as e:
            log_error(logger, "Invalid transcription id", {"error": str(e)})
            return JSONResponse(
                status_code=400, content={"detail": "Invalid transcription id",
                                          "error": str(e)})
        except PyMongoError as e:
            log_error(logger, "Error fetching transcription", {"error": str(e)})
            return JSONResponse(
                status_code=500, content={"detail": "Failed to get transcription",
                                          "error": str(e)})

    @staticmethod
    async def edit_transcription(transcription_id: str, updates: Dict[str, Any]) -> JSONResponse:
        """Edit transcription fields by `_id`."""
        try:
            obj_id = ObjectId(transcription_id)
            existing = await database["transcriptions"].find_one({"_id": obj_id})
            if not existing:
                return JSONResponse(status_code=404, content={"detail": "Transcription not found"})

            set_fields: Dict[str, Any] = {}
            if "movie_id" in updates:
                set_fields["movie_id"] = updates["movie_id"]
            if "clip_scene_id" in updates:
                set_fields["clip_scene_id"] = updates["clip_scene_id"]
            if "background_audio_url" in updates:
                set_fields["background_audio_url"] = updates["background_audio_url"]
            if "voices_audio_url" in updates:
                set_fields["voices_audio_url"] = updates["voices_audio_url"]
            if "characters" in updates:
                set_fields["characters"] = updates["characters"]
            if "duration" in updates:
                set_fields["duration"] = float(updates["duration"])
            if "status" in updates:
                set_fields["status"] = updates["status"]

            if not set_fields:
                return JSONResponse(
                    status_code=400, content={"detail": "No valid fields to update"})

            set_fields["updated_at"] = datetime.utcnow()
            await database["transcriptions"].update_one({"_id": obj_id}, {"$set": set_fields})
            updated = await database["transcriptions"].find_one({"_id": obj_id})

            log_info(logger, "Transcription updated",
                     {"id": transcription_id, "updates": list(set_fields.keys())})
            return JSONResponse(status_code=200, content={
                "transcription": TranscriptionResponse.from_db(updated).dict()
            })
        except InvalidId as e:
            log_error(logger, "Invalid transcription id for update", {"error": str(e)})
            return JSONResponse(
                status_code=400, content={"detail": "Invalid transcription id",
                                          "error": str(e)})
        except PyMongoError as e:
            log_error(logger, "Error updating transcription", {"error": str(e)})
            return JSONResponse(
                status_code=500, content={"detail": "Failed to update transcription",
                                          "error": str(e)})

    @staticmethod
    async def delete_transcription(transcription_id: str) -> JSONResponse:
        """Delete transcription by `_id`."""
        try:
            obj_id = ObjectId(transcription_id)
            res = await database["transcriptions"].delete_one({"_id": obj_id})
            if res.deleted_count == 0:
                return JSONResponse(status_code=404, content={"detail": "Transcription not found"})

            log_info(logger, "Transcription deleted", {"id": transcription_id})
            return JSONResponse(
                status_code=200, content={"log": "Transcription deleted successfully"})
        except InvalidId as e:
            log_error(logger, "Invalid transcription id for delete", {"error": str(e)})
            return JSONResponse(
                status_code=400, content={"detail": "Invalid transcription id",
                                          "error": str(e)})
        except PyMongoError as e:
            log_error(logger, "Error deleting transcription", {"error": str(e)})
            return JSONResponse(
                status_code=500, content={"detail": "Failed to delete transcription",
                                          "error": str(e)})

    @staticmethod
    async def get_transcriptions_by_clip(clip_scene_id: str) -> JSONResponse:
        """Get all transcriptions for a specific clip_scene.
        
        Args:
            clip_scene_id: Clip scene ID
            
        Returns:
            JSONResponse with list of transcriptions for this clip
        """
        try:
            cursor = database["transcriptions"].find({"clip_scene_id": clip_scene_id})
            transcriptions = []

            async for doc in cursor:
                transcriptions.append(TranscriptionResponse.from_db(doc).dict())

            log_info(logger,
                     f"Found {len(transcriptions)} transcription(s) for clip {clip_scene_id}")

            return JSONResponse(
                status_code=200,
                content={
                    "clip_scene_id": clip_scene_id,
                    "total_transcriptions": len(transcriptions),
                    "transcriptions": transcriptions
                }
            )
        except PyMongoError as e:
            log_error(logger, "Error fetching transcriptions by clip", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to get transcriptions", "error": str(e)}
            )
