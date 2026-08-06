from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from bson import ObjectId
from core.db import get_db
from core.base_models import utcnow
from auth.deps import get_current_user

router = APIRouter(prefix="/api/admin")


async def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("global_role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


async def _log(admin: dict, action: str, target_type: str, target_id: str, target_label: str = "", detail: str = ""):
    """Record an admin action into the audit trail."""
    db = get_db()
    await db.admin_activity.insert_one({
        "actor_id": admin["id"], "actor_email": admin.get("email"),
        "action": action, "target_type": target_type, "target_id": target_id,
        "target_label": target_label, "detail": detail, "created_at": utcnow(),
    })


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
    for k in ["document", "code", "image", "audio", "music", "research"]:
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
    await _log(admin, "suspend" if body.suspended else "reactivate", "user", user_id, u.get("email", ""))
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
    await _log(admin, "role_change", "user", user_id, "", f"role → {body.global_role}")
    return {"ok": True, "global_role": body.global_role}


@router.delete("/users/{user_id}")
async def delete_user(user_id: str, admin: dict = Depends(require_admin)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete yourself")
    db = get_db()
    u = await db.users.find_one({"_id": ObjectId(user_id)})
    if not u:
        raise HTTPException(status_code=404, detail="User not found")

    # Cascade: remove orgs owned solely by this user + everything scoped to them.
    owned = await db.organizations.find({"owner_id": user_id}).to_list(1000)
    owned_ids = [str(o["_id"]) for o in owned]
    org_removed = 0
    for oid in owned_ids:
        for coll in ("creations", "projects", "artifacts", "chat_sessions", "chat_messages",
                     "api_keys", "agents", "agent_runs", "memories", "audit_logs",
                     "teams", "team_members", "payment_transactions"):
            try:
                await db[coll].delete_many({"org_id": oid})
            except Exception:
                pass
        await db.memberships.delete_many({"org_id": oid})
        await db.organizations.delete_one({"_id": ObjectId(oid)})
        org_removed += 1

    # Remove the user's own footprint everywhere (memberships in other orgs, sessions, creations, keys).
    await db.memberships.delete_many({"user_id": user_id})
    await db.sessions.delete_many({"user_id": user_id})
    await db.creations.delete_many({"user_id": user_id})
    await db.api_keys.delete_many({"user_id": user_id})
    await db.users.delete_one({"_id": ObjectId(user_id)})

    await _log(admin, "delete", "user", user_id, u.get("email", ""),
               f"cascaded {org_removed} owned org(s)")
    return {"ok": True, "orgs_removed": org_removed}


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
    parts = []
    if "plan" in updates:
        parts.append(f"plan → {updates['plan']}")
    if "credits" in updates:
        parts.append(f"credits → {o.get('credits')}")
    if parts:
        await _log(admin, "org_update", "organization", org_id, org.get("name", ""), "; ".join(parts))
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
    await _log(admin, "grant_all", "organization", "*", f"{updated} orgs",
               f"{'+' if body.add_credits > 0 else ''}{body.add_credits} credits")
    return {"ok": True, "updated": updated, "add_credits": body.add_credits}


@router.get("/activity")
async def activity(admin: dict = Depends(require_admin)):
    db = get_db()
    docs = await db.admin_activity.find({}).sort("created_at", -1).to_list(300)
    return [{
        "id": str(d["_id"]), "actor_email": d.get("actor_email"), "action": d.get("action"),
        "target_type": d.get("target_type"), "target_id": d.get("target_id"),
        "target_label": d.get("target_label"), "detail": d.get("detail"),
        "created_at": d["created_at"].isoformat() if d.get("created_at") else None,
    } for d in docs]


@router.post("/credits/monthly-reset")
async def monthly_reset(admin: dict = Depends(require_admin)):
    """Immediately refill every org's credits to its plan allowance (manual trigger of the monthly reset)."""
    from billing.monthly_reset import apply_monthly_reset
    n = await apply_monthly_reset(force=True)
    await _log(admin, "monthly_reset", "organization", "*", f"{n} orgs", "credits refilled to plan allowance")
    return {"ok": True, "updated": n}
