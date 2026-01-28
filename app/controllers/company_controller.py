"""
Company controller: business logic for creating, retrieving,
updating and deleting companies. Stores documents in MongoDB.
"""
# pylint: disable=W0718,R0801
from datetime import datetime
from math import ceil

from fastapi.responses import JSONResponse
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.config.database import database
from app.models.company_model import CompanyCreate, CompanyUpdate, CompanyResponse
from app.utils.logger import get_logger, log_info, log_error

logger = get_logger(__name__)


class CompanyController:
    """Business logic for company CRUD operations."""

    @staticmethod
    async def create_company(company_data: CompanyCreate) -> JSONResponse:
        """
        Create a new company.

        Args:
            company_data: Company creation data

        Returns:
            JSONResponse with created company data

        Raises:
            PyMongoError: If database operation fails
        """
        try:
            collection = database["companies"]

            company_dict = {
                "companie_name": company_data.companie_name,
                "description": company_data.description,
                "sagas_list": [],
                "timestamp": datetime.utcnow()
            }

            result = await collection.insert_one(company_dict)

            created_company = await collection.find_one({"_id": result.inserted_id})
            response = CompanyResponse.from_mongo(created_company)

            log_info(logger, f"Company created: {result.inserted_id}")

            return JSONResponse(
                status_code=201,
                content=response.model_dump(by_alias=True)
            )
        except PyMongoError as e:
            log_error(logger, "Error creating company", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to create company", "error": str(e)}
            )

    @staticmethod
    async def get_company_by_id(company_id: str) -> JSONResponse:
        """
        Retrieve a company by ID.

        Args:
            company_id: Company ID

        Returns:
            JSONResponse with company data

        Raises:
            InvalidId: If company_id is not a valid ObjectId
            PyMongoError: If database operation fails
        """
        try:
            oid = ObjectId(company_id)
        except InvalidId:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid company ID format"}
            )

        try:
            collection = database["companies"]
            company = await collection.find_one({"_id": oid})

            if not company:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Company not found"}
                )

            response = CompanyResponse.from_mongo(company)
            return JSONResponse(
                status_code=200,
                content=response.model_dump(by_alias=True)
            )
        except PyMongoError as e:
            log_error(logger, "Error fetching company", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to fetch company", "error": str(e)}
            )

    @staticmethod
    async def get_all_companies(page: int = 1, page_size: int = 10) -> JSONResponse:
        """
        Retrieve all companies with pagination.

        Args:
            page: Page number (1-indexed)
            page_size: Number of items per page

        Returns:
            JSONResponse with paginated company list

        Raises:
            PyMongoError: If database operation fails
        """
        try:
            collection = database["companies"]

            skip = (page - 1) * page_size

            total_count = await collection.count_documents({})

            cursor = collection.find({}).skip(skip).limit(page_size).sort("timestamp", -1)
            companies = await cursor.to_list(length=page_size)

            companies_response = [
                CompanyResponse.from_mongo(company).model_dump(by_alias=True)
                for company in companies
            ]

            total_pages = ceil(total_count / page_size) if page_size > 0 else 0

            return JSONResponse(
                status_code=200,
                content={
                    "data": companies_response,
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_items": total_count,
                        "total_pages": total_pages
                    }
                }
            )
        except PyMongoError as e:
            log_error(logger, "Error fetching companies", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to fetch companies", "error": str(e)}
            )

    @staticmethod
    async def update_company(company_id: str, updates: CompanyUpdate) -> JSONResponse:
        """
        Update a company by ID.

        Args:
            company_id: Company ID
            updates: Fields to update

        Returns:
            JSONResponse with updated company data

        Raises:
            InvalidId: If company_id is not a valid ObjectId
            PyMongoError: If database operation fails
        """
        try:
            oid = ObjectId(company_id)
        except InvalidId:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid company ID format"}
            )

        try:
            collection = database["companies"]

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
                    content={"detail": "Company not found"}
                )

            updated_company = await collection.find_one({"_id": oid})
            response = CompanyResponse.from_mongo(updated_company)

            log_info(logger, f"Company updated: {company_id}")

            return JSONResponse(
                status_code=200,
                content=response.model_dump(by_alias=True)
            )
        except PyMongoError as e:
            log_error(logger, "Error updating company", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to update company", "error": str(e)}
            )

    @staticmethod
    async def delete_company(company_id: str) -> JSONResponse:
        """
        Delete a company by ID.

        Args:
            company_id: Company ID

        Returns:
            JSONResponse with deletion confirmation

        Raises:
            InvalidId: If company_id is not a valid ObjectId
            PyMongoError: If database operation fails
        """
        try:
            oid = ObjectId(company_id)
        except InvalidId:
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid company ID format"}
            )

        try:
            collection = database["companies"]
            sagas_collection = database["sagas"]
            movies_collection = database["movies"]

            company = await collection.find_one({"_id": oid})
            if not company:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Company not found"}
                )

            sagas = await sagas_collection.find({"company_id": company_id}).to_list(length=None)
            saga_ids = [str(saga["_id"]) for saga in sagas]

            if saga_ids:
                movies_deleted = await movies_collection.delete_many({"saga_id": {"$in": saga_ids}})
                log_info(logger,
                         f"Deleted {movies_deleted.deleted_count} movies from company {company_id}")

            sagas_deleted = await sagas_collection.delete_many({"company_id": company_id})
            log_info(logger,
                     f"Deleted {sagas_deleted.deleted_count} sagas from company {company_id}")

            await collection.delete_one({"_id": oid})

            log_info(logger, f"Company deleted: {company_id}")

            return JSONResponse(
                status_code=200,
                content={
                    "detail": "Company deleted successfully",
                    "company_id": company_id,
                    "sagas_deleted": sagas_deleted.deleted_count,
                    "movies_deleted": movies_deleted.deleted_count if saga_ids else 0
                }
            )
        except PyMongoError as e:
            log_error(logger, "Error deleting company", {"error": str(e)})
            return JSONResponse(
                status_code=500,
                content={"detail": "Failed to delete company", "error": str(e)}
            )
