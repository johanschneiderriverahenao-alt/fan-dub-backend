"""
Plan API views/routes.
"""
# pylint: disable=W0718
from typing import Dict, Any
from fastapi import APIRouter, Depends, Query

from app.controllers.plan_controller import PlanController
from app.utils.dependencies import get_current_admin
from app.models.plan_model import PlanCreate, PlanUpdate

router = APIRouter(prefix="/plans", tags=["Plans"])


@router.get("/")
async def list_plans(active_only: bool = Query(True, description="Show only active plans")):
    """List all available plans (public endpoint)."""
    return await PlanController.list_all(active_only=active_only)


@router.get("/{plan_id}")
async def get_plan_by_id(plan_id: str):
    """Get plan details by ID (public endpoint)."""
    return await PlanController.get_by_id(plan_id)


@router.get("/by-name/{plan_name}")
async def get_plan_by_name(plan_name: str):
    """Get plan details by name (public endpoint)."""
    return await PlanController.get_by_name(plan_name)


@router.post("/")
async def create_plan(
    plan_data: PlanCreate,
    current_user: Dict[str, Any] = Depends(get_current_admin)
):
    """Create new plan (admin only)."""
    user_id = current_user.get("_id") or current_user.get("id")
    return await PlanController.create(plan_data, created_by=user_id)


@router.put("/{plan_id}")
async def update_plan(
    plan_id: str,
    plan_data: PlanUpdate,
    _: Dict[str, Any] = Depends(get_current_admin)
):
    """Update plan (admin only)."""
    return await PlanController.update(plan_id, plan_data)


@router.delete("/{plan_id}")
async def delete_plan(
    plan_id: str,
    _: Dict[str, Any] = Depends(get_current_admin)
):
    """Delete plan - soft delete (admin only)."""
    return await PlanController.delete(plan_id)
