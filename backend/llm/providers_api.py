"""Admin-only REST API for the Emergent Universal Key (mounted at /api/admin/providers).

The platform runs entirely on a single Emergent Universal Key. The admin can view
the active key (masked), replace it with another Universal Key (applied instantly,
no restart), or reset back to the platform default.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.deps import get_current_user
from core.base_models import utcnow
from core.db import get_db
from llm import providers as P

router = APIRouter(prefix="/api/admin/providers")


async def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get("global_role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


async def _audit(admin: dict, action: str, detail: str = ""):
    try:
        await get_db().admin_activity.insert_one({
            "actor_id": admin["id"], "actor_email": admin.get("email"),
            "action": action, "target_type": "universal_key",
            "target_id": "universal_key", "target_label": "Emergent Universal Key",
            "detail": detail, "created_at": utcnow(),
        })
    except Exception:
        pass


class KeyUpdate(BaseModel):
    api_key: str


@router.get("/universal-key")
async def get_universal_key(admin: dict = Depends(require_admin)):
    """Current active Universal Key (masked) + its source."""
    return await P.summary()


@router.put("/universal-key")
async def set_universal_key(body: KeyUpdate, admin: dict = Depends(require_admin)):
    """Replace the active Universal Key — applied immediately, no restart."""
    try:
        out = await P.set_key(body.api_key)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    await _audit(admin, "universal_key_update", "key replaced")
    return out


@router.post("/universal-key/reset")
async def reset_universal_key(admin: dict = Depends(require_admin)):
    """Reset back to the platform-provided default key."""
    out = await P.reset_key()
    await _audit(admin, "universal_key_reset", "reset to default")
    return out
