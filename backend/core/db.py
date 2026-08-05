from motor.motor_asyncio import AsyncIOMotorClient

from core.config import settings
from core.logging import logger

_client: AsyncIOMotorClient | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongo_url)
    return _client


def get_db():
    return get_client()[settings.db_name]


async def ping() -> bool:
    try:
        await get_client().admin.command("ping")
        return True
    except Exception as e:
        logger.error("MongoDB ping failed: %s", e)
        return False


async def ensure_indexes():
    db = get_db()
    await db.system_meta.create_index("key", unique=True)
    logger.info("Indexes ensured")


def close_client():
    global _client
    if _client is not None:
        _client.close()
        _client = None
