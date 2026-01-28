"""
Movie controller: business logic for creating, retrieving,
updating and deleting movies. Stores documents in MongoDB.
"""
# pylint: disable=W0718,R0801
from datetime import datetime
from math import ceil

from fastapi.responses import JSONResponse
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.config.database import database
from app.models.movie_model import MovieCreate, MovieUpdate, MovieResponse
from app.utils.logger import get_logger, log_info, log_error

logger = get_logger(__name__)


class MovieController:
    """Business logic for movie CRUD operations."""

    @staticmethod
    async def create_movie(movie_data: MovieCreate) -> JSONResponse:
        """
        Create a new movie.

        Args:
            movie_data: Movie creation data

        Returns:
            JSONResponse with created movie data

        Raises:
            PyMongoError: If database operation fails
        """
        try:
            collection = database["movies"]
            sagas_collection = database["sagas"]

            try:
                saga_oid = ObjectId(movie_data.saga_id)
            except InvalidId:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid saga ID format"}
                )

            saga = await sagas_collection.find_one({"_id": saga_oid})
            if not saga:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Saga not found"}
                )

            movie_dict = {
                "movie_name": movie_data.movie_name,
                "description": movie_data.description,
                "saga_id": movie_data.saga_id,
                "characters_available": movie_data.characters_available,
                "timestamp": datetime.utcnow()
            }

            result = await collection.insert_one(movie_dict)

            await sagas_collection.update_one(
                {"_id": saga_oid},
                {"$addToSet": {"movies_list": str(result.inserted_id)}}
            )

            created_movie = await collection.find_one({"_id": result.inserted_id})
            response = MovieResponse.from_mongo(created_movie)

            log_info(logger, f"Movie created: {result.inserted_id}")

            return JSONResponse(
                status_code=201,
                content=response.model_dump(by_alias=True)
            )
        except PyMongoError as e:
            log_error(logger, "Error creating movie", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to create movie", "error": str(e)}
            )

    @staticmethod
    async def get_movie_by_id(movie_id: str) -> JSONResponse:
        """
        Retrieve a movie by ID.

        Args:
            movie_id: Movie ID

        Returns:
            JSONResponse with movie data

        Raises:
            InvalidId: If movie_id is not a valid ObjectId
            PyMongoError: If database operation fails
        """
        try:
            oid = ObjectId(movie_id)
        except InvalidId:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid movie ID format"}
            )

        try:
            collection = database["movies"]
            movie = await collection.find_one({"_id": oid})

            if not movie:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Movie not found"}
                )

            response = MovieResponse.from_mongo(movie)
            return JSONResponse(
                status_code=200,
                content=response.model_dump(by_alias=True)
            )
        except PyMongoError as e:
            log_error(logger, "Error fetching movie", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to fetch movie", "error": str(e)}
            )

    @staticmethod
    async def get_all_movies(page: int = 1, page_size: int = 10) -> JSONResponse:
        """
        Retrieve all movies with pagination.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            JSONResponse with paginated movie list

        Raises:
            PyMongoError: If database operation fails
        """
        try:
            collection = database["movies"]

            skip = (page - 1) * page_size

            total_count = await collection.count_documents({})

            cursor = collection.find({}).skip(skip).limit(page_size).sort("timestamp", -1)
            movies = await cursor.to_list(length=page_size)

            movies_response = [
                MovieResponse.from_mongo(movie).model_dump(by_alias=True)
                for movie in movies
            ]

            total_pages = ceil(total_count / page_size) if page_size > 0 else 0

            return JSONResponse(
                status_code=200,
                content={
                    "data": movies_response,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_items": total_count,
                        "total_pages": total_pages
                    }
                }
            )
        except PyMongoError as e:
            log_error(logger, "Error fetching movies", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to fetch movies", "error": str(e)}
            )

    @staticmethod
    async def get_movies_by_saga(saga_id: str, page: int = 1, page_size: int = 10) -> JSONResponse:
        """
        Retrieve all movies for a specific saga with pagination.

        Args:
            saga_id: Saga ID
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            JSONResponse with paginated movie list

        Raises:
            PyMongoError: If database operation fails
        """
        try:
            collection = database["movies"]

            skip = (page - 1) * page_size

            total_count = await collection.count_documents({"saga_id": saga_id})

            cursor = (
                collection.find({"saga_id": saga_id})
                .skip(skip)
                .limit(page_size)
                .sort("timestamp", -1)
            )

            movies = await cursor.to_list(length=page_size)

            movies_response = [
                MovieResponse.from_mongo(movie).model_dump(by_alias=True)
                for movie in movies
            ]

            total_pages = ceil(total_count / page_size) if page_size > 0 else 0

            return JSONResponse(
                status_code=200,
                content={
                    "data": movies_response,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_items": total_count,
                        "total_pages": total_pages
                    }
                }
            )
        except PyMongoError as e:
            log_error(logger, "Error fetching movies by saga", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to fetch movies", "error": str(e)}
            )

    @staticmethod
    async def update_movie(movie_id: str, updates: MovieUpdate) -> JSONResponse:
        """
        Update a movie by ID.

        Args:
            movie_id: Movie ID
            updates: Fields to update

        Returns:
            JSONResponse with updated movie data

        Raises:
            InvalidId: If movie_id is not a valid ObjectId
            PyMongoError: If database operation fails
        """
        try:
            oid = ObjectId(movie_id)
        except InvalidId:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid movie ID format"}
            )

        try:
            collection = database["movies"]

            update_data = {
                k: v
                for k, v in updates.model_dump(exclude_unset=True).items()
                if v is not None
            }

            if not update_data:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "No valid fields to update"}
                )

            result = await collection.update_one(
                {"_id": oid},
                {"$set": update_data}
            )

            if result.matched_count == 0:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Movie not found"}
                )

            updated_movie = await collection.find_one({"_id": oid})
            response = MovieResponse.from_mongo(updated_movie)

            log_info(logger, f"Movie updated: {movie_id}")

            return JSONResponse(
                status_code=200,
                content=response.model_dump(by_alias=True)
            )
        except PyMongoError as e:
            log_error(logger, "Error updating movie", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to update movie", "error": str(e)}
            )

    @staticmethod
    async def delete_movie(movie_id: str) -> JSONResponse:
        """
        Delete a movie by ID.

        Args:
            movie_id: Movie ID

        Returns:
            JSONResponse with deletion confirmation

        Raises:
            InvalidId: If movie_id is not a valid ObjectId
            PyMongoError: If database operation fails
        """
        try:
            oid = ObjectId(movie_id)
        except InvalidId:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid movie ID format"}
            )

        try:
            collection = database["movies"]
            sagas_collection = database["sagas"]

            movie = await collection.find_one({"_id": oid})
            if not movie:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Movie not found"}
                )

            await collection.delete_one({"_id": oid})

            if movie.get("saga_id"):
                try:
                    saga_oid = ObjectId(movie["saga_id"])
                    await sagas_collection.update_one(
                        {"_id": saga_oid},
                        {"$pull": {"movies_list": movie_id}}
                    )
                except (InvalidId, Exception) as e:
                    log_error(logger, "Error removing movie from saga", {"error": str(e)})

            log_info(logger, f"Movie deleted: {movie_id}")

            return JSONResponse(
                status_code=200,
                content={"detail": "Movie deleted successfully", "movie_id": movie_id}
            )
        except PyMongoError as e:
            log_error(logger, "Error deleting movie", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to delete movie", "error": str(e)}
            )
