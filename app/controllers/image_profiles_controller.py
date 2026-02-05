"""
ImageProfile controller: business logic for creating, retrieving,
updating and deleting image profiles. Stores documents in MongoDB.
"""
# pylint: disable=W0718,R0914,R0911
from datetime import datetime
from math import ceil
from typing import Dict, List

from fastapi.responses import JSONResponse
from fastapi import UploadFile
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.config.database import database
from app.models.image_profiles_model import (
    ImageProfileCreate,
    ImageProfileUpdate,
    ImageProfileResponse
)
from app.services.r2_storage_service import r2_service
from app.utils.logger import get_logger, log_info, log_error

logger = get_logger(__name__)


class ImageProfileController:
    """Business logic for image profile CRUD operations."""

    @staticmethod
    async def create_image_profile(
        image_profile_data: ImageProfileCreate,
        image_file: UploadFile
    ) -> JSONResponse:
        """
        Create a new image profile with file upload.

        Args:
            image_profile_data: ImageProfile creation data
            image_file: Image file to upload

        Returns:
            JSONResponse with created image profile data

        Raises:
            PyMongoError: If database operation fails
        """
        try:
            collection = database["image_profiles"]

            if not image_file.content_type.startswith('image/'):
                return JSONResponse(
                    status_code=400,
                    content={"detail": "File must be an image"}
                )

            image_profile_dict = {
                "name": image_profile_data.name,
                "company_associated": image_profile_data.company_associated,
                "saga_associated": image_profile_data.saga_associated,
                "created_at": datetime.utcnow()
            }

            result = await collection.insert_one(image_profile_dict)
            image_profile_id = str(result.inserted_id)

            upload_result = await r2_service.upload_file(
                file=image_file,
                folder="profile-images",
                custom_filename=f"{image_profile_id}_{image_file.filename}"
            )

            await collection.update_one(
                {"_id": result.inserted_id},
                {
                    "$set": {
                        "image_url": upload_result["file_url"],
                        "image_key": upload_result["file_key"],
                        "image_filename": upload_result["original_filename"],
                        "image_content_type": upload_result["content_type"],
                        "image_size": upload_result["size"],
                        "image_uploaded_at": datetime.utcnow()
                    }
                }
            )

            created_image_profile = await collection.find_one({"_id": result.inserted_id})
            response = ImageProfileResponse.from_mongo(created_image_profile)

            log_info(logger, f"ImageProfile created: {result.inserted_id}")

            return JSONResponse(
                status_code=201,
                content={
                    "message": "Image profile created successfully",
                    "image_profile": response.model_dump(by_alias=True),
                    "upload_info": {
                        "file_key": upload_result["file_key"],
                        "file_url": upload_result["file_url"],
                        "size": upload_result["size"]
                    }
                }
            )
        except RuntimeError as e:
            log_error(logger, "Upload error during image profile creation", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": str(e)}
            )
        except PyMongoError as e:
            log_error(logger, "Error creating image profile", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to create image profile", "error": str(e)}
            )

    @staticmethod
    async def get_image_profile_by_id(image_profile_id: str) -> JSONResponse:
        """
        Retrieve an image profile by ID.

        Args:
            image_profile_id: ImageProfile ID

        Returns:
            JSONResponse with image profile data

        Raises:
            InvalidId: If image_profile_id is not a valid ObjectId
            PyMongoError: If database operation fails
        """
        try:
            oid = ObjectId(image_profile_id)
        except InvalidId:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid image profile ID format"}
            )

        try:
            collection = database["image_profiles"]
            image_profile = await collection.find_one({"_id": oid})

            if not image_profile:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Image profile not found"}
                )

            response = ImageProfileResponse.from_mongo(image_profile)

            return JSONResponse(
                status_code=200,
                content=response.model_dump(by_alias=True)
            )
        except PyMongoError as e:
            log_error(logger, "Error retrieving image profile", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to retrieve image profile", "error": str(e)}
            )

    @staticmethod
    async def get_all_image_profiles(
        page: int = 1,
        page_size: int = 20,
        company_associated: str = None,
        saga_associated: str = None
    ) -> JSONResponse:
        """
        Retrieve all image profiles with pagination and optional filters.
        Results are grouped by company_associated -> saga_associated -> images.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page
            company_associated: Optional filter by company
            saga_associated: Optional filter by saga

        Returns:
            JSONResponse with grouped and paginated image profiles data

        Raises:
            PyMongoError: If database operation fails
        """
        try:
            collection = database["image_profiles"]

            query = {}
            if company_associated:
                query["company_associated"] = company_associated
            if saga_associated:
                query["saga_associated"] = saga_associated

            total_items = await collection.count_documents(query)

            skip = (page - 1) * page_size
            cursor = collection.find(query).skip(skip).limit(page_size)
            image_profiles = await cursor.to_list(length=page_size)

            grouped_data: Dict[str, Dict[str, List[dict]]] = {}

            for profile in image_profiles:
                company = profile.get("company_associated", "Unknown")
                saga = profile.get("saga_associated", "Unknown")

                if company not in grouped_data:
                    grouped_data[company] = {}

                if saga not in grouped_data[company]:
                    grouped_data[company][saga] = []

                grouped_data[company][saga].append({
                    "id": str(profile["_id"]),
                    "name": profile.get("name"),
                    "image_url": profile.get("image_url")
                })

            total_pages = ceil(total_items / page_size) if total_items > 0 else 0

            return JSONResponse(
                status_code=200,
                content={
                    "data": grouped_data,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_items": total_items,
                        "total_pages": total_pages
                    }
                }
            )
        except PyMongoError as e:
            log_error(logger, "Error retrieving image profiles", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to retrieve image profiles", "error": str(e)}
            )

    @staticmethod
    async def update_image_profile(
        image_profile_id: str,
        updates: ImageProfileUpdate
    ) -> JSONResponse:
        """
        Update an image profile by ID.

        Args:
            image_profile_id: ImageProfile ID
            updates: Fields to update

        Returns:
            JSONResponse with updated image profile data

        Raises:
            InvalidId: If image_profile_id is not a valid ObjectId
            PyMongoError: If database operation fails
        """
        try:
            oid = ObjectId(image_profile_id)
        except InvalidId:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid image profile ID format"}
            )

        try:
            collection = database["image_profiles"]

            update_data = {k: v for k, v in updates.model_dump(exclude_unset=True).items()
                           if v is not None}

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
                    content={"detail": "Image profile not found"}
                )

            updated_image_profile = await collection.find_one({"_id": oid})
            response = ImageProfileResponse.from_mongo(updated_image_profile)

            log_info(logger, f"ImageProfile updated: {image_profile_id}")

            return JSONResponse(
                status_code=200,
                content=response.model_dump(by_alias=True)
            )
        except PyMongoError as e:
            log_error(logger, "Error updating image profile", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to update image profile", "error": str(e)}
            )

    @staticmethod
    async def delete_image_profile(image_profile_id: str) -> JSONResponse:
        """
        Delete an image profile by ID.

        Args:
            image_profile_id: ImageProfile ID

        Returns:
            JSONResponse with deletion confirmation

        Raises:
            InvalidId: If image_profile_id is not a valid ObjectId
            PyMongoError: If database operation fails
        """
        try:
            oid = ObjectId(image_profile_id)
        except InvalidId:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid image profile ID format"}
            )

        try:
            collection = database["image_profiles"]

            image_profile = await collection.find_one({"_id": oid})
            if not image_profile:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Image profile not found"}
                )

            if image_profile.get("image_key"):
                try:
                    await r2_service.delete_file(image_profile["image_key"])
                    log_info(logger, f"Image deleted from R2: {image_profile['image_key']}")
                except Exception as e:
                    log_error(logger, "Failed to delete image from R2", {"error": str(e)})

            await collection.delete_one({"_id": oid})

            log_info(logger, f"ImageProfile deleted: {image_profile_id}")

            return JSONResponse(
                status_code=200,
                content={"message": f"Image profile {image_profile_id} deleted successfully"}
            )
        except PyMongoError as e:
            log_error(logger, "Error deleting image profile", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to delete image profile", "error": str(e)}
            )

    @staticmethod
    async def upload_image(  # noqa: C901
        image_profile_id: str,
        image_file: UploadFile
    ) -> JSONResponse:
        """
        Upload an image file to R2 and update the image profile.

        Args:
            image_profile_id: ImageProfile ID
            image_file: Image file to upload

        Returns:
            JSONResponse with updated image profile data including image URL

        Raises:
            InvalidId: If image_profile_id is not a valid ObjectId
            RuntimeError: If upload or database operation fails
        """
        try:
            oid = ObjectId(image_profile_id)
        except InvalidId:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid image profile ID format"}
            )

        try:
            collection = database["image_profiles"]

            image_profile = await collection.find_one({"_id": oid})
            if not image_profile:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Image profile not found"}
                )

            if not image_file.content_type.startswith('image/'):
                return JSONResponse(
                    status_code=400,
                    content={"detail": "File must be an image"}
                )

            if image_profile.get("image_url") and image_profile.get("image_key"):
                try:
                    await r2_service.delete_file(image_profile["image_key"])
                    log_info(logger, f"Old image deleted: {image_profile['image_key']}")
                except Exception as e:
                    log_error(logger, "Failed to delete old image", {"error": str(e)})

            upload_result = await r2_service.upload_file(
                file=image_file,
                folder="profile-images",
                custom_filename=f"{image_profile_id}_{image_file.filename}"
            )

            await collection.update_one(
                {"_id": oid},
                {
                    "$set": {
                        "image_url": upload_result["file_url"],
                        "image_key": upload_result["file_key"],
                        "image_filename": upload_result["original_filename"],
                        "image_content_type": upload_result["content_type"],
                        "image_size": upload_result["size"],
                        "image_uploaded_at": datetime.utcnow()
                    }
                }
            )

            updated_image_profile = await collection.find_one({"_id": oid})
            response = ImageProfileResponse.from_mongo(updated_image_profile)

            log_info(logger, f"Image uploaded for image profile: {image_profile_id}")

            return JSONResponse(
                status_code=200,
                content={
                    "message": "Image uploaded successfully",
                    "image_profile": response.model_dump(by_alias=True),
                    "upload_info": {
                        "file_key": upload_result["file_key"],
                        "file_url": upload_result["file_url"],
                        "size": upload_result["size"]
                    }
                }
            )

        except RuntimeError as e:
            log_error(logger, "Upload error", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": str(e)}
            )
        except PyMongoError as e:
            log_error(logger, "Database error during image upload", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to update image profile", "error": str(e)}
            )
        except Exception as e:
            log_error(logger, "Unexpected error during image upload", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Unexpected error occurred", "error": str(e)}
            )
