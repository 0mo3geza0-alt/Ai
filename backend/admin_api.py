from fastapi import APIRouter, Depends, HTTPException
from core.db import get_db
from auth.deps import get_current_user

router = APIRouter(prefix="/api/admin")


async def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("global_role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("/stats")
async def stats(admin: dict = Depends(require_admin)):
    db = get_db()
    creations = {}
    for k in ["document", "code", "image", "audio"]:
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
    docs = await db.users.find({}).sort("created_at", -1).to_list(500)
    return [{"id": str(u["_id"]), "email": u["email"], "name": u.get("name"),
             "global_role": u.get("global_role", "user"), "auth_provider": u.get("auth_provider", "local"),
             "created_at": u.get("created_at").isoformat() if u.get("created_at") else None} for u in docs]
