"""
Controller for transcription operations: create, edit, get, delete.

Handles calling OpenAI (via curl) to transcribe uploaded audio and
persists the result into MongoDB. Follows project logging and response style.
"""
from datetime import datetime
import os
import json
import tempfile
import asyncio
import subprocess
from typing import Optional, Dict, Any

from fastapi.responses import JSONResponse
from fastapi import UploadFile
from bson import ObjectId

from app.config.database import database
from app.models.transcription_model import TranscriptionResponse
from app.utils.logger import get_logger, log_info, log_error

logger = get_logger(__name__)


class TranscriptionController:
    """Business logic for transcription CRUD operations."""

    @staticmethod
    async def _call_openai_curl(file_path: str) -> str:
        """Call OpenAI transcription endpoint via curl and return text.

        This uses a subprocess to run the curl command so the calling pattern
        mirrors the project's reference scripts that used curl.
        """
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

        model = os.getenv("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-transcribe")
        cmd = [
            "curl", "-s", "-X", "POST",
            "https://api.openai.com/v1/audio/transcriptions",
            "-H", f"Authorization: Bearer {api_key}",
            "-F", f"file=@{file_path}",
            "-F", f"model={model}"
        ]

        loop = asyncio.get_event_loop()

        def _run():
            return subprocess.run(cmd, capture_output=True, text=True)

        proc = await loop.run_in_executor(None, _run)
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or "OpenAI curl call failed")

        try:
            payload = json.loads(proc.stdout)
            # Whisper returns `text` field for transcription output
            return payload.get("text") or payload.get("transcript") or ""
        except Exception as e:
            raise RuntimeError(f"Invalid OpenAI response: {str(e)}")

    @staticmethod
    async def create_transcription(audio_file: UploadFile, movie_name: str, duration: float) -> JSONResponse:
        """Create a new transcription by calling OpenAI and storing result."""
        if duration is None:
            return JSONResponse(status_code=400, content={"detail": "duration is required"})

        tmp = None
        try:
            suffix = os.path.splitext(audio_file.filename or "")[1] or ".audio"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmpf:
                tmp = tmpf.name
                content = await audio_file.read()
                tmpf.write(content)

            text = await TranscriptionController._call_openai_curl(tmp)

            record = {
                "movie_name": movie_name,
                "transcription": text,
                "duration": float(duration),
                "timestamp": datetime.utcnow(),
                "updated_at": None,
            }

            db = database["transcriptions"]
            result = await db.insert_one(record)
            created = await db.find_one({"_id": result.inserted_id})

            log_info(logger, f"Transcription created for movie {movie_name}", {"id": str(result.inserted_id)})

            resp = TranscriptionResponse.from_db(created).dict()
            return JSONResponse(
                status_code=201,
                content={
                    "transcription": resp,
                    "log": "Transcription created successfully"
                }
            )

        except Exception as e:
            log_error(logger, "Failed to create transcription", {"error": str(e)})
            return JSONResponse(status_code=500, content={"detail": "Failed to create transcription", "error": str(e)})

        finally:
            try:
                if tmp and os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass

    @staticmethod
    async def get_transcription(transcription_id: str) -> JSONResponse:
        try:
            db = database["transcriptions"]
            obj_id = ObjectId(transcription_id)
            doc = await db.find_one({"_id": obj_id})
            if not doc:
                return JSONResponse(status_code=404, content={"detail": "Transcription not found"})

            resp = TranscriptionResponse.from_db(doc).dict()
            return JSONResponse(status_code=200, content={"transcription": resp})

        except Exception as e:
            log_error(logger, "Error fetching transcription", {"error": str(e)})
            return JSONResponse(status_code=400 if isinstance(e, (TypeError, ValueError)) else 500, content={"detail": "Failed to get transcription", "error": str(e)})

    @staticmethod
    async def edit_transcription(transcription_id: str, updates: Dict[str, Any]) -> JSONResponse:
        try:
            db = database["transcriptions"]
            obj_id = ObjectId(transcription_id)
            existing = await db.find_one({"_id": obj_id})
            if not existing:
                return JSONResponse(status_code=404, content={"detail": "Transcription not found"})

            set_fields = {}
            if "movie_name" in updates:
                set_fields["movie_name"] = updates["movie_name"]
            if "transcription" in updates:
                set_fields["transcription"] = updates["transcription"]
            if "duration" in updates:
                set_fields["duration"] = float(updates["duration"])

            if not set_fields:
                return JSONResponse(status_code=400, content={"detail": "No valid fields to update"})

            set_fields["updated_at"] = datetime.utcnow()

            await db.update_one({"_id": obj_id}, {"$set": set_fields})
            updated = await db.find_one({"_id": obj_id})

            resp = TranscriptionResponse.from_db(updated).dict()
            log_info(logger, f"Transcription {transcription_id} updated", {"updates": list(set_fields.keys())})
            return JSONResponse(status_code=200, content={"transcription": resp})

        except Exception as e:
            log_error(logger, "Error updating transcription", {"error": str(e)})
            return JSONResponse(status_code=400 if isinstance(e, (TypeError, ValueError)) else 500, content={"detail": "Failed to update transcription", "error": str(e)})

    @staticmethod
    async def delete_transcription(transcription_id: str) -> JSONResponse:
        try:
            db = database["transcriptions"]
            obj_id = ObjectId(transcription_id)
            res = await db.delete_one({"_id": obj_id})
            if res.deleted_count == 0:
                return JSONResponse(status_code=404, content={"detail": "Transcription not found"})

            log_info(logger, f"Transcription {transcription_id} deleted")
            return JSONResponse(status_code=200, content={"log": "Transcription deleted successfully"})

        except Exception as e:
            log_error(logger, "Error deleting transcription", {"error": str(e)})
            return JSONResponse(status_code=400 if isinstance(e, (TypeError, ValueError)) else 500, content={"detail": "Failed to delete transcription", "error": str(e)})
