from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

import os
from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware

from core.config import settings
from core.logging import logger
from core.errors import AppError, app_error_handler, unhandled_error_handler
from core import db as database
from core.base_models import utcnow
from auth.router import router as auth_router
from auth.security import hash_password, verify_password
from workspace.router import router as workspace_router
from studio.router import router as studio_router
from admin_api import router as admin_router
from memory.router import router as memory_router
from agents.router import router as agents_router
from security.router import router as security_router
from billing.router import router as billing_router
from tools.router import router as tools_router
from planning.router import router as planning_router
from security.middleware import SecurityMiddleware
from memory import embeddings as _embeddings
from workspace.storage import init_storage

app = FastAPI(title=settings.app_name, version=settings.app_version)
meta_router = APIRouter(prefix="/api")


@meta_router.get("/health")
async def health():
    db_ok = await database.ping()
    return {"status": "ok" if db_ok else "degraded", "service": settings.app_name,
            "version": settings.app_version, "phase": settings.phase,
            "database": "connected" if db_ok else "unavailable", "env": settings.env}


@meta_router.get("/version")
async def version():
    return {"name": settings.app_name, "version": settings.app_version, "phase": settings.phase}


@meta_router.get("/")
async def root():
    return {"message": f"{settings.app_name} API", "version": settings.app_version}


app.include_router(meta_router)
app.include_router(auth_router)
app.include_router(workspace_router)
app.include_router(studio_router)
app.include_router(admin_router)
app.include_router(memory_router)
app.include_router(agents_router)
app.include_router(security_router)
app.include_router(billing_router)
app.include_router(tools_router)
app.include_router(planning_router)

app.add_middleware(SecurityMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_origin_regex=r"https://.*\.(emergentagent\.com|emergent\.sh)",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)


async def _ensure_indexes():
    db = database.get_db()
    await db.system_meta.create_index("key", unique=True)
    await db.users.create_index("email", unique=True)
    await db.memberships.create_index([("org_id", 1), ("user_id", 1)], unique=True)
    await db.sessions.create_index("jti")
    await db.sessions.create_index("expires_at", expireAfterSeconds=0)
    await db.api_keys.create_index("prefix", unique=True)
    await db.wsfiles.create_index([("project_id", 1), ("file_key", 1), ("version", -1)])
    await db.memories.create_index("org_id")
    await db.memories.create_index([("org_id", 1), ("agent_id", 1)])
    await db.agents.create_index([("org_id", 1), ("created_at", -1)])
    await db.agent_runs.create_index([("org_id", 1), ("agent_id", 1), ("created_at", -1)])
    await db.audit_logs.create_index([("org_id", 1), ("created_at", -1)])
    await db.audit_logs.create_index("created_at", expireAfterSeconds=60 * 60 * 24 * 30)


async def _seed_admin():
    db = database.get_db()
    email = os.environ.get("ADMIN_EMAIL", "admin@aiplatform.com")
    password = os.environ.get("ADMIN_PASSWORD", "admin12345")
    existing = await db.users.find_one({"email": email})
    if existing is None:
        res = await db.users.insert_one({"email": email, "name": "Admin",
                                         "password_hash": hash_password(password),
                                         "global_role": "admin", "auth_provider": "local",
                                         "created_at": utcnow()})
        user_id = res.inserted_id
    else:
        user_id = existing["_id"]
        upd = {}
        if not verify_password(password, existing.get("password_hash", "")):
            upd["password_hash"] = hash_password(password)
        if existing.get("global_role") != "admin":
            upd["global_role"] = "admin"
        if upd:
            await db.users.update_one({"_id": user_id}, {"$set": upd})
    # Ensure admin has a pro org + membership + default_org_id (idempotent)
    user = await db.users.find_one({"_id": user_id})
    org_id = user.get("default_org_id") if user else None
    org = None
    if org_id:
        try:
            from bson import ObjectId as _OID
            org = await db.organizations.find_one({"_id": _OID(org_id)})
        except Exception:
            org = None
    if not org:
        org_ins = await db.organizations.insert_one({"name": "Admin Org", "owner_id": str(user_id),
                                                     "plan": "pro", "credits": 100000, "created_at": utcnow()})
        org_id = str(org_ins.inserted_id)
        await db.users.update_one({"_id": user_id}, {"$set": {"default_org_id": org_id}})
    else:
        # Make sure plan/credits are healthy for admin org
        if org.get("plan") != "pro" or (org.get("credits", 0) < 1000):
            await db.organizations.update_one({"_id": org["_id"]}, {"$set": {"plan": "pro", "credits": 100000}})
    membership = await db.memberships.find_one({"org_id": str(org_id), "user_id": str(user_id)})
    if not membership:
        await db.memberships.insert_one({"org_id": str(org_id), "user_id": str(user_id),
                                         "role": "owner", "created_at": utcnow()})


@app.on_event("startup")
async def on_startup():
    await _ensure_indexes()
    await _seed_admin()
    try:
        init_storage()
    except Exception as e:
        logger.error("Storage init failed (uploads may not work): %s", e)
    import asyncio as _asyncio
    _asyncio.create_task(_asyncio.to_thread(_embeddings.warmup))
    try:
        from billing.setup_stripe import setup_catalog
        _asyncio.create_task(_asyncio.to_thread(setup_catalog))
    except Exception as e:
        logger.error("Stripe setup skipped: %s", e)
    try:
        from billing.monthly_reset import monthly_reset_loop
        _asyncio.create_task(monthly_reset_loop())
    except Exception as e:
        logger.error("Monthly reset loop not started: %s", e)
    logger.info("%s %s (%s) started", settings.app_name, settings.app_version, settings.phase)


@app.on_event("shutdown")
async def on_shutdown():
    database.close_client()
    logger.info("Shutdown complete")
