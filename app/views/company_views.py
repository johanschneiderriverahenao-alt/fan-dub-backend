"""
FastAPI views for company endpoints.

Endpoints:
 - POST /companies/               -> create company
 - GET /companies/                -> get all companies (paginated)
 - GET /companies/{id}            -> get company by ID
 - PUT /companies/{id}            -> update company by ID
 - DELETE /companies/{id}         -> delete company by ID
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.controllers.company_controller import CompanyController
from app.controllers.auth_controller import AuthController
from app.models.company_model import CompanyCreate, CompanyUpdate
from app.utils.logger import get_logger, log_info, log_error
from app.utils.dependencies import get_current_admin

logger = get_logger(__name__)

router = APIRouter()


@router.post("/companies/", response_class=JSONResponse)
async def create_company(
    company: CompanyCreate,
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """
    Create a new company.

    Args:
        company: Company data to create

    Returns:
        JSONResponse with created company
    """
    try:
        log_info(logger, f"Creating company: {company.companie_name}")
        return await CompanyController.create_company(company)
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "create_company endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to create company", "error": str(e)}
        )


@router.get("/companies/", response_class=JSONResponse)
async def get_all_companies(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    _: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """
    Get all companies with pagination.

    Args:
        page: Page number (default: 1)
        page_size: Items per page (default: 10, max: 100)

    Returns:
        JSONResponse with paginated companies list
    """
    try:
        log_info(logger, f"Fetching companies - page: {page}, page_size: {page_size}")
        return await CompanyController.get_all_companies(page, page_size)
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "get_all_companies endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to fetch companies", "error": str(e)}
        )


@router.get("/companies/{company_id}", response_class=JSONResponse)
async def get_company(
    company_id: str,
    _: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """
    Get a company by ID.

    Args:
        company_id: Company ID

    Returns:
        JSONResponse with company data
    """
    try:
        log_info(logger, f"Fetching company: {company_id}")
        return await CompanyController.get_company_by_id(company_id)
    except InvalidId:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid company ID format"}
        )
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "get_company endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to fetch company", "error": str(e)}
        )


@router.put("/companies/{company_id}", response_class=JSONResponse)
async def update_company(
    company_id: str,
    updates: CompanyUpdate,
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """
    Update a company by ID.

    Args:
        company_id: Company ID
        updates: Fields to update

    Returns:
        JSONResponse with updated company
    """
    try:
        log_info(logger, f"Updating company: {company_id}")
        return await CompanyController.update_company(company_id, updates)
    except InvalidId:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid company ID format"}
        )
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "update_company endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to update company", "error": str(e)}
        )


@router.delete("/companies/{company_id}", response_class=JSONResponse)
async def delete_company(
    company_id: str,
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """
    Delete a company by ID (Admin only).
    Cascades deletion to all related sagas and movies.

    Args:
        company_id: Company ID

    Returns:
        JSONResponse with deletion confirmation
    """
    try:
        log_info(logger, f"Deleting company: {company_id}")
        return await CompanyController.delete_company(company_id)
    except InvalidId:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid company ID format"}
        )
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "delete_company endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to delete company", "error": str(e)}
        )
