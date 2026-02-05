"""
FastAPI views for image profile endpoints.

Endpoints:
 - POST /image-profiles/                       -> create image profile (admin)
 - POST /image-profiles/{id}/upload-image      -> upload image for profile (admin)
 - GET /image-profiles/{id}                    -> get image profile by ID
 - GET /image-profiles/                        -> get all image profiles (grouped, paginated)
 - PUT /image-profiles/{id}                    -> update image profile (admin)
 - DELETE /image-profiles/{id}                 -> delete image profile (admin)
"""
from fastapi import APIRouter, Depends, Query, File, UploadFile, Form
from fastapi.responses import JSONResponse
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.controllers.image_profiles_controller import ImageProfileController
from app.controllers.auth_controller import AuthController
from app.models.image_profiles_model import ImageProfileCreate, ImageProfileUpdate
from app.utils.logger import get_logger, log_info, log_error
from app.utils.dependencies import get_current_admin

logger = get_logger(__name__)

router = APIRouter()


@router.post("/image-profiles/", response_class=JSONResponse)
async def create_image_profile(
    name: str = Form(..., description="Name of the image profile"),
    company_associated: str = Form(..., description="Company associated"),
    saga_associated: str = Form(..., description="Saga associated"),
    image: UploadFile = File(..., description="Image file to upload"),
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """
    Create a new image profile with image upload. Admin only.

    Args:
        name: Name of the image profile
        company_associated: Company associated with this image
        saga_associated: Saga associated with this image
        image: Image file to upload (multipart/form-data)

    Returns:
        JSONResponse with created image profile
    """
    try:
        log_info(logger, f"Creating image profile: {name}")

        max_size = 10 * 1024 * 1024
        image.file.seek(0, 2)
        file_size = image.file.tell()
        image.file.seek(0)

        if file_size > max_size:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": (
                        "File too large. Maximum size is 10MB, "
                        f"got {file_size / (1024 * 1024):.2f}MB"
                    )
                }
            )

        image_profile_data = ImageProfileCreate(
            name=name,
            company_associated=company_associated,
            saga_associated=saga_associated
        )

        return await ImageProfileController.create_image_profile(image_profile_data, image)
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "create_image_profile endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to create image profile", "error": str(e)}
        )


@router.post("/image-profiles/{image_profile_id}/upload-image", response_class=JSONResponse)
async def upload_image_to_profile(
    image_profile_id: str,
    image: UploadFile = File(..., description="Image file to upload"),
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """
    Upload an image file to R2 storage for a specific image profile. Admin only.

    Args:
        image_profile_id: The image profile ID
        image: Image file to upload (multipart/form-data)

    Returns:
        JSONResponse with updated image profile data and image URL
    """
    try:
        log_info(logger, f"Uploading image for profile: {image_profile_id}")

        max_size = 10 * 1024 * 1024
        image.file.seek(0, 2)
        file_size = image.file.tell()
        image.file.seek(0)

        if file_size > max_size:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": (
                        "File too large. Maximum size is 10MB, "
                        f"got {file_size / (1024 * 1024):.2f}MB"
                    )
                }
            )

        return await ImageProfileController.upload_image(image_profile_id, image)
    except InvalidId:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid image profile ID format"}
        )
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "upload_image endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to upload image", "error": str(e)}
        )


@router.get("/image-profiles/{image_profile_id}", response_class=JSONResponse)
async def get_image_profile_by_id(
    image_profile_id: str,
    _: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """
    Get an image profile by ID.

    Args:
        image_profile_id: The image profile ID

    Returns:
        JSONResponse with image profile data
    """
    try:
        log_info(logger, f"Fetching image profile: {image_profile_id}")
        return await ImageProfileController.get_image_profile_by_id(image_profile_id)
    except InvalidId:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid image profile ID format"}
        )
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "get_image_profile_by_id endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to fetch image profile", "error": str(e)}
        )


@router.get("/image-profiles/", response_class=JSONResponse)
async def get_all_image_profiles(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    company_associated: str = Query(None, description="Filter by company"),
    saga_associated: str = Query(None, description="Filter by saga"),
    _: dict = Depends(AuthController.get_current_user)
) -> JSONResponse:
    """
    Get all image profiles with pagination and optional filters.
    Results are grouped by company -> saga -> images.

    Args:
        page: Page number (default: 1)
        page_size: Items per page (default: 20, max: 100)
        company_associated: Optional filter by company
        saga_associated: Optional filter by saga

    Returns:
        JSONResponse with grouped and paginated image profiles
    """
    try:
        log_info(logger, "Fetching image profiles with filters")
        return await ImageProfileController.get_all_image_profiles(
            page, page_size, company_associated, saga_associated
        )
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "get_all_image_profiles endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to fetch image profiles", "error": str(e)}
        )


@router.put("/image-profiles/{image_profile_id}", response_class=JSONResponse)
async def update_image_profile(
    image_profile_id: str,
    updates: ImageProfileUpdate,
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """
    Update an image profile by ID. Admin only.

    Args:
        image_profile_id: The image profile ID
        updates: Fields to update

    Returns:
        JSONResponse with updated image profile data
    """
    try:
        log_info(logger, f"Updating image profile: {image_profile_id}")
        return await ImageProfileController.update_image_profile(image_profile_id, updates)
    except InvalidId:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid image profile ID format"}
        )
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "update_image_profile endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to update image profile", "error": str(e)}
        )


@router.delete("/image-profiles/{image_profile_id}", response_class=JSONResponse)
async def delete_image_profile(
    image_profile_id: str,
    _: dict = Depends(get_current_admin)
) -> JSONResponse:
    """
    Delete an image profile by ID. Admin only.

    Args:
        image_profile_id: The image profile ID

    Returns:
        JSONResponse with deletion confirmation
    """
    try:
        log_info(logger, f"Deleting image profile: {image_profile_id}")
        return await ImageProfileController.delete_image_profile(image_profile_id)
    except InvalidId:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid image profile ID format"}
        )
    except (RuntimeError, PyMongoError) as e:
        log_error(logger, "delete_image_profile endpoint error", {"error": str(e)})
        return JSONResponse(
            status_code=500,
            content={"detail": "Failed to delete image profile", "error": str(e)}
        )
