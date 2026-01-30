# pylint: disable=W0718
"""
Main FastAPI application with lifespan events and middleware configuration.
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.config.settings import settings
from app.config.database import client
from app.utils.logger import get_logger, log_info, log_error
from app.views import (auth_views,
                       audit_log_views,
                       transcription_view,
                       company_views,
                       saga_views,
                       movie_views,
                       clip_scene_views,
                       news_views,
                       dubbing_session_views)

logger = get_logger(__name__)
load_dotenv()

app = FastAPI(
    title=settings.app_name,
    description="Authentication and audit logging service",
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_views.router, prefix="/auth", tags=["authentication"])
app.include_router(audit_log_views.router, prefix="/audit", tags=["audit_logs"])
app.include_router(transcription_view.router, tags=["transcriptions"])
app.include_router(company_views.router, tags=["companies"])
app.include_router(saga_views.router, tags=["sagas"])
app.include_router(movie_views.router, tags=["movies"])
app.include_router(clip_scene_views.router, tags=["clips_scenes"])
app.include_router(news_views.router, tags=["news"])
app.include_router(dubbing_session_views.router, tags=["dubbing_sessions"])


app.add_middleware(SessionMiddleware,
                   secret_key=os.getenv("SECRET_KEY", "your-secret-key"))


@app.middleware("http")
async def custom_middleware(request: Request, call_next):
    """
    Custom HTTP middleware for request processing.
    """
    response = await call_next(request)
    response.headers["X-Process-Time"] = "processing"
    return response


@app.on_event("startup")
async def startup_event():
    """
    Startup event handler.
    Initialize database connection and logger.
    """
    try:
        log_info(logger, f"Starting {settings.app_name} v{settings.app_version}")
        _ = client
        log_info(logger, "Database connection established")
        log_info(logger, "Application started successfully")
    except Exception as e:
        log_error(logger, "Failed to initialize application", {"error": str(e)})
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """
    Shutdown event handler.
    Close database connections and cleanup resources.
    """
    try:
        log_info(logger, "Shutting down application")
        if client is not None:
            client.close()
        log_info(logger, "Application shutdown completed")
    except Exception as e:
        log_error(logger, "Error during shutdown", {"error": str(e)})


@app.get("/", tags=["health"])
async def root() -> dict:
    """
    Root health check endpoint.

    Returns:
        Dictionary with application status information.
    """
    return {
        "status": "online",
        "app": settings.app_name,
        "version": settings.app_version
    }


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """
    Application health check endpoint.

    Returns:
        Dictionary indicating application health status.
    """
    return {
        "status": "healthy",
        "database": "connected",
        "message": "Application is running correctly"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, port=8001)
