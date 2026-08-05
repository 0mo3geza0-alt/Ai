from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from bson import ObjectId
from core.db import get_db
from auth.deps import get_current_user

router = APIRouter(prefix="/api/admin")


async def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("global_role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


class RoleBody(BaseModel):
    global_role: str  # admin | user


class OrgAdminBody(BaseModel):
    credits: int | None = None       # set absolute
    add_credits: int | None = None   # increment (negative = deduct)
    plan: str | None = None          # free | pro | business


class SuspendBody(BaseModel):
    suspended: bool


class GrantAllBody(BaseModel):
    add_credits: int


@router.get("/stats")
async def stats(admin: dict = Depends(require_admin)):
    db = get_db()
    creations = {}
    for k in ["document", "code", "image", "audio", "video", "music", "research"]:
        creations[k] = await db.creations.count_documents({"kind": k})
    return {
        "users": await db.users.count_documents({}),
        "organizations": await db.organizations.count_documents({}),
        "projects": await db.projects.count_documents({}),
        "api_keys": await db.api_keys.count_documents({}),
        "chat_messages": await db.chat_messages.count_documents({"role": "user"}),
        "creations": creations,
    }


@router.get("/users")
async def users(admin: dict = Depends(require_admin)):
    db = get_db()
    docs = await db.users.find({}).sort("created_at", -1).to_list(1000)
    out = []
    for u in docs:
        uid = str(u["_id"])
        orgs = await db.memberships.count_documents({"user_id": uid})
        out.append({"id": uid, "email": u["email"], "name": u.get("name"),
                    "global_role": u.get("global_role", "user"), "auth_provider": u.get("auth_provider", "local"),
                    "suspended": u.get("suspended", False), "orgs": orgs,
                    "created_at": u.get("created_at").isoformat() if u.get("created_at") else None})
    return out


@router.patch("/users/{user_id}/suspend")
async def suspend_user(user_id: str, body: SuspendBody, admin: dict = Depends(require_admin)):
    if user_id == admin["id"] and body.suspended:
        raise HTTPException(status_code=400, detail="You cannot suspend yourself")
    db = get_db()
    u = await db.users.find_one({"_id": ObjectId(user_id)})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"suspended": body.suspended}})
    if body.suspended:
        # kill active sessions so existing tokens can't refresh
        await db.sessions.delete_many({"user_id": user_id})
    return {"ok": True, "suspended": body.suspended}


@router.patch("/users/{user_id}/role")
async def set_role(user_id: str, body: RoleBody, admin: dict = Depends(require_admin)):
    if body.global_role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="Role must be 'admin' or 'user'")
    if user_id == admin["id"] and body.global_role != "admin":
        raise HTTPException(status_code=400, detail="You cannot demote yourself")
    db = get_db()
    res = await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"global_role": body.global_role}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "global_role": body.global_role}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete yourself")
    db = get_db()
    u = await db.users.find_one({"_id": ObjectId(user_id)})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    await db.users.delete_one({"_id": ObjectId(user_id)})
    await db.memberships.delete_many({"user_id": user_id})
    await db.sessions.delete_many({"user_id": user_id})
    return {"ok": True}


@router.get("/organizations")
async def organizations(admin: dict = Depends(require_admin)):
    db = get_db()
    docs = await db.organizations.find({}).sort("created_at", -1).to_list(1000)
    out = []
    for o in docs:
        oid = str(o["_id"])
        owner = await db.users.find_one({"_id": ObjectId(o["owner_id"])}) if o.get("owner_id") else None
        out.append({"id": oid, "name": o["name"], "plan": o.get("plan", "free"), "credits": o.get("credits", 0),
                    "owner_email": owner["email"] if owner else None,
                    "members": await db.memberships.count_documents({"org_id": oid}),
                    "created_at": o.get("created_at").isoformat() if o.get("created_at") else None})
    return out


@router.patch("/organizations/{org_id}")
async def update_org(org_id: str, body: OrgAdminBody, admin: dict = Depends(require_admin)):
    db = get_db()
    org = await db.organizations.find_one({"_id": ObjectId(org_id)})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    updates = {}
    if body.plan in ("free", "pro", "business"):
        updates["plan"] = body.plan
    if body.credits is not None:
        updates["credits"] = max(0, body.credits)
    if body.add_credits:
        # apply increment/decrement with a floor of 0
        current = org.get("credits", 0)
        updates["credits"] = max(0, current + body.add_credits)
    if updates:
        await db.organizations.update_one({"_id": org["_id"]}, {"$set": updates})
    o = await db.organizations.find_one({"_id": org["_id"]})
    return {"id": org_id, "plan": o.get("plan"), "credits": o.get("credits")}


@router.post("/credits/grant-all")
async def grant_all(body: GrantAllBody, admin: dict = Depends(require_admin)):
    """Add (or deduct, if negative) credits to every organization at once."""
    db = get_db()
    if body.add_credits == 0:
        return {"ok": True, "updated": 0}
    orgs = await db.organizations.find({}).to_list(5000)
    updated = 0
    for o in orgs:
        new_val = max(0, o.get("credits", 0) + body.add_credits)
        await db.organizations.update_one({"_id": o["_id"]}, {"$set": {"credits": new_val}})
        updated += 1
    return {"ok": True, "updated": updated, "add_credits": body.add_credits}
