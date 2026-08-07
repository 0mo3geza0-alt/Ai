"""Modular multi-provider AI gateway with hot-reloadable, encrypted API keys.

The platform owner manages providers entirely from the Admin Panel (stored in
MongoDB, keys encrypted at rest with Fernet). Every text generation reads the
active providers fresh from the DB, so pasting/updating a key takes effect
IMMEDIATELY with no restart/redeploy.

All providers are reached through their OpenAI-compatible Chat Completions API
using a single unified async client (openai.AsyncOpenAI with a per-provider
base_url), which gives uniform streaming + usage across every provider. If all
configured providers fail (or none are enabled), the caller falls back to the
built-in Emergent Universal Key path so the app never goes down.
"""
import os
import time
import uuid
import asyncio
import datetime as _dt

from cryptography.fernet import Fernet, InvalidToken
from openai import AsyncOpenAI

from core.db import get_db
from core.base_models import utcnow
from core.logging import logger

# ----------------------------------------------------------------- encryption
_ENC_KEY = os.environ.get("ENCRYPTION_KEY", "")
try:
    _FERNET = Fernet(_ENC_KEY.encode()) if _ENC_KEY else None
except Exception as e:  # pragma: no cover
    logger.error("Invalid ENCRYPTION_KEY: %s", e)
    _FERNET = None


def encrypt_key(plain: str) -> str:
    if not plain:
        return ""
    if not _FERNET:
        raise RuntimeError("ENCRYPTION_KEY not configured")
    return _FERNET.encrypt(plain.encode()).decode()


def decrypt_key(token: str) -> str:
    if not token:
        return ""
    if not _FERNET:
        return ""
    try:
        return _FERNET.decrypt(token.encode()).decode()
    except (InvalidToken, Exception):  # noqa: BLE001
        return ""


def mask_key(plain: str) -> str:
    """sk-****************abcd style mask (never exposes the full key)."""
    if not plain:
        return ""
    if len(plain) <= 8:
        return "*" * len(plain)
    return f"{plain[:3]}{'*' * 12}{plain[-4:]}"


# ------------------------------------------------------------- provider registry
# slug -> defaults. `key_optional` providers (Ollama) can run without an API key.
REGISTRY = {
    "openai":      {"label": "OpenAI",                 "base_url": "https://api.openai.com/v1",                         "model": "gpt-4o-mini"},
    "anthropic":   {"label": "Anthropic (Claude)",     "base_url": "https://api.anthropic.com/v1/",                     "model": "claude-3-5-sonnet-latest"},
    "gemini":      {"label": "Google Gemini",          "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/", "model": "gemini-2.0-flash"},
    "openrouter":  {"label": "OpenRouter",             "base_url": "https://openrouter.ai/api/v1",                      "model": "google/gemini-2.0-flash-exp:free"},
    "groq":        {"label": "Groq",                   "base_url": "https://api.groq.com/openai/v1",                    "model": "llama-3.3-70b-versatile"},
    "deepseek":    {"label": "DeepSeek",               "base_url": "https://api.deepseek.com/v1",                       "model": "deepseek-chat"},
    "xai":         {"label": "xAI (Grok)",             "base_url": "https://api.x.ai/v1",                               "model": "grok-2-latest"},
    "cerebras":    {"label": "Cerebras",               "base_url": "https://api.cerebras.ai/v1",                        "model": "llama3.1-8b"},
    "huggingface": {"label": "Hugging Face",           "base_url": "https://router.huggingface.co/v1",                  "model": "meta-llama/Llama-3.1-8B-Instruct"},
    "together":    {"label": "Together AI",            "base_url": "https://api.together.xyz/v1",                       "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo"},
    "fireworks":   {"label": "Fireworks AI",           "base_url": "https://api.fireworks.ai/inference/v1",             "model": "accounts/fireworks/models/llama-v3p1-8b-instruct"},
    "sambanova":   {"label": "SambaNova",              "base_url": "https://api.sambanova.ai/v1",                       "model": "Meta-Llama-3.1-8B-Instruct"},
    "ollama":      {"label": "Ollama (self-hosted)",   "base_url": "http://localhost:11434/v1",                         "model": "llama3.1",  "key_optional": True},
    "custom":      {"label": "Custom (OpenAI-compatible)", "base_url": "",                                              "model": ""},
}
PROVIDER_ORDER = list(REGISTRY.keys())

