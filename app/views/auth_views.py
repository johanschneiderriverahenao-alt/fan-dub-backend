"""
Authentication views for user login operations.
"""
# pylint: disable=R0801,W0718

from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.models.user import (
    UserLogin,
    UserBase,
    ChangePassword,
    ChangeEmail,
    VerificationRequest,
    VerificationConfirm,
    RegisterWithVerification,
    ChangePasswordWithVerification
)
from app.controllers.auth_controller import AuthController
from app.utils.logger import get_logger
from app.utils.dependencies import get_current_user_from_token, get_current_admin

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
    except HTTPException as he:
        logger.error("Validation error in register endpoint: %s", str(he.detail))
        return JSONResponse(status_code=he.status_code, content={"message": he.detail})
    except Exception as e:
        logger.error("Unexpected error in register endpoint: %s", str(e))
        return JSONResponse(
            status_code=500,
            content={"message": "Registration failed", "details": str(e)}
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
    except HTTPException as he:
        logger.error("Validation error in login endpoint: %s", str(he.detail))
        return JSONResponse(status_code=he.status_code, content={"message": he.detail})
    except Exception as e:
        logger.error("Unexpected error in login endpoint: %s", str(e))
        return JSONResponse(
            status_code=500,
            content={"message": "Login failed", "log": str(e)}
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
    except HTTPException as he:
        logger.error("Validation error in change-password endpoint: %s", str(he.detail))
        return JSONResponse(status_code=he.status_code, content={"message": he.detail})
    except Exception as e:
        logger.error("Unexpected error in change-password endpoint: %s", str(e))
        return JSONResponse(
            status_code=500, content={"message": "Password change failed", "details": str(e)})


@router.post("/change-email")
async def change_email(email_data: ChangeEmail) -> JSONResponse:
    """
    Change a user's email address.

    Args:
        email_data: Contains `email`, `new_email`, and `current_password`.

    Returns:
        JSONResponse with operation result.
    """
    try:
        response = await AuthController.change_email(email_data)
        return response
    except HTTPException as he:
        logger.error("Validation error in change-email endpoint: %s", str(he.detail))
        return JSONResponse(status_code=he.status_code, content={"message": he.detail})
    except Exception as e:
        logger.error("Unexpected error in change-email endpoint: %s", str(e))
        return JSONResponse(status_code=500, content={"message": "Email change failed",
                                                      "details": str(e)})


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
    except HTTPException as he:
        logger.error("Validation error in get profile endpoint: %s", str(he.detail))
        return JSONResponse(status_code=he.status_code, content={"message": he.detail})
    except Exception as e:
        logger.error("Unexpected error in get profile endpoint: %s", str(e))
        return JSONResponse(
            status_code=500,
            content={"message": "Failed to retrieve profile", "details": str(e)}
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
    except HTTPException as he:
        logger.error("Validation error in delete user endpoint: %s", str(he.detail))
        return JSONResponse(status_code=he.status_code, content={"message": he.detail})
    except Exception as e:
        logger.error("Unexpected error in delete user endpoint: %s", str(e))
        return JSONResponse(
            status_code=500,
            content={"message": "User deletion failed", "details": str(e)}
        )


@router.put("/update-role")
async def update_user_role(
    user_email: str,
    new_role: str,
    _: Dict[str, Any] = Depends(get_current_admin)
) -> JSONResponse:
    """
    Update a user's role (Admin only).

    Args:
        user_email: Email of the user to update.
        new_role: New role (user or admin).

    Returns:
        JSONResponse with update confirmation.

    Status Codes:
        - 200: Role updated successfully.
        - 400: Invalid role value.
        - 403: Insufficient permissions.
        - 404: User not found.
        - 500: Unexpected server error.
    """
    try:
        response = await AuthController.update_user_role(user_email, new_role)
        return response
    except HTTPException as he:
        logger.error("Validation error in update role endpoint: %s", str(he.detail))
        return JSONResponse(status_code=he.status_code, content={"message": he.detail})
    except Exception as e:
        logger.error("Unexpected error in update role endpoint: %s", str(e))
        return JSONResponse(
            status_code=500,
            content={"message": "Role update failed", "details": str(e)}
        )


@router.post("/send-verification-code")
async def send_verification_code(verification_request: VerificationRequest) -> JSONResponse:
    """
    Send a verification code to the user's email.

    Args:
        verification_request: Contains email and purpose (registration or password_change).

    Returns:
        JSONResponse indicating success or failure.

    Status Codes:
        - 200: Verification code sent successfully.
        - 400: Email already registered (for registration) or invalid request.
        - 404: User not found (for password_change).
        - 500: Unexpected server error.
    """
    try:
        response = await AuthController.send_verification_code(verification_request)
        return response
    except HTTPException as he:
        logger.error("Validation error in send verification code endpoint: %s", str(he.detail))
        return JSONResponse(status_code=he.status_code, content={"message": he.detail})
    except Exception as e:
        logger.error("Unexpected error in send verification code endpoint: %s", str(e))
        return JSONResponse(
            status_code=500,
            content={"message": "Failed to send verification code", "details": str(e)}
        )


@router.post("/verify-code")
async def verify_code(verification_confirm: VerificationConfirm) -> JSONResponse:
    """
    Verify a verification code and return a verification token.

    Args:
        verification_confirm: Contains email, code, and purpose.

    Returns:
        JSONResponse with verification token on success.

    Status Codes:
        - 200: Code verified successfully.
        - 400: Invalid or expired code.
        - 500: Unexpected server error.
    """
    try:
        response = await AuthController.verify_code(verification_confirm)
        return response
    except HTTPException as he:
        logger.error("Validation error in verify code endpoint: %s", str(he.detail))
        return JSONResponse(status_code=he.status_code, content={"message": he.detail})
    except Exception as e:
        logger.error("Unexpected error in verify code endpoint: %s", str(e))
        return JSONResponse(
            status_code=500,
            content={"message": "Failed to verify code", "details": str(e)}
        )


@router.post("/register-with-verification")
async def register_with_verification(
    registration_data: RegisterWithVerification
) -> JSONResponse:
    """
    Complete user registration after email verification.

    Args:
        registration_data: Contains email, password, and verification_token.

    Returns:
        JSONResponse with new user information on success.

    Status Codes:
        - 201: User registered successfully.
        - 400: Invalid verification token or email already registered.
        - 500: Unexpected server error.
    """
    try:
        response = await AuthController.register_with_verification(registration_data)
        return response
    except HTTPException as he:
        logger.error("Validation error in register with verification endpoint: %s", str(he.detail))
        return JSONResponse(status_code=he.status_code, content={"message": he.detail})
    except Exception as e:
        logger.error("Unexpected error in register with verification endpoint: %s", str(e))
        return JSONResponse(
            status_code=500,
            content={"message": "Registration failed", "details": str(e)}
        )


@router.post("/change-password-with-verification")
async def change_password_with_verification(
    password_data: ChangePasswordWithVerification
) -> JSONResponse:
    """
    Change user password after email verification.

    Args:
        password_data: Contains email, new_password, and verification_token.

    Returns:
        JSONResponse with operation result.

    Status Codes:
        - 200: Password changed successfully.
        - 400: Invalid verification token.
        - 404: User not found.
        - 500: Unexpected server error.
    """
    try:
        response = await AuthController.change_password_with_verification(password_data)
        return response
    except HTTPException as he:
        logger.error("Validation error in change password with verification endpoint: %s",
                     str(he.detail))
        return JSONResponse(status_code=he.status_code, content={"message": he.detail})
    except Exception as e:
        logger.error("Unexpected error in change password with verification endpoint: %s", str(e))
        return JSONResponse(
            status_code=500,
            content={"message": "Password change failed", "details": str(e)}
        )
