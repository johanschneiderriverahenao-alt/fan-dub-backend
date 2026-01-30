"""
FastAPI views for dubbing session endpoints.

Endpoints:
 - POST /dubbing-sessions/                     -> create dubbing session
 - POST /dubbing-sessions/{id}/upload-dialogue -> upload recorded dialogue
 - GET /dubbing-sessions/{id}                  -> get session by ID
 - GET /dubbing-sessions/user/me               -> get all user sessions
 - DELETE /dubbing-sessions/{id}               -> delete session
"""

from fastapi import APIRouter, Depends, UploadFile, Query, Form
from fastapi.responses import JSONResponse
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.controllers.dubbing_session_controller import DubbingSessionController
from app.controllers.auth_controller import AuthController
from app.models.dubbing_session_model import DubbingSessionCreate
from app.utils.logger import get_logger, log_info, log_error

logger = get_logger(__name__)

router = APIRouter()


@router.post("/dubbing-sessions/", response_class=JSONResponse)
async def create_dubbing_session(
    session_data: DubbingSessionCreate,
    current_user: dict = Depends(AuthController.get_current_user),
) -> JSONResponse:
    """Create a new dubbing session.

    User selects a character from a transcription to dub.
    Requires authentication.

    Args:
        session_data: Transcription ID and character ID
        current_user: Authenticated user

    Returns:
        JSONResponse with created session
    """
    try:
        user_id = current_user.get("id") or current_user.get("_id")
        log_info(
            logger,
            f"User {user_id} creating dubbing session for character {session_data.character_id}",
        )
        return await DubbingSessionController.create_session(
            user_id, session_data.transcription_id, session_data.character_id
        )
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "create_dubbing_session endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to create session", "error": str(e)},
        )


@router.post("/dubbing-sessions/{session_id}/upload-dialogue", response_class=JSONResponse)
async def upload_dialogue(
    session_id: str,
    dialogue_id: str = Form(...),
    audio_file: UploadFile = None,
    _: dict = Depends(AuthController.get_current_user),
) -> JSONResponse:
    """Upload a recorded dialogue audio for a dubbing session.

    User uploads their recorded audio for a specific dialogue.
    Requires authentication.

    Args:
        session_id: Dubbing session ID
        dialogue_id: ID of the dialogue being recorded
        audio_file: Audio file (.mp3)
        current_user: Authenticated user

    Returns:
        JSONResponse with updated session
    """
    try:
        if not audio_file or not audio_file.filename:
            return JSONResponse(
                status_code=400, content={"detail": "audio_file is required"}
            )

        log_info(
            logger, f"User uploading dialogue {dialogue_id} for session {session_id}"
        )
        return await DubbingSessionController.upload_dialogue(
            session_id, dialogue_id, audio_file
        )
    except (RuntimeError, OSError, PyMongoError) as e:
        log_error(logger, "upload_dialogue endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to upload dialogue", "error": str(e)},
        )


@router.get("/dubbing-sessions/{session_id}", response_class=JSONResponse)
async def get_dubbing_session(
    session_id: str, current_user: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """Get a dubbing session by ID.

    User can only view their own sessions.
    Requires authentication.

    Args:
        session_id: Session ID
        current_user: Authenticated user

    Returns:
        JSONResponse with session data
    """
    try:
        user_id = current_user.get("id") or current_user.get("_id")
        log_info(logger, f"User {user_id} fetching session {session_id}")
        return await DubbingSessionController.get_session(session_id, user_id)
    except (InvalidId, RuntimeError, PyMongoError) as e:
        log_error(logger, "get_dubbing_session endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500, content={"detail": "Failed to get session", "error": str(e)}
        )


@router.get("/dubbing-sessions/{session_id}/dialogues", response_class=JSONResponse)
async def get_session_dialogues(
    session_id: str, current_user: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """Get all dialogues for a dubbing session with recording status.

    Shows which dialogues need to be recorded and which are already done.
    Requires authentication.

    Args:
        session_id: Session ID
        current_user: Authenticated user

    Returns:
        JSONResponse with dialogues list and progress
    """
    try:
        user_id = current_user.get("id") or current_user.get("_id")
        log_info(logger, f"User {user_id} fetching dialogues for session {session_id}")
        return await DubbingSessionController.get_session_dialogues(session_id, user_id)
    except (InvalidId, RuntimeError, PyMongoError) as e:
        log_error(logger, "get_session_dialogues endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500, content={"detail": "Failed to get dialogues", "error": str(e)}
        )


@router.get("/dubbing-sessions/user/me", response_class=JSONResponse)
async def get_my_dubbing_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(AuthController.get_current_user),
) -> JSONResponse:
    """Get all dubbing sessions for the authenticated user.

    Returns paginated list of user's dubbing sessions.
    Requires authentication.

    Args:
        page: Page number
        page_size: Items per page
        current_user: Authenticated user

    Returns:
        JSONResponse with paginated sessions
    """
    try:
        user_id = current_user.get("id") or current_user.get("_id")
        log_info(logger, f"User {user_id} fetching their sessions")
        return await DubbingSessionController.get_user_sessions(user_id, page, page_size)
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "get_my_dubbing_sessions endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to get sessions", "error": str(e)},
        )


