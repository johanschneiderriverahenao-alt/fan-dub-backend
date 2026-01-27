"""
Authentication views for user login operations.
"""
# pylint: disable=R0801,W0718

from typing import Dict, Any
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.models.user import UserLogin, UserBase, ChangePassword
from app.controllers.auth_controller import AuthController
from app.utils.logger import get_logger
from app.utils.dependencies import get_current_user_from_token

logger = get_logger(__name__)

router = APIRouter()


@router.post("/register")
async def register(user_data: UserBase) -> JSONResponse:
    """
    Register a new user.

    Args:
        user_data: User registration data (email, password).

    Returns:
        JSONResponse with new user information on success.
        JSONResponse with error details on failure.

    Status Codes:
        - 201: User registered successfully.
        - 400: Email already registered.
        - 500: Unexpected server error.
    """
    try:
        response = await AuthController.register(user_data)
        return response
    except Exception as e:
        logger.error("Unexpected error in register endpoint: %s", str(e))
        return JSONResponse(
            status_code=500,
            content={"error": "Registration failed", "details": str(e)}
        )


@router.post("/login")
async def login(login_data: UserLogin) -> JSONResponse:
    """
    Authenticate user and return access token.

    Args:
        login_data: User login credentials (email, password).

    Returns:
        JSONResponse with access token and user information on success.
        JSONResponse with error details on failure.

    Status Codes:
        - 200: Authentication successful.
        - 401: Invalid credentials.
        - 500: Unexpected server error.
    """
    try:
        response = await AuthController.login(login_data)
        return response
    except Exception as e:
        logger.error("Unexpected error in login endpoint: %s", str(e))
        return JSONResponse(
            status_code=500,
            content={"error": "Login failed", "log": str(e)}
        )


@router.post("/change-password")
async def change_password(password_data: ChangePassword) -> JSONResponse:
    """
    Change a user's password when email and current password match.

    Args:
        password_data: Contains `email`, `current_password`, and `new_password`.

    Returns:
        JSONResponse with operation result.
    """
    try:
        response = await AuthController.change_password(password_data)
        return response
    except Exception as e:
        logger.error("Unexpected error in change-password endpoint: %s", str(e))
        return JSONResponse(
            status_code=500, content={"error": "Password change failed", "details": str(e)})


@router.get("/me")
async def get_current_user_profile(
    current_user: Dict[str, Any] = Depends(get_current_user_from_token)
) -> JSONResponse:
    """
    Get the current authenticated user's profile.

    This endpoint requires authentication via Bearer token in the Authorization header.

    Args:
        current_user: Current user data extracted from token (auto-injected).

    Returns:
        JSONResponse with user profile data.

    Status Codes:
        - 200: Profile retrieved successfully.
        - 401: Invalid or missing token.
        - 500: Unexpected server error.
    """
    try:
        user_id = current_user.get("id")
        response = await AuthController.get_user_profile(user_id)
        return response
    except Exception as e:
        logger.error("Unexpected error in get profile endpoint: %s", str(e))
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to retrieve profile", "details": str(e)}
        )


@router.delete("/me")
async def delete_current_user(
    current_user: Dict[str, Any] = Depends(get_current_user_from_token)
) -> JSONResponse:
    """
    Delete the current authenticated user and all related data.

    This endpoint requires authentication via Bearer token in the Authorization header.
    It will permanently delete the user account and all associated data including:
    - User profile
    - Audit logs

    Args:
        current_user: Current user data extracted from token (auto-injected).

    Returns:
        JSONResponse with deletion confirmation.

    Status Codes:
        - 200: User deleted successfully.
        - 401: Invalid or missing token.
        - 404: User not found.
        - 500: Unexpected server error.
    """
    try:
        user_id = current_user.get("id")
        response = await AuthController.delete_user(user_id)
        return response
    except Exception as e:
        logger.error("Unexpected error in delete user endpoint: %s", str(e))
        return JSONResponse(
            status_code=500,
            content={"error": "User deletion failed", "details": str(e)}
        )
