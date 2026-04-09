"""Construcción y persistencia del objeto 'resultado' final de la misión."""

from motor.motor_asyncio import AsyncIOMotorDatabase

_COLLECTION = "sesiones_viaje"


def construir_resultado(sesion: dict) -> dict:
    """Consolida los datos de planeación, operación y costeo en un objeto resultado.

    Args:
        sesion: Documento completo de sesión recuperado de MongoDB.

    Returns:
        Dict con las claves clave del resultado operativo:
        vehiculo_seleccionado, unidades, distancia_total_km, tiempo_total_h, costo_total.
    """
    operacion = sesion.get("operacion") or {}
    vehiculo = operacion.get("vehiculo") or {}
    planeacion = sesion.get("planeacion") or {}
    costeo = sesion.get("costeo") or {}

    return {
        "vehiculo_seleccionado": vehiculo.get("modelo", "N/A"),
        "unidades": operacion.get("unidades", 1),
        "distancia_total_km": planeacion.get("distancia_operativa_km", 0.0),
        "tiempo_total_h": planeacion.get("tiempo_operativo_h", 0.0),
        "costo_total": costeo.get("costo_total", 0.0),
    }


async def persistir_resultado(
    token: str,
    resultado: dict,
    db: AsyncIOMotorDatabase,
) -> None:
    """Persiste el objeto resultado en la sesión y avanza fase_actual a 'resultado'."""
    await db[_COLLECTION].update_one(
        {"token": token},
        {
            "$set": {
                "resultado": resultado,
            }
        },
    )
