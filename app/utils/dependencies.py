"""
Dependency functions for FastAPI routes.
"""
from typing import Dict, Any
from fastapi import Header, HTTPException, status, Depends

from app.controllers.auth_controller import AuthController
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def get_current_user_from_token(
    authorization: str = Header(None, description="Bearer token")
) -> Dict[str, Any]:
    """
    Extract and validate the current user from the Authorization header.

    Args:
        authorization: Authorization header with Bearer token.

    Returns:
        User data dictionary.

    Raises:
        HTTPException if token is invalid or missing.
    """
    if not authorization:
        logger.warning("Missing authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing"
        )

    if not authorization.startswith("Bearer "):
        logger.warning("Invalid authorization header format")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected 'Bearer <token>'"
        )

    token = authorization.replace("Bearer ", "").strip()

    if not token:
        logger.warning("Missing token in authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token not provided"
        )

    user = await AuthController.get_current_user(token)
    return user


async def get_current_admin(
    current_user: Dict[str, Any] = Depends(AuthController.get_current_user)
) -> Dict[str, Any]:
    """
    Verify that the current user has admin role.

    Args:
        current_user: Current user data from token.

    Returns:
        User data dictionary if user is admin.

    Raises:
        HTTPException if user is not admin.
    """
    user_role = current_user.get("role", "user")

    if user_role != "admin":
        logger.warning("Access denied for user %s - insufficient permissions",
                       current_user.get('email'))
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Admin role required."
        )

    logger.info("Admin access granted for user %s", current_user.get('email'))
    return current_user
