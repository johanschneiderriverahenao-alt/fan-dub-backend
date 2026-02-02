"""
Plan controller: business logic for admin-managed payment plans.
"""
# pylint: disable=W0718,R0801
from datetime import datetime
from typing import Optional
from fastapi.responses import JSONResponse
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError

from app.config.database import database
from app.models.plan_model import PlanCreate, PlanUpdate
from app.utils.logger import get_logger, log_info, log_error

logger = get_logger(__name__)


class PlanController:
    """Business logic for plan operations."""

    @staticmethod
    async def list_all(active_only: bool = False) -> JSONResponse:
        """List all plans.

        Args:
            active_only: If True, only return active plans

        Returns:
            JSONResponse with list of plans
        """
        try:
            query = {"is_active": True} if active_only else {}
            plans = await database["plans"].find(query).sort("sort_order", 1).to_list(length=None)

            serialized_plans = []
            for plan in plans:
                plan_data = {**plan, "_id": str(plan["_id"])}
                for field in ["created_at", "updated_at"]:
                    if field in plan_data and isinstance(plan_data[field], datetime):
                        plan_data[field] = plan_data[field].isoformat()
                serialized_plans.append(plan_data)

            return JSONResponse(
                status_code=200,
                content={"data": serialized_plans, "count": len(serialized_plans)}
            )

        except PyMongoError as e:
            log_error(logger, f"Database error listing plans: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Database error"}
            )
        except Exception as e:
            log_error(logger, f"Error listing plans: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    @staticmethod
    async def get_by_id(plan_id: str) -> JSONResponse:
        """Get plan by ID.

        Args:
            plan_id: Plan ID

        Returns:
            JSONResponse with plan data
        """
        try:
            try:
                obj_id = ObjectId(plan_id)
            except InvalidId:
                return JSONResponse(
                    status_code=400, content={"detail": "Invalid plan ID"}
                )

            plan = await database["plans"].find_one({"_id": obj_id})
            if not plan:
                return JSONResponse(
                    status_code=404, content={"detail": "Plan not found"}
                )

            plan_data = {**plan, "_id": str(plan["_id"])}
            for field in ["created_at", "updated_at"]:
                if field in plan_data and isinstance(plan_data[field], datetime):
                    plan_data[field] = plan_data[field].isoformat()

            return JSONResponse(status_code=200, content={"data": plan_data})

        except PyMongoError as e:
            log_error(logger, f"Database error getting plan: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Database error"}
            )
        except Exception as e:
            log_error(logger, f"Error getting plan: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    @staticmethod
    async def get_by_name(plan_name: str) -> JSONResponse:
        """Get plan by name.

        Args:
            plan_name: Plan name

        Returns:
            JSONResponse with plan data
        """
        try:
            plan = await database["plans"].find_one({"name": plan_name, "is_active": True})
            if not plan:
                return JSONResponse(
                    status_code=404, content={"detail": "Plan not found"}
                )

            plan_data = {**plan, "_id": str(plan["_id"])}
            for field in ["created_at", "updated_at"]:
                if field in plan_data and isinstance(plan_data[field], datetime):
                    plan_data[field] = plan_data[field].isoformat()

            return JSONResponse(status_code=200, content={"data": plan_data})

        except PyMongoError as e:
            log_error(logger, f"Database error getting plan: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Database error"}
            )
        except Exception as e:
            log_error(logger, f"Error getting plan: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    @staticmethod
    async def create(plan_data: PlanCreate, created_by: Optional[str] = None) -> JSONResponse:
        """Create new plan.

        Args:
            plan_data: Plan data
            created_by: User ID who created the plan

        Returns:
            JSONResponse with created plan
        """
        try:
            existing = await database["plans"].find_one({"name": plan_data.name})
            if existing:
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"Plan '{plan_data.name}' already exists"}
                )

            plan_dict = plan_data.model_dump()
            plan_dict["created_at"] = datetime.utcnow()
            plan_dict["updated_at"] = datetime.utcnow()
            if created_by:
                plan_dict["created_by"] = created_by

            result = await database["plans"].insert_one(plan_dict)

            response_data = {
                **plan_dict,
                "_id": str(result.inserted_id),
                "created_at": plan_dict["created_at"].isoformat(),
                "updated_at": plan_dict["updated_at"].isoformat()
            }

            log_info(logger, f"Plan created: {plan_data.name} by {created_by}")

            return JSONResponse(
                status_code=201,
                content={"detail": "Plan created successfully", "data": response_data}
            )

        except PyMongoError as e:
            log_error(logger, f"Database error creating plan: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Database error"}
            )
        except Exception as e:
            log_error(logger, f"Error creating plan: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    @staticmethod
    async def update(plan_id: str, plan_data: PlanUpdate) -> JSONResponse:
        """Update plan.

        Args:
            plan_id: Plan ID
            plan_data: Update data

        Returns:
            JSONResponse with update result
        """
        try:
            try:
                obj_id = ObjectId(plan_id)
            except InvalidId:
                return JSONResponse(
                    status_code=400, content={"detail": "Invalid plan ID"}
                )

            update_dict = {k: v for k, v in plan_data.model_dump().items() if v is not None}
            if not update_dict:
                return JSONResponse(
                    status_code=400, content={"detail": "No fields to update"}
                )

            update_dict["updated_at"] = datetime.utcnow()

            result = await database["plans"].update_one(
                {"_id": obj_id},
                {"$set": update_dict}
            )

            if result.matched_count == 0:
                return JSONResponse(
                    status_code=404, content={"detail": "Plan not found"}
                )

            log_info(logger, f"Plan updated: {plan_id}")

            return JSONResponse(
                status_code=200,
                content={"detail": "Plan updated successfully"}
            )

        except PyMongoError as e:
            log_error(logger, f"Database error updating plan: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Database error"}
            )
        except Exception as e:
            log_error(logger, f"Error updating plan: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    @staticmethod
    async def delete(plan_id: str) -> JSONResponse:
        """Delete plan (soft delete by setting is_active to False).

        Args:
            plan_id: Plan ID

        Returns:
            JSONResponse with deletion result
        """
        try:
            try:
                obj_id = ObjectId(plan_id)
            except InvalidId:
                return JSONResponse(
                    status_code=400, content={"detail": "Invalid plan ID"}
                )

            result = await database["plans"].update_one(
                {"_id": obj_id},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
            )

            if result.matched_count == 0:
                return JSONResponse(
                    status_code=404, content={"detail": "Plan not found"}
                )

            log_info(logger, f"Plan deactivated: {plan_id}")

            return JSONResponse(
                status_code=200,
                content={"detail": "Plan deactivated successfully"}
            )

        except PyMongoError as e:
            log_error(logger, f"Database error deactivating plan: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Database error"}
            )
        except Exception as e:
            log_error(logger, f"Error deactivating plan: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )
