"""
Credit and Payment API views/routes.
"""
# pylint: disable=W0718,R1714
from datetime import datetime
from typing import Any, Dict

import mercadopago  # type: ignore
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.config.database import database
from app.config.settings import settings
from app.controllers.auth_controller import AuthController
from app.controllers.credit_controller import CreditController
from app.utils.logger import get_logger, log_error, log_info

logger = get_logger(__name__)

router = APIRouter(prefix="/credits", tags=["Credits & Payments"])

MP_SDK = (
    mercadopago.SDK(settings.mercadopago_access_token)
    if settings.mercadopago_access_token
    else None
)


async def get_user_id(
    current_user: Dict[str, Any] = Depends(
        AuthController.get_current_user
    ),
) -> str:
    """Extract user_id from current user."""
    return current_user.get("_id") or current_user.get("id")


@router.get("/me")
async def get_my_credits(user_id: str = Depends(get_user_id)):
    """Get current user's credits and usage information."""
    return await CreditController.get_user_credits(user_id)


@router.get("/check-availability")
async def check_dubbing_availability(user_id: str = Depends(get_user_id)):
    """Check if user can create a dubbing and how."""
    result = await CreditController.check_can_create_dubbing(user_id)
    return JSONResponse(status_code=200, content=result)


@router.post("/consume")
async def consume_dubbing(
    method: str,
    user_id: str = Depends(get_user_id)
):
    """Consume a dubbing slot using specified method (free, ad, credit)."""
    if method not in ["free", "ad", "credit"]:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid method. Must be: free, ad, or credit"}
        )
    return await CreditController.consume_dubbing(user_id, method)


@router.get("/packages")
async def get_credit_packages():
    """Get available credit packages for purchase."""
    return await CreditController.get_credit_packages()


@router.post("/payment-intent")
async def create_payment_intent(
    package_name: str,
    user_id: str = Depends(get_user_id)
):
    """Create a MercadoPago payment preference for purchasing credits."""
    return await CreditController.create_payment_intent(user_id, package_name)


@router.get("/transactions")
async def get_my_transactions(user_id: str = Depends(get_user_id)):
    """Get current user's payment transaction history."""
    return await CreditController.get_user_transactions(user_id)


@router.post("/webhook")
async def mercadopago_webhook(request: Request):
    """Handle MercadoPago webhook notifications."""
    try:
        payload = await request.json()

        log_info(logger, f"MercadoPago webhook received: {payload.get('type')}")

        notification_type = payload.get("type")

        if notification_type == "payment":
            payment_id = payload.get("data", {}).get("id")

            if not payment_id:
                return JSONResponse(status_code=400, content={"detail": "No payment ID"})

            if MP_SDK:
                payment_info = MP_SDK.payment().get(payment_id)
                payment_data = payment_info["response"]

                status = payment_data.get("status")

                if status == "approved":
                    preference_id = (
                        payment_data.get("metadata", {}).get("preference_id")
                        or payment_data.get("external_reference")
                    )

                    if not preference_id:
                        log_info(logger, f"Payment approved but no preference_id: {payment_id}")
                    else:
                        await CreditController.handle_payment_success(preference_id)

                elif status == "rejected" or status == "cancelled":
                    log_error(logger, f"Payment {status}: {payment_id}")
                    await database["payment_transactions"].update_one(
                        {"stripe_payment_intent_id": payment_id},
                        {
                            "$set": {
                                "status": "failed",
                                "updated_at": datetime.utcnow()
                            }
                        }
                    )
                else:
                    log_info(logger, f"Payment status: {status}")

        return JSONResponse(status_code=200, content={"detail": "Webhook received"})

    except Exception as e:
        log_error(logger, f"Error handling MercadoPago webhook: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Webhook handling error"}
        )


@router.post("/ad-watched")
async def record_ad_watched(
    ad_provider: str = "default",
    user_id: str = Depends(get_user_id)
):
    """Record that user watched an ad (for verification before granting dubbing)."""
    try:

        user_credits = await database["user_credits"].find_one({"user_id": user_id})
        if not user_credits:
            return JSONResponse(
                status_code=404,
                content={"detail": "User credits not found"}
            )

        today = datetime.utcnow().strftime("%Y-%m-%d")
        current_usage = user_credits.get("current_daily_usage", {})

        if current_usage.get("date") != today:
            current_usage = {"date": today, "ads_watched": 0}

        ads_watched = current_usage.get("ads_watched", 0)
        daily_ad_limit = user_credits.get("daily_ad_limit", 3)

        if ads_watched >= daily_ad_limit:
            return JSONResponse(
                status_code=400,
                content={"detail": "Daily ad limit reached"}
            )

        log_info(logger, f"User {user_id} watched ad from {ad_provider}")

        return JSONResponse(
            status_code=200,
            content={
                "detail": "Ad watched recorded",
                "ads_remaining": daily_ad_limit - ads_watched - 1
            }
        )

    except Exception as e:
        log_error(logger, f"Error recording ad watch: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )


@router.delete("/transactions/{transaction_id}")
async def delete_transaction(
    transaction_id: str,
    user_id: str = Depends(get_user_id)
):
    """Delete a specific transaction from payment history."""
    return await CreditController.delete_transaction(user_id, transaction_id)


@router.delete("/transactions")
async def delete_all_transactions(user_id: str = Depends(get_user_id)):
    """Delete all transactions from payment history."""
    return await CreditController.delete_all_transactions(user_id)
