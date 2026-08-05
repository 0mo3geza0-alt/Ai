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

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
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
        org = await db.organizations.insert_one({"name": "Admin Org", "owner_id": str(res.inserted_id),
                                                 "created_at": utcnow()})
        await db.memberships.insert_one({"org_id": str(org.inserted_id), "user_id": str(res.inserted_id),
                                         "role": "owner", "created_at": utcnow()})
        await db.users.update_one({"_id": res.inserted_id}, {"$set": {"default_org_id": str(org.inserted_id)}})
    elif not verify_password(password, existing.get("password_hash", "")):
        await db.users.update_one({"email": email}, {"$set": {"password_hash": hash_password(password)}})


@app.on_event("startup")
async def on_startup():
    await _ensure_indexes()
    await _seed_admin()
    try:
        init_storage()
    except Exception as e:
        logger.error("Storage init failed (uploads may not work): %s", e)
    logger.info("%s %s (%s) started", settings.app_name, settings.app_version, settings.phase)


@app.on_event("shutdown")
async def on_shutdown():
    database.close_client()
    logger.info("Shutdown complete")