@router.delete("/dubbing-sessions/{session_id}", response_class=JSONResponse)
async def delete_dubbing_session(
    session_id: str, current_user: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """Delete a dubbing session.

    User can only delete their own sessions.
    Requires authentication.

    Args:
        session_id: Session ID
        current_user: Authenticated user

    Returns:
        JSONResponse with deletion confirmation
    """
    try:
        user_id = current_user.get("id") or current_user.get("_id")
        log_info(logger, f"User {user_id} deleting session {session_id}")
        return await DubbingSessionController.delete_session(session_id, user_id)
    except (InvalidId, RuntimeError, PyMongoError) as e:
        log_error(logger, "delete_dubbing_session endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to delete session", "error": str(e)},
        )


@router.post("/dubbing-sessions/{session_id}/process", response_class=JSONResponse)
async def process_dubbing_session(
    session_id: str, current_user: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """Process and mix all audio for a dubbing session.

    This endpoint:
    1. Downloads background and voices audio from transcription
    2. Silences original character voice in dialogue time ranges
    3. Overlays user's recorded audio (trimmed/padded to fit exactly)
    4. Mixes everything and generates final dubbed audio
    5. Uploads final audio to R2 storage

    Requirements:
    - All character dialogues must be recorded
    - Session must belong to authenticated user

    Args:
        session_id: Session ID to process
        current_user: Authenticated user

    Returns:
        JSONResponse with final dubbed audio URL
    """
    try:
        user_id = current_user.get("id") or current_user.get("_id")
        log_info(logger, f"User {user_id} processing session {session_id}")
        return await DubbingSessionController.process_dubbing_session(session_id, user_id)
    except (InvalidId, RuntimeError, PyMongoError) as e:
        log_error(logger, "process_dubbing_session endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to process session", "error": str(e)},
        )


@router.post("/dubbing-sessions/collaborative/process", response_class=JSONResponse)
async def process_collaborative_dubbing(
    session_ids: list[str],
    current_user: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """Process collaborative dubbing from multiple users/sessions.

    Allows mixing multiple dubbing sessions where each user dubbed a different character.
    All sessions must be from the same transcription.

    Example use case:
    - User A dubs "Sid" → session_1
    - User B dubs "Manny" → session_2
    - User C dubs "Diego" → session_3
    - POST /collaborative/process with [session_1, session_2, session_3]
    - Result: Final audio with all 3 characters dubbed

    Features:
    - Automatic audio normalization (handles loud/quiet recordings)
    - Time adjustment (trim/pad to fit exact duration)
    - Mixes all characters into one final audio

    Args:
        session_ids: List of session IDs to mix together
        current_user: Authenticated user

    Returns:
        JSONResponse with final collaborative audio URL
    """
    try:
        user_id = current_user.get("id") or current_user.get("_id")
        log_info(logger,
                 f"User {user_id} processing collaborative dubbing for {len(session_ids)} sessions")
        return await DubbingSessionController.process_collaborative_dubbing(session_ids, user_id)
    except (InvalidId, RuntimeError, PyMongoError) as e:
        log_error(logger, "process_collaborative_dubbing endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to process collaborative dubbing", "error": str(e)},
        )


@router.get(
    "/transcription/{transcription_id}/dubbing-info",
    summary="Get Dubbing Collaboration Info",
    description="""
    Get information about which characters are available for dubbing.

    **Perfect for sharing with friends!**

    Shows:
    - Available characters (no one dubbing them yet)
    - Taken characters (someone is already dubbing)
    - Active sessions for each character

    **Frontend Flow:**
    1. User sees transcription they want to dub
    2. Calls this endpoint to see available characters
    3. User selects a character
    4. User shares the transcription_id with friends via:
       - Copy/paste the transcription_id
       - Generate QR code with: `http://your-app.com/dub/{transcription_id}`
       - Share direct link
    5. Friends open the link, see available characters (excluding taken ones)
    6. Each friend picks a different character
    7. When ready, anyone calls /collaborative/process with all session_ids

    **UI Suggestion:**
    ```
    Character: Sid (3 dialogues) ✅ AVAILABLE
    Character: Manny (1 dialogue) ❌ Taken by @user123
    Character: Diego (1 dialogue) ✅ AVAILABLE

    [Share Link] [QR Code]
    ```
    """,
    response_description="Character availability and shareable information",
)
async def get_dubbing_info(
    transcription_id: str,
    _: dict = Depends(AuthController.get_current_user),
):
    """Get character availability for collaborative dubbing."""
    return await DubbingSessionController.get_transcription_dubbing_info(
        transcription_id
    )
