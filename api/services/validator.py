"""Motor de validación: semáforo de viabilidad del viaje."""

from motor.motor_asyncio import AsyncIOMotorDatabase

from api.models.seguridad import SeguridadOperativa

_RESERVA_AUTONOMIA = 1.2  # 20% de margen de seguridad


def validar_capacidad(pasajeros: int, capacidad_vehiculo: int, unidades: int) -> dict:
    """Valida que la flota tenga capacidad suficiente.

    Returns:
        {
            "requerida": int,
            "capacidad_total": int,
            "valido": bool,
        }
    """
    capacidad_total = capacidad_vehiculo * unidades
    return {
        "requerida": pasajeros,
        "capacidad_total": capacidad_total,
        "valido": capacidad_total >= pasajeros,
    }


def validar_autonomia(distancia_operativa_km: float, autonomia_vehiculo_km: float) -> dict:
    """Valida que la autonomía cubra la distancia con 20% de reserva.

    Criterio: autonomia_vehiculo >= distancia_operativa * 1.2

    Returns:
        {
            "distancia_total_km": float,
            "autonomia_vehiculo_km": float,
            "minimo_requerido_km": float,
            "valido": bool,
        }
    """
    minimo_requerido = round(distancia_operativa_km * _RESERVA_AUTONOMIA, 2)
    return {
        "distancia_total_km": distancia_operativa_km,
        "autonomia_vehiculo_km": autonomia_vehiculo_km,
        "minimo_requerido_km": minimo_requerido,
        "valido": autonomia_vehiculo_km >= minimo_requerido,
    }


async def validar_tiempo_operacion(
    tiempo_operativo_h: float,
    db: AsyncIOMotorDatabase,
) -> dict:
    """Valida el tiempo operativo contra los límites de seguridad.

    Lee la colección `seguridad_operativa` para obtener max_horas_jornada.

    Returns:
        {
            "maximo_permitido_h": float,
            "estimado_h": float,
            "valido": bool,
        }
    """
    seguridad_doc = await db["seguridad_operativa"].find_one({})

    if seguridad_doc is not None:
        seguridad = SeguridadOperativa.model_validate(seguridad_doc)
        maximo = seguridad.operador.max_horas_jornada
    else:
        maximo = 12.0  # Valor conservador por defecto

    return {
        "maximo_permitido_h": maximo,
        "estimado_h": round(tiempo_operativo_h, 4),
        "valido": maximo >= tiempo_operativo_h,
    }