COLL = "ai_providers"
LOGS = "ai_provider_logs"

# rough token estimator for streamed responses (no exact usage from stream)
try:
    import tiktoken
    _ENC = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(text: str) -> int:
        try:
            return len(_ENC.encode(text or ""))
        except Exception:
            return max(1, len(text or "") // 4)
except Exception:  # pragma: no cover
    def _count_tokens(text: str) -> int:
        return max(1, len(text or "") // 4)


# --------------------------------------------------------------- serialization
def _public(doc: dict) -> dict:
    """Admin-facing view. NEVER includes the full/decrypted key."""
    plain = decrypt_key(doc.get("api_key_enc", ""))
    reg = REGISTRY.get(doc.get("slug"), {})
    return {
        "id": doc["id"],
        "slug": doc["slug"],
        "name": doc.get("name") or reg.get("label", doc["slug"]),
        "enabled": bool(doc.get("enabled", False)),
        "has_key": bool(plain),
        "key_masked": mask_key(plain),
        "key_optional": bool(reg.get("key_optional", False)),
        "base_url": doc.get("base_url") or reg.get("base_url", ""),
        "model": doc.get("model") or reg.get("model", ""),
        "priority": int(doc.get("priority", 999)),
        "monthly_budget": float(doc.get("monthly_budget", 0) or 0),
        "price_in": float(doc.get("price_in", 0) or 0),   # USD / 1M input tokens
        "price_out": float(doc.get("price_out", 0) or 0),  # USD / 1M output tokens
        "status": doc.get("status", "untested"),
        "last_error": doc.get("last_error", ""),
        "last_tested_at": doc.get("last_tested_at"),
        "updated_at": doc.get("updated_at"),
    }


# ------------------------------------------------------------------ seed / CRUD
async def seed_defaults():
    """Idempotently create a disabled row for every known provider."""
    db = get_db()
    existing = {d["slug"] async for d in db[COLL].find({}, {"slug": 1})}
    prio = 1
    for slug in PROVIDER_ORDER:
        if slug in existing:
            continue
        reg = REGISTRY[slug]
        await db[COLL].insert_one({
            "id": str(uuid.uuid4()),
            "slug": slug,
            "name": reg["label"],
            "enabled": False,
            "api_key_enc": "",
            "base_url": reg["base_url"],
            "model": reg["model"],
            "priority": prio,
            "monthly_budget": 0,
            "price_in": 0,
            "price_out": 0,
            "status": "untested",
            "last_error": "",
            "created_at": utcnow(),
            "updated_at": utcnow(),
        })
        prio += 1
    try:
        await db[LOGS].create_index([("ts", -1)])
        await db[LOGS].create_index([("provider_id", 1), ("ts", -1)])
    except Exception:
        pass


async def list_public() -> list[dict]:
    db = get_db()
    docs = [d async for d in db[COLL].find({}).sort("priority", 1)]
    return [_public(d) for d in docs]


async def get_raw(pid: str) -> dict | None:
    return await get_db()[COLL].find_one({"id": pid})


async def create_provider(slug: str, data: dict) -> dict:
    if slug not in REGISTRY:
        raise ValueError("Unknown provider type")
    db = get_db()
    reg = REGISTRY[slug]
    doc = {
        "id": str(uuid.uuid4()),
        "slug": slug,
        "name": data.get("name") or reg["label"],
        "enabled": bool(data.get("enabled", False)),
        "api_key_enc": encrypt_key(data.get("api_key", "") or ""),
        "base_url": data.get("base_url") or reg["base_url"],
        "model": data.get("model") or reg["model"],
        "priority": int(data.get("priority", 999)),
        "monthly_budget": float(data.get("monthly_budget", 0) or 0),
        "price_in": float(data.get("price_in", 0) or 0),
        "price_out": float(data.get("price_out", 0) or 0),
        "status": "untested",
        "last_error": "",
        "created_at": utcnow(),
        "updated_at": utcnow(),
    }
    await db[COLL].insert_one(doc)
    return _public(doc)


async def update_provider(pid: str, data: dict) -> dict | None:
    db = get_db()
    doc = await db[COLL].find_one({"id": pid})
    if not doc:
        return None
    upd = {"updated_at": utcnow()}
    for f in ("name", "base_url", "model"):
        if data.get(f) is not None:
            upd[f] = data[f]
    if data.get("enabled") is not None:
        upd["enabled"] = bool(data["enabled"])
    for f in ("priority",):
        if data.get(f) is not None:
            upd[f] = int(data[f])
    for f in ("monthly_budget", "price_in", "price_out"):
        if data.get(f) is not None:
            upd[f] = float(data[f] or 0)
    # Only replace the key when a NEW non-masked key is provided.
    new_key = data.get("api_key")
    if new_key and "*" not in new_key:
        upd["api_key_enc"] = encrypt_key(new_key.strip())
        upd["status"] = "untested"
    await db[COLL].update_one({"id": pid}, {"$set": upd})
    return _public(await db[COLL].find_one({"id": pid}))


async def delete_provider(pid: str) -> bool:
    res = await get_db()[COLL].delete_one({"id": pid})
    return res.deleted_count > 0


# --------------------------------------------------------------------- client
def _client(doc: dict) -> AsyncOpenAI:
    reg = REGISTRY.get(doc["slug"], {})
    base = doc.get("base_url") or reg.get("base_url") or ""
    key = decrypt_key(doc.get("api_key_enc", "")) or ("ollama" if reg.get("key_optional") else "")
    if not base:
        raise RuntimeError("No base_url configured")
    if not key:
        raise RuntimeError("No API key configured")
    return AsyncOpenAI(api_key=key, base_url=base, timeout=90.0, max_retries=0)


def _model(doc: dict) -> str:
    return doc.get("model") or REGISTRY.get(doc["slug"], {}).get("model") or ""


# --------------------------------------------------------------- usage / budget
async def _month_start() -> _dt.datetime:
    now = utcnow()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def _month_cost(pid: str) -> float:
    db = get_db()
    since = await _month_start()
    cur = db[LOGS].aggregate([
        {"$match": {"provider_id": pid, "success": True, "ts": {"$gte": since}}},
        {"$group": {"_id": None, "cost": {"$sum": "$cost"}}},
    ])
    async for row in cur:
        return float(row.get("cost", 0) or 0)
    return 0.0


async def record_log(doc, model, success, latency_ms, ptoks, ctoks, cost, error="", rtype="chat", estimated=False):
    try:
        await get_db()[LOGS].insert_one({
            "id": str(uuid.uuid4()),
            "provider_id": (doc or {}).get("id", ""),
            "provider_slug": (doc or {}).get("slug", ""),
            "provider_name": (doc or {}).get("name", ""),
            "model": model,
            "success": bool(success),
            "latency_ms": int(latency_ms),
            "prompt_tokens": int(ptoks or 0),
            "completion_tokens": int(ctoks or 0),
            "total_tokens": int((ptoks or 0) + (ctoks or 0)),
            "cost": float(cost or 0),
            "estimated": bool(estimated),
            "error": (error or "")[:500],
            "request_type": rtype,
            "ts": utcnow(),
        })
    except Exception as e:  # pragma: no cover
        logger.error("provider log failed: %s", e)


def _cost(doc, ptoks, ctoks) -> float:
    pin = float(doc.get("price_in", 0) or 0)
    pout = float(doc.get("price_out", 0) or 0)
    return round((ptoks / 1_000_000.0) * pin + (ctoks / 1_000_000.0) * pout, 6)


# ------------------------------------------------------------------- the chain
async def _active_chain() -> list[dict]:
    """Enabled providers, sorted by priority, that have a usable key AND are not
    over their monthly budget. Read FRESH from DB every call => instant updates."""
    db = get_db()
    docs = [d async for d in db[COLL].find({"enabled": True}).sort("priority", 1)]
    out = []
    for d in docs:
        reg = REGISTRY.get(d["slug"], {})
        has_key = bool(decrypt_key(d.get("api_key_enc", ""))) or bool(reg.get("key_optional"))
        if not has_key or not _model(d):
            continue
        budget = float(d.get("monthly_budget", 0) or 0)
        if budget > 0 and await _month_cost(d["id"]) >= budget:
            continue  # budget exhausted -> skip (auto rotate to next)
        out.append(d)
    return out


async def generate_text(system: str, full_prompt: str, rtype: str = "chat") -> tuple[str, bool]:
    """Try each active provider by priority. Returns (text, used_provider).
    Raises if every configured provider fails (caller then uses Emergent)."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": full_prompt}]
    chain = await _active_chain()
    last_err = None
    for doc in chain:
        model = _model(doc)
        t0 = time.time()
        try:
            client = _client(doc)
            resp = await client.chat.completions.create(
                model=model, messages=messages, max_tokens=4096, temperature=0.7)
            text = (resp.choices[0].message.content or "").strip()
            u = getattr(resp, "usage", None)
            pt = getattr(u, "prompt_tokens", 0) or 0
            ct = getattr(u, "completion_tokens", 0) or 0
            if not text:
                raise RuntimeError("empty response")
            await record_log(doc, model, True, (time.time() - t0) * 1000, pt, ct, _cost(doc, pt, ct), rtype=rtype)
            await _mark_status(doc["id"], "active", "")
            return text, True
        except Exception as e:  # noqa: BLE001
            last_err = e
            logger.error("provider %s/%s failed: %s", doc["slug"], model, e)
            await record_log(doc, model, False, (time.time() - t0) * 1000, 0, 0, 0, error=str(e), rtype=rtype)
            await _mark_status(doc["id"], "error", str(e)[:200])
    raise RuntimeError(f"all providers failed: {last_err}" if chain else "no providers configured")


async def stream_text(system: str, full_prompt: str, rtype: str = "chat"):
    """Async generator of text deltas from the first working provider.
    Yields {'delta': str} then a final {'done': True, 'used': bool}. If ALL
    configured providers fail up-front, yields {'fallback': True} and returns."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": full_prompt}]
    chain = await _active_chain()
    if not chain:
        yield {"fallback": True}
        return
    ptoks_est = _count_tokens(system) + _count_tokens(full_prompt)
    last_err = None
    for idx, doc in enumerate(chain):
        model = _model(doc)
        t0 = time.time()
        acc = []
        started = False
        try:
            client = _client(doc)
            stream = await client.chat.completions.create(
                model=model, messages=messages, max_tokens=4096, temperature=0.7, stream=True)
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                piece = getattr(delta, "content", None)
                if piece:
                    started = True
                    acc.append(piece)
                    yield {"delta": piece}
            text = "".join(acc)
            if not text.strip():
                raise RuntimeError("empty stream")
            ctoks = _count_tokens(text)
            await record_log(doc, model, True, (time.time() - t0) * 1000, ptoks_est, ctoks,
                             _cost(doc, ptoks_est, ctoks), rtype=rtype, estimated=True)
            await _mark_status(doc["id"], "active", "")
            yield {"done": True, "used": True}
            return
        except Exception as e:  # noqa: BLE001
            last_err = e
            logger.error("provider stream %s/%s failed: %s", doc["slug"], model, e)
            await record_log(doc, model, False, (time.time() - t0) * 1000, 0, 0, 0, error=str(e), rtype=rtype)
            await _mark_status(doc["id"], "error", str(e)[:200])
            if started:
                # partial output already sent to the client -> cannot cleanly
                # restart on another provider; end the turn here.
                yield {"done": True, "used": True}
                return
    # every provider failed before producing anything -> let caller use Emergent
    yield {"fallback": True}


