"""
Company Pydantic models for the companies domain.

Models:
- `CompanyBase`: shared fields
- `CompanyCreate`: request model for creating a company
- `CompanyUpdate`: fields allowed to update
- `CompanyDB`: DB representation
- `CompanyResponse`: response model
"""
# pylint: disable=R0801
from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from bson import ObjectId


class CompanyBase(BaseModel):
    """Shared fields for companies."""

    companie_name: str = Field(..., description="Name of the company")
    description: str = Field(..., description="Description of the company")


class CompanyCreate(CompanyBase):
    """Request model used when creating a company."""


class CompanyUpdate(BaseModel):
    """Model for update requests. All fields optional."""

    companie_name: Optional[str] = None
    description: Optional[str] = None
    sagas_list: Optional[List[str]] = None


class CompanyDB(CompanyBase):
    """Internal DB model."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(default_factory=ObjectId, alias="_id")
    sagas_list: List[str] = Field(default_factory=list, description="List of saga IDs")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class CompanyResponse(BaseModel):
    """Response model for Company."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: str = Field(alias="_id", description="Company ID")
    companie_name: str
    description: str
    sagas_list: List[str]
    timestamp: str

    @classmethod
    def from_mongo(cls, doc: dict) -> "CompanyResponse":
        """Transform MongoDB doc into response model."""
        if not doc:
            return None
        doc["_id"] = str(doc["_id"])
        if "timestamp" in doc and isinstance(doc["timestamp"], datetime):
            doc["timestamp"] = doc["timestamp"].isoformat()
        return cls(**doc)
