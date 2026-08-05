from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI, APIRouter
from starlette.middleware.cors import CORSMiddleware

from core.config import settings
from core.logging import logger
from core.errors import AppError, app_error_handler, unhandled_error_handler
from core import db as database

app = FastAPI(title=settings.app_name, version=settings.app_version)
api_router = APIRouter(prefix="/api")


@api_router.get("/health")
async def health():
    db_ok = await database.ping()
    return {
        "status": "ok" if db_ok else "degraded",
        "service": settings.app_name,
        "version": settings.app_version,
        "phase": settings.phase,
        "database": "connected" if db_ok else "unavailable",
        "env": settings.env,
    }


@api_router.get("/version")
async def version():
    return {"name": settings.app_name, "version": settings.app_version, "phase": settings.phase}


@api_router.get("/")
async def root():
    return {"message": f"{settings.app_name} API", "version": settings.app_version}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)


@app.on_event("startup")
async def on_startup():
    await database.ensure_indexes()
    logger.info("%s %s (%s) started", settings.app_name, settings.app_version, settings.phase)


@app.on_event("shutdown")
async def on_shutdown():
    database.close_client()
    logger.info("Shutdown complete")
