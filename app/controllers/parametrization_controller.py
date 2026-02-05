"""
Parametrization controller: business logic for system configuration.
"""
# pylint: disable=W0718,R0801
from datetime import datetime
from typing import Any
from fastapi.responses import JSONResponse
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.config.database import database
from app.models.parametrization_model import ParametrizationCreate, ParametrizationUpdate
from app.utils.logger import get_logger, log_info, log_error

logger = get_logger(__name__)


class ParametrizationController:
    """Business logic for parametrization operations."""

    @staticmethod
    async def get_by_type(param_type: str) -> JSONResponse:
        """Get parametrization by type.

        Args:
            param_type: Type identifier

        Returns:
            JSONResponse with parametrization data
        """
        try:
            param = await database["parametrization"].find_one(
                {"type": param_type, "is_active": True}
            )
            if not param:
                return JSONResponse(
                    status_code=404,
                    content={"detail": f"Parametrization '{param_type}' not found"}
                )

            param_data = {**param, "_id": str(param["_id"])}
            for field in ["created_at", "updated_at"]:
                if field in param_data and isinstance(param_data[field], datetime):
                    param_data[field] = param_data[field].isoformat()

            return JSONResponse(status_code=200, content={"data": param_data})

        except PyMongoError as e:
            log_error(logger, f"Database error getting parametrization: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Database error"}
            )
        except Exception as e:
            log_error(logger, f"Error getting parametrization: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    @staticmethod
    async def get_config_value(param_type: str, key: str, default: Any = None) -> Any:
        """Get a specific config value from parametrization.

        Args:
            param_type: Type identifier
            key: Config key
            default: Default value if not found

        Returns:
            Config value or default
        """
        try:
            param = await database["parametrization"].find_one(
                {"type": param_type, "is_active": True}
            )
            if not param:
                return default

            return param.get("config", {}).get(key, default)

        except Exception as e:
            log_error(logger, f"Error getting config value: {str(e)}")
            return default

    @staticmethod
    async def list_all() -> JSONResponse:
        """List all parametrizations.

        Returns:
            JSONResponse with list of parametrizations
        """
        try:
            params = await database["parametrization"].find().to_list(length=None)

            serialized_params = []
            for param in params:
                param_data = {**param, "_id": str(param["_id"])}
                for field in ["created_at", "updated_at"]:
                    if field in param_data and isinstance(param_data[field], datetime):
                        param_data[field] = param_data[field].isoformat()
                serialized_params.append(param_data)

            return JSONResponse(
                status_code=200,
                content={"data": serialized_params, "count": len(serialized_params)}
            )

        except PyMongoError as e:
            log_error(logger, f"Database error listing parametrizations: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Database error"}
            )
        except Exception as e:
            log_error(logger, f"Error listing parametrizations: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    @staticmethod
    async def create(param_data: ParametrizationCreate) -> JSONResponse:
        """Create new parametrization.

        Args:
            param_data: Parametrization data

        Returns:
            JSONResponse with created parametrization
        """
        try:
            existing = await database["parametrization"].find_one({"type": param_data.type})
            if existing:
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"Parametrization type '{param_data.type}' already exists"}
                )

            param_dict = param_data.model_dump()
            param_dict["created_at"] = datetime.utcnow()
            param_dict["updated_at"] = datetime.utcnow()

            result = await database["parametrization"].insert_one(param_dict)

            response_data = {
                **param_dict,
                "_id": str(result.inserted_id),
                "created_at": param_dict["created_at"].isoformat(),
                "updated_at": param_dict["updated_at"].isoformat()
            }

            log_info(logger, f"Parametrization created: {param_data.type}")

            return JSONResponse(
                status_code=201,
                content={"detail": "Parametrization created successfully", "data": response_data}
            )

        except PyMongoError as e:
            log_error(logger, f"Database error creating parametrization: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Database error"}
            )
        except Exception as e:
            log_error(logger, f"Error creating parametrization: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    @staticmethod
    async def update(param_id: str, param_data: ParametrizationUpdate) -> JSONResponse:
        """Update parametrization.

        Args:
            param_id: Parametrization ID
            param_data: Update data

        Returns:
            JSONResponse with update result
        """
        try:
            try:
                obj_id = ObjectId(param_id)
            except InvalidId:
                return JSONResponse(
                    status_code=400, content={"detail": "Invalid parametrization ID"}
                )

            update_dict = {k: v for k, v in param_data.model_dump().items() if v is not None}
            if not update_dict:
                return JSONResponse(
                    status_code=400, content={"detail": "No fields to update"}
                )

            update_dict["updated_at"] = datetime.utcnow()

            result = await database["parametrization"].update_one(
                {"_id": obj_id},
                {"$set": update_dict}
            )

            if result.matched_count == 0:
                return JSONResponse(
                    status_code=404, content={"detail": "Parametrization not found"}
                )

            log_info(logger, f"Parametrization updated: {param_id}")

            return JSONResponse(
                status_code=200,
                content={"detail": "Parametrization updated successfully"}
            )

        except PyMongoError as e:
            log_error(logger, f"Database error updating parametrization: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Database error"}
            )
        except Exception as e:
            log_error(logger, f"Error updating parametrization: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    @staticmethod
    async def delete(param_id: str) -> JSONResponse:
        """Delete parametrization.

        Args:
            param_id: Parametrization ID

        Returns:
            JSONResponse with deletion result
        """
        try:
            try:
                obj_id = ObjectId(param_id)
            except InvalidId:
                return JSONResponse(
                    status_code=400, content={"detail": "Invalid parametrization ID"}
                )

            result = await database["parametrization"].delete_one({"_id": obj_id})

            if result.deleted_count == 0:
                return JSONResponse(
                    status_code=404, content={"detail": "Parametrization not found"}
                )

            log_info(logger, f"Parametrization deleted: {param_id}")

            return JSONResponse(
                status_code=200,
                content={"detail": "Parametrization deleted successfully"}
            )

        except PyMongoError as e:
            log_error(logger, f"Database error deleting parametrization: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Database error"}
            )
        except Exception as e:
            log_error(logger, f"Error deleting parametrization: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    @staticmethod
    async def initialize_default_configs() -> None:
        """Initialize default parametrization configs if they don't exist."""
        try:
            credits_config = await database["parametrization"].find_one({"type": "credits_config"})
            if not credits_config:
                await database["parametrization"].insert_one({
                    "type": "credits_config",
                    "name": "Credits Configuration",
                    "description": "Daily limits and credits configuration",
                    "config": {
                        "daily_free_limit": 3,
                        "daily_ad_limit": 3,
                        "credits_never_expire": True
                    },
                    "is_active": True,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                })
                log_info(logger, "Default credits_config initialized")

            ads_config = await database["parametrization"].find_one({"type": "ads_config"})
            if not ads_config:
                await database["parametrization"].insert_one({
                    "type": "ads_config",
                    "name": "Ads Configuration",
                    "description": "Advertisement system configuration",
                    "config": {
                        "enabled": True,
                        "providers": ["google_adsense", "custom"],
                        "min_watch_duration_seconds": 15
                    },
                    "is_active": True,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                })
                log_info(logger, "Default ads_config initialized")

        except Exception as e:
            log_error(logger, f"Error initializing default configs: {str(e)}")
