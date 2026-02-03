"""Movie search controller: provides regex search over the `movie_name` field.

This module implements an async controller compatible with the project's
FastAPI-based MVC structure. Helpers are extracted to keep functions small
and to satisfy static analysis (complexity / local variable) constraints.
"""

from typing import List, Dict, Any
import math
import difflib
from datetime import datetime

from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from bson import ObjectId

from app.config.database import database
from app.utils.logger import get_logger, log_info, log_error

logger = get_logger(__name__)


def _serialize(value: Any) -> Any:
    """Recursively serialize values not supported by JSON (datetime, ObjectId)."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    return value


def _score_and_select_top(docs: List[Dict[str, Any]],
                          pattern: str, top_n: int = 10) -> List[Dict[str, Any]]:
    """Score documents by similarity on `movie_name` and return top N documents."""
    pattern_norm = pattern.lower()
    scored: List[Dict[str, Any]] = []
    for d in docs:
        movie_name = d.get("movie_name", "")
        score = difflib.SequenceMatcher(None, pattern_norm, movie_name.lower()).ratio()
        scored.append({"score": score, "doc": d})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return [item["doc"] for item in scored[:top_n]]


class MovieSearchController:
    """Controller para búsqueda de películas usando expresión regular y paginación.

    Exposes a public search method and a helper to build JSON responses. Keeping
    small public methods reduces measured complexity in linters.
    """

    @staticmethod
    def build_response(items: List[Dict[str, Any]],
                       total: int, page: int, page_size: int) -> JSONResponse:
        """Construye el `JSONResponse` estándar para los endpoints de películas."""
        total_pages = math.ceil(total / page_size) if page_size > 0 else 1
        return JSONResponse(
            status_code=200,
            content={
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            },
        )

    @staticmethod
    async def search_movies_regex(pattern: str, page: int = 1, page_size: int = 10) -> JSONResponse:
        """Buscar películas por `pattern` (RegExp) sobre el campo `movie_name`.

        Devuelve únicamente las 10 películas con mayor similitud y aplica paginación
        sobre ese conjunto (skip/limit calculados en memoria).
        """
        log_info(logger, "Initiating movie regex search",
                 {"pattern": pattern, "page": page, "page_size": page_size})

        # Buscar documentos que cumplan el RegExp (case-insensitive) sobre `movie_name`.
        try:
            cursor = database["movies"].find({"movie_name": {"$regex": pattern, "$options": "i"}})
            docs: List[Dict[str, Any]] = await cursor.to_list(length=1000)
        except PyMongoError as e:
            log_error(logger, "DB error in search_movies_regex",
                      {"error": str(e), "pattern": pattern})
            return JSONResponse(status_code=500,
                                content={"message": "Error searching movies", "details": str(e)})

        if not docs:
            return MovieSearchController.build_response([], 0, page, page_size)

        top_ten = _score_and_select_top(docs, pattern, top_n=10)

        total = len(top_ten)
        skip = (page - 1) * page_size
        page_items = top_ten[skip: skip + page_size]

        items = [_serialize(doc) for doc in page_items]

        log_info(logger, "Movie regex search completed",
                 {"pattern": pattern, "returned": len(items), "total_top": total})

        return MovieSearchController.build_response(items, total, page, page_size)
