"""
Audit log controller for tracking application operations.

Handles creation and retrieval of audit logs for authentication events.
"""
# pylint: disable=W0718

from datetime import datetime
from fastapi.responses import JSONResponse
from bson import ObjectId

from app.config.database import database
from app.models.audit_log import AuditLog, AuditLogResponse
from app.utils.logger import get_logger, log_info, log_error

logger = get_logger(__name__)


class AuditLogController:
    """Controller for managing audit log operations."""

    @staticmethod
    async def create_log(
        user_id: str,
        action: str,
        status: str,
        details: dict = None
    ) -> JSONResponse:
        """
        Create an audit log entry.

        Args:
            user_id: ID of the user performing the action.
            action: Type of action (e.g., 'LOGIN', 'LOGOUT', 'REGISTER').
            status: Status of the action ('SUCCESS', 'FAILED', 'PENDING').
            details: Additional details about the action (optional).

        Returns:
            JSONResponse with the created audit log or error message.

        Raises:
            Exception: If log creation fails.
        """
        try:
            log_data = AuditLog(
                user_id=ObjectId(user_id),
                action=action,
                status=status,
                details=details or {},
                created_at=datetime.utcnow()
            )

            db = database.get_db()
            result = await db.audit_logs.insert_one(log_data.dict(by_alias=True))

            log_info(logger, f"Audit log created for user {user_id}", {
                "action": action,
                "status": status,
                "log_id": str(result.inserted_id)
            })

            return JSONResponse(
                status_code=201,
                content={
                    "id": str(result.inserted_id),
                    "user_id": user_id,
                    "action": action,
                    "status": status,
                    "log": "Audit log created successfully"
                }
            )
        except Exception as e:
            log_error(logger, f"Failed to create audit log for user {user_id}", {
                "error": str(e),
                "action": action
            })
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Failed to create audit log",
                    "log": f"Error: {str(e)}"
                }
            )

    @staticmethod
    async def get_user_logs(user_id: str, limit: int = 50) -> JSONResponse:
        """
        Get all audit logs for a specific user.

        Args:
            user_id: ID of the user.
            limit: Maximum number of logs to return (default: 50).

        Returns:
            JSONResponse with list of audit logs or error message.

        Raises:
            Exception: If query fails.
        """
        try:
            db = database.get_db()
            logs = await db.audit_logs.find({
                "user_id": ObjectId(user_id)
            }).sort("created_at", -1).limit(limit).to_list(length=limit)

            log_list = [AuditLogResponse(**log).dict() for log in logs]

            log_info(logger, f"Retrieved {len(log_list)} audit logs for user {user_id}")

            return JSONResponse(
                status_code=200,
                content={
                    "user_id": user_id,
                    "logs": log_list,
                    "count": len(log_list),
                    "log": "Audit logs retrieved successfully"
                }
            )
        except Exception as e:
            log_error(logger, f"Failed to retrieve audit logs for user {user_id}", {
                "error": str(e)
            })
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Failed to retrieve audit logs",
                    "log": f"Error: {str(e)}"
                }
            )

    @staticmethod
    async def get_all_logs(limit: int = 100) -> JSONResponse:
        """
        Get all audit logs from the system.

        Args:
            limit: Maximum number of logs to return (default: 100).

        Returns:
            JSONResponse with list of all audit logs or error message.

        Raises:
            Exception: If query fails.
        """
        try:
            db = database.get_db()
            logs = await db.audit_logs.find({}).sort("created_at", -1).limit(
                limit
            ).to_list(length=limit)

            log_list = [AuditLogResponse(**log).dict() for log in logs]

            log_info(logger, f"Retrieved {len(log_list)} total audit logs")

            return JSONResponse(
                status_code=200,
                content={
                    "logs": log_list,
                    "count": len(log_list),
                    "log": "All audit logs retrieved successfully"
                }
            )
        except Exception as e:
            log_error(logger, "Failed to retrieve all audit logs", {
                "error": str(e)
            })
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Failed to retrieve audit logs",
                    "log": f"Error: {str(e)}"
                }
            )
