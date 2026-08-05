"""Stripe subscription billing (Flow A — claimable sandbox). Digital SaaS, GB → SMP tax mode."""
import os
import asyncio
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from bson import ObjectId

from core.db import get_db
from core.logging import logger
from auth.deps import require_permission
from billing.setup_stripe import PLAN_BY_LOOKUP, CATALOG

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

router = APIRouter(prefix="/api")

# Public plan catalog for the pricing page (features are display-only).
PLANS_PUBLIC = [
    {
        "id": "free", "name": "Free", "monthly": 0, "yearly": 0,
        "credits": 200, "highlight": False,
        "features": ["200 credits / month", "AI Chat & Documents", "Image generation", "Community gallery"],
    },
    {
        "id": "pro", "name": "Pro", "monthly": 19, "yearly": 180,
        "monthly_lookup": "pro_monthly", "yearly_lookup": "pro_yearly",
        "credits": 10000, "highlight": True,
        "features": ["10,000 credits / month", "Everything in Free", "AI Video & Music", "AI Agents & Knowledge base", "Priority generation"],
    },
    {
        "id": "business", "name": "Business", "monthly": 49, "yearly": 470,
        "monthly_lookup": "business_monthly", "yearly_lookup": "business_yearly",
        "credits": 50000, "highlight": False,
        "features": ["50,000 credits / month", "Everything in Pro", "Team agents & workflows", "Highest priority", "Dedicated support"],
    },
]


class CheckoutRequest(BaseModel):
    lookup_key: str
    origin_url: str
    quantity: int = Field(1, ge=1, le=1)


@router.get("/billing/plans")
async def list_plans():
    return {"plans": PLANS_PUBLIC}


async def _apply_plan(db, org_id: str, lookup_key: str):
    mapping = PLAN_BY_LOOKUP.get(lookup_key)
    if not mapping or not org_id:
        return
    plan, credits = mapping
    await db.organizations.update_one(
        {"_id": ObjectId(org_id)}, {"$set": {"plan": plan, "credits": credits}}
    )


@router.post("/billing/orgs/{org_id}/checkout")
async def create_checkout(org_id: str, req: CheckoutRequest, ctx: dict = Depends(require_permission("member:manage"))):
    db = get_db()
    prices = await asyncio.to_thread(lambda: stripe.Price.list(lookup_keys=[req.lookup_key], active=True, limit=1).data)
    if not prices:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {req.lookup_key}")
    price = prices[0]
    kwargs = dict(
        line_items=[{"price": price.id, "quantity": req.quantity}],
        mode="subscription",
        customer_email=ctx["user"].get("email") or None,
        success_url=f"{req.origin_url}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{req.origin_url}/payment/cancel",
        metadata={"org_id": org_id, "user_id": ctx["user"]["id"], "lookup_key": req.lookup_key},
    )

    def _create():
        # GB + digital SaaS → Stripe-managed payments (tax handled by Stripe). Fall back to Stripe Tax if ineligible.
        try:
            return stripe.checkout.Session.create(**kwargs, managed_payments={"enabled": True})
        except stripe.error.InvalidRequestError as e:
            msg = (getattr(e, "user_message", "") or "").lower()
            if "managed payments" in msg or "ineligible" in msg:
                return stripe.checkout.Session.create(**kwargs, automatic_tax={"enabled": True}, billing_address_collection="required")
            raise

    session = await asyncio.to_thread(_create)
    await db.payment_transactions.insert_one({
        "session_id": session.id, "org_id": org_id, "user_id": ctx["user"]["id"],
        "lookup_key": req.lookup_key, "amount": (price.unit_amount or 0) / 100.0, "currency": price.currency,
        "status": "initiated", "payment_status": "pending",
        "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
    })
    return {"checkout_url": session.url, "session_id": session.id}


@router.get("/billing/status/{session_id}")
async def get_status(session_id: str):
    db = get_db()
    record = await db.payment_transactions.find_one({"session_id": session_id})
    if not record:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if record.get("payment_status") != "paid":
        try:
            s = await asyncio.to_thread(stripe.checkout.Session.retrieve, session_id)
            if s.payment_status == "paid" or s.status == "complete":
                res = await db.payment_transactions.find_one_and_update(
                    {"session_id": session_id, "payment_status": {"$ne": "paid"}},
                    {"$set": {"status": "completed", "payment_status": "paid",
                              "stripe_subscription_id": s.subscription,
                              "updated_at": datetime.now(timezone.utc)}},
                    return_document=True,
                )
                if res:
                    await _apply_plan(db, res.get("org_id"), res.get("lookup_key"))
                record = await db.payment_transactions.find_one({"session_id": session_id})
        except stripe.error.StripeError:
            pass
    return {"session_id": record["session_id"], "status": record["status"],
            "payment_status": record["payment_status"], "lookup_key": record.get("lookup_key")}


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    db = get_db()
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature")
    obj, t = event["data"]["object"], event["type"]
    if t == "checkout.session.completed":
        res = await db.payment_transactions.find_one_and_update(
            {"session_id": obj["id"], "payment_status": {"$ne": "paid"}},
            {"$set": {"status": "completed", "payment_status": obj.get("payment_status", "paid"),
                      "stripe_subscription_id": obj.get("subscription"),
                      "updated_at": datetime.now(timezone.utc)}},
            return_document=True,
        )
        if res:
            await _apply_plan(db, res.get("org_id"), res.get("lookup_key"))
    elif t == "checkout.session.expired":
        await db.payment_transactions.update_one({"session_id": obj["id"]},
            {"$set": {"status": "expired", "payment_status": "expired", "updated_at": datetime.now(timezone.utc)}})
    return {"status": "ok"}
