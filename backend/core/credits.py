"""Shared, race-safe organization credit helpers."""
from bson import ObjectId
from fastapi import HTTPException


async def spend(db, org_id: str, cost: int) -> int:
    """Atomically debit credits only when balance >= cost. Returns remaining."""
    if cost <= 0:
        org = await db.organizations.find_one({"_id": ObjectId(org_id)})
        return (org or {}).get("credits", 0)
    updated = await db.organizations.find_one_and_update(
        {"_id": ObjectId(org_id), "credits": {"$gte": cost}},
        {"$inc": {"credits": -cost}},
        return_document=True,
    )
    if not updated:
        raise HTTPException(status_code=402, detail="Not enough credits. Upgrade the organization plan.")
    return updated.get("credits", 0)


async def refund(db, org_id: str, cost: int):
    if cost > 0:
        await db.organizations.update_one({"_id": ObjectId(org_id)}, {"$inc": {"credits": cost}})
