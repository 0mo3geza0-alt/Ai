"""Security middleware: in-process rate limiting + audit logging.

Implemented as pure ASGI (not BaseHTTPMiddleware) so SSE/streaming responses
are never buffered. Rate limits heavy endpoints per client (user or IP) and
records an audit trail for every mutating /api request.
"""
import re
import time
import asyncio
from collections import defaultdict, deque

from starlette.responses import JSONResponse

from core.db import get_db
from core.base_models import utcnow
from core.logging import logger
from auth.security import decode_token

RATE_LIMIT = 40          # heavy requests
RATE_WINDOW = 60         # per seconds, per client
HEAVY = ("/generate/", "/agents/", "/memories", "/chat/")
_buckets: dict[str, deque] = defaultdict(deque)
_ORG_RE = re.compile(r"/orgs/([a-f0-9]{24})")


def _header(scope, name: bytes) -> str:
    for k, v in scope.get("headers", []):
        if k == name:
            return v.decode("latin-1")
    return ""


def _client_id(scope) -> str:
    auth = _header(scope, b"authorization")
    if auth.startswith("Bearer "):
        try:
            p = decode_token(auth[7:])
            if p.get("sub"):
                return "u:" + p["sub"]
        except Exception:
            pass
    client = scope.get("client")
    return "ip:" + (client[0] if client else "unknown")


def _rate_limited(cid: str) -> bool:
    now = time.time()
    dq = _buckets[cid]
    while dq and dq[0] < now - RATE_WINDOW:
        dq.popleft()
    if len(dq) >= RATE_LIMIT:
        return True
    dq.append(now)
    return False


async def _audit(path: str, method: str, status: int, cid: str, blocked: bool = False):
    try:
        m = _ORG_RE.search(path)
        doc = {"method": method, "path": path, "status": status, "client": cid,
               "org_id": m.group(1) if m else None,
               "user_id": cid[2:] if cid.startswith("u:") else None,
               "blocked": blocked, "created_at": utcnow()}
        await get_db().audit_logs.insert_one(doc)
    except Exception as e:
        logger.error("audit write failed: %s", e)


class SecurityMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        method = scope.get("method", "GET")
        mutating = method in ("POST", "PATCH", "PUT", "DELETE")
        is_heavy = mutating and any(h in path for h in HEAVY)
        cid = _client_id(scope) if (is_heavy or (mutating and path.startswith("/api/"))) else None

        if is_heavy and _rate_limited(cid):
            asyncio.create_task(_audit(path, method, 429, cid, blocked=True))
            resp = JSONResponse(status_code=429,
                                content={"detail": "Rate limit exceeded. Please slow down and retry shortly."})
            return await resp(scope, receive, send)

        status_holder = {"status": 0}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        await self.app(scope, receive, send_wrapper)

        if mutating and path.startswith("/api/") and "/auth/" not in path:
            asyncio.create_task(_audit(path, method, status_holder["status"], cid))
