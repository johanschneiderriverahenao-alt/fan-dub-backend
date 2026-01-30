"""
Authentication controller for user login and token management.
"""
# pylint: disable=W0718,R0914,C0302

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import re
import secrets
import bcrypt
from jose import JWTError, jwt
from fastapi import HTTPException, status, Header
from fastapi.responses import JSONResponse
from bson import ObjectId

from app.config.settings import settings
from app.config.database import database
from app.models.user import (
    UserLogin,
    UserResponse,
    UserInDB,
    UserBase,
    ChangePassword,
    ChangeEmail,
    VerificationRequest,
    VerificationConfirm,
    RegisterWithVerification,
    ChangePasswordWithVerification,
)
from app.services.email_service import EmailService
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
    async def _audit_log(user_email: str, action: str, status_text: str,
                         details: dict, user_id: Optional[str] = None) -> None:
        """Insert an audit log entry, errors are logged but do not raise."""
        try:
            entry = {
                "user_email": user_email,
                "action": action,
                "status": status_text,
                "details": details,
                "created_at": datetime.utcnow(),
            }
            if user_id:
                entry["user_id"] = user_id
            await database["audit_logs"].insert_one(entry)
        except Exception as e:
            log_error(logger, f"Failed to create audit log for {action}", {"error": str(e)})

    @staticmethod
    async def _get_user_by_email(email: str) -> Optional[dict]:
        """Return user document by email or None."""
        try:
            return await database["users"].find_one({"email": email})
        except Exception as e:
            log_error(logger, "Error fetching user by email", {"error": str(e), "email": email})
            return None

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
    async def send_verification_code(verification_request: VerificationRequest) -> JSONResponse:
        """
        Send a verification code to the user's email.

        Args:
            verification_request: Contains email and purpose (registration or password_change).

        Returns:
            JSONResponse indicating success or failure.
        """
        try:
            email_norm = AuthController._validate_and_normalize_email(
                getattr(verification_request, "email", None)
            )
            purpose = verification_request.purpose

            if purpose == "registration":
                existing_user = await database["users"].find_one({"email": email_norm})
                if existing_user:
                    log_error(logger, "Registration verification failed: email already exists",
                              {"email": email_norm})
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="El correo ya está registrado"
                    )

            if purpose == "password_change":
                user = await database["users"].find_one({"email": email_norm})
                if not user:
                    log_error(logger, "Password change verification failed: user not found",
                              {"email": email_norm})
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Usuario no encontrado"
                    )

            code = EmailService.generate_verification_code()

            verification_data = {
                "email": email_norm,
                "code": code,
                "purpose": purpose,
                "created_at": datetime.utcnow(),
                "expires_at": datetime.utcnow() + timedelta(minutes=10),
                "verified": False
            }

            await database["verification_codes"].delete_many({
                "email": email_norm,
                "purpose": purpose
            })

            await database["verification_codes"].insert_one(verification_data)

            email_sent = await EmailService.send_verification_email(
                email_norm, code, purpose
            )

            if not email_sent:
                log_error(logger, "Failed to send verification email", {"email": email_norm})
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="No se pudo enviar el correo de verificación"
                )

            log_info(logger, f"Verification code sent to {email_norm}", {"purpose": purpose})

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "Código de verificación enviado correctamente",
                    "email": email_norm,
                    "expires_in_minutes": 10
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            log_error(logger, "Unexpected error sending verification code", {"error": str(e)})
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"message": "Error al enviar el código de verificación", "details": str(e)}
            )

    @staticmethod
    async def verify_code(verification_confirm: VerificationConfirm) -> JSONResponse:
        """
        Verify a code and return a verification token.

        Args:
            verification_confirm: Contains email, code, and purpose.

        Returns:
            JSONResponse with verification token on success.
        """
        try:
            email_norm = AuthController._validate_and_normalize_email(
                getattr(verification_confirm, "email", None)
            )
            code = verification_confirm.code
            purpose = verification_confirm.purpose

            verification_record = await database["verification_codes"].find_one({
                "email": email_norm,
                "code": code,
                "purpose": purpose,
                "verified": False
            })

            if not verification_record:
                log_error(logger, "Invalid or expired verification code",
                          {"email": email_norm, "purpose": purpose})
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Código de verificación inválido o expirado"
                )

            if verification_record["expires_at"] < datetime.utcnow():
                await database["verification_codes"].delete_one({"_id": verification_record["_id"]})
                log_error(logger, "Verification code expired", {"email": email_norm})
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El código de verificación ha expirado"
                )

            verification_token = secrets.token_urlsafe(32)

            await database["verification_codes"].update_one(
                {"_id": verification_record["_id"]},
                {
                    "$set": {
                        "verified": True,
                        "verification_token": verification_token,
                        "token_expires_at": datetime.utcnow() + timedelta(minutes=30)
                    }
                }
            )

            log_info(logger, f"Verification code confirmed for {email_norm}", {"purpose": purpose})

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "Código verificado correctamente",
                    "verification_token": verification_token,
                    "expires_in_minutes": 30
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            log_error(logger, "Unexpected error verifying code", {"error": str(e)})
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"message": "Error al verificar el código", "details": str(e)}
            )

    @staticmethod
    async def register_with_verification(
        registration_data: RegisterWithVerification
    ) -> JSONResponse:
        """
        Complete user registration after email verification.

        Args:
            registration_data: Contains email, password, and verification_token.

        Returns:
            JSONResponse with new user data on success.
        """
        try:
            email_norm = AuthController._validate_and_normalize_email(
                getattr(registration_data, "email", None)
            )

            verification_record = await database["verification_codes"].find_one({
                "email": email_norm,
                "purpose": "registration",
                "verified": True,
                "verification_token": registration_data.verification_token
            })

            if not verification_record:
                log_error(logger, "Invalid verification token", {"email": email_norm})
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Token de verificación inválido"
                )

            if verification_record.get("token_expires_at", datetime.utcnow()) < datetime.utcnow():
                await database["verification_codes"].delete_one({"_id": verification_record["_id"]})
                log_error(logger, "Verification token expired", {"email": email_norm})
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El token de verificación ha expirado"
                )

            existing_user = await database["users"].find_one({"email": email_norm})
            if existing_user:
                log_error(logger, "User already exists", {"email": email_norm})
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El correo ya está registrado"
                )

            AuthController._validate_password_for_registration(
                getattr(registration_data, "password", None), email_norm
            )

            hashed_password = AuthController.hash_password(registration_data.password)

            new_user = {
                "email": email_norm,
                "password_hash": hashed_password,
                "created_at": datetime.utcnow()
            }

            result = await database["users"].insert_one(new_user)

            await database["verification_codes"].delete_one({"_id": verification_record["_id"]})

            log_info(logger, f"User registered successfully with verification: {email_norm}")

            try:
                await AuthController._audit_log(
                    user_email=email_norm,
                    action="register_with_verification",
                    status_text="success",
                    details={"user_id": str(result.inserted_id)},
                    user_id=str(result.inserted_id)
                )
            except Exception as audit_error:
                log_error(logger, "Failed to log registration audit", {"error": str(audit_error)})

            return JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content={
                    "message": "Usuario registrado exitosamente",
                    "user_id": str(result.inserted_id),
                    "email": email_norm
                }
            )

        except HTTPException:
            raise
        except Exception as e:
            log_error(logger, "Unexpected error during registration", {"error": str(e)})
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"message": "Error al registrar usuario", "details": str(e)}
            )

    @staticmethod
    async def change_password_with_verification(
        password_data: ChangePasswordWithVerification
    ) -> JSONResponse:
        """
        Change user password after email verification.

        Args:
            password_data: Contains email, new_password, and verification_token.

        Returns:
            JSONResponse with operation result.
        """
        try:
            email_norm = AuthController._validate_and_normalize_email(
                getattr(password_data, "email", None)
            )

            verification_record = await database["verification_codes"].find_one({
                "email": email_norm,
                "purpose": "password_change",
                "verified": True,
                "verification_token": password_data.verification_token
            })

            if not verification_record:
                log_error(logger, "Invalid verification token for password change",
                          {"email": email_norm})
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Token de verificación inválido"
                )

            if verification_record.get("token_expires_at", datetime.utcnow()) < datetime.utcnow():
                await database["verification_codes"].delete_one({"_id": verification_record["_id"]})
                log_error(logger, "Verification token expired for password change",
                          {"email": email_norm})
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El token de verificación ha expirado"
                )

            user = await database["users"].find_one({"email": email_norm})
            if not user:
                log_error(logger, "User not found for password change", {"email": email_norm})
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Usuario no encontrado"
                )

            AuthController._validate_password_for_registration(
                getattr(password_data, "new_password", None), email_norm
            )

            new_hashed_password = AuthController.hash_password(password_data.new_password)

            await database["users"].update_one(
                {"_id": user["_id"]},
                {"$set": {"password_hash": new_hashed_password}}
            )

            await database["verification_codes"].delete_one({"_id": verification_record["_id"]})

            log_info(logger, f"Password changed successfully with verification for {email_norm}")

            try:
                await AuthController._audit_log(
                    user_email=email_norm,
                    action="change_password_with_verification",
                    status_text="success",
                    details={},
                    user_id=str(user["_id"])
                )
            except Exception as audit_error:
                log_error(logger, "Failed to log password change audit",
                          {"error": str(audit_error)})

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"message": "Contraseña cambiada exitosamente"}
            )

        except HTTPException:
            raise
        except Exception as e:
            log_error(logger, "Unexpected error changing password", {"error": str(e)})
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"message": "Error al cambiar la contraseña", "details": str(e)}
            )

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
            email_norm = AuthController._validate_and_normalize_email(
                getattr(login_data, "email", None)
            )

            user = await database["users"].find_one({"email": email_norm})

            if not user or not AuthController.verify_password(
                login_data.password,
                user["password_hash"],
            ):
                log_info(logger, f"Failed login attempt for email {login_data.email}")

                try:
                    await database["audit_logs"].insert_one({
                        "user_email": login_data.email,
                        "action": "LOGIN",
                        "status": "FAILED",
                        "details": {"reason": "Invalid credentials"},
                        "created_at": datetime.utcnow(),
                    })
                except Exception as audit_error:
                    log_error(logger, "Failed to create audit log for failed login",
                              {"error": str(audit_error)})

                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password",
                )

            access_token = AuthController.create_access_token(str(user["_id"]))

            user["_id"] = str(user["_id"])
            if isinstance(user.get("created_at"), datetime):
                user["created_at"] = user["created_at"].isoformat()
            user_response = UserResponse(**user)

            log_info(logger, f"User {login_data.email} logged in successfully")

            try:
                await database["audit_logs"].insert_one({
                    "user_id": str(user["_id"]),
                    "user_email": login_data.email,
                    "action": "LOGIN",
                    "status": "SUCCESS",
                    "details": {"ip": "unknown", "user_agent": "unknown"},
                    "created_at": datetime.utcnow(),
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
                    "log": f"User {login_data.email} authenticated successfully",
                },
            )

        except HTTPException:
            raise
        except Exception as e:
            log_error(logger, "Unexpected error during login", {"error": str(e)})
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"message": "Login failed", "log": str(e)},
            )

    @staticmethod
    def _validate_and_normalize_email(email: Optional[str]) -> str:
        """Normalize and validate email for basic rules.

        Raises HTTPException with exact messages on validation failures.
        """
        if not email or (isinstance(email, str) and email.strip() == ""):
            log_error(logger, "Email validation failed: missing email", {})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="El correo es obligatorio")

        if isinstance(email, str) and " " in email:
            log_error(logger, "Email validation failed: contains spaces", {"email": email})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El correo no debe contener espacios")

        email_norm = email.lower()

        if len(email_norm) > 254:
            log_error(logger, "Email validation failed: too long", {"email": email_norm})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="El correo es demasiado largo")

        email_regex = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
        if not email_regex.match(email_norm):
            log_error(logger, "Email validation failed: invalid format", {"email": email_norm})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ingresa un correo electrónico válido")

        return email_norm

    @staticmethod
    async def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
        """
        Get current user from the `Authorization` header.

        Args:
            authorization: Authorization header value, e.g. 'Bearer <token>'.

        Returns:
            User data dictionary.

        Raises:
            HTTPException if token is missing, invalid, or user not found.
        """
        try:
            if not authorization:
                log_error(logger, "Missing authorization header", {})
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing authorization header"
                )

            if authorization.lower().startswith("bearer "):
                token = authorization.split(" ", 1)[1]
            else:
                token = authorization

            user_id = AuthController.verify_token(token)
            user = await database["users"].find_one({"_id": ObjectId(user_id)})
            if not user:
                log_error(logger, f"User {user_id} not found in database")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User not found"
                )

            user["_id"] = str(user["_id"])
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
            email_norm = AuthController._validate_and_normalize_email(
                getattr(user_data, "email", None))

            AuthController._validate_password_for_registration(
                getattr(user_data, "password", None), email_norm)

            existing_user = await database["users"].find_one({"email": email_norm})
            if existing_user:
                log_info(logger, f"Registration attempt with existing email: {email_norm}")
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"message": "Email already registered"}
                )

            hashed_password = AuthController.hash_password(user_data.password)

            new_user = {
                "email": email_norm,
                "password_hash": hashed_password,
                "created_at": datetime.utcnow()
            }

            result = await database["users"].insert_one(new_user)

            log_info(logger, f"User registered successfully: {user_data.email}")

            try:
                await database["audit_logs"].insert_one({
                    "user_id": str(result.inserted_id),
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
                content={"message": "Registration failed", "details": str(e)}
            )

    @staticmethod
    def _validate_password_for_registration(password: Optional[str], email: str) -> None:
        """Validate password according to the complex business rules for registration.

        Raises HTTPException with exact messages when validation fails.
        """
        if not password or (isinstance(password, str) and password == ""):
            log_error(logger, "Password validation failed: missing password", {})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña es obligatoria")

        if len(password) < 8:
            log_error(logger, "Password validation failed: too short", {})
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Debe tener al menos 8 caracteres")

        if " " in password:
            log_error(logger, "Password validation failed: contains spaces", {})
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="La contraseña no puede contener espacios")

        if password.lower() == (email or "").lower():
            log_error(logger, "Password validation failed: equals email", {"email": email})
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="La contraseña no puede ser igual al correo")

        if not re.search(r"[A-Z]", password):
            log_error(logger, "Password validation failed: missing uppercase", {})
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Debe incluir al menos una letra mayúscula")

        if not re.search(r"[a-z]", password):
            log_error(logger, "Password validation failed: missing lowercase", {})
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Debe incluir al menos una letra minúscula")

        if not re.search(r"[0-9]", password):
            log_error(logger, "Password validation failed: missing number", {})
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Debe incluir al menos un número")

        allowed_specials = "!@#$%^&*()_+-=[]{}|;:'\",.<>?/\\"
        special_class = re.escape(allowed_specials)
        if not re.search(r"[" + special_class + r"]", password):
            log_error(logger, "Password validation failed: missing special char", {})
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Debe incluir al menos un carácter especial")

        allowed_pattern = r"^[A-Za-z0-9" + special_class + r"]+$"
        if not re.match(allowed_pattern, password):
            log_error(logger, "Password validation failed: invalid characters", {})
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="La contraseña contiene caracteres no permitidos")

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
            email_norm = AuthController._validate_and_normalize_email(
                getattr(password_data, "email", None)
            )

            AuthController._validate_password_for_registration(
                getattr(password_data, "new_password", None), email_norm
            )

            db = database["users"]
            user = await db.find_one({"email": email_norm})
            if not user:
                log_info(logger, f"Password change attempt for unknown email {email_norm}")
                return JSONResponse(status_code=404, content={"error": "User not found"})

            if not AuthController.verify_password(
                    password_data.current_password, user["password_hash"]):
                await AuthController._audit_log(
                    email_norm,
                    "PASSWORD_CHANGE",
                    "FAILED",
                    {"reason": "Incorrect current password"},
                    user_id=str(user.get("_id")) if user else None,
                )

                log_info(logger, f"Incorrect current password for email {email_norm}")
                return JSONResponse(
                    status_code=401, content={"error": "Current password is incorrect"})

            if password_data.new_password == password_data.current_password:
                await AuthController._audit_log(
                    email_norm,
                    "PASSWORD_CHANGE",
                    "FAILED",
                    {"reason": "New password equals current password"},
                    user_id=str(user.get("_id")) if user else None,
                )

                log_info(logger, f"Attempt to change to same password for email {email_norm}")
                return JSONResponse(
                    status_code=400,
                    content={"error": "New password must be different from current passwords"}
                )

            new_hashed = AuthController.hash_password(password_data.new_password)
            await db.update_one({"_id": user["_id"]}, {"$set": {"password_hash": new_hashed}})

            await AuthController._audit_log(
                email_norm,
                "PASSWORD_CHANGE",
                "SUCCESS",
                {"method": "email_and_current_password"},
                user_id=str(user.get("_id")) if user else None,
            )

            log_info(logger, f"Password changed successfully for email {email_norm}")
            return JSONResponse(
                status_code=200, content={"message": "Password changed successfully"})

        except HTTPException as http_exc:
            log_error(logger, "Validation error during password change",
                      {"detail": http_exc.detail, "status_code": http_exc.status_code})
            return JSONResponse(
                status_code=http_exc.status_code,
                content={"message": "Password change failed", "details": http_exc.detail}
            )
        except Exception as e:
            log_error(logger, "Unexpected error changing password", {"error": str(e)})
            return JSONResponse(
                status_code=500, content={"error": "Password change failed", "details": str(e)})

    @staticmethod
    async def change_email(email_data: ChangeEmail) -> JSONResponse:
        """Change a user's email after validating new and current email and password."""
        status_code = None
        content = None
        try:
            old_email = AuthController._validate_and_normalize_email(getattr(email_data,
                                                                             "email", None))
            new_email = AuthController._validate_and_normalize_email(getattr(email_data,
                                                                             "new_email", None))

            if old_email == new_email:
                log_info(logger, f"Attempt to change to same email for {old_email}")
                status_code = status.HTTP_400_BAD_REQUEST
                content = {"error": "New email must be different from current email"}
            else:
                user = await AuthController._get_user_by_email(old_email)
                if not user:
                    log_info(logger, f"Email change attempt for unknown email {old_email}")
                    status_code = status.HTTP_404_NOT_FOUND
                    content = {"error": "User not found"}
                else:
                    if not AuthController.verify_password(email_data.current_password,
                                                          user["password_hash"]):
                        await AuthController._audit_log(old_email, "EMAIL_CHANGE",
                                                        "FAILED", {"reason": "Incorrect password"},
                                                        user_id=str(user.get("_id"))
                                                        if user else None)
                        log_info(logger, f"Incorrect password for email change for {old_email}")
                        status_code = status.HTTP_401_UNAUTHORIZED
                        content = {"error": "Current password is incorrect"}
                    else:
                        existing = await AuthController._get_user_by_email(new_email)
                        if existing:
                            log_info(
                                logger,
                                f"Email change attempt to already-registered email {new_email}")
                            status_code = status.HTTP_400_BAD_REQUEST
                            content = {"error": "Email already registered"}
                        else:
                            await database["users"].update_one({"_id": user["_id"]},
                                                               {"$set": {"email": new_email}})
                            await AuthController._audit_log(old_email,
                                                            "EMAIL_CHANGE", "SUCCESS",
                                                            {"new_email": new_email},
                                                            user_id=str(user.get("_id"))
                                                            if user else None)
                            log_info(logger, f"Email changed from {old_email} to {new_email}")
                            status_code = status.HTTP_200_OK
                            content = {"message": "Email changed successfully", "email": new_email}

        except Exception as e:
            if isinstance(e, HTTPException):
                http_exc = e
                log_error(logger, "Validation error during email change",
                          {"detail": http_exc.detail, "status_code": http_exc.status_code})
                status_code = http_exc.status_code
                content = {"message": "Email change failed", "details": http_exc.detail}
            else:
                log_error(logger, "Unexpected error changing email", {"error": str(e)})
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
                content = {"error": "Email change failed", "details": str(e)}

        return JSONResponse(status_code=status_code, content=content)

    @staticmethod
    async def get_user_profile(user_id: str) -> JSONResponse:
        """
        Get user profile information by user ID.

        Args:
            user_id: The ID of the user.

        Returns:
            JSONResponse with user profile data.
        """
        try:
            user = await database["users"].find_one({"_id": ObjectId(user_id)})
            if not user:
                log_error(logger, f"User profile not found for user_id {user_id}")
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"error": "User not found"}
                )

            user["_id"] = str(user["_id"])
            if isinstance(user.get("created_at"), datetime):
                user["created_at"] = user["created_at"].isoformat()

            user_response = UserResponse(**user)
            log_info(logger, f"User profile retrieved for user_id {user_id}")

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"user": user_response.dict(by_alias=True)}
            )

        except Exception as e:
            log_error(logger, "Error retrieving user profile", {"error": str(e)})
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Failed to retrieve user profile", "details": str(e)}
            )

    @staticmethod
    async def delete_user(user_id: str) -> JSONResponse:
        """
        Delete a user and all related data from the database.

        Args:
            user_id: The ID of the user to delete.

        Returns:
            JSONResponse with operation result.
        """
        try:
            user = await database["users"].find_one({"_id": ObjectId(user_id)})
            if not user:
                log_error(logger, f"User not found for deletion: user_id {user_id}")
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND,
                    content={"error": "User not found"}
                )

            user_email = user.get("email", "unknown")

            try:
                audit_delete_result = await database["audit_logs"].delete_many(
                    {"user_id": str(user_id)}
                )
                log_info(
                    logger,
                    f"Deleted {audit_delete_result.deleted_count} audit logs for user {user_id}"
                )
            except Exception as audit_error:
                log_error(
                    logger,
                    "Failed to delete audit logs during user deletion",
                    {"error": str(audit_error)}
                )

            delete_result = await database["users"].delete_one({"_id": ObjectId(user_id)})

            if delete_result.deleted_count == 0:
                log_error(logger, f"Failed to delete user {user_id}")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={"error": "Failed to delete user"}
                )

            try:
                await database["audit_logs"].insert_one({
                    "user_id": user_id,
                    "user_email": user_email,
                    "action": "USER_DELETION",
                    "status": "SUCCESS",
                    "details": {"deleted_by": "self"},
                    "created_at": datetime.utcnow()
                })
            except Exception as audit_error:
                log_error(
                    logger,
                    "Failed to create audit log for user deletion",
                    {"error": str(audit_error)}
                )

            log_info(logger, f"User {user_id} ({user_email}) deleted successfully")

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "User and related data deleted successfully",
                    "user_email": user_email
                }
            )

        except Exception as e:
            log_error(logger, "Unexpected error deleting user", {"error": str(e)})
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "User deletion failed", "details": str(e)}
            )

    @staticmethod
    async def update_user_role(user_email: str, new_role: str) -> JSONResponse:
        """Update a user's role (admin operation).

        Validates role and updates the user document.
        """
        try:
            if new_role not in ["user", "admin"]:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={"error": "Invalid role. Must be 'user' or 'admin'"},
                )

            email_norm = user_email.lower()

            result = await database["users"].update_one(
                {"email": email_norm}, {"$set": {"role": new_role}}
            )

            if getattr(result, "matched_count", 0) == 0:
                return JSONResponse(
                    status_code=status.HTTP_404_NOT_FOUND, content={"error": "User not found"}
                )

            log_info(logger, f"User {user_email} role updated to {new_role}")

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"message": f"User role updated to {new_role}", "email": user_email,
                         "role": new_role},
            )

        except Exception as e:
            log_error(logger, "Error updating user role", {"error": str(e)})
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "Failed to update user role", "details": str(e)},
            )
