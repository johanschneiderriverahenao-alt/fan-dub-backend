"""
Audit log data models for tracking application operations.
Defines the structure for storing audit logs in MongoDB.
"""
# pylint: disable=R0903

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId


class AuditLogBase(BaseModel):
    """Base model for audit log data."""

    action: str = Field(..., description="Type of action performed")
    status: str = Field(..., description="Status of the action")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")


class AuditLog(AuditLogBase):
    """Internal audit log model for database storage."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        populate_by_name=True,
    )

    user_id: ObjectId = Field(..., description="ID of the user")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuditLogResponse(BaseModel):
    """Response model for audit log data."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., alias="_id", description="Audit log ID")
    user_id: str = Field(..., description="ID of the user")
    action: str = Field(..., description="Type of action performed")
    status: str = Field(..., description="Status of the action")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional details")
    created_at: str = Field(..., description="Creation timestamp")

    @classmethod
    def from_db(cls, data: dict):
        """
        Create response from database document.

        Args:
            data: Database document dictionary.

        Returns:
            AuditLogResponse instance.
        """
        return cls(
            id=str(data.get("_id")),
            user_id=str(data.get("user_id")),
            action=data.get("action"),
            status=data.get("status"),
            details=data.get("details"),
            created_at=data.get("created_at", datetime.utcnow()).isoformat()
        )
