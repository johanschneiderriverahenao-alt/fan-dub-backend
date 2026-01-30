"""
FastAPI views for news / carousel endpoints.

Endpoints:
 - POST /news           -> create news item (admin)
 - GET /news            -> get latest 10 news items (auth)
 - PUT /news/{news_id}  -> update news item (admin)
 - DELETE /news/{news_id} -> delete news item (admin)
"""
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.controllers.news_controller import NewsController
from app.models.news_model import NewsCreate, NewsUpdate
from app.utils.logger import get_logger, log_info, log_error
from app.utils.dependencies import get_current_admin

logger = get_logger(__name__)

router = APIRouter()


@router.post("/news", response_class=JSONResponse)
async def create_news(
    news: NewsCreate,
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """
    Create a new carousel/news item (Admin only).

    Args:
        news: NewsCreate payload

    Returns:
        JSONResponse with created news item
    """
    try:
        log_info(logger, f"Creating news: {news.title}")
        return await NewsController.create_news(news)
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "create_news endpoint error", {"error": str(e)})
        return JSONResponse(status_code=500, content={"detail": "Failed to create news",
                                                      "error": str(e)})


@router.get("/news", response_class=JSONResponse)
async def get_latest_news() -> JSONResponse:
    """
    Get latest 10 carousel/news items for authenticated users.

    Returns:
        JSONResponse with list of latest news items
    """
    try:
        log_info(logger, "Fetching latest news items (public)")
        return await NewsController.get_latest_news()
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "get_latest_news endpoint error", {"error": str(e)})
        return JSONResponse(status_code=500, content={"detail":
                                                      "Failed to fetch news", "error": str(e)})


@router.put("/news/{news_id}", response_class=JSONResponse)
async def update_news(
    news_id: str,
    updates: NewsUpdate,
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """
    Update a news item by ID (Admin only).

    Args:
        news_id: News item ID
        updates: Fields to update

    Returns:
        JSONResponse with updated news item
    """
    try:
        log_info(logger, f"Updating news: {news_id}")
        return await NewsController.update_news(news_id, updates)
    except InvalidId:
        return JSONResponse(status_code=400, content={"detail": "Invalid news ID format"})
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "update_news endpoint error", {"error": str(e)})
        return JSONResponse(status_code=500,
                            content={"detail": "Failed to update news", "error": str(e)})


@router.delete("/news/{news_id}", response_class=JSONResponse)
async def delete_news(
    news_id: str,
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """
    Delete a news item by ID (Admin only).

    Args:
        news_id: News item ID

    Returns:
        JSONResponse with deletion confirmation
    """
    try:
        log_info(logger, f"Deleting news: {news_id}")
        return await NewsController.delete_news(news_id)
    except InvalidId:
        return JSONResponse(status_code=400, content={"detail": "Invalid news ID format"})
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "delete_news endpoint error", {"error": str(e)})
        return JSONResponse(status_code=500, content={"detail":
                                                      "Failed to delete news", "error": str(e)})
