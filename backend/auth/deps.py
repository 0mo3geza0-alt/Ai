import hashlib
from fastapi import Request, HTTPException, Depends
from bson import ObjectId

from core.db import get_db
from core.base_models import utcnow
from auth.security import decode_token
from auth.rbac import has_permission


async def get_current_user(request: Request) -> dict:
    """Authenticate via JWT Bearer token OR X-API-Key. Returns the user dict (with str id)."""
    db = get_db()

    api_key = request.headers.get("X-API-Key")
    if api_key and "." in api_key:
        prefix, secret = api_key.split(".", 1)
        rec = await db.api_keys.find_one({"prefix": prefix, "revoked": False})
        if not rec or rec["key_hash"] != hashlib.sha256(secret.encode()).hexdigest():
            raise HTTPException(status_code=401, detail="Invalid API key")
        await db.api_keys.update_one({"_id": rec["_id"]}, {"$set": {"last_used": utcnow()}})
        user = await db.users.find_one({"_id": ObjectId(rec["user_id"])})
        if not user:
            raise HTTPException(status_code=401, detail="API key owner not found")
        user["id"] = str(user["_id"])
        user["_api_key"] = {"scopes": rec.get("scopes", []), "org_id": rec["org_id"]}
        return user

    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user["id"] = str(user["_id"])
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def require_permission(permission: str):
    """Dependency factory: enforce org membership + permission (org_id from path)."""

    async def dep(org_id: str, current_user: dict = Depends(get_current_user)) -> dict:
        db = get_db()
        # global admin bypass
        if current_user.get("global_role") == "admin":
            return {"user": current_user, "role": "owner", "org_id": org_id}
        # API-key scope check
        ak = current_user.get("_api_key")
        if ak is not None:
            if ak["org_id"] != org_id:
                raise HTTPException(status_code=403, detail="API key not scoped to this org")
            if not (has_permission("owner", permission) if "*" in ak["scopes"]
                    else (permission in ak["scopes"])):
                raise HTTPException(status_code=403, detail="API key missing scope")
        membership = await db.memberships.find_one({"org_id": org_id, "user_id": current_user["id"]})
        if not membership:
            raise HTTPException(status_code=403, detail="Not a member of this organization")
        if ak is None and not has_permission(membership["role"], permission):
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")
        return {"user": current_user, "role": membership["role"], "org_id": org_id}

    return dep
