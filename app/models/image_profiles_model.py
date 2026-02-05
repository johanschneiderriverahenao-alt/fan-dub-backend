"""
Pydantic models for image_profiles entity.
Handles data validation and serialization for user profile images.
"""
from datetime import datetime
from typing import Optional

from bson import ObjectId
from pydantic import BaseModel, Field, ConfigDict


class ImageProfileBase(BaseModel):
    """Base model with common fields."""

    name: str = Field(..., description="Name or identifier of the image")
    company_associated: str = Field(..., description="Company associated with this image")
    saga_associated: str = Field(..., description="Saga associated with this image")


class ImageProfileCreate(ImageProfileBase):
    """Request model used when creating an image profile."""


class ImageProfileUpdate(BaseModel):
    """Model for update requests. All fields optional."""

    image_url: Optional[str] = None
    name: Optional[str] = None
    company_associated: Optional[str] = None
    saga_associated: Optional[str] = None


class ImageProfileDB(ImageProfileBase):
    """Internal DB model."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: ObjectId = Field(default_factory=ObjectId, alias="_id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ImageProfileResponse(BaseModel):
    """Response model for ImageProfile."""

    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    id: str = Field(alias="_id", description="ImageProfile ID")
    name: str
    company_associated: str
    saga_associated: str
    image_url: Optional[str] = None
    created_at: str

    @classmethod
    def from_mongo(cls, doc: dict) -> "ImageProfileResponse":
        """Transform MongoDB doc into response model."""
        if not doc:
            return None
        doc["_id"] = str(doc["_id"])
        if "created_at" in doc and isinstance(doc["created_at"], datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        return cls(**doc)
