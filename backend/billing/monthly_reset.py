"""Automatic monthly credit refill: every org's credits reset to its plan allowance at month start."""
import asyncio
from datetime import datetime, timezone

from core.db import get_db
from core.logging import logger
from billing.setup_stripe import PLAN_CREDITS


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


async def backfill_reset_month():
    """Mark existing orgs with the current month WITHOUT touching credits (avoids wiping balances on deploy)."""
    db = get_db()
    await db.organizations.update_many(
        {"last_reset_month": {"$exists": False}},
        {"$set": {"last_reset_month": _current_month()}},
    )


async def apply_monthly_reset(force: bool = False) -> int:
    """Reset credits to the plan allowance for orgs due this month. force=True resets all orgs now."""
    db = get_db()
    month = _current_month()
    query = {} if force else {"last_reset_month": {"$ne": month}}
    orgs = await db.organizations.find(query).to_list(10000)
    n = 0
    for o in orgs:
        credits = PLAN_CREDITS.get(o.get("plan", "free"), PLAN_CREDITS["free"])
        await db.organizations.update_one(
            {"_id": o["_id"]}, {"$set": {"credits": credits, "last_reset_month": month}}
        )
        n += 1
    if n:
        logger.info("Monthly credit reset applied to %d orgs (%s, force=%s)", n, month, force)
    return n


async def monthly_reset_loop():
    """Backfill once, then check hourly and refill when the calendar month rolls over."""
    try:
        await backfill_reset_month()
    except Exception as e:
        logger.error("Monthly reset backfill failed: %s", e)
    while True:
        await asyncio.sleep(3600)
        try:
            await apply_monthly_reset()
        except Exception as e:
            logger.error("Monthly reset loop error: %s", e)
