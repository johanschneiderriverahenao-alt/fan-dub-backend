"""
Audit log views for retrieving operation logs.

Provides endpoints to view audit logs for users and system.
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.controllers.audit_log_controller import AuditLogController
from app.controllers.auth_controller import AuthController
from app.utils.logger import get_logger, log_info

logger = get_logger(__name__)

router = APIRouter()


@router.get("/logs/user/{user_id}", response_class=JSONResponse)
async def get_user_logs(
    user_id: str,
    limit: int = Query(50, ge=1, le=1000),
    _: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """
    Get all audit logs for a specific user.

    Args:
        user_id: ID of the user to retrieve logs for.
        limit: Maximum number of logs to return (1-1000).
        _: Current authenticated user (dependency).

    Returns:
        JSONResponse with list of audit logs.
    """
    log_info(logger, f"Fetching audit logs for user {user_id}", {
        "endpoint": "/audit/logs/user/{user_id}",
        "limit": limit
    })

    return await AuditLogController.get_user_logs(user_id, limit)


@router.get("/logs", response_class=JSONResponse)
async def get_all_logs(
    limit: int = Query(100, ge=1, le=5000),
    _: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """
    Get all audit logs from the system.

    Requires authentication. Only authenticated users can view logs.

    Args:
        limit: Maximum number of logs to return (1-5000).
        _: Current authenticated user (dependency).

    Returns:
        JSONResponse with list of all system audit logs.
    """
    log_info(logger, "Fetching all system audit logs", {
        "endpoint": "/audit/logs",
        "limit": limit
    })

    return await AuditLogController.get_all_logs(limit)
