"""Selección de flota: vehículo óptimo + número de unidades requeridas."""

import math

from motor.motor_asyncio import AsyncIOMotorDatabase

from api.models.nivel_servicio import NivelServicio
from api.models.vehiculo import Vehiculo


async def seleccionar_flota(
    pasajeros: int,
    nivel: NivelServicio,
    db: AsyncIOMotorDatabase,
) -> dict:
    """Selecciona el vehículo más adecuado y calcula las unidades necesarias.

    Filtra vehículos activos cuya capacidad >= capacidad_minima del nivel,
    ordenando por capacidad ascendente para minimizar unidades.

    Returns:
        Dict con 'vehiculo' (datos del vehículo) y 'unidades' (int).

    Raises:
        ValueError si no hay vehículos disponibles para el nivel.
    """
    capacidad_minima = nivel.requisitos.capacidad_minima

    vehiculo_doc = await db["vehiculos"].find_one(
        {
            "estado": "activo",
            "capacidad.pasajeros": {"$gte": capacidad_minima},
        },
        sort=[("capacidad.pasajeros", 1)],
    )

    if vehiculo_doc is None:
        raise ValueError(
            f"No hay vehículos disponibles con capacidad mínima {capacidad_minima} "
            f"para el nivel {nivel.nombre!r}."
        )

    vehiculo = Vehiculo.model_validate(vehiculo_doc)
    unidades = math.ceil(pasajeros / vehiculo.capacidad.pasajeros)

    return {
        "vehiculo": {
            "id": vehiculo.id,
            "tipo": vehiculo.tipo,
            "modelo": vehiculo.modelo,
            "capacidad_pasajeros": vehiculo.capacidad.pasajeros,
            "rendimiento_km_l": vehiculo.combustible.rendimiento_km_l,
            "tanque_l": vehiculo.combustible.capacidad_tanque_l,
            "costo_mantenimiento_km": vehiculo.mantenimiento.costo_km,
            "autonomia_total": round(
                vehiculo.combustible.capacidad_tanque_l
                * vehiculo.combustible.rendimiento_km_l
                * (1 - vehiculo.operacion.factor_seguridad_combustible),
                2,
            ),
        },
        "unidades": unidades,
    }
