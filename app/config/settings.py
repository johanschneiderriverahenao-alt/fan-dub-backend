"""
Application configuration with Pydantic Settings.
Reads environment variables from .env file.
"""
# pylint: disable=R0903

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Main application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "fan_dub_db"

    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    cors_origins_str: str = "http://localhost:3000,http://localhost:8000"

    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_endpoint_url: str = ""
    r2_bucket_name: str = "dub-videos"
    r2_public_url: str = ""

    resend_api_key: str = ""
    resend_from_email: str = "YouDub 🎙️ <onboarding@resend.dev>"

    mercadopago_access_token: str = ""
    mercadopago_public_key: str = ""
    mercadopago_webhook_secret: str = ""
    mercadopago_success_url: str = "http://localhost:3000/payment/success"
    mercadopago_failure_url: str = "http://localhost:3000/payment/failure"
    mercadopago_pending_url: str = "http://localhost:3000/payment/pending"

    app_name: str = "Fan Dub Backend"
    app_version: str = "1.0.0"
    debug: bool = False

    @property
    def cors_origins(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        if self.cors_origins_str:
            return [origin.strip() for origin in self.cors_origins_str.split(",") if origin.strip()]
        return ["http://localhost:3000", "http://localhost:8000"]


settings = Settings()
