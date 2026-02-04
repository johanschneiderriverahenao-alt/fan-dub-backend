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


def _score_and_sort(docs: List[Dict[str, Any]], pattern: str) -> List[Dict[str, Any]]:
    """Score documents by similarity on `movie_name` and sort by descending score."""
    pattern_norm = pattern.lower()
    scored: List[Dict[str, Any]] = []
    for d in docs:
        movie_name = d.get("movie_name", "")
        score = difflib.SequenceMatcher(None, pattern_norm, movie_name.lower()).ratio()
        scored.append({"score": score, "doc": d})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return [item["doc"] for item in scored]


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
                "data": items,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_items": total,
                    "total_pages": total_pages
                }
            },
        )

    @staticmethod
    async def search_movies_regex(pattern: str, page: int = 1, page_size: int = 10) -> JSONResponse:
        """Buscar películas por `pattern` (RegExp) sobre el campo `movie_name`.

        Devuelve todas las películas que coinciden con el patrón, ordenadas por similitud
        descendente, y aplica paginación sobre el conjunto completo.
        """
        log_info(logger, "Initiating movie regex search",
                 {"pattern": pattern, "page": page, "page_size": page_size})

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

        sorted_results = _score_and_sort(docs, pattern)

        total = len(sorted_results)
        skip = (page - 1) * page_size
        page_items = sorted_results[skip: skip + page_size]

        items = [_serialize(doc) for doc in page_items]

        log_info(logger, "Movie regex search completed",
                 {"pattern": pattern, "returned": len(items), "total_matches": total})

        return MovieSearchController.build_response(items, total, page, page_size)
