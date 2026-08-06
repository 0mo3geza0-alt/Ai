"""Idempotent Stripe catalog setup for subscription plans (Flow A claimable sandbox)."""
import os
import stripe
from core.logging import logger

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY") or "sk_test_emergent"

# Subscription plans. Free is app-managed only (no Stripe price).
CATALOG = [
    {
        "emergent_product_id": "pro_plan",
        "name": "VibeVerse Pro",
        "tax_code": "txcd_10103001",  # SaaS
        "prices": [
            {"lookup_key": "pro_monthly", "amount": 1900, "currency": "usd", "interval": "month"},
            {"lookup_key": "pro_yearly", "amount": 18000, "currency": "usd", "interval": "year"},
        ],
    },
    {
        "emergent_product_id": "business_plan",
        "name": "VibeVerse Business",
        "tax_code": "txcd_10103001",
        "prices": [
            {"lookup_key": "business_monthly", "amount": 4900, "currency": "usd", "interval": "month"},
            {"lookup_key": "business_yearly", "amount": 47000, "currency": "usd", "interval": "year"},
        ],
    },
]

# lookup_key -> (plan name, credits granted)
PLAN_BY_LOOKUP = {
    "pro_monthly": ("pro", 10000),
    "pro_yearly": ("pro", 10000),
    "business_monthly": ("business", 50000),
    "business_yearly": ("business", 50000),
}

# Monthly credit allowance per plan (used by admin + auto monthly reset).
PLAN_CREDITS = {"free": 200, "pro": 10000, "business": 50000}


def ensure_tax_settings():
    """Set a head office address so Stripe Tax (automatic_tax) works in the sandbox."""
    try:
        s = stripe.tax.Settings.retrieve()
        if s.get("head_office") and s["head_office"].get("address"):
            return
        stripe.tax.Settings.modify(
            head_office={"address": {"country": "GB", "line1": "1 VibeVerse Way",
                                     "city": "London", "postal_code": "EC1A 1BB"}},
            defaults={"tax_behavior": "exclusive"},
        )
    except Exception as e:
        logger.error("Tax settings setup failed: %s", e)


def _get_or_create_product(entry):
    for p in stripe.Product.list(active=True).auto_paging_iter():
        if p.to_dict().get("metadata", {}).get("emergent_product_id") == entry["emergent_product_id"]:
            return p
    return stripe.Product.create(
        name=entry["name"],
        tax_code=entry.get("tax_code"),
        metadata={"managed_by": "emergent", "emergent_product_id": entry["emergent_product_id"]},
    )


def setup_catalog():
    """Create products/prices if missing. Safe to run on every startup."""
    try:
        ensure_tax_settings()
        for entry in CATALOG:
            product = _get_or_create_product(entry)
            for p in entry["prices"]:
                existing = stripe.Price.list(lookup_keys=[p["lookup_key"]], active=True, limit=1).data
                if existing and (existing[0].unit_amount != p["amount"] or existing[0].currency != p["currency"]):
                    stripe.Price.modify(existing[0].id, active=False)
                    existing = []
                if not existing:
                    stripe.Price.create(
                        product=product.id,
                        unit_amount=p["amount"],
                        currency=p["currency"],
                        lookup_key=p["lookup_key"],
                        transfer_lookup_key=True,
                        recurring={"interval": p["interval"]},
                    )
        logger.info("Stripe catalog ready")
    except Exception as e:  # never block startup on Stripe
        logger.error("Stripe catalog setup failed: %s", e)
