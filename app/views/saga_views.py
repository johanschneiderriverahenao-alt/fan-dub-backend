"""
FastAPI views for saga endpoints.

Endpoints:
 - POST /sagas/                   -> create saga
 - GET /sagas/                    -> get all sagas (paginated)
 - GET /sagas/{id}                -> get saga by ID
 - GET /sagas/company/{company_id} -> get sagas by company (paginated)
 - PUT /sagas/{id}                -> update saga by ID
 - DELETE /sagas/{id}             -> delete saga by ID
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.controllers.saga_controller import SagaController
from app.controllers.auth_controller import AuthController
from app.models.saga_model import SagaCreate, SagaUpdate
from app.utils.logger import get_logger, log_info, log_error
from app.utils.dependencies import get_current_admin

logger = get_logger(__name__)

router = APIRouter()


@router.post("/sagas/", response_class=JSONResponse)
async def create_saga(
    saga: SagaCreate,
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """
    Create a new saga.

    Args:
        saga: Saga data to create

    Returns:
        JSONResponse with created saga
    """
    try:
        log_info(logger, f"Creating saga: {saga.saga_name}")
        return await SagaController.create_saga(saga)
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "create_saga endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to create saga", "error": str(e)}
        )


@router.get("/sagas/", response_class=JSONResponse)
async def get_all_sagas(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    _: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """
    Get all sagas with pagination.

    Args:
        page: Page number (default: 1)
        page_size: Items per page (default: 10, max: 100)

    Returns:
        JSONResponse with paginated sagas list
    """
    try:
        log_info(logger, f"Fetching sagas - page: {page}, page_size: {page_size}")
        return await SagaController.get_all_sagas(page, page_size)
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "get_all_sagas endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to fetch sagas", "error": str(e)}
        )


@router.get("/sagas/{saga_id}", response_class=JSONResponse)
async def get_saga(
    saga_id: str,
    _: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """
    Get a saga by ID.

    Args:
        saga_id: Saga ID

    Returns:
        JSONResponse with saga data
    """
    try:
        log_info(logger, f"Fetching saga: {saga_id}")
        return await SagaController.get_saga_by_id(saga_id)
    except InvalidId:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid saga ID format"}
        )
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "get_saga endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to fetch saga", "error": str(e)}
        )


@router.get("/sagas/company/{company_id}", response_class=JSONResponse)
async def get_sagas_by_company(
    company_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    _: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """
    Get all sagas for a specific company with pagination.

    Args:
        company_id: Company ID
        page: Page number (default: 1)
        page_size: Items per page (default: 10, max: 100)

    Returns:
        JSONResponse with paginated sagas list
    """
    try:
        log_info(logger, f"Fetching sagas for company: {company_id}")
        return await SagaController.get_sagas_by_company(company_id, page, page_size)
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "get_sagas_by_company endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to fetch sagas", "error": str(e)}
        )


@router.put("/sagas/{saga_id}", response_class=JSONResponse)
async def update_saga(
    saga_id: str,
    updates: SagaUpdate,
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """
    Update a saga by ID.

    Args:
        saga_id: Saga ID
        updates: Fields to update

    Returns:
        JSONResponse with updated saga
    """
    try:
        log_info(logger, f"Updating saga: {saga_id}")
        return await SagaController.update_saga(saga_id, updates)
    except InvalidId:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid saga ID format"}
        )
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "update_saga endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to update saga", "error": str(e)}
        )


@router.delete("/sagas/{saga_id}", response_class=JSONResponse)
async def delete_saga(
    saga_id: str,
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """
    Delete a saga by ID (Admin only).
    Cascades deletion to all related movies.

    Args:
        saga_id: Saga ID

    Returns:
        JSONResponse with deletion confirmation
    """
    try:
        log_info(logger, f"Deleting saga: {saga_id}")
        return await SagaController.delete_saga(saga_id)
    except InvalidId:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid saga ID format"}
        )
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "delete_saga endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to delete saga", "error": str(e)}
        )
