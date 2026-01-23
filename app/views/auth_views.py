"""
Authentication views for user login operations.
"""
# pylint: disable=R0801,W0718

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models.user import UserLogin, UserBase
from app.controllers.auth_controller import AuthController
from app.utils.logger import get_logger

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
