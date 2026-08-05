import os
import requests
from fastapi import HTTPException

EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"


def exchange_session(session_id: str) -> dict:
    """Exchange an Emergent OAuth session_id for user profile data (server-side only)."""
    try:
        resp = requests.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": session_id}, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.HTTPError:
        raise HTTPException(status_code=401, detail="Invalid or expired OAuth session")
    except Exception:
        raise HTTPException(status_code=502, detail="OAuth provider unavailable")
