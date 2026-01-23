"""
MongoDB connection configuration with Motor (async driver).
Optimized singleton pattern with connection pooling.
All collections in single database: fan_dub_db
"""

import os
import threading
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from dotenv import load_dotenv

from app.utils.logger import get_logger

load_dotenv()

logger = get_logger(__name__)


class OptimizedDatabaseManager:
    """
    Singleton Database Manager with optimized connection pooling.
    All collections in single database: fan_dub_db
    Manages MongoDB connections for the entire application.
    """

    _instance: Optional['OptimizedDatabaseManager'] = None
    _lock = threading.Lock()
    _client: Optional[AsyncIOMotorClient] = None

    def __new__(cls) -> 'OptimizedDatabaseManager':
        """Implement singleton pattern with thread safety."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize database manager."""
        if not hasattr(self, '_initialized'):
            self._initialized = True

    def _connect(self):
        """Initialize MongoDB client with async connection pooling."""
        if self._client is None:
            mongo_url = os.getenv("MONGODB_URL")
            if not mongo_url:
                logger.error("MONGODB_URL environment variable is not set")
                raise ValueError("MONGODB_URL environment variable is required")

            self._client = AsyncIOMotorClient(
                mongo_url,
                maxPoolSize=int(os.getenv("MONGO_MAX_POOL_SIZE", "50")),
                minPoolSize=int(os.getenv("MONGO_MIN_POOL_SIZE", "3")),
                maxIdleTimeMS=int(os.getenv("MONGO_MAX_IDLE_TIME_MS", "60000")),
                serverSelectionTimeoutMS=int(
                    os.getenv("MONGO_SERVER_SELECTION_TIMEOUT_MS", "5000")),
                socketTimeoutMS=int(os.getenv("MONGO_SOCKET_TIMEOUT_MS", "30000")),
                connectTimeoutMS=int(os.getenv("MONGO_CONNECT_TIMEOUT_MS", "10000")),
            )
            logger.info("MongoDB singleton initialized successfully")
            logger.info("All collections stored in database: fan_dub_db")

    @property
    def client(self) -> AsyncIOMotorClient:
        """Get the MongoDB client instance."""
        if self._client is None:
            self._connect()
        return self._client

    async def connect(self) -> None:
        """Connect to MongoDB."""
        self._connect()
        logger.info("Connected to MongoDB")

    async def disconnect(self) -> None:
        """Disconnect from MongoDB."""
        if self._client is not None:
            logger.info("Closing MongoDB connection")
            self._client.close()
            self._client = None


_db_manager = OptimizedDatabaseManager()

client = _db_manager.client
database = client["fan_dub_db"]


def get_users_collection() -> AsyncIOMotorCollection:
    """Get users collection for authentication."""
    return database["users"]


def get_audit_logs_collection() -> AsyncIOMotorCollection:
    """Get audit logs collection for tracking operations."""
    return database["audit_logs"]


async def connect_db() -> None:
    """
    Connect to MongoDB.

    Raises:
        ValueError: If MONGODB_URL is not set.
    """
    await _db_manager.connect()


async def close_db() -> None:
    """Close MongoDB connection."""
    await _db_manager.disconnect()


def get_db():
    """
    Get database instance.

    Returns:
        Database reference for MongoDB operations.

    Raises:
        RuntimeError: If database is not initialized.
    """
    if database is None:
        raise RuntimeError("Database not initialized. Run connect_db() first.")
    return database
