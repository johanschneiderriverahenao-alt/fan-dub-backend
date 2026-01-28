"""
FastAPI views for movie endpoints.

Endpoints:
 - POST /movies/                  -> create movie
 - GET /movies/                   -> get all movies (paginated)
 - GET /movies/{id}               -> get movie by ID
 - GET /movies/saga/{saga_id}     -> get movies by saga (paginated)
 - PUT /movies/{id}               -> update movie by ID
 - DELETE /movies/{id}            -> delete movie by ID
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.controllers.movie_controller import MovieController
from app.controllers.auth_controller import AuthController
from app.models.movie_model import MovieCreate, MovieUpdate
from app.utils.logger import get_logger, log_info, log_error
from app.utils.dependencies import get_current_admin

logger = get_logger(__name__)

router = APIRouter()


@router.post("/movies/", response_class=JSONResponse)
async def create_movie(
    movie: MovieCreate,
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """
    Create a new movie.

    Args:
        movie: Movie data to create

    Returns:
        JSONResponse with created movie
    """
    try:
        log_info(logger, f"Creating movie: {movie.movie_name}")
        return await MovieController.create_movie(movie)
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "create_movie endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to create movie", "error": str(e)}
        )


@router.get("/movies/", response_class=JSONResponse)
async def get_all_movies(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    _: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """
    Get all movies with pagination.

    Args:
        page: Page number (default: 1)
        page_size: Items per page (default: 10, max: 100)

    Returns:
        JSONResponse with paginated movies list
    """
    try:
        log_info(logger, f"Fetching movies - page: {page}, page_size: {page_size}")
        return await MovieController.get_all_movies(page, page_size)
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "get_all_movies endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to fetch movies", "error": str(e)}
        )


@router.get("/movies/{movie_id}", response_class=JSONResponse)
async def get_movie(
    movie_id: str,
    _: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """
    Get a movie by ID.

    Args:
        movie_id: Movie ID

    Returns:
        JSONResponse with movie data
    """
    try:
        log_info(logger, f"Fetching movie: {movie_id}")
        return await MovieController.get_movie_by_id(movie_id)
    except InvalidId:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid movie ID format"}
        )
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "get_movie endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to fetch movie", "error": str(e)}
        )


@router.get("/movies/saga/{saga_id}", response_class=JSONResponse)
async def get_movies_by_saga(
    saga_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    _: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """
    Get all movies for a specific saga with pagination.

    Args:
        saga_id: Saga ID
        page: Page number (default: 1)
        page_size: Items per page (default: 10, max: 100)

    Returns:
        JSONResponse with paginated movies list
    """
    try:
        log_info(logger, f"Fetching movies for saga: {saga_id}")
        return await MovieController.get_movies_by_saga(saga_id, page, page_size)
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "get_movies_by_saga endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to fetch movies", "error": str(e)}
        )


@router.put("/movies/{movie_id}", response_class=JSONResponse)
async def update_movie(
    movie_id: str,
    updates: MovieUpdate,
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """
    Update a movie by ID.

    Args:
        movie_id: Movie ID
        updates: Fields to update

    Returns:
        JSONResponse with updated movie
    """
    try:
        log_info(logger, f"Updating movie: {movie_id}")
        return await MovieController.update_movie(movie_id, updates)
    except InvalidId:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid movie ID format"}
        )
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "update_movie endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to update movie", "error": str(e)}
        )


@router.delete("/movies/{movie_id}", response_class=JSONResponse)
async def delete_movie(
    movie_id: str,
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """
    Delete a movie by ID (Admin only).

    Args:
        movie_id: Movie ID

    Returns:
        JSONResponse with deletion confirmation
    """
    try:
        log_info(logger, f"Deleting movie: {movie_id}")
        return await MovieController.delete_movie(movie_id)
    except InvalidId:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid movie ID format"}
        )
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "delete_movie endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to delete movie", "error": str(e)}
        )
