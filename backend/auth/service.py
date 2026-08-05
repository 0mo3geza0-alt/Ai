from datetime import datetime
from bson import ObjectId
from core.base_models import utcnow


def oid(v: str) -> ObjectId:
    return ObjectId(v)


def serialize_user(u: dict) -> dict:
    return {
        "id": str(u["_id"]),
        "email": u["email"],
        "name": u.get("name", ""),
        "picture": u.get("picture"),
        "global_role": u.get("global_role", "user"),
        "auth_provider": u.get("auth_provider", "local"),
        "default_org_id": u.get("default_org_id"),
        "suspended": u.get("suspended", False),
        "created_at": _iso(u.get("created_at")),
    }


def serialize_org(o: dict) -> dict:
    return {"id": str(o["_id"]), "name": o["name"], "owner_id": o.get("owner_id"),
            "plan": o.get("plan", "free"), "credits": o.get("credits", 0),
            "created_at": _iso(o.get("created_at"))}


def serialize_team(t: dict) -> dict:
    return {"id": str(t["_id"]), "org_id": t["org_id"], "name": t["name"],
            "created_at": _iso(t.get("created_at"))}


def serialize_membership(m: dict, user: dict = None) -> dict:
    d = {"id": str(m["_id"]), "org_id": m["org_id"], "user_id": m["user_id"], "role": m["role"]}
    if user:
        d["email"] = user["email"]
        d["name"] = user.get("name", "")
    return d


def serialize_api_key(k: dict, secret: str = None) -> dict:
    d = {"id": str(k["_id"]), "org_id": k["org_id"], "name": k["name"], "prefix": k["prefix"],
         "scopes": k.get("scopes", []), "revoked": k.get("revoked", False),
         "last_used": _iso(k.get("last_used")), "created_at": _iso(k.get("created_at"))}
    if secret:
        d["key"] = secret  # full key shown ONCE at creation
    return d


def _iso(v):
    if isinstance(v, datetime):
        return v.isoformat()
    return v
