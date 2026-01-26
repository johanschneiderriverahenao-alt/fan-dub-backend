"""
Authentication controller for user login and token management.
"""
# pylint: disable=W0718,R0914

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import bcrypt
from jose import JWTError, jwt
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from bson import ObjectId

from app.config.settings import settings
from app.config.database import database
from app.models.user import UserLogin, UserResponse, UserInDB, UserBase, ChangePassword
from app.utils.logger import get_logger, log_info, log_error

logger = get_logger(__name__)


class AuthController:
    """Authentication controller for user operations."""

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt.

        Args:
            password: Plain text password.

        Returns:
            Hashed password string.
        """
        try:
            password_bytes = password.encode('utf-8')[:72]
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(password_bytes, salt)
            return hashed.decode('utf-8')
        except Exception as e:
            log_error(logger, "Error hashing password", {"error": str(e)})
            raise

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify a plain password against its hash.

        Args:
            plain_password: Plain text password.
            hashed_password: Hashed password.

        Returns:
            True if password matches, False otherwise.
        """
        try:
            password_bytes = plain_password.encode('utf-8')[:72]
            hashed_bytes = hashed_password.encode('utf-8')
            return bcrypt.checkpw(password_bytes, hashed_bytes)
        except Exception as e:
            log_error(logger, "Error verifying password", {"error": str(e)})
            return False

    @staticmethod
    def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
        """
        Create a JWT access token.

        Args:
            user_id: User ID to encode in token.
            expires_delta: Custom expiration time.

        Returns:
            JWT token string.
        """
        try:
            if expires_delta:
                expire = datetime.now(timezone.utc) + expires_delta
            else:
                expire = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.access_token_expire_minutes
                )

            to_encode = {"sub": user_id, "exp": expire}
            encoded_jwt = jwt.encode(
                to_encode,
                settings.secret_key,
                algorithm=settings.algorithm
            )
            log_info(logger, f"Access token created for user {user_id}")
            return encoded_jwt
        except Exception as e:
            log_error(logger, "Error creating access token", {"error": str(e)})
            raise

    @staticmethod
    def verify_token(token: str) -> str:
        """
        Verify and decode a JWT token.

        Args:
            token: JWT token to verify.

        Returns:
            User ID extracted from token.

        Raises:
            HTTPException if token is invalid or expired.
        """
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.algorithm]
            )
            user_id: str = payload.get("sub")
            if user_id is None:
                log_error(logger, "Token verification failed: no user ID", {})
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
            return user_id
        except JWTError as e:
            log_error(logger, "JWT verification error", {"error": str(e)})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired or invalid"
            ) from e
        except Exception as e:
            log_error(logger, "Unexpected error verifying token", {"error": str(e)})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token verification failed"
            ) from e

    @staticmethod
    async def login(login_data: UserLogin) -> JSONResponse:
        """
        Authenticate user and return access token.

        Args:
            login_data: User login credentials.

        Returns:
            JSONResponse with access token and user data.

        Raises:
            HTTPException if credentials are invalid.
        """
        try:
            user = await database["users"].find_one({"email": login_data.email})

            if not user or not AuthController.verify_password(
                login_data.password,
                user["password_hash"]
            ):
                log_info(logger, f"Failed login attempt for email {login_data.email}")

                try:
                    await database["audit_logs"].insert_one({
                        "user_email": login_data.email,
                        "action": "LOGIN",
                        "status": "FAILED",
                        "details": {"reason": "Invalid credentials"},
                        "created_at": datetime.utcnow()
                    })
                except Exception as audit_error:
                    log_error(logger, "Failed to create audit log for failed login",
                              {"error": str(audit_error)})

                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password"
                )

            access_token = AuthController.create_access_token(str(user["_id"]))

            user["_id"] = str(user["_id"])
            if isinstance(user.get("created_at"), datetime):
                user["created_at"] = user["created_at"].isoformat()
            user_response = UserResponse(**user)

            log_info(logger, f"User {login_data.email} logged in successfully")

            try:
                await database["audit_logs"].insert_one({
                    "user_id": user["_id"],
                    "user_email": login_data.email,
                    "action": "LOGIN",
                    "status": "SUCCESS",
                    "details": {"ip": "unknown", "user_agent": "unknown"},
                    "created_at": datetime.utcnow()
                })
            except Exception as audit_error:
                log_error(logger, "Failed to create audit log for successful login",
                          {"error": str(audit_error)})

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "access_token": access_token,
                    "token_type": "bearer",
                    "user": user_response.dict(),
                    "log": f"User {login_data.email} authenticated successfully"
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            log_error(logger, "Unexpected error during login", {"error": str(e)})
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Login failed", "log": str(e)}
            )

    @staticmethod
    async def get_current_user(token: str) -> Dict[str, Any]:
        """
        Get current user from token.

        Args:
            token: JWT token.

        Returns:
            User data dictionary.

        Raises:
            HTTPException if token is invalid or user not found.
        """
        try:
            user_id = AuthController.verify_token(token)
            user = await database["users"].find_one({"_id": ObjectId(user_id)})
            if not user:
                log_error(logger, f"User {user_id} not found in database")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found"
                )

            return UserInDB(**user).dict()

        except HTTPException:
            raise
        except Exception as e:
            log_error(logger, "Error getting current user", {"error": str(e)})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials"
            ) from e

    @staticmethod
    async def register(user_data: UserBase) -> JSONResponse:
        """
        Register a new user.

        Args:
            user_data: User registration data (email, password).

        Returns:
            JSONResponse with new user data on success.

        Raises:
            HTTPException if email already exists or registration fails.
        """
        try:
            existing_user = await database["users"].find_one({"email": user_data.email})
            if existing_user:
                log_info(logger, f"Registration attempt with existing email: {user_data.email}")
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"error": "Email already registered"}
                )

            hashed_password = AuthController.hash_password(user_data.password)

            new_user = {
                "email": user_data.email,
                "password_hash": hashed_password,
                "created_at": datetime.utcnow()
            }

            result = await database["users"].insert_one(new_user)

            log_info(logger, f"User registered successfully: {user_data.email}")

            try:
                await database["audit_logs"].insert_one({
                    "user_id": result.inserted_id,
                    "user_email": user_data.email,
                    "action": "REGISTER",
                    "status": "SUCCESS",
                    "details": {"method": "email_password"},
                    "created_at": datetime.utcnow()
                })
            except Exception as audit_error:
                log_error(logger, "Failed to create audit log for registration",
                          {"error": str(audit_error)})

            return JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content={
                    "message": "User registered successfully",
                    "user_id": str(result.inserted_id),
                    "email": user_data.email
                }
            )

        except Exception as e:
            log_error(logger, "Unexpected error during registration", {"error": str(e)})
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Registration failed", "details": str(e)}
            )

    @staticmethod
    async def change_password(password_data: ChangePassword) -> JSONResponse:
        """
        Change a user's password when email and current password match.

        Args:
            password_data: Contains `email`, `current_password`, and `new_password`.

        Returns:
            JSONResponse with operation result.
        """
        try:
            db = database["users"]
            user = await db.find_one({"email": password_data.email})
            if not user:
                log_info(logger, f"Password change attempt for unknown email {password_data.email}")
                return JSONResponse(status_code=404, content={"error": "User not found"})

            if not AuthController.verify_password(
                    password_data.current_password, user["password_hash"]):
                try:
                    await database["audit_logs"].insert_one({
                        "user_email": password_data.email,
                        "action": "PASSWORD_CHANGE",
                        "status": "FAILED",
                        "details": {"reason": "Incorrect current password"},
                        "created_at": datetime.utcnow()
                    })
                except Exception as audit_error:
                    log_error(
                        logger, "Failed to create audit log for failed password change",
                        {"error": str(audit_error)})

                log_info(logger, f"Incorrect current password for email {password_data.email}")
                return JSONResponse(
                        status_code=401, content={"error": "Current password is incorrect"})

            new_hashed = AuthController.hash_password(password_data.new_password)
            await db.update_one({"_id": user["_id"]}, {"$set": {"password_hash": new_hashed}})

            try:
                await database["audit_logs"].insert_one({
                    "user_id": str(user.get("_id")),
                    "user_email": password_data.email,
                    "action": "PASSWORD_CHANGE",
                    "status": "SUCCESS",
                    "details": {"method": "email_and_current_password"},
                    "created_at": datetime.utcnow()
                })
            except Exception as audit_error:
                log_error(
                    logger,
                    "Failed to create audit log for successful password change",
                    {"error": str(audit_error)})

            log_info(logger, f"Password changed successfully for email {password_data.email}")
            return JSONResponse(
                status_code=200, content={"message": "Password changed successfully"})

        except Exception as e:
            log_error(logger, "Unexpected error changing password", {"error": str(e)})
            return JSONResponse(
                status_code=500, content={"error": "Password change failed", "details": str(e)})
