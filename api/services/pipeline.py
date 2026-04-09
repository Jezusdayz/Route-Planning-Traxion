"""Pipeline de re-cálculo: re-ejecuta el flujo completo desde el chat cuando cambia input."""

from motor.motor_asyncio import AsyncIOMotorDatabase

from api.models.nivel_servicio import NivelServicio
from api.services.geocoding import geocode_ciudad
from api.services.planner import calcular_mision
from api.services.routing import calcular_ruta
from api.services.session_manager import get_session, update_seccion

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

    # Leer valores actuales desde sección input_usuario de la sesión
    input_actual = sesion.get("input_usuario") or {}

    # Merge: input nuevo sobre valores de sesión existentes; filtra valores centinela
    _INVALIDOS = {"sin definir", "sin_definir", "", None}
    origen = input_usuario.get("origen_texto") or input_actual.get("origen_texto", "")
    destino = input_usuario.get("destino_texto") or input_actual.get("destino_texto", "")
    pasajeros = input_usuario.get("pasajeros") or input_actual.get("pasajeros", 1)
    nivel_raw = input_usuario.get("nivel_servicio")
    nivel_id = (nivel_raw if nivel_raw not in _INVALIDOS else None) or input_actual.get("nivel_servicio", "economico")
    duracion = input_usuario.get("duracion_estimada_horas") or input_actual.get("duracion_estimada_horas")

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

    # 4. Actualizar sección input_usuario con los nuevos datos
    input_actualizado = {
        **input_actual,
        "origen_texto": origen,
        "destino_texto": destino,
        "pasajeros": pasajeros,
        "nivel_servicio": nivel_id,
    }
    if duracion is not None:
        input_actualizado["duracion_estimada_horas"] = duracion

    await update_seccion(token, "input_usuario", input_actualizado, db)

    # 5. Actualizar normalizacion
    normalizacion = {
        "origen": {"ciudad": origen, "lat": coords_origen["lat"], "lon": coords_origen["lon"]},
        "destino": {"ciudad": destino, "lat": coords_destino["lat"], "lon": coords_destino["lon"]},
    }
    await update_seccion(token, "normalizacion", normalizacion, db)

    # 6. Re-ejecutar misión (flota + validaciones + costeo)
    return await calcular_mision(
        token=token,
        pasajeros=pasajeros,
        nivel=nivel,
        distancia_base_km=ruta["distancia_km"],
        tiempo_base_h=ruta["tiempo_h"],
        db=db,
    )
