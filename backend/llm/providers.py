"""Emergent Universal Key manager — hot-reloadable, no restart needed.

The whole platform runs on a single Emergent Universal Key. The default key
comes from the ``EMERGENT_LLM_KEY`` environment variable. The platform owner can
replace it with ANOTHER Universal Key from the Admin Panel; the new key is
stored (encrypted with Fernet) in MongoDB and applied IMMEDIATELY to an
in-memory cache, so every subsequent AI call (text/chat/image/voice/music) uses
it with no restart or redeploy.
"""
import os

from cryptography.fernet import Fernet, InvalidToken

from core.db import get_db
from core.base_models import utcnow
from core.logging import logger

SETTINGS = "ai_settings"
KEY_DOC = "universal_key"
EMERGENT_DASHBOARD = "https://app.emergent.sh/"

# The platform-provided default key (never overwritten in the DB).
_ENV_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

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
    """sk-emergent-********abcd style mask (never exposes the full key)."""
    if not plain:
        return ""
    if len(plain) <= 8:
        return "*" * len(plain)
    return f"{plain[:12]}{'*' * 8}{plain[-4:]}"


# ---------------------------------------------------- in-memory active key state
_active_key = _ENV_KEY
_is_custom = False
_updated_at = None


async def load_key():
    """Load the owner's custom key (if any) from the DB into the in-memory cache.
    Called once on startup so a previously-set key survives restarts."""
    global _active_key, _is_custom, _updated_at
    try:
        doc = await get_db()[SETTINGS].find_one({"key": KEY_DOC})
    except Exception as e:  # pragma: no cover
        logger.error("load universal key failed: %s", e)
        doc = None
    if doc and doc.get("value_enc"):
        plain = decrypt_key(doc["value_enc"])
        if plain:
            _active_key = plain
            _is_custom = True
            _updated_at = doc.get("updated_at")
            return
    _active_key = _ENV_KEY
    _is_custom = False
    _updated_at = None


def get_key() -> str:
    """Return the currently-active Universal Key (custom if set, else default)."""
    return _active_key or _ENV_KEY


async def set_key(new_key: str) -> dict:
    """Replace the active Universal Key. Stored encrypted + applied instantly."""
    global _active_key, _is_custom, _updated_at
    new_key = (new_key or "").strip()
    if not new_key:
        raise ValueError("Universal key cannot be empty")
    if "*" in new_key:
        raise ValueError("Please paste the full key, not the masked value")
    if not _FERNET:
        raise RuntimeError("ENCRYPTION_KEY not configured")
    now = utcnow()
    await get_db()[SETTINGS].update_one(
        {"key": KEY_DOC},
        {"$set": {"value_enc": encrypt_key(new_key), "updated_at": now}},
        upsert=True,
    )
    _active_key = new_key
    _is_custom = True
    _updated_at = now
    return await summary()


async def reset_key() -> dict:
    """Remove the custom key and fall back to the platform default (env)."""
    global _active_key, _is_custom, _updated_at
    try:
        await get_db()[SETTINGS].delete_one({"key": KEY_DOC})
    except Exception:  # pragma: no cover
        pass
    _active_key = _ENV_KEY
    _is_custom = False
    _updated_at = None
    return await summary()


async def summary() -> dict:
    """Admin-facing view of the active key (never the full key)."""
    active = get_key()
    return {
        "key_masked": mask_key(active),
        "has_key": bool(active),
        "source": "custom" if _is_custom else "default",
        "is_custom": _is_custom,
        "has_default": bool(_ENV_KEY),
        "updated_at": _updated_at,
        "dashboard_url": EMERGENT_DASHBOARD,
    }
