"""
Parametrization API views/routes.
"""
# pylint: disable=W0718
from typing import Dict, Any
from fastapi import APIRouter, Depends

from app.controllers.parametrization_controller import ParametrizationController
from app.controllers.auth_controller import AuthController
from app.utils.dependencies import get_current_admin
from app.models.parametrization_model import ParametrizationCreate, ParametrizationUpdate

router = APIRouter(prefix="/parametrization", tags=["Parametrization"])


@router.get("/{param_type}")
async def get_parametrization_by_type(
    param_type: str,
    _: Dict[str, Any] = Depends(AuthController.get_current_user)
):
    """Get parametrization by type (requires authentication)."""
    return await ParametrizationController.get_by_type(param_type)


@router.get("/")
async def list_all_parametrizations(_: Dict[str, Any] = Depends(get_current_admin)):
    """List all parametrizations (admin only)."""
    return await ParametrizationController.list_all()


@router.post("/")
async def create_parametrization(
    param_data: ParametrizationCreate,
    _: Dict[str, Any] = Depends(get_current_admin)
):
    """Create new parametrization (admin only)."""
    return await ParametrizationController.create(param_data)


@router.put("/{param_id}")
async def update_parametrization(
    param_id: str,
    param_data: ParametrizationUpdate,
    _: Dict[str, Any] = Depends(get_current_admin)
):
    """Update parametrization (admin only)."""
    return await ParametrizationController.update(param_id, param_data)


@router.delete("/{param_id}")
async def delete_parametrization(
    param_id: str,
    _: Dict[str, Any] = Depends(get_current_admin)
):
    """Delete parametrization (admin only)."""
    return await ParametrizationController.delete(param_id)