async def _mark_status(pid: str, status: str, error: str):
    try:
        await get_db()[COLL].update_one(
            {"id": pid}, {"$set": {"status": status, "last_error": error, "updated_at": utcnow()}})
    except Exception:
        pass


# ---------------------------------------------------------------- test / usage
async def test_provider(pid: str) -> dict:
    doc = await get_raw(pid)
    if not doc:
        return {"connected": False, "error": "not found"}
    model = _model(doc)
    t0 = time.time()
    try:
        client = _client(doc)
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with the single word: pong"}],
            max_tokens=8, temperature=0)
        txt = (resp.choices[0].message.content or "").strip()
        latency = int((time.time() - t0) * 1000)
        await _mark_status(pid, "connected", "")
        await get_db()[COLL].update_one({"id": pid}, {"$set": {"last_tested_at": utcnow()}})
        return {"connected": True, "latency_ms": latency, "model": model, "sample": txt[:60]}
    except Exception as e:  # noqa: BLE001
        latency = int((time.time() - t0) * 1000)
        await _mark_status(pid, "failed", str(e)[:200])
        await get_db()[COLL].update_one({"id": pid}, {"$set": {"last_tested_at": utcnow()}})
        return {"connected": False, "latency_ms": latency, "model": model, "error": str(e)[:400]}


