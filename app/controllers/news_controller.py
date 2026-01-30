"""
News controller: business logic for creating, retrieving,
updating and deleting carousel/news items. Stores documents in MongoDB.
"""
# pylint: disable=W0718,R0801
from datetime import datetime

from typing import Dict, Any

from fastapi.responses import JSONResponse
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.config.database import database
from app.models.news_model import (
    NewsCreate,
    NewsUpdate,
    NewsResponse,
)
from app.utils.logger import get_logger, log_info, log_error

logger = get_logger(__name__)


class NewsController:
    """Business logic for news/carousel CRUD operations."""

    @staticmethod
    async def create_news(news_data: NewsCreate) -> JSONResponse:
        """
        Create a new news/carousel item.

        Returns:
            JSONResponse with created news item
        """
        try:
            if not news_data.title or not news_data.title.strip():
                return JSONResponse(status_code=400, content={"detail": "Title must not be empty"})
            if not news_data.description or not news_data.description.strip():
                return JSONResponse(status_code=400, content={"detail":
                                                              "Description must not be empty"})

            collection = database["news"]

            doc: Dict[str, Any] = {
                "title": news_data.title,
                "description": news_data.description,
                "image_url": str(news_data.image_url),
                "link": str(news_data.link),
                "label": news_data.label,
                "timestamp": datetime.utcnow(),
            }

            result = await collection.insert_one(doc)

            created = await collection.find_one({"_id": result.inserted_id})
            response = NewsResponse.from_mongo(created)

            log_info(logger, f"News created: {result.inserted_id}")

            return JSONResponse(status_code=201, content=response.model_dump(by_alias=True))
        except PyMongoError as e:
            log_error(logger, "Error creating news", {"error": str(e)})
            return JSONResponse(status_code=500, content={"detail":
                                                          "Failed to create news", "error": str(e)})

    @staticmethod
    async def get_latest_news() -> JSONResponse:
        """
        Retrieve latest 10 news items ordered by timestamp DESC.

        Returns:
            JSONResponse with list of news items
        """
        try:
            collection = database["news"]
            cursor = collection.find({}).sort("timestamp", -1).limit(10)
            items = await cursor.to_list(length=10)

            data = [NewsResponse.from_mongo(item).model_dump(by_alias=True) for item in items]

            return JSONResponse(status_code=200, content={"data": data})
        except PyMongoError as e:
            log_error(logger, "Error fetching latest news", {"error": str(e)})
            return JSONResponse(status_code=500, content={"detail":
                                                          "Failed to fetch news", "error": str(e)})

    @staticmethod
    async def update_news(news_id: str, updates: NewsUpdate) -> JSONResponse:
        """
        Update a news item by ID (partial updates allowed).

        Returns:
            JSONResponse with updated news item
        """
        try:
            try:
                oid = ObjectId(news_id)
            except InvalidId:
                return JSONResponse(status_code=400, content={"detail": "Invalid news ID format"})

            collection = database["news"]

            update_data = {k: v for k,
                           v in updates.model_dump(exclude_unset=True).items() if v is not None}

            if not update_data:
                return JSONResponse(status_code=400,
                                    content={"detail": "No valid fields to update"})

            if "title" in update_data and not str(update_data["title"]).strip():
                return JSONResponse(status_code=400, content={"detail": "Title must not be empty"})
            if "description" in update_data and not str(update_data["description"]).strip():
                return JSONResponse(status_code=400,
                                    content={"detail": "Description must not be empty"})

            result = await collection.update_one({"_id": oid}, {"$set": update_data})

            if result.matched_count == 0:
                return JSONResponse(status_code=404, content={"detail": "News not found"})

            updated = await collection.find_one({"_id": oid})
            response = NewsResponse.from_mongo(updated)

            log_info(logger, f"News updated: {news_id}")

            return JSONResponse(status_code=200, content=response.model_dump(by_alias=True))
        except PyMongoError as e:
            log_error(logger, "Error updating news", {"error": str(e)})
            return JSONResponse(status_code=500,
                                content={"detail": "Failed to update news", "error": str(e)})

    @staticmethod
    async def delete_news(news_id: str) -> JSONResponse:
        """
        Delete a news item by ID.

        Returns:
            JSONResponse with deletion confirmation
        """
        try:
            try:
                oid = ObjectId(news_id)
            except InvalidId:
                return JSONResponse(status_code=400, content={"detail": "Invalid news ID format"})

            collection = database["news"]

            item = await collection.find_one({"_id": oid})
            if not item:
                return JSONResponse(status_code=404, content={"detail": "News not found"})

            await collection.delete_one({"_id": oid})

            log_info(logger, f"News deleted: {news_id}")

            return JSONResponse(status_code=200,
                                content={"detail": "News deleted successfully", "news_id": news_id})
        except PyMongoError as e:
            log_error(logger, "Error deleting news", {"error": str(e)})
            return JSONResponse(status_code=500,
                                content={"detail": "Failed to delete news", "error": str(e)})
