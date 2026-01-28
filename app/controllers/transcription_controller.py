"""
Transcription controller: business logic for creating, retrieving,
updating and deleting transcriptions. Uses OpenAI transcription endpoint
via curl and stores documents in MongoDB.
"""
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
from app.utils.logger import get_logger, log_info, log_error

logger = get_logger(__name__)


open_ai_transcription = os.getenv("OPENAI_API_KEY")
_OPENAI_MODEL = "gpt-4o-transcribe"


class TranscriptionController:
    """Business logic for transcription CRUD operations."""

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
        audio_file: UploadFile,
        movie_name: str,
        duration: float
    ) -> JSONResponse:
        """Create a new transcription by calling OpenAI and storing result.

        Returns JSONResponse with the created document fields.
        """
        if duration is None:
            return JSONResponse(status_code=400, content={"detail": "duration is required"})

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

            result = await database["transcriptions"].insert_one({
                "movie_name": movie_name,
                "transcription": text,
                "duration": float(duration),
                "timestamp": datetime.utcnow(),
                "updated_at": None,
            })

            log_info(logger, "Transcription created",
                     {"id": str(result.inserted_id), "movie_name": movie_name})

            return JSONResponse(
                status_code=201,
                content={
                    "transcription": TranscriptionResponse.from_db(
                        await database["transcriptions"].find_one({"_id": result.inserted_id})
                    ).dict()
                }
            )

        except (RuntimeError, OSError, PyMongoError) as e:
            log_error(logger, "Failed to create transcription", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to create transcription", "error": str(e)},
            )

        finally:
            try:
                if tmp_path and os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass

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
            if "movie_name" in updates:
                set_fields["movie_name"] = updates["movie_name"]
            if "transcription" in updates:
                set_fields["transcription"] = updates["transcription"]
            if "duration" in updates:
                set_fields["duration"] = float(updates["duration"])

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
