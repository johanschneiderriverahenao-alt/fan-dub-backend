"""
Dubbing Session controller: business logic for user dubbing sessions.
"""
# pylint: disable=W0718,R0801,C0302,R0914,R0911,R0912,R0915,R0914,R1732
# flake8: noqa: C901
import subprocess
from datetime import datetime
import tempfile
import os
import requests
from fastapi.responses import JSONResponse
from fastapi import UploadFile
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.config.database import database
from app.controllers.credit_controller import CreditController
from app.models.dubbing_session_model import DubbingSessionResponse
from app.services.r2_storage_service import R2StorageService
from app.services.email_service import EmailService
from app.utils.logger import get_logger, log_info, log_error

logger = get_logger(__name__)


def get_audio_segment():
    """Lazy import of AudioSegment. Raises error if pydub not installed."""
    try:
        from pydub import AudioSegment
        return AudioSegment
    except ImportError as e:
        raise ImportError(
            "pydub is required for audio processing. "
            "Install it locally: pip install pydub. "
            "Audio processing is only available in development mode."
        ) from e


class DubbingSessionController:
    """Business logic for dubbing session CRUD operations."""

    @staticmethod
    async def create_session(
        user_id: str, transcription_id: str, character_id: str
    ) -> JSONResponse:
        """Create a new dubbing session for a user.

        Args:
            user_id: ID of the user creating the session
            transcription_id: ID of the transcription
            character_id: ID of the character to dub

        Returns:
            JSONResponse with the created session
        """
        try:
            can_create = await CreditController.check_can_create_dubbing(user_id)
            if not can_create["can_create"]:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": can_create["message"],
                        "error_code": "INSUFFICIENT_CREDITS"
                    }
                )

            transcription = await database["transcriptions"].find_one(
                {"_id": ObjectId(transcription_id)}
            )
            if not transcription:
                return JSONResponse(
                    status_code=404, content={"detail": "Transcription not found"}
                )

            character = next(
                (
                    c
                    for c in transcription.get("characters", [])
                    if c.get("character_id") == character_id
                ),
                None,
            )
            if not character:
                return JSONResponse(
                    status_code=404,
                    content={"detail": f"Character {character_id} not found in transcription"},
                )

            existing_session = await database["dubbing_sessions"].find_one({
                "transcription_id": transcription_id,
                "character_id": character_id,
                "user_id": user_id,
                "status": {"$ne": "deleted"}
            })

            if existing_session:
                return JSONResponse(
                    status_code=200,
                    content={
                        "message": "You already have a session for this character",
                        "session": DubbingSessionResponse.from_db(
                            existing_session
                        ).model_dump(exclude_none=False),
                    },
                )

            result = await database["dubbing_sessions"].insert_one(
                {
                    "user_id": user_id,
                    "transcription_id": transcription_id,
                    "clip_scene_id": transcription.get("clip_scene_id"),
                    "character_id": character_id,
                    "character_name": character.get("character_name"),
                    "dialogues_recorded": [],
                    "final_dubbed_audio_url": None,
                    "status": "recording",
                    "created_at": datetime.utcnow(),
                    "completed_at": None,
                }
            )

            consume_result = await CreditController.consume_dubbing(
                user_id, can_create["method"]
            )
            if consume_result.status_code != 200:
                await database["dubbing_sessions"].delete_one({"_id": result.inserted_id})
                return JSONResponse(
                    status_code=500,
                    content={"detail": "Failed to consume dubbing credit"}
                )

            log_info(
                logger,
                f"Dubbing session created for user {user_id}, character {character_id} "
                f"using method: {can_create['method']}",
            )

            session = await database["dubbing_sessions"].find_one(
                {"_id": result.inserted_id}
            )
            return JSONResponse(
                status_code=201,
                content={
                    "session": DubbingSessionResponse.from_db(
                        session
                    ).model_dump(exclude_none=False)
                },
            )

        except (InvalidId, PyMongoError) as e:
            log_error(logger, "Failed to create dubbing session", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to create session", "error": str(e)},
            )

    @staticmethod
    async def upload_dialogue(
        session_id: str, dialogue_id: str, audio_file: UploadFile
    ) -> JSONResponse:
        """Upload a recorded dialogue audio for a session.

        Args:
            session_id: ID of the dubbing session
            dialogue_id: ID of the dialogue being recorded
            audio_file: Audio file uploaded by user

        Returns:
            JSONResponse with updated session and warnings if any
        """
        try:
            obj_id = ObjectId(session_id)
            session = await database["dubbing_sessions"].find_one({"_id": obj_id})
            if not session:
                return JSONResponse(
                    status_code=404, content={"detail": "Session not found"}
                )

            transcription = await database["transcriptions"].find_one(
                {"_id": ObjectId(session.get("transcription_id"))}
            )
            if not transcription:
                return JSONResponse(
                    status_code=404, content={"detail": "Transcription not found"}
                )

            expected_dialogue = None
            for character in transcription.get("characters", []):
                if character.get("character_id") == session.get("character_id"):
                    for dlg in character.get("dialogues", []):
                        if dlg.get("dialogue_id") == dialogue_id:
                            expected_dialogue = dlg
                            break
                if expected_dialogue:
                    break

            if not expected_dialogue:
                return JSONResponse(
                    status_code=404,
                    content={
                        "detail": (
                            f"Dialogue {dialogue_id} not found for character "
                            f"{session.get('character_id')}"
                        )
                    },
                )

            log_info(logger, f"Validating audio file: {audio_file.filename}")

            content = await audio_file.read()
            file_size = len(content)

            if file_size == 0:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Audio file is empty"}
                )

            filename_lower = audio_file.filename.lower()
            allowed_extensions = ('.mp3', '.ogg', '.webm', '.wav', '.m4a')
            if not filename_lower.endswith(allowed_extensions):
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": (
                            "Unsupported file format. Allowed: "
                            f"{', '.join(allowed_extensions)}"
                        )
                    },
                )

            log_info(logger, f"File size: {file_size} bytes")

            file_ext = os.path.splitext(audio_file.filename)[1] or '.mp3'

            try:
                temp_validation = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
                temp_validation.write(content)
                temp_validation.close()

                AudioSegment = get_audio_segment()
                test_audio = AudioSegment.from_file(temp_validation.name)
                log_info(logger,
                         f"Audio validated: {len(test_audio)}ms duration, format: {file_ext}")

                os.unlink(temp_validation.name)

            except Exception as e:
                log_error(logger, "Invalid audio file uploaded", {"error": str(e)})
                try:
                    os.unlink(temp_validation.name)
                except Exception:
                    pass
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": (
                            "Invalid audio file. Please upload a valid "
                            "MP3, OGG, or WEBM file."
                        ),
                        "error": str(e),
                    },
                )

            await audio_file.seek(0)

            r2_service = R2StorageService()
            upload_result = await r2_service.upload_file(
                audio_file, folder=f"dubbing/{session_id}/dialogues"
            )

            expected_duration = (
                expected_dialogue.get("end_time", 0)
                - expected_dialogue.get("start_time", 0)
            )

            dialogues = session.get("dialogues_recorded", [])

            dialogues = [d for d in dialogues if d.get("dialogue_id") != dialogue_id]

            new_dialogue = {
                "dialogue_id": dialogue_id,
                "audio_url": upload_result["file_url"],
                "duration": upload_result.get("size", 0) / 1000,
                "expected_duration": expected_duration,
                "uploaded_at": datetime.utcnow().isoformat(),
            }
            dialogues.append(new_dialogue)

            await database["dubbing_sessions"].update_one(
                {"_id": obj_id}, {"$set": {"dialogues_recorded": dialogues}}
            )

            log_info(logger, f"Dialogue {dialogue_id} uploaded for session {session_id}")

            updated_session = await database["dubbing_sessions"].find_one({"_id": obj_id})

            response_data = {
                "message": "Dialogue uploaded successfully",
                "session": DubbingSessionResponse.from_db(
                    updated_session
                ).model_dump(exclude_none=False),
                "dialogue_info": {
                    "text": expected_dialogue.get("text"),
                    "expected_duration": expected_duration,
                    "start_time": expected_dialogue.get("start_time"),
                    "end_time": expected_dialogue.get("end_time"),
                },
                "warning": (
                    "Note: Audio duration validation requires audio processing library. "
                    "Make sure your recording fits within the expected time slot."
                ),
            }

            return JSONResponse(status_code=200, content=response_data)

        except (InvalidId, PyMongoError, RuntimeError) as e:
            log_error(logger, "Failed to upload dialogue", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to upload dialogue", "error": str(e)},
            )

    @staticmethod
    async def get_session_dialogues(session_id: str, user_id: str) -> JSONResponse:
        """Get all dialogues for a dubbing session with recording status.

        Args:
            session_id: Session ID
            user_id: User ID (for ownership verification)

        Returns:
            JSONResponse with dialogues list showing which are recorded/pending
        """
        try:
            obj_id = ObjectId(session_id)
            session = await database["dubbing_sessions"].find_one({"_id": obj_id})

            if not session:
                return JSONResponse(
                    status_code=404, content={"detail": "Session not found"}
                )

            if str(session.get("user_id")) != user_id:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Not authorized to access this session"},
                )

            transcription = await database["transcriptions"].find_one(
                {"_id": ObjectId(session.get("transcription_id"))}
            )
            if not transcription:
                return JSONResponse(
                    status_code=404, content={"detail": "Transcription not found"}
                )

            character_data = next(
                (
                    c
                    for c in transcription.get("characters", [])
                    if c.get("character_id") == session.get("character_id")
                ),
                None,
            )

            if not character_data:
                return JSONResponse(
                    status_code=404, content={"detail": "Character not found"}
                )

            recorded_ids = {
                d.get("dialogue_id") for d in session.get("dialogues_recorded", [])
            }

            dialogues_list = []
            for dlg in character_data.get("dialogues", []):
                dialogue_info = {
                    "dialogue_id": dlg.get("dialogue_id"),
                    "text": dlg.get("text"),
                    "start_time": dlg.get("start_time"),
                    "end_time": dlg.get("end_time"),
                    "duration": dlg.get("end_time", 0) - dlg.get("start_time", 0),
                    "is_recorded": dlg.get("dialogue_id") in recorded_ids,
                }
                dialogues_list.append(dialogue_info)

            total_dialogues = len(dialogues_list)
            recorded_count = len(recorded_ids)

            return JSONResponse(
                status_code=200,
                content={
                    "session_id": session_id,
                    "character_name": session.get("character_name"),
                    "character_id": session.get("character_id"),
                    "total_dialogues": total_dialogues,
                    "recorded_dialogues": recorded_count,
                    "pending_dialogues": total_dialogues - recorded_count,
                    "progress_percentage": (
                        round((recorded_count / total_dialogues) * 100, 2)
                        if total_dialogues > 0
                        else 0
                    ),
                    "dialogues": dialogues_list,
                },
            )

        except (InvalidId, PyMongoError) as e:
            log_error(logger, "Failed to get session dialogues", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to get dialogues", "error": str(e)},
            )

    @staticmethod
    async def get_session(session_id: str, user_id: str) -> JSONResponse:
        """Get a dubbing session by ID (user can only see their own).

        Args:
            session_id: Session ID
            user_id: User ID (for ownership verification)

        Returns:
            JSONResponse with session data
        """
        try:
            obj_id = ObjectId(session_id)
            session = await database["dubbing_sessions"].find_one(
                {"_id": obj_id, "user_id": user_id}
            )
            if not session:
                return JSONResponse(
                    status_code=404, content={"detail": "Session not found"}
                )

            return JSONResponse(
                status_code=200,
                content={
                    "session": DubbingSessionResponse.from_db(
                        session
                    ).model_dump(exclude_none=False)
                },
            )

        except (InvalidId, PyMongoError) as e:
            log_error(logger, "Failed to get session", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to get session", "error": str(e)},
            )

    @staticmethod
    async def get_user_sessions(user_id: str, page: int = 1, page_size: int = 10) -> JSONResponse:
        """Get all dubbing sessions for a user.

        Args:
            user_id: User ID
            page: Page number
            page_size: Items per page

        Returns:
            JSONResponse with paginated sessions
        """
        try:
            skip = (page - 1) * page_size
            cursor = (
                database["dubbing_sessions"]
                .find({"user_id": user_id})
                .sort("created_at", -1)
                .skip(skip)
                .limit(page_size)
            )

            sessions = []
            async for doc in cursor:
                sessions.append(DubbingSessionResponse.from_db(doc).model_dump(exclude_none=False))

            total = await database["dubbing_sessions"].count_documents({"user_id": user_id})

            return JSONResponse(
                status_code=200,
                content={
                    "data": sessions,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_items": total,
                        "total_pages": (total + page_size - 1) // page_size,
                    },
                },
            )

        except PyMongoError as e:
            log_error(logger, "Failed to get user sessions", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to get sessions", "error": str(e)},
            )

    @staticmethod
    async def delete_session(session_id: str, user_id: str) -> JSONResponse:
        """Delete a dubbing session (user can only delete their own).

        Args:
            session_id: Session ID
            user_id: User ID (for ownership verification)

        Returns:
            JSONResponse with deletion confirmation
        """
        try:
            obj_id = ObjectId(session_id)
            result = await database["dubbing_sessions"].delete_one(
                {"_id": obj_id, "user_id": user_id}
            )

            if result.deleted_count == 0:
                return JSONResponse(
                    status_code=404, content={"detail": "Session not found"}
                )

            log_info(logger, f"Dubbing session {session_id} deleted by user {user_id}")
            return JSONResponse(
                status_code=200, content={"message": "Session deleted successfully"}
            )

        except (InvalidId, PyMongoError) as e:
            log_error(logger, "Failed to delete session", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to delete session", "error": str(e)},
            )

    @staticmethod
    async def process_dubbing_session(session_id: str, user_id: str) -> JSONResponse:
        """Process and mix all audio for a dubbing session.

        This method:
        1. Downloads background and voices audio from transcription
        2. For each user dialogue, silences the original voice in that time range
        3. Overlays user's recorded audio (trimmed or padded to fit)
        4. Generates final mixed audio
        5. Uploads to R2 and updates session

        Args:
            session_id: Dubbing session ID
            user_id: User ID (for ownership verification)

        Returns:
            JSONResponse with final audio URL
        """
        temp_files = []
        try:
            AudioSegment = get_audio_segment()
            
            obj_id = ObjectId(session_id)
            session = await database["dubbing_sessions"].find_one({"_id": obj_id})

            if not session:
                return JSONResponse(
                    status_code=404, content={"detail": "Session not found"}
                )

            if str(session.get("user_id")) != user_id:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Not authorized to process this session"},
                )

            transcription = await database["transcriptions"].find_one(
                {"_id": ObjectId(session.get("transcription_id"))}
            )
            if not transcription:
                return JSONResponse(
                    status_code=404, content={"detail": "Transcription not found"}
                )

            character_data = next(
                (
                    c
                    for c in transcription.get("characters", [])
                    if c.get("character_id") == session.get("character_id")
                ),
                None,
            )

            if not character_data:
                return JSONResponse(
                    status_code=404, content={"detail": "Character not found"}
                )

            expected_dialogues = character_data.get("dialogues", [])
            recorded_dialogues = session.get("dialogues_recorded", [])

            if len(recorded_dialogues) < len(expected_dialogues):
                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": (
                            f"Not all dialogues recorded. Expected "
                            f"{len(expected_dialogues)}, got {len(recorded_dialogues)}"
                        )
                    },
                )

            log_info(logger, f"Starting audio processing for session {session_id}")

            background_url = transcription.get("background_audio_url")
            voices_url = transcription.get("voices_audio_url")

            if not background_url or not voices_url:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Transcription missing audio files"},
                )

            log_info(logger, "Downloading background audio...")
            background_response = requests.get(background_url, timeout=60)
            background_response.raise_for_status()
            background_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            background_temp.write(background_response.content)
            background_temp.close()
            temp_files.append(background_temp.name)

            log_info(logger, "Downloading voices audio...")
            voices_response = requests.get(voices_url, timeout=60)
            voices_response.raise_for_status()
            voices_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            voices_temp.write(voices_response.content)
            voices_temp.close()
            temp_files.append(voices_temp.name)

            background_audio = AudioSegment.from_mp3(background_temp.name)
            voices_audio = AudioSegment.from_mp3(voices_temp.name)

            log_info(
                logger,
                (
                    f"Audio loaded: background={len(background_audio)}ms, "
                    f"voices={len(voices_audio)}ms"
                ),
            )

            modified_voices = voices_audio

            recorded_map = {d["dialogue_id"]: d for d in recorded_dialogues}

            for dialogue in expected_dialogues:
                dialogue_id = dialogue.get("dialogue_id")
                start_ms = int(dialogue.get("start_time", 0) * 1000)
                end_ms = int(dialogue.get("end_time", 0) * 1000)

                log_info(logger,
                         f"Silencing dialogue {dialogue_id} from {start_ms}ms to {end_ms}ms")
                silence_duration = end_ms - start_ms
                silence = AudioSegment.silent(duration=silence_duration)

                modified_voices = (
                    modified_voices[:start_ms] + silence + modified_voices[end_ms:]
                )

                if dialogue_id in recorded_map:
                    user_audio_url = recorded_map[dialogue_id].get("audio_url")

                    log_info(logger, f"Downloading user audio for {dialogue_id}...")
                    log_info(logger, f"URL: {user_audio_url}")
                    user_response = requests.get(user_audio_url, timeout=60)
                    user_response.raise_for_status()

                    content_length = len(user_response.content)
                    log_info(logger, f"Downloaded {content_length} bytes")

                    if content_length == 0:
                        log_error(logger, f"Downloaded audio for {dialogue_id} is empty", {})
                        return JSONResponse(
                            status_code=400,
                            content={
                                "detail": (
                                    f"Audio file for dialogue {dialogue_id} "
                                    "is empty or corrupted"
                                )
                            },
                        )

                    file_ext = '.mp3'
                    if '.ogg' in user_audio_url.lower():
                        file_ext = '.ogg'
                    elif '.webm' in user_audio_url.lower():
                        file_ext = '.webm'

                    user_temp = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
                    user_temp.write(user_response.content)
                    user_temp.close()
                    temp_files.append(user_temp.name)

                    log_info(logger, f"Saved to temp file: {user_temp.name}")

                    try:
                        user_audio = AudioSegment.from_file(user_temp.name)
                        log_info(logger, f"Audio loaded successfully: {len(user_audio)}ms")
                    except Exception as e:
                        log_error(
                            logger,
                            f"Failed to decode user audio for {dialogue_id}",
                            {"error": str(e), "file_size": content_length}
                        )
                        return JSONResponse(
                            status_code=400,
                            content={
                                "detail": (
                                    f"Audio file for dialogue {dialogue_id} "
                                    "could not be decoded"
                                ),
                                "error": str(e),
                                "suggestion": (
                                    "Please re-upload this dialogue with a valid audio file "
                                    "(MP3, OGG, or WEBM)"
                                ),
                            },
                        )

                    target_dbfs = voices_audio.dBFS
                    change_in_dbfs = target_dbfs - user_audio.dBFS
                    user_audio = user_audio.apply_gain(change_in_dbfs)
                    log_info(
                        logger,
                        (
                            f"Audio normalized: adjusted {change_in_dbfs:.2f} dBFS "
                            "to match original"
                        ),
                    )
                    user_duration_ms = len(user_audio)

                    if user_duration_ms > silence_duration:
                        log_info(
                            logger,
                            (
                                f"Trimming user audio from {user_duration_ms}ms "
                                f"to {silence_duration}ms"
                            ),
                        )
                        user_audio = user_audio[:silence_duration]
                    elif user_duration_ms < silence_duration:
                        padding = AudioSegment.silent(duration=silence_duration - user_duration_ms)
                        log_info(
                            logger,
                            (
                                f"Padding user audio from {user_duration_ms}ms "
                                f"to {silence_duration}ms"
                            ),
                        )
                        user_audio = user_audio + padding

                    log_info(logger, f"Overlaying user audio at {start_ms}ms")
                    modified_voices = modified_voices.overlay(user_audio, position=start_ms)

            log_info(logger, "Mixing background and voices...")
            final_audio = background_audio.overlay(modified_voices)

            output_temp_audio = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            output_temp_audio.close()
            temp_files.append(output_temp_audio.name)

            log_info(logger, "Exporting final audio...")
            final_audio.export(output_temp_audio.name, format="mp3", bitrate="192k")

            r2_service = R2StorageService()

            video_url = transcription.get("video_url")
            final_video_url = None

            if video_url:
                log_info(logger, f"Video found, downloading: {video_url}")
                try:
                    video_response = requests.get(video_url, timeout=120)
                    video_response.raise_for_status()

                    video_ext = '.mp4'
                    if '.webm' in video_url.lower():
                        video_ext = '.webm'
                    elif '.mov' in video_url.lower():
                        video_ext = '.mov'

                    video_temp = tempfile.NamedTemporaryFile(delete=False, suffix=video_ext)
                    video_temp.write(video_response.content)
                    video_temp.close()
                    temp_files.append(video_temp.name)

                    log_info(logger,
                             "Video downloaded, combining with dubbed audio using ffmpeg...")

                    output_video_temp = tempfile.NamedTemporaryFile(delete=False, suffix='.mp4')
                    output_video_temp.close()
                    temp_files.append(output_video_temp.name)

                    ffmpeg_cmd = [
                        'ffmpeg',
                        '-i', video_temp.name,
                        '-i', output_temp_audio.name,
                        '-c:v', 'copy',
                        '-c:a', 'aac',
                        '-b:a', '192k',
                        '-map', '0:v:0',
                        '-map', '1:a:0',
                        '-shortest',
                        '-y',
                        output_video_temp.name
                    ]

                    log_info(logger, f"Running ffmpeg: {' '.join(ffmpeg_cmd)}")
                    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, check=False)

                    if result.returncode != 0:
                        log_error(logger, "FFmpeg failed", {
                            "returncode": result.returncode,
                            "stderr": result.stderr
                        })
                        raise RuntimeError(f"FFmpeg failed: {result.stderr}")

                    log_info(logger, "Video processing completed, uploading to R2...")

                    with open(output_video_temp.name, 'rb') as f:
                        video_bytes = f.read()
                        video_upload_result = await r2_service.upload_file_bytes(
                            video_bytes,
                            filename=f"dubbed_{session_id}.mp4",
                            folder="dubbing/final_videos"
                        )

                    final_video_url = video_upload_result["file_url"]
                    log_info(logger, f"Final dubbed video uploaded: {final_video_url}")

                except Exception as e:
                    log_error(logger, "Failed to process video", {"error": str(e)})
                    log_info(logger, "Continuing with audio-only output")

            log_info(logger, "Uploading final dubbed audio to R2...")

            with open(output_temp_audio.name, "rb") as f:
                audio_bytes = f.read()

                upload_result = await r2_service.upload_file_bytes(
                    audio_bytes,
                    filename=f"dubbed_{session_id}.mp3",
                    folder="dubbing/final"
                )

            final_url = upload_result["file_url"]

            await database["dubbing_sessions"].update_one(
                {"_id": obj_id},
                {
                    "$set": {
                        "final_dubbed_audio_url": final_url,
                        "final_dubbed_video_url": final_video_url,
                        "status": "completed",
                        "completed_at": datetime.utcnow(),
                    }
                },
            )

            log_info(logger, f"Dubbing session {session_id} processing completed!")

            updated_session = await database["dubbing_sessions"].find_one({"_id": obj_id})

            completed_count = await database["dubbing_sessions"].count_documents({
                "user_id": user_id,
                "status": "completed"
            })

            if completed_count == 1:
                try:
                    user = await database["users"].find_one({"_id": ObjectId(user_id)})
                    if user and user.get("email"):
                        dubbing_url = final_video_url if final_video_url else final_url

                        log_info(logger, f"Sending first dubbing email to {user['email']}")
                        await EmailService.send_first_dubbing_email(
                            email=user["email"],
                            video_url=dubbing_url
                        )
                except Exception as email_error:
                    log_error(
                        logger,
                        "Failed to send first dubbing email", 
                        {"error": str(email_error)}
                    )

            session_response = DubbingSessionResponse.from_db(updated_session)

            response_content = {
                "message": (
                    "Dubbing processed successfully! Video with dubbed audio ready."
                    if final_video_url
                    else "Dubbing processed successfully!"
                ),
                "final_audio_url": final_url,
                "session": session_response.model_dump(exclude_none=False),
            }

            if final_video_url:
                response_content["final_video_url"] = final_video_url
                log_info(logger, f"Response includes video URL: {final_video_url}")

            return JSONResponse(
                status_code=200,
                content=response_content,
            )

        except requests.RequestException as e:
            log_error(logger, "Failed to download audio files", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to download audio files", "error": str(e)},
            )
        except Exception as e:
            log_error(logger, "Failed to process dubbing session", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to process audio", "error": str(e)},
            )
        finally:
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except Exception as e:
                    log_error(logger, f"Failed to delete temp file {temp_file}", {"error": str(e)})

    @staticmethod
    async def process_collaborative_dubbing(
        session_ids: list[str], _user_id: str
    ) -> JSONResponse:
        """Process and mix multiple dubbing sessions from different users.

        Allows collaborative dubbing where each user dubs a different character.
        All sessions must be from the same transcription.

        Args:
            session_ids: List of session IDs to mix together
            user_id: User requesting the collaborative mix

        Returns:
            JSONResponse with final collaborative audio URL
        """
        temp_files = []
        try:
            AudioSegment = get_audio_segment()
            
            if not session_ids or len(session_ids) == 0:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "At least one session ID is required"},
                )

            sessions = []
            transcription_id = None

            for sid in session_ids:
                session = await database["dubbing_sessions"].find_one(
                    {"_id": ObjectId(sid)}
                )
                if not session:
                    return JSONResponse(
                        status_code=404,
                        content={"detail": f"Session {sid} not found"},
                    )

                if transcription_id is None:
                    transcription_id = session.get("transcription_id")
                elif transcription_id != session.get("transcription_id"):
                    return JSONResponse(
                        status_code=400,
                        content={
                            "detail": "All sessions must be from the same transcription"
                        },
                    )

                sessions.append(session)

            character_ids = [s.get("character_id") for s in sessions]
            if len(character_ids) != len(set(character_ids)):
                seen = set()
                duplicates = []
                for char_id in character_ids:
                    if char_id in seen:
                        char_session = next(s for s in sessions if s.get("character_id") == char_id)
                        duplicates.append(char_session.get("character_name"))
                    seen.add(char_id)

                return JSONResponse(
                    status_code=400,
                    content={
                        "detail": "Cannot mix sessions with duplicate characters",
                        "duplicate_characters": duplicates,
                        "message": "Each session must be for a different character"
                    }
                )

            log_info(
                logger,
                f"Processing collaborative dubbing for {len(sessions)} sessions",
            )

            transcription = await database["transcriptions"].find_one(
                {"_id": ObjectId(transcription_id)}
            )
            if not transcription:
                return JSONResponse(
                    status_code=404, content={"detail": "Transcription not found"}
                )

            background_url = transcription.get("background_audio_url")
            voices_url = transcription.get("voices_audio_url")

            if not background_url or not voices_url:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Transcription missing audio files"},
                )

            log_info(logger, "Downloading background audio...")
            background_response = requests.get(background_url, timeout=60)
            background_response.raise_for_status()
            background_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            background_temp.write(background_response.content)
            background_temp.close()
            temp_files.append(background_temp.name)

            log_info(logger, "Downloading voices audio...")
            voices_response = requests.get(voices_url, timeout=60)
            voices_response.raise_for_status()
            voices_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            voices_temp.write(voices_response.content)
            voices_temp.close()
            temp_files.append(voices_temp.name)

            background_audio = AudioSegment.from_mp3(background_temp.name)
            voices_audio = AudioSegment.from_mp3(voices_temp.name)

            log_info(
                logger,
                f"Audio loaded: background={len(background_audio)}ms, voices={len(voices_audio)}ms",
            )

            modified_voices = voices_audio
            all_character_ids = set()

            for session in sessions:
                character_id = session.get("character_id")
                all_character_ids.add(character_id)

                character_data = next(
                    (
                        c
                        for c in transcription.get("characters", [])
                        if c.get("character_id") == character_id
                    ),
                    None,
                )

                if not character_data:
                    continue

                expected_dialogues = character_data.get("dialogues", [])
                recorded_dialogues = session.get("dialogues_recorded", [])
                recorded_map = {d["dialogue_id"]: d for d in recorded_dialogues}

                for dialogue in expected_dialogues:
                    dialogue_id = dialogue.get("dialogue_id")
                    start_ms = int(dialogue.get("start_time", 0) * 1000)
                    end_ms = int(dialogue.get("end_time", 0) * 1000)
                    silence_duration = end_ms - start_ms

                    log_info(
                        logger,
                        (
                            f"Silencing {character_id} dialogue {dialogue_id} "
                            f"from {start_ms}ms to {end_ms}ms"
                        ),
                    )

                    silence = AudioSegment.silent(duration=silence_duration)
                    modified_voices = (
                        modified_voices[:start_ms]
                        + silence
                        + modified_voices[end_ms:]
                    )

                    if dialogue_id in recorded_map:
                        user_audio_url = recorded_map[dialogue_id].get("audio_url")

                        log_info(
                            logger,
                            f"Downloading user audio for {character_id}/{dialogue_id}...",
                        )
                        user_response = requests.get(user_audio_url, timeout=60)
                        user_response.raise_for_status()

                        file_ext = '.mp3'
                        if '.ogg' in user_audio_url.lower():
                            file_ext = '.ogg'
                        elif '.webm' in user_audio_url.lower():
                            file_ext = '.webm'

                        user_temp = tempfile.NamedTemporaryFile(
                            delete=False, suffix=file_ext
                        )
                        user_temp.write(user_response.content)
                        user_temp.close()
                        temp_files.append(user_temp.name)

                        user_audio = AudioSegment.from_file(user_temp.name)

                        target_dbfs = voices_audio.dBFS
                        change_in_dbfs = target_dbfs - user_audio.dBFS
                        user_audio = user_audio.apply_gain(change_in_dbfs)

                        user_duration_ms = len(user_audio)

                        if user_duration_ms > silence_duration:
                            log_info(
                                logger,
                                (
                                    f"Trimming {character_id} audio from "
                                    f"{user_duration_ms}ms to {silence_duration}ms"
                                ),
                            )
                            user_audio = user_audio[:silence_duration]
                        elif user_duration_ms < silence_duration:
                            padding = AudioSegment.silent(
                                duration=silence_duration - user_duration_ms
                            )
                            log_info(
                                logger,
                                (
                                    f"Padding {character_id} audio from "
                                    f"{user_duration_ms}ms to {silence_duration}ms"
                                ),
                            )

                            user_audio = user_audio + padding

                        log_info(
                            logger, f"Overlaying {character_id} audio at {start_ms}ms"
                        )
                        modified_voices = modified_voices.overlay(
                            user_audio, position=start_ms
                        )

            log_info(logger, "Mixing background and voices...")
            final_audio = background_audio.overlay(modified_voices)

            output_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            output_temp.close()
            temp_files.append(output_temp.name)

            log_info(logger, "Exporting final collaborative audio...")
            final_audio.export(output_temp.name, format="mp3", bitrate="192k")

            log_info(logger, "Uploading final collaborative dubbed audio to R2...")
            r2_service = R2StorageService()

            with open(output_temp.name, "rb") as f:
                audio_bytes = f.read()

                upload_result = await r2_service.upload_file_bytes(
                    audio_bytes,
                    filename=f"collaborative_dubbed_{'_'.join(session_ids[:3])}.mp3",
                    folder="dubbing/collaborative",
                )

            final_url = upload_result["file_url"]

            log_info(
                logger, f"Collaborative dubbing completed! Characters: {all_character_ids}"
            )

            return JSONResponse(
                status_code=200,
                content={
                    "message": "Collaborative dubbing processed successfully!",
                    "final_audio_url": final_url,
                    "sessions_processed": len(sessions),
                    "characters_dubbed": list(all_character_ids),
                    "transcription_id": transcription_id,
                },
            )

        except requests.RequestException as e:
            log_error(logger, "Failed to download audio files", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to download audio files", "error": str(e)},
            )
        except Exception as e:
            log_error(
                logger, "Failed to process collaborative dubbing", {"error": str(e)}
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to process audio", "error": str(e)},
            )
        finally:
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.unlink(temp_file)
                except Exception as e:
                    log_error(
                        logger,
                        f"Failed to delete temp file {temp_file}",
                        {"error": str(e)},
                    )

    @staticmethod
    async def get_transcription_dubbing_info(transcription_id: str) -> JSONResponse:
        """Get dubbing information for a transcription.

        Shows which characters are available and which are already being dubbed.
        Useful for collaborative dubbing to see what's available.

        Args:
            transcription_id: Transcription ID

        Returns:
            JSONResponse with character availability and active sessions
        """
        try:
            transcription = await database["transcriptions"].find_one(
                {"_id": ObjectId(transcription_id)}
            )
            if not transcription:
                return JSONResponse(
                    status_code=404, content={"detail": "Transcription not found"}
                )

            active_sessions = await database["dubbing_sessions"].find(
                {"transcription_id": transcription_id, "status": {"$ne": "deleted"}}
            ).to_list(length=None)

            characters = []
            taken_characters = {}

            for session in active_sessions:
                char_id = session.get("character_id")
                if char_id not in taken_characters:
                    taken_characters[char_id] = []
                taken_characters[char_id].append({
                    "session_id": str(session.get("_id")),
                    "user_id": session.get("user_id"),
                    "status": session.get("status"),
                    "dialogues_count": len(session.get("dialogues_recorded", [])),
                })

            for character in transcription.get("characters", []):
                char_id = character.get("character_id")
                char_name = character.get("character_name")
                dialogues_count = len(character.get("dialogues", []))

                characters.append({
                    "character_id": char_id,
                    "character_name": char_name,
                    "dialogues_count": dialogues_count,
                    "is_available": True,
                    "active_sessions": taken_characters.get(char_id, []),
                    "active_sessions_count": len(taken_characters.get(char_id, [])),
                })

            movie_id = transcription.get("movie_id")
            clip_scene_id = transcription.get("clip_scene_id")

            return JSONResponse(
                status_code=200,
                content={
                    "transcription_id": transcription_id,
                    "movie_id": movie_id,
                    "clip_scene_id": clip_scene_id,
                    "total_characters": len(characters),
                    "total_active_sessions": len(active_sessions),
                    "characters": characters,
                    "shareable_info": {
                        "message": (
                            "Share this transcription_id with friends! "
                            "Everyone can dub any character they want."
                        ),
                        "transcription_id": transcription_id,
                        "url_format": (
                            f"http://your-frontend.com/dub/{transcription_id}"
                        ),
                        "note": (
                            "For collaborative dubbing, use different characters "
                            "and mix sessions together."
                        ),
                    },
                },
            )

        except (InvalidId, PyMongoError) as e:
            log_error(logger, "Failed to get dubbing info", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to get dubbing info", "error": str(e)},
            )