async def usage_summary() -> dict:
    db = get_db()
    now = utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month = await _month_start()

    async def agg(match):
        cur = db[LOGS].aggregate([
            {"$match": match},
            {"$group": {"_id": None,
                        "requests": {"$sum": 1},
                        "ok": {"$sum": {"$cond": ["$success", 1, 0]}},
                        "cost": {"$sum": "$cost"},
                        "latency": {"$avg": "$latency_ms"},
                        "tokens": {"$sum": "$total_tokens"}}},
        ])
        async for r in cur:
            return r
        return {"requests": 0, "ok": 0, "cost": 0, "latency": 0, "tokens": 0}

    day = await agg({"ts": {"$gte": today}})
    mon = await agg({"ts": {"$gte": month}})

    # per-provider month breakdown + remaining budget
    providers = []
    async for d in db[COLL].find({}).sort("priority", 1):
        mc = await _month_cost(d["id"])
        budget = float(d.get("monthly_budget", 0) or 0)
        providers.append({
            "id": d["id"], "name": d.get("name"), "slug": d["slug"],
            "enabled": bool(d.get("enabled")), "status": d.get("status", "untested"),
            "month_cost": round(mc, 4),
            "monthly_budget": budget,
            "remaining_budget": round(budget - mc, 4) if budget > 0 else None,
        })

    total_req = mon.get("requests", 0) or 0
    ok_req = mon.get("ok", 0) or 0
    return {
        "today_requests": day.get("requests", 0) or 0,
        "month_requests": total_req,
        "estimated_cost_month": round(mon.get("cost", 0) or 0, 4),
        "estimated_cost_today": round(day.get("cost", 0) or 0, 4),
        "avg_response_ms": int(mon.get("latency", 0) or 0),
        "success_rate": round((ok_req / total_req) * 100, 1) if total_req else 100.0,
        "month_tokens": mon.get("tokens", 0) or 0,
        "providers": providers,
    }


