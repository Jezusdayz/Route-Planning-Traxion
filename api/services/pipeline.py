"""Pipeline de re-cálculo: re-ejecuta el flujo completo desde el chat cuando cambia input."""

from motor.motor_asyncio import AsyncIOMotorDatabase

from api.models.nivel_servicio import NivelServicio
from api.services.geocoding import geocode_ciudad
from api.services.planner import calcular_mision
from api.services.routing import calcular_ruta
from api.services.session_manager import get_session

_COLLECTION = "sesiones_viaje"


async def recalcular_viaje(
    token: str,
    input_usuario: dict,
    db: AsyncIOMotorDatabase,
) -> dict:
    """Re-ejecuta el pipeline completo: geocode → ruta → misión (flota + costeo).

    Merge el ``input_usuario`` recibido con la sesión existente para rellenar
    los campos no modificados por el usuario en este turno.

    Args:
        token: Token de la sesión activa.
        input_usuario: Campos modificados por el usuario (puede ser parcial).
        db: Conexión a MongoDB.

    Returns:
        Dict con 'planeacion', 'operacion', 'validaciones', 'supuestos', 'costeo'.

    Raises:
        ValueError si la sesión no existe, el nivel no está en catálogo,
        o alguna validación de viabilidad falla.
    """
    sesion = await get_session(token, db)
    if sesion is None:
        raise ValueError("Sesión no encontrada o expirada.")

    # Merge: input nuevo sobre valores de sesión existentes
    origen = input_usuario.get("origen_texto") or sesion.get("origen", "")
    destino = input_usuario.get("destino_texto") or sesion.get("destino", "")
    pasajeros = input_usuario.get("pasajeros") or sesion.get("pasajeros", 1)
    nivel_id = input_usuario.get("nivel_servicio") or sesion.get("nivel_servicio", "economico")

    # 1. Geocodificación
    coords_origen = await geocode_ciudad(origen, db)
    coords_destino = await geocode_ciudad(destino, db)

    # 2. Cálculo de ruta
    ruta = await calcular_ruta(
        coords_origen["lat"], coords_origen["lon"],
        coords_destino["lat"], coords_destino["lon"],
    )

    # 3. Cargar nivel de servicio
    nivel_doc = await db["niveles_servicio"].find_one({"_id": nivel_id})
    if nivel_doc is None:
        raise ValueError(f"Nivel de servicio no encontrado: {nivel_id!r}.")
    nivel = NivelServicio.model_validate(nivel_doc)

    # 4. Actualizar base de la sesión con los nuevos datos
    await db[_COLLECTION].update_one(
        {"token": token},
        {
            "$set": {
                "origen": origen,
                "destino": destino,
                "pasajeros": pasajeros,
                "nivel_servicio": nivel_id,
                "distancia_km": ruta["distancia_km"],
                "tiempo_h": ruta["tiempo_h"],
                "input_usuario": input_usuario,
            }
        },
    )

    # 5. Re-ejecutar misión (flota + validaciones + costeo)
    return await calcular_mision(
        token=token,
        pasajeros=pasajeros,
        nivel=nivel,
        distancia_base_km=ruta["distancia_km"],
        tiempo_base_h=ruta["tiempo_h"],
        db=db,
    )
