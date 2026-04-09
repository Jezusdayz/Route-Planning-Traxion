"""Servicio de autenticación: generación y validación de SessionTokens."""

import uuid
from datetime import datetime, timezone, timedelta

from motor.motor_asyncio import AsyncIOMotorDatabase

_COLLECTION = "sesiones_viaje"
_TTL_MINUTOS = 60


def generate_token() -> str:
    """Genera un UUID v4 como token de sesión."""
    return str(uuid.uuid4())


async def validate_token(token: str, db: AsyncIOMotorDatabase) -> dict | None:
    """Retorna el documento de sesión si el token es válido y no ha expirado."""
    sesion = await db[_COLLECTION].find_one({"token": token, "activa": True})
    if sesion is None:
        return None
    expira_en = sesion.get("expira_en")
    if expira_en and datetime.now(timezone.utc) > expira_en:
        await db[_COLLECTION].update_one({"token": token}, {"$set": {"activa": False}})
        return None
    return sesion


def calcular_expiracion() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=_TTL_MINUTOS)
