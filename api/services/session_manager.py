"""Servicio: persistencia de sesiones de viaje en MongoDB."""

from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

_COLLECTION = "sesiones_viaje"


async def create_session(token: str, datos_viaje: dict, db: AsyncIOMotorDatabase) -> None:
    """Persiste una nueva sesión de viaje en MongoDB."""
    from api.services.auth import calcular_expiracion

    documento = {
        "token": token,
        "activa": True,
        "creada_en": datetime.now(timezone.utc),
        "expira_en": calcular_expiracion(),
        **datos_viaje,
    }
    await db[_COLLECTION].insert_one(documento)


async def get_session(token: str, db: AsyncIOMotorDatabase) -> dict | None:
    """Recupera el documento de sesión de viaje por token."""
    return await db[_COLLECTION].find_one({"token": token})


async def expire_session(token: str, db: AsyncIOMotorDatabase) -> None:
    """Marca una sesión como inactiva."""
    await db[_COLLECTION].update_one(
        {"token": token},
        {"$set": {"activa": False, "finalizada_en": datetime.now(timezone.utc)}},
    )
