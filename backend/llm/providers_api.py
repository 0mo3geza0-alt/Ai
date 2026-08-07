"""Admin-only REST API for the AI Provider Manager (mounted at /api/admin/providers)."""
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


async def _audit(admin: dict, action: str, label: str, detail: str = ""):
    try:
        await get_db().admin_activity.insert_one({
            "actor_id": admin["id"], "actor_email": admin.get("email"),
            "action": action, "target_type": "ai_provider", "target_id": label,
            "target_label": label, "detail": detail, "created_at": utcnow(),
        })
    except Exception:
        pass


class ProviderCreate(BaseModel):
    slug: str
    name: str | None = None
    enabled: bool | None = False
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    priority: int | None = 999
    monthly_budget: float | None = 0
    price_in: float | None = 0
    price_out: float | None = 0


class ProviderUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    priority: int | None = None
    monthly_budget: float | None = None
    price_in: float | None = None
    price_out: float | None = None


@router.get("/catalog")
async def catalog(admin: dict = Depends(require_admin)):
    """Known provider types + their sensible defaults (for the 'add provider' UI)."""
    return [{"slug": s, "label": r["label"], "base_url": r["base_url"],
             "model": r["model"], "key_optional": bool(r.get("key_optional"))}
            for s, r in P.REGISTRY.items()]


@router.get("")
async def list_providers(admin: dict = Depends(require_admin)):
    await P.seed_defaults()
    return await P.list_public()


@router.post("")
async def create(body: ProviderCreate, admin: dict = Depends(require_admin)):
    try:
        out = await P.create_provider(body.slug, body.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await _audit(admin, "provider_create", out["name"])
    return out


@router.put("/{pid}")
async def update(pid: str, body: ProviderUpdate, admin: dict = Depends(require_admin)):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    out = await P.update_provider(pid, data)
    if not out:
        raise HTTPException(status_code=404, detail="Provider not found")
    changed = [k for k in data if k != "api_key"]
    if "api_key" in data:
        changed.append("key")
    await _audit(admin, "provider_update", out["name"], "changed: " + ", ".join(changed))
    return out


@router.delete("/{pid}")
async def remove(pid: str, admin: dict = Depends(require_admin)):
    ok = await P.delete_provider(pid)
    if not ok:
        raise HTTPException(status_code=404, detail="Provider not found")
    await _audit(admin, "provider_delete", pid)
    return {"ok": True}


@router.post("/{pid}/test")
async def test(pid: str, admin: dict = Depends(require_admin)):
    res = await P.test_provider(pid)
    await _audit(admin, "provider_test", pid, "connected" if res.get("connected") else res.get("error", "failed"))
    return res


@router.get("/usage")
async def usage(admin: dict = Depends(require_admin)):
    return await P.usage_summary()


@router.get("/logs")
async def logs(limit: int = 100, admin: dict = Depends(require_admin)):
    return await P.recent_logs(limit)