async def recent_logs(limit: int = 100) -> list[dict]:
    db = get_db()
    out = []
    async for d in db[LOGS].find({}).sort("ts", -1).limit(min(limit, 500)):
        out.append({
            "id": d.get("id"),
            "provider_name": d.get("provider_name") or d.get("provider_slug"),
            "provider_slug": d.get("provider_slug"),
            "model": d.get("model"),
            "success": d.get("success"),
            "latency_ms": d.get("latency_ms"),
            "total_tokens": d.get("total_tokens"),
            "cost": d.get("cost"),
            "estimated": d.get("estimated", False),
            "error": d.get("error", ""),
            "request_type": d.get("request_type"),
            "ts": d.get("ts"),
        })
    return out


# ------------------------------------------------- direct keys for TTS / images
async def direct_key(slug: str) -> tuple[str, str] | None:
    """Return (api_key, base_url) for an enabled provider that has a key, else None.
    Used so TTS (OpenAI) / images (Gemini) can use the owner's own key when set."""
    d = await get_db()[COLL].find_one({"slug": slug, "enabled": True})
    if not d:
        return None
    k = decrypt_key(d.get("api_key_enc", ""))
    if not k:
        return None
    return k, (d.get("base_url") or REGISTRY.get(slug, {}).get("base_url", ""))
