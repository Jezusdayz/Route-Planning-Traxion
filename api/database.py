from contextlib import asynccontextmanager

import motor.motor_asyncio

from api.config import settings

_client: motor.motor_asyncio.AsyncIOMotorClient | None = None
_db: motor.motor_asyncio.AsyncIOMotorDatabase | None = None


@asynccontextmanager
async def lifespan(app):
    global _client, _db
    _client = motor.motor_asyncio.AsyncIOMotorClient(settings.mongodb_url)
    _db = _client[settings.mongodb_db_name]
    yield
    _client.close()


def get_db() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not initialised — lifespan not active")
    return _db
