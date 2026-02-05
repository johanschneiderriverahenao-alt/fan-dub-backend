"""
Saga controller: business logic for creating, retrieving,
updating and deleting sagas. Stores documents in MongoDB.
"""
# pylint: disable=W0718,R0801
from datetime import datetime
from math import ceil

from fastapi.responses import JSONResponse
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.config.database import database
from app.models.saga_model import SagaCreate, SagaUpdate, SagaResponse
from app.utils.logger import get_logger, log_info, log_error

logger = get_logger(__name__)


class SagaController:
    """Business logic for saga CRUD operations."""

    @staticmethod
    async def create_saga(saga_data: SagaCreate) -> JSONResponse:
        """
        Create a new saga.

        Args:
            saga_data: Saga creation data

        Returns:
            JSONResponse with created saga data

        Raises:
            PyMongoError: If database operation fails
        """
        try:
            collection = database["sagas"]
            companies_collection = database["companies"]

            try:
                company_oid = ObjectId(saga_data.company_id)
            except InvalidId:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid company ID format"}
                )

            company = await companies_collection.find_one({"_id": company_oid})
            if not company:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Company not found"}
                )

            saga_dict = {
                "saga_name": saga_data.saga_name,
                "description": saga_data.description,
                "company_id": saga_data.company_id,
                "image_url": saga_data.image_url,
                "movies_list": [],
                "timestamp": datetime.utcnow()
            }

            result = await collection.insert_one(saga_dict)

            await companies_collection.update_one(
                {"_id": company_oid},
                {"$addToSet": {"sagas_list": str(result.inserted_id)}}
            )

            created_saga = await collection.find_one({"_id": result.inserted_id})
            response = SagaResponse.from_mongo(created_saga)

            log_info(logger, f"Saga created: {result.inserted_id}")

            return JSONResponse(
                status_code=201,
                content=response.model_dump(by_alias=True)
            )
        except PyMongoError as e:
            log_error(logger, "Error creating saga", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to create saga", "error": str(e)}
            )

    @staticmethod
    async def get_saga_by_id(saga_id: str) -> JSONResponse:
        """
        Retrieve a saga by ID.

        Args:
            saga_id: Saga ID

        Returns:
            JSONResponse with saga data

        Raises:
            InvalidId: If saga_id is not a valid ObjectId
            PyMongoError: If database operation fails
        """
        try:
            oid = ObjectId(saga_id)
        except InvalidId:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid saga ID format"}
            )

        try:
            collection = database["sagas"]
            saga = await collection.find_one({"_id": oid})

            if not saga:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Saga not found"}
                )

            response = SagaResponse.from_mongo(saga)
            return JSONResponse(
                status_code=200,
                content=response.model_dump(by_alias=True)
            )
        except PyMongoError as e:
            log_error(logger, "Error fetching saga", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to fetch saga", "error": str(e)}
            )

    @staticmethod
    async def get_all_sagas(page: int = 1, page_size: int = 10) -> JSONResponse:
        """
        Retrieve all sagas with pagination.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            JSONResponse with paginated saga list

        Raises:
            PyMongoError: If database operation fails
        """
        try:
            collection = database["sagas"]

            skip = (page - 1) * page_size

            total_count = await collection.count_documents({})

            cursor = collection.find({}).skip(skip).limit(page_size).sort("timestamp", -1)
            sagas = await cursor.to_list(length=page_size)

            sagas_response = [
                SagaResponse.from_mongo(saga).model_dump(by_alias=True)
                for saga in sagas
            ]

            total_pages = ceil(total_count / page_size) if page_size > 0 else 0

            return JSONResponse(
                status_code=200,
                content={
                    "data": sagas_response,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_items": total_count,
                        "total_pages": total_pages
                    }
                }
            )
        except PyMongoError as e:
            log_error(logger, "Error fetching sagas", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to fetch sagas", "error": str(e)}
            )

    @staticmethod
    async def get_sagas_by_company(company_id: str,
                                   page: int = 1,
                                   page_size: int = 10) -> JSONResponse:
        """
        Retrieve all sagas for a specific company with pagination.

        Args:
            company_id: Company ID
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            JSONResponse with paginated saga list

        Raises:
            PyMongoError: If database operation fails
        """
        try:
            collection = database["sagas"]

            skip = (page - 1) * page_size

            total_count = await collection.count_documents({"company_id": company_id})

            cursor = (
                collection.find({"company_id": company_id})
                .skip(skip)
                .limit(page_size)
                .sort("timestamp", -1)
            )
            sagas = await cursor.to_list(length=page_size)

            sagas_response = [
                SagaResponse.from_mongo(saga).model_dump(by_alias=True)
                for saga in sagas
            ]

            total_pages = ceil(total_count / page_size) if page_size > 0 else 0

            return JSONResponse(
                status_code=200,
                content={
                    "data": sagas_response,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_items": total_count,
                        "total_pages": total_pages
                    }
                }
            )
        except PyMongoError as e:
            log_error(logger, "Error fetching sagas by company", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to fetch sagas", "error": str(e)}
            )

    @staticmethod
    async def update_saga(saga_id: str, updates: SagaUpdate) -> JSONResponse:
        """
        Update a saga by ID.

        Args:
            saga_id: Saga ID
            updates: Fields to update

        Returns:
            JSONResponse with updated saga data

        Raises:
            InvalidId: If saga_id is not a valid ObjectId
            PyMongoError: If database operation fails
        """
        try:
            oid = ObjectId(saga_id)
        except InvalidId:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid saga ID format"}
            )

        try:
            collection = database["sagas"]

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
                    content={"detail": "Saga not found"}
                )

            updated_saga = await collection.find_one({"_id": oid})
            response = SagaResponse.from_mongo(updated_saga)

            log_info(logger, f"Saga updated: {saga_id}")

            return JSONResponse(
                status_code=200,
                content=response.model_dump(by_alias=True)
            )
        except PyMongoError as e:
            log_error(logger, "Error updating saga", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to update saga", "error": str(e)}
            )

    @staticmethod
    async def delete_saga(saga_id: str) -> JSONResponse:
        """
        Delete a saga by ID.

        Args:
            saga_id: Saga ID

        Returns:
            JSONResponse with deletion confirmation

        Raises:
            InvalidId: If saga_id is not a valid ObjectId
            PyMongoError: If database operation fails
        """
        try:
            oid = ObjectId(saga_id)
        except InvalidId:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid saga ID format"}
            )

        try:
            collection = database["sagas"]
            companies_collection = database["companies"]
            movies_collection = database["movies"]

            saga = await collection.find_one({"_id": oid})
            if not saga:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Saga not found"}
                )

            movies_deleted = await movies_collection.delete_many({"saga_id": saga_id})
            log_info(logger, f"Deleted {movies_deleted.deleted_count} movies from saga {saga_id}")

            await collection.delete_one({"_id": oid})

            if saga.get("company_id"):
                try:
                    company_oid = ObjectId(saga["company_id"])
                    await companies_collection.update_one(
                        {"_id": company_oid},
                        {"$pull": {"sagas_list": saga_id}}
                    )
                except (InvalidId, Exception) as e:
                    log_error(logger, "Error removing saga from company", {"error": str(e)})

            log_info(logger, f"Saga deleted: {saga_id}")

            return JSONResponse(
                status_code=200,
                content={
                    "detail": "Saga deleted successfully",
                    "saga_id": saga_id,
                    "movies_deleted": movies_deleted.deleted_count
                }
            )
        except PyMongoError as e:
            log_error(logger, "Error deleting saga", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to delete saga", "error": str(e)}
            )
