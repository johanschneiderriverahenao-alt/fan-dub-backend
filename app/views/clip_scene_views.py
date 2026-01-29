"""
FastAPI views for clip scene endpoints.

Endpoints:
 - POST /clips-scenes/                        -> create clip scene
 - GET /clips-scenes/{id}                     -> get clip scene by ID
 - GET /clips-scenes/movie/{movie_id}         -> get clip scenes by movie (paginated)
 - PUT /clips-scenes/{id}                     -> update clip scene by ID
 - DELETE /clips-scenes/{id}                  -> delete clip scene by ID (admin only)
"""
# pylint: disable=R0801

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.controllers.clip_scene_controller import ClipSceneController
from app.controllers.auth_controller import AuthController
from app.models.clip_scene_model import ClipSceneCreate, ClipSceneUpdate
from app.utils.logger import get_logger, log_info, log_error
from app.utils.dependencies import get_current_admin

logger = get_logger(__name__)

router = APIRouter()


@router.post("/clips-scenes/", response_class=JSONResponse)
async def create_clip_scene(
    clip_scene: ClipSceneCreate,
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """
    Create a new clip scene.

    Args:
        clip_scene: ClipScene data to create

    Returns:
        JSONResponse with created clip scene
    """
    try:
        log_info(logger, f"Creating clip scene: {clip_scene.scene_name}")
        return await ClipSceneController.create_clip_scene(clip_scene)
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "create_clip_scene endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to create clip scene", "error": str(e)}
        )


@router.get("/clips-scenes/{clip_scene_id}", response_class=JSONResponse)
async def get_clip_scene_by_id(
    clip_scene_id: str,
    _: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """
    Get a clip scene by ID.

    Args:
        clip_scene_id: The clip scene ID

    Returns:
        JSONResponse with clip scene data
    """
    try:
        log_info(logger, f"Fetching clip scene: {clip_scene_id}")
        return await ClipSceneController.get_clip_scene_by_id(clip_scene_id)
    except InvalidId:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid clip scene ID format"}
        )
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "get_clip_scene_by_id endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to fetch clip scene", "error": str(e)}
        )


@router.get("/clips-scenes/movie/{movie_id}", response_class=JSONResponse)
async def get_clips_scenes_by_movie(
    movie_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    _: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """
    Get all clip scenes for a specific movie with pagination.

    Args:
        movie_id: The movie ID to filter by
        page: Page number (default: 1)
        page_size: Items per page (default: 10, max: 100)

    Returns:
        JSONResponse with paginated clip scenes list
    """
    try:
        log_info(logger, f"Fetching clip scenes for movie: {movie_id}")
        return await ClipSceneController.get_clips_scenes_by_movie(movie_id, page, page_size)
    except InvalidId:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid movie ID format"}
        )
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "get_clips_scenes_by_movie endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to fetch clip scenes", "error": str(e)}
        )


@router.put("/clips-scenes/{clip_scene_id}", response_class=JSONResponse)
async def update_clip_scene(
    clip_scene_id: str,
    updates: ClipSceneUpdate,
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """
    Update a clip scene by ID.

    Args:
        clip_scene_id: The clip scene ID
        updates: Fields to update

    Returns:
        JSONResponse with updated clip scene data
    """
    try:
        log_info(logger, f"Updating clip scene: {clip_scene_id}")
        return await ClipSceneController.update_clip_scene(clip_scene_id, updates)
    except InvalidId:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid clip scene ID format"}
        )
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "update_clip_scene endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to update clip scene", "error": str(e)}
        )


@router.delete("/clips-scenes/{clip_scene_id}", response_class=JSONResponse)
async def delete_clip_scene(
    clip_scene_id: str,
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """
    Delete a clip scene by ID. Admin only.

    Args:
        clip_scene_id: The clip scene ID

    Returns:
        JSONResponse with deletion confirmation
    """
    try:
        log_info(logger, f"Deleting clip scene: {clip_scene_id}")
        return await ClipSceneController.delete_clip_scene(clip_scene_id)
    except InvalidId:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid clip scene ID format"}
        )
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "delete_clip_scene endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to delete clip scene", "error": str(e)}
        )
