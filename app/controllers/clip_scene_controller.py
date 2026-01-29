"""
ClipScene controller: business logic for creating, retrieving,
updating and deleting clip scenes. Stores documents in MongoDB.
"""
# pylint: disable=W0718,R0801
from datetime import datetime
from math import ceil

from fastapi.responses import JSONResponse
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.config.database import database
from app.models.clip_scene_model import ClipSceneCreate, ClipSceneUpdate, ClipSceneResponse
from app.utils.logger import get_logger, log_info, log_error

logger = get_logger(__name__)


class ClipSceneController:
    """Business logic for clip scene CRUD operations."""

    @staticmethod
    async def create_clip_scene(clip_scene_data: ClipSceneCreate) -> JSONResponse:
        """
        Create a new clip scene.

        Args:
            clip_scene_data: ClipScene creation data

        Returns:
            JSONResponse with created clip scene data

        Raises:
            PyMongoError: If database operation fails
        """
        try:
            collection = database["clips_scenes"]
            movies_collection = database["movies"]

            try:
                movie_oid = ObjectId(clip_scene_data.movie_id)
            except InvalidId:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid movie ID format"}
                )

            movie = await movies_collection.find_one({"_id": movie_oid})
            if not movie:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Movie not found"}
                )

            clip_scene_dict = {
                "scene_name": clip_scene_data.scene_name,
                "description": clip_scene_data.description,
                "movie_id": clip_scene_data.movie_id,
                "characters": clip_scene_data.characters,
                "image_url": clip_scene_data.image_url,
                "video_url": clip_scene_data.video_url,
                "transcription": clip_scene_data.transcription,
                "timestamp": datetime.utcnow()
            }

            result = await collection.insert_one(clip_scene_dict)

            await movies_collection.update_one(
                {"_id": movie_oid},
                {"$addToSet": {"clips_scenes_list": str(result.inserted_id)}}
            )

            created_clip_scene = await collection.find_one({"_id": result.inserted_id})
            response = ClipSceneResponse.from_mongo(created_clip_scene)

            log_info(logger, f"ClipScene created: {result.inserted_id}")

            return JSONResponse(
                status_code=201,
                content=response.model_dump(by_alias=True)
            )
        except PyMongoError as e:
            log_error(logger, "Error creating clip scene", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to create clip scene", "error": str(e)}
            )

    @staticmethod
    async def get_clip_scene_by_id(clip_scene_id: str) -> JSONResponse:
        """
        Retrieve a clip scene by ID.

        Args:
            clip_scene_id: ClipScene ID

        Returns:
            JSONResponse with clip scene data

        Raises:
            InvalidId: If clip_scene_id is not a valid ObjectId
            PyMongoError: If database operation fails
        """
        try:
            oid = ObjectId(clip_scene_id)
        except InvalidId:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid clip scene ID format"}
            )

        try:
            collection = database["clips_scenes"]
            clip_scene = await collection.find_one({"_id": oid})

            if not clip_scene:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Clip scene not found"}
                )

            response = ClipSceneResponse.from_mongo(clip_scene)

            return JSONResponse(
                status_code=200,
                content=response.model_dump(by_alias=True)
            )
        except PyMongoError as e:
            log_error(logger, "Error retrieving clip scene", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to retrieve clip scene", "error": str(e)}
            )

    @staticmethod
    async def get_clips_scenes_by_movie(
        movie_id: str,
        page: int = 1,
        page_size: int = 10
    ) -> JSONResponse:
        """
        Retrieve all clip scenes for a specific movie with pagination.

        Args:
            movie_id: Movie ID to filter by
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            JSONResponse with paginated clip scenes data

        Raises:
            InvalidId: If movie_id is not a valid ObjectId
            PyMongoError: If database operation fails
        """
        try:
            ObjectId(movie_id)
        except InvalidId:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid movie ID format"}
            )

        try:
            collection = database["clips_scenes"]

            query = {"movie_id": movie_id}
            total_items = await collection.count_documents(query)

            skip = (page - 1) * page_size
            cursor = collection.find(query).skip(skip).limit(page_size)
            clips_scenes = await cursor.to_list(length=page_size)

            clips_scenes_response = [
                ClipSceneResponse.from_mongo(clip_scene).model_dump(by_alias=True)
                for clip_scene in clips_scenes
            ]

            total_pages = ceil(total_items / page_size) if total_items > 0 else 0

            return JSONResponse(
                status_code=200,
                content={
                    "data": clips_scenes_response,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_items": total_items,
                        "total_pages": total_pages
                    }
                }
            )
        except PyMongoError as e:
            log_error(logger, "Error retrieving clips scenes", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to retrieve clips scenes", "error": str(e)}
            )

    @staticmethod
    async def update_clip_scene(clip_scene_id: str, updates: ClipSceneUpdate) -> JSONResponse:
        """
        Update a clip scene by ID.

        Args:
            clip_scene_id: ClipScene ID
            updates: Fields to update

        Returns:
            JSONResponse with updated clip scene data

        Raises:
            InvalidId: If clip_scene_id is not a valid ObjectId
            PyMongoError: If database operation fails
        """
        try:
            oid = ObjectId(clip_scene_id)
        except InvalidId:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid clip scene ID format"}
            )

        try:
            collection = database["clips_scenes"]

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
                    content={"detail": "Clip scene not found"}
                )

            updated_clip_scene = await collection.find_one({"_id": oid})
            response = ClipSceneResponse.from_mongo(updated_clip_scene)

            log_info(logger, f"ClipScene updated: {clip_scene_id}")

            return JSONResponse(
                status_code=200,
                content=response.model_dump(by_alias=True)
            )
        except PyMongoError as e:
            log_error(logger, "Error updating clip scene", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to update clip scene", "error": str(e)}
            )

    @staticmethod
    async def delete_clip_scene(clip_scene_id: str) -> JSONResponse:
        """
        Delete a clip scene by ID.

        Args:
            clip_scene_id: ClipScene ID

        Returns:
            JSONResponse with deletion confirmation

        Raises:
            InvalidId: If clip_scene_id is not a valid ObjectId
            PyMongoError: If database operation fails
        """
        try:
            oid = ObjectId(clip_scene_id)
        except InvalidId:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid clip scene ID format"}
            )

        try:
            collection = database["clips_scenes"]
            movies_collection = database["movies"]

            clip_scene = await collection.find_one({"_id": oid})
            if not clip_scene:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Clip scene not found"}
                )

            await collection.delete_one({"_id": oid})

            try:
                movie_oid = ObjectId(clip_scene["movie_id"])
                await movies_collection.update_one(
                    {"_id": movie_oid},
                    {"$pull": {"clips_scenes_list": clip_scene_id}}
                )
            except (InvalidId, KeyError):
                pass

            log_info(logger, f"ClipScene deleted: {clip_scene_id}")

            return JSONResponse(
                status_code=200,
                content={"message": f"Clip scene {clip_scene_id} deleted successfully"}
            )
        except PyMongoError as e:
            log_error(logger, "Error deleting clip scene", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to delete clip scene", "error": str(e)}
            )
