"""
Payment Transaction models for Stripe payments and credit purchases.

Models:
- `PaymentIntentCreate` : Create a payment intent
- `PaymentTransaction` : Payment transaction record
- `PaymentTransactionDB` : DB representation
- `PaymentTransactionResponse` : Response model
"""
# pylint: disable=R0801
from __future__ import annotations

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class PaymentIntentCreate(BaseModel):
    """Model for creating a payment intent."""

    package_name: str = Field(..., description="Credit package name")
    credits: int = Field(..., description="Number of credits to purchase")
    amount_usd: float = Field(..., description="Amount in USD")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class PaymentTransactionBase(BaseModel):
    """Base model for payment transactions."""

    user_id: str = Field(..., description="ID of the user making the payment")
    package_name: str = Field(..., description="Package purchased")
    credits_purchased: int = Field(..., description="Number of credits purchased")
    amount_usd: float = Field(..., description="Amount paid in USD")
    currency: str = Field(default="usd", description="Payment currency")
    stripe_payment_intent_id: Optional[str] = Field(None, description="Stripe Payment Intent ID")
    stripe_charge_id: Optional[str] = Field(None, description="Stripe Charge ID")
    status: str = Field(
        default="pending",
        description="Status: pending, succeeded, failed, refunded"
    )
    payment_method: str = Field(default="stripe", description="Payment method used")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict,
                                               description="Additional metadata")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class PaymentTransactionCreate(PaymentTransactionBase):
    """Model for creating a payment transaction."""
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class PaymentTransactionUpdate(BaseModel):
    """Model for updating a payment transaction."""

    stripe_payment_intent_id: Optional[str] = None
    stripe_charge_id: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class PaymentTransactionDB(PaymentTransactionBase):
    """Database representation of a payment transaction."""

    id: str = Field(default="", alias="_id", description="MongoDB document ID")
    created_at: datetime = Field(default_factory=datetime.utcnow,
                                 description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow,
                                 description="Last update timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class PaymentTransactionResponse(BaseModel):
    """Response model for payment transactions."""

    id: str = Field(..., alias="_id", description="MongoDB document ID")
    user_id: str
    package_name: str
    credits_purchased: int
    amount_usd: float
    currency: str
    stripe_payment_intent_id: Optional[str] = None
    stripe_charge_id: Optional[str] = None
    status: str
    payment_method: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class WebhookEvent(BaseModel):
    """Model for Stripe webhook events."""

    event_id: str = Field(..., description="Stripe event ID")
    event_type: str = Field(..., description="Event type")
    payment_intent_id: Optional[str] = Field(None, description="Payment intent ID")
    data: Dict[str, Any] = Field(..., description="Event data")

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )
