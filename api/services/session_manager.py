"""Servicio: persistencia de sesiones de viaje en MongoDB."""

from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

_COLLECTION = "sesiones_viaje"


async def create_session(token: str, input_usuario: dict, db: AsyncIOMotorDatabase) -> None:
    """Persiste una nueva sesión con identidad + input_usuario.

    Sólo almacena los campos de identidad. Cada etapa del pipeline
    persiste su propia sección mediante ``update_seccion``.
    """
    from api.services.auth import calcular_expiracion

    documento = {
        "token": token,
        "activa": True,
        "creada_en": datetime.now(timezone.utc),
        "expira_en": calcular_expiracion(),
        "input_usuario": input_usuario,
    }
    await db[_COLLECTION].insert_one(documento)


async def update_seccion(
    token: str,
    seccion: str,
    datos: dict,
    db: AsyncIOMotorDatabase,
) -> None:
    """Persiste una sección del Gran JSON usando $set quirúrgico."""
    await db[_COLLECTION].update_one(
        {"token": token},
        {"$set": {seccion: datos}},
    )


async def append_historial(
    token: str,
    entry: dict,
    db: AsyncIOMotorDatabase,
) -> None:
    """Agrega una entrada al historial de auditoría (nunca enviado al LLM)."""
    await db[_COLLECTION].update_one(
        {"token": token},
        {"$push": {"historial": entry}},
    )


async def get_session(token: str, db: AsyncIOMotorDatabase) -> dict | None:
    """Recupera el documento de sesión de viaje por token."""
    return await db[_COLLECTION].find_one({"token": token})


async def expire_session(token: str, db: AsyncIOMotorDatabase) -> None:
    """Marca una sesión como inactiva."""
    await db[_COLLECTION].update_one(
        {"token": token},
        {"$set": {"activa": False, "finalizada_en": datetime.now(timezone.utc)}},
    )
