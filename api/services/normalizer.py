"""Paso 2 del pipeline: normalización de input_usuario a coordenadas reales.

Geocodifica origen y destino, luego acumula el resultado en la sesión
sin sobrescribir datos anteriores.
"""

from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from api.services.geocoding import geocode_ciudad

_COLLECTION = "sesiones_viaje"


async def normalizar(
    token: str,
    input_usuario: dict,
    db: AsyncIOMotorDatabase,
) -> dict:
    """Geocodifica origen y destino del input_usuario y persiste la normalización.

    La normalización se AÑADE al documento de sesión existente.
    Actualiza `fase_actual` a 'normalizacion'.

    Returns:
        Dict con la normalizacion resultante:
        {
            "origen": {"ciudad": str, "lat": float, "lon": float},
            "destino": {"ciudad": str, "lat": float, "lon": float},
        }
    """
    origen_texto = input_usuario.get("origen_texto") or ""
    destino_texto = input_usuario.get("destino_texto") or ""

    coords_origen = await geocode_ciudad(origen_texto, db)
    coords_destino = await geocode_ciudad(destino_texto, db)

    normalizacion = {
        "origen": {"ciudad": origen_texto, **coords_origen},
        "destino": {"ciudad": destino_texto, **coords_destino},
    }

    await db[_COLLECTION].update_one(
        {"token": token},
        {
            "$set": {
                "input_usuario": input_usuario,
                "normalizacion": normalizacion,
                "fase_actual": "normalizacion",
                "actualizado_en": datetime.now(timezone.utc),
            }
        },
    )

    return normalizacion
