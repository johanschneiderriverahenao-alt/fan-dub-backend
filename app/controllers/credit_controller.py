"""
Credit and Payment controller: business logic for credits, limits, and payments.
"""
# pylint: disable=W0718,R0801,R0914,R0912,R0915,R0911,R1705
# flake8: noqa: C901

from datetime import datetime
from typing import Any, Dict
import json

import mercadopago
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from bson import ObjectId

from app.config.database import database
from app.config.settings import settings
from app.models.credit_model import (
    UserCreditsCreate,
    DailyUsage,
)
from app.models.payment_model import (
    PaymentTransactionCreate,
)
from app.utils.logger import get_logger, log_info, log_error
from app.services.email_service import EmailService

logger = get_logger(__name__)

MP_SDK = (
    mercadopago.SDK(settings.mercadopago_access_token)
    if settings.mercadopago_access_token
    else None
)


class CreditController:
    """Business logic for credit and payment operations."""

    @staticmethod
    async def initialize_user_credits(user_id: str) -> JSONResponse:
        """Initialize credits for a new user.

        Args:
            user_id: ID of the user

        Returns:
            JSONResponse with the created credits record
        """
        try:
            existing = await database["user_credits"].find_one({"user_id": user_id})
            if existing:
                return JSONResponse(
                    status_code=200,
                    content={"detail": "User credits already initialized"}
                )

            limits_config = await database["parametrization"].find_one(
                {"type": "daily_limits", "is_active": True}
            )
            daily_free = limits_config["config"]["free"] if limits_config else 3
            daily_ads = limits_config["config"]["ads"] if limits_config else 3

            today = datetime.utcnow().strftime("%Y-%m-%d")
            credits_data = UserCreditsCreate(
                user_id=user_id,
                paid_credits=0,
                daily_free_limit=daily_free,
                daily_ad_limit=daily_ads,
                current_daily_usage=DailyUsage(
                    date=today,
                    free_dubbings_used=0,
                    credits_used=0,
                    ads_watched=0
                )
            )

            credits_dict = credits_data.model_dump()
            credits_dict["created_at"] = datetime.utcnow()
            credits_dict["updated_at"] = datetime.utcnow()

            result = await database["user_credits"].insert_one(credits_dict)

            response_data = {
                **credits_dict,
                "_id": str(result.inserted_id),
                "created_at": credits_dict["created_at"].isoformat(),
                "updated_at": credits_dict["updated_at"].isoformat()
            }

            log_info(logger, f"Initialized credits for user {user_id}")
            return JSONResponse(
                status_code=201,
                content={"detail": "Credits initialized successfully", "data": response_data}
            )

        except PyMongoError as e:
            log_error(logger, f"Database error initializing credits: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Database error"}
            )
        except Exception as e:
            log_error(logger, f"Error initializing credits: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    @staticmethod
    async def get_user_credits(user_id: str) -> JSONResponse:
        """Get user credits and usage information.

        Args:
            user_id: ID of the user

        Returns:
            JSONResponse with credits information
        """
        try:
            user_credits = await database["user_credits"].find_one({"user_id": user_id})
            if not user_credits:
                return await CreditController.initialize_user_credits(user_id)

            today = datetime.utcnow().strftime("%Y-%m-%d")
            current_usage = user_credits.get("current_daily_usage")

            if not current_usage or current_usage.get("date") != today:
                user_credits["current_daily_usage"] = {
                    "date": today,
                    "free_dubbings_used": 0,
                    "credits_used": 0,
                    "ads_watched": 0
                }
                await database["user_credits"].update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "current_daily_usage": user_credits["current_daily_usage"],
                            "updated_at": datetime.utcnow()
                        }
                    }
                )

            daily_usage = user_credits.get("current_daily_usage", {})
            free_used = daily_usage.get("free_dubbings_used", 0)
            ads_watched = daily_usage.get("ads_watched", 0)

            available_free = max(0, user_credits.get("daily_free_limit", 3) - free_used)
            available_ads = max(0, user_credits.get("daily_ad_limit", 3) - ads_watched)

            response_data = {
                **user_credits,
                "_id": str(user_credits["_id"]),
                "available_free_dubbings": available_free,
                "available_ad_dubbings": available_ads
            }

            if "created_at" in response_data and isinstance(response_data["created_at"], datetime):
                response_data["created_at"] = response_data["created_at"].isoformat()
            if "updated_at" in response_data and isinstance(response_data["updated_at"], datetime):
                response_data["updated_at"] = response_data["updated_at"].isoformat()

            return JSONResponse(status_code=200, content={"data": response_data})

        except PyMongoError as e:
            log_error(logger, f"Database error getting credits: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Database error"}
            )
        except Exception as e:
            log_error(logger, f"Error getting credits: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    @staticmethod
    async def check_can_create_dubbing(user_id: str) -> Dict[str, Any]:
        """Check if user can create a dubbing and return the method to use.

        Args:
            user_id: ID of the user

        Returns:
            Dict with can_create, method (free, ad, credit), and message
        """
        try:
            credits_response = await CreditController.get_user_credits(user_id)
            if credits_response.status_code != 200:
                return {
                    "can_create": False,
                    "method": None,
                    "message": "Error retrieving user credits"
                }

            response_body = credits_response.body.decode()
            credits_data = json.loads(response_body)["data"]

            available_free = credits_data.get("available_free_dubbings", 0)
            available_ads = credits_data.get("available_ad_dubbings", 0)
            paid_credits = credits_data.get("paid_credits", 0)

            if available_free > 0:
                return {
                    "can_create": True,
                    "method": "free",
                    "message": (
                        f"Using free dubbing ({available_free} remaining today)"
                    )
                }
            elif available_ads > 0:
                return {
                    "can_create": True,
                    "method": "ad",
                    "message": (
                        f"Watch an ad to unlock dubbing "
                        f"({available_ads} ads available today)"
                    )
                }
            elif paid_credits > 0:
                return {
                    "can_create": True,
                    "method": "credit",
                    "message": f"Using 1 paid credit ({paid_credits} credits available)"
                }
            return {
                "can_create": False,
                "method": None,
                "message": (
                    "No dubbings available. Purchase credits or wait for reset."
                )
            }

        except Exception as e:
            log_error(logger, f"Error checking dubbing availability: {str(e)}")
            return {
                "can_create": False,
                "method": None,
                "message": "Error checking availability"
            }

    @staticmethod
    async def consume_dubbing(user_id: str, method: str) -> JSONResponse:
        """Consume a dubbing using the specified method.

        Args:
            user_id: ID of the user
            method: Method to use (free, ad, credit)

        Returns:
            JSONResponse indicating success or failure
        """
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")

            if method == "free":
                result = await database["user_credits"].update_one(
                    {
                        "user_id": user_id,
                        "current_daily_usage.date": today
                    },
                    {
                        "$inc": {"current_daily_usage.free_dubbings_used": 1},
                        "$set": {"updated_at": datetime.utcnow()}
                    }
                )
                if result.modified_count == 0:
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Could not consume free dubbing"}
                    )
                log_info(logger, f"User {user_id} consumed 1 free dubbing")

            elif method == "ad":
                result = await database["user_credits"].update_one(
                    {
                        "user_id": user_id,
                        "current_daily_usage.date": today
                    },
                    {
                        "$inc": {"current_daily_usage.ads_watched": 1},
                        "$set": {"updated_at": datetime.utcnow()}
                    }
                )
                if result.modified_count == 0:
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Could not consume ad dubbing"}
                    )
                log_info(logger, f"User {user_id} watched an ad for dubbing")

            elif method == "credit":
                result = await database["user_credits"].update_one(
                    {
                        "user_id": user_id,
                        "paid_credits": {"$gte": 1}
                    },
                    {
                        "$inc": {
                            "paid_credits": -1,
                            "current_daily_usage.credits_used": 1
                        },
                        "$set": {"updated_at": datetime.utcnow()}
                    }
                )
                if result.modified_count == 0:
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Insufficient credits"}
                    )
                log_info(logger, f"User {user_id} consumed 1 paid credit")
            else:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Invalid method"}
                )

            return JSONResponse(
                status_code=200,
                content={"detail": "Dubbing consumed successfully", "method": method}
            )

        except PyMongoError as e:
            log_error(logger, f"Database error consuming dubbing: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Database error"}
            )
        except Exception as e:
            log_error(logger, f"Error consuming dubbing: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    @staticmethod
    async def get_credit_packages() -> JSONResponse:
        """Get available credit packages.

        Returns:
            JSONResponse with available packages
        """
        try:
            plans_cursor = database["plans"].find({"is_active": True})
            plans = await plans_cursor.to_list(length=100)

            packages = []
            for plan in plans:
                plan_data = {
                    **plan,
                    "_id": str(plan["_id"])
                }
                if "created_at" in plan_data and isinstance(plan_data["created_at"], datetime):
                    plan_data["created_at"] = plan_data["created_at"].isoformat()
                if "updated_at" in plan_data and isinstance(plan_data["updated_at"], datetime):
                    plan_data["updated_at"] = plan_data["updated_at"].isoformat()
                packages.append(plan_data)

            return JSONResponse(status_code=200, content={"data": packages})
        except PyMongoError as e:
            log_error(logger, f"Database error getting credit packages: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Database error"}
            )
        except Exception as e:
            log_error(logger, f"Error getting credit packages: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    @staticmethod
    async def create_payment_intent(
        user_id: str, package_name: str
    ) -> JSONResponse:
        """Create a MercadoPago preference for purchasing credits.

        Args:
            user_id: ID of the user
            package_name: Name of the package to purchase

        Returns:
            JSONResponse with payment preference details
        """
        try:
            plan = await database["plans"].find_one(
                {"name": package_name, "is_active": True}
            )
            if not plan:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Package not found"}
                )

            try:
                user_oid = ObjectId(user_id)
            except Exception:
                user_oid = None

            user = None
            if user_oid:
                user = await database["users"].find_one({"_id": ObjectId(user_oid)})
            if not user:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "User not found"}
                )

            preference_data = {
                "items": [
                    {
                        "title": (
                            f"Plan {plan['name']} - {plan['credits']} créditos"
                        ),
                        "description": plan.get("description", ""),
                        "quantity": 1,
                        "unit_price": float(plan["price_usd"]),
                        "currency_id": "COP",
                    }
                ],
                "payer": {
                    "email": user.get("email", ""),
                    "name": user.get("full_name", ""),
                },
                "back_urls": {
                    "success": settings.mercadopago_success_url,
                    "failure": settings.mercadopago_failure_url,
                    "pending": settings.mercadopago_pending_url,
                },
                "auto_return": "approved",
                "statement_descriptor": "YOUDUB",
                "external_reference": f"user_{user_id}_{plan['name']}",
                "metadata": {
                    "user_id": user_id,
                    "package_name": plan["name"],
                    "credits": plan["credits"],
                },
            }

            if not MP_SDK:
                return JSONResponse(
                    status_code=500,
                    content={"detail": "MercadoPago not configured"}
                )

            try:
                preference_response = MP_SDK.preference().create(preference_data)
                log_info(logger, f"MercadoPago response: {preference_response}")

                if "status" in preference_response and preference_response["status"] >= 400:
                    error_msg = (
                        preference_response
                        .get("response", {})
                        .get("message", "Unknown error")
                    )
                    log_error(logger, f"MercadoPago error: {error_msg}")
                    return JSONResponse(
                        status_code=500,
                        content={"detail": f"MercadoPago error: {error_msg}"}
                    )

                preference = preference_response.get("response", preference_response)

                if not preference.get("id"):
                    log_error(logger, f"No preference ID in response: {preference_response}")
                    return JSONResponse(
                        status_code=500,
                        content={"detail": "Invalid MercadoPago response"}
                    )

            except Exception as mp_error:
                log_error(logger, f"MercadoPago SDK error: {str(mp_error)}")
                return JSONResponse(
                    status_code=500,
                    content={"detail": f"Payment gateway error: {str(mp_error)}"}
                )

            transaction_data = PaymentTransactionCreate(
                user_id=user_id,
                package_name=plan["name"],
                credits_purchased=plan["credits"],
                amount_usd=plan["price_usd"],
                currency="COP",
                stripe_payment_intent_id=preference["id"],
                status="pending",
                payment_method="mercadopago"
            )

            trans_dict = transaction_data.model_dump()
            trans_dict["created_at"] = datetime.utcnow()
            trans_dict["updated_at"] = datetime.utcnow()

            result = await database["payment_transactions"].insert_one(trans_dict)
            trans_dict["_id"] = str(result.inserted_id)

            log_info(logger,
                     f"Created MercadoPago preference for user {user_id}: {preference['id']}")

            return JSONResponse(
                status_code=201,
                content={
                    "preference_id": preference["id"],
                    "init_point": preference["init_point"],
                    "sandbox_init_point": preference.get("sandbox_init_point", ""),
                    "amount": plan["price_usd"],
                    "credits": plan["credits"],
                    "transaction_id": trans_dict["_id"]
                }
            )

        except Exception as e:
            log_error(logger, f"Error creating MercadoPago preference: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    @staticmethod
    async def handle_payment_success(payment_id: str) -> JSONResponse:
        """Handle successful MercadoPago payment and add credits to user.

        Args:
            payment_id: MercadoPago payment ID or preference ID

        Returns:
            JSONResponse indicating success
        """
        try:
            transaction = await database["payment_transactions"].find_one(
                {"stripe_payment_intent_id": payment_id}
            )
            if not transaction:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Transaction not found"}
                )

            if transaction.get("status") == "succeeded":
                return JSONResponse(
                    status_code=200,
                    content={"detail": "Payment already processed"}
                )

            await database["payment_transactions"].update_one(
                {"_id": transaction["_id"]},
                {
                    "$set": {
                        "status": "succeeded",
                        "completed_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )

            credits_to_add = transaction["credits_purchased"]
            result = await database["user_credits"].update_one(
                {"user_id": transaction["user_id"]},
                {
                    "$inc": {"paid_credits": credits_to_add},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )

            if result.modified_count == 0:
                log_error(
                    logger,
                    f"Could not add credits to user {transaction['user_id']}"
                )
                return JSONResponse(
                    status_code=500,
                    content={"detail": "Error adding credits"}
                )

            log_info(
                logger,
                f"Added {credits_to_add} credits to user {transaction['user_id']} "
                f"from payment {payment_id}"
            )

            # Send payment success email
            try:
                user = None
                try:
                    trans_user_oid = ObjectId(transaction["user_id"])
                except Exception:
                    trans_user_oid = None

                if trans_user_oid:
                    user = await database["users"].find_one({"_id": ObjectId(trans_user_oid)})
                if user:
                    plan = await database["plans"].find_one({"name": transaction["package_name"]})
                    if plan:
                        await EmailService.send_payment_success_email(
                            email=user.get("email", ""),
                            plan_name=(
                                plan.get("display_name")
                                or plan.get("name", transaction["package_name"])
                            ),
                            num_credits=credits_to_add,
                            features=plan.get("features", []),
                        )
                        log_info(logger, f"Payment confirmation email sent to {user.get('email')}")
                    else:
                        log_error(logger, f"Plan not found: {transaction['package_name']}")
                else:
                    log_error(logger, f"User not found: {transaction['user_id']}")
            except Exception as email_error:
                log_error(logger, f"Error sending payment success email: {str(email_error)}")

            return JSONResponse(
                status_code=200,
                content={
                    "detail": "Payment successful, credits added",
                    "credits_added": credits_to_add
                }
            )

        except PyMongoError as e:
            log_error(logger, f"Database error handling payment success: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Database error"}
            )
        except Exception as e:
            log_error(logger, f"Error handling payment success: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    @staticmethod
    async def get_user_transactions(user_id: str) -> JSONResponse:
        """Get user payment transaction history.

        Args:
            user_id: ID of the user

        Returns:
            JSONResponse with transaction history
        """
        try:
            transactions = await database["payment_transactions"].find(
                {"user_id": user_id}
            ).sort("created_at", -1).to_list(length=100)

            serialized_transactions = []
            for trans in transactions:
                trans_data = {
                    **trans,
                    "_id": str(trans["_id"])
                }
                for field in ["created_at", "updated_at", "completed_at"]:
                    if field in trans_data and isinstance(trans_data[field], datetime):
                        trans_data[field] = trans_data[field].isoformat()
                serialized_transactions.append(trans_data)

            return JSONResponse(
                status_code=200,
                content={"data": serialized_transactions, "count": len(serialized_transactions)}
            )

        except PyMongoError as e:
            log_error(logger, f"Database error getting transactions: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Database error"}
            )
        except Exception as e:
            log_error(logger, f"Error getting transactions: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    @staticmethod
    async def delete_transaction(user_id: str, transaction_id: str) -> JSONResponse:
        """Delete a specific transaction from user's payment history.

        Args:
            user_id: ID of the user
            transaction_id: ID of the transaction to delete

        Returns:
            JSONResponse confirming deletion
        """
        try:
            transaction = await database["payment_transactions"].find_one({
                "_id": ObjectId(transaction_id),
                "user_id": user_id
            })

            if not transaction:
                return JSONResponse(
                    status_code=404,
                    content={"detail": "Transaction not found or does not belong to user"}
                )

            result = await database["payment_transactions"].delete_one({
                "_id": ObjectId(transaction_id)
            })

            if result.deleted_count == 0:
                return JSONResponse(
                    status_code=500,
                    content={"detail": "Failed to delete transaction"}
                )

            log_info(logger, f"User {user_id} deleted transaction {transaction_id}")

            return JSONResponse(
                status_code=200,
                content={"detail": "Transaction deleted successfully"}
            )

        except PyMongoError as e:
            log_error(logger, f"Database error deleting transaction: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Database error"}
            )
        except Exception as e:
            log_error(logger, f"Error deleting transaction: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

    @staticmethod
    async def delete_all_transactions(user_id: str) -> JSONResponse:
        """Delete all transactions from user's payment history.

        Args:
            user_id: ID of the user

        Returns:
            JSONResponse confirming deletion with count
        """
        try:
            result = await database["payment_transactions"].delete_many({
                "user_id": user_id
            })

            log_info(
                logger,
                f"User {user_id} deleted {result.deleted_count} transactions from history"
            )

            return JSONResponse(
                status_code=200,
                content={
                    "detail": "Transaction history cleared successfully",
                    "deleted_count": result.deleted_count
                }
            )

        except PyMongoError as e:
            log_error(logger, f"Database error deleting transaction history: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Database error"}
            )
        except Exception as e:
            log_error(logger, f"Error deleting transaction history: {str(e)}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )
