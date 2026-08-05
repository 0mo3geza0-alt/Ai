"""Admin security endpoints: audit log query + security overview."""
from fastapi import APIRouter, Depends, HTTPException
from core.db import get_db
from auth.deps import get_current_user
from security.middleware import RATE_LIMIT, RATE_WINDOW

router = APIRouter(prefix="/api/admin")


async def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("global_role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


@router.get("/audit-logs")
async def audit_logs(limit: int = 100, blocked: bool | None = None,
                     method: str | None = None, admin: dict = Depends(require_admin)):
    db = get_db()
    q = {}
    if blocked is not None:
        q["blocked"] = blocked
    if method:
        q["method"] = method.upper()
    docs = await db.audit_logs.find(q).sort("created_at", -1).to_list(min(limit, 500))
    out = []
    for d in docs:
        user = None
        if d.get("user_id"):
            from bson import ObjectId
            try:
                u = await db.users.find_one({"_id": ObjectId(d["user_id"])})
                user = u.get("email") if u else None
            except Exception:
                user = None
        out.append({"id": str(d["_id"]), "method": d.get("method"), "path": d.get("path"),
                    "status": d.get("status"), "client": d.get("client"), "user_email": user,
                    "org_id": d.get("org_id"), "blocked": d.get("blocked", False),
                    "created_at": _iso(d.get("created_at"))})
    return out


@router.get("/security/overview")
async def security_overview(admin: dict = Depends(require_admin)):
    db = get_db()
    total = await db.audit_logs.count_documents({})
    blocked = await db.audit_logs.count_documents({"blocked": True})
    by_method = {}
    for m in ("POST", "PATCH", "PUT", "DELETE"):
        by_method[m] = await db.audit_logs.count_documents({"method": m})
    errors = await db.audit_logs.count_documents({"status": {"$gte": 400}})
    return {"total_events": total, "blocked_events": blocked, "error_events": errors,
            "by_method": by_method,
            "rate_limit": {"limit": RATE_LIMIT, "window_seconds": RATE_WINDOW,
                           "scope": "heavy endpoints (generate / agents / memories / chat)"}}
