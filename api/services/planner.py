"""Motor de planeación operativa: orquesta flota, validación y persistencia."""

from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase

from api.models.nivel_servicio import NivelServicio
from api.services.fleet_manager import seleccionar_flota
from api.services.validator import (
    validar_autonomia,
    validar_capacidad,
    validar_tiempo_operacion,
)

_COLLECTION = "sesiones_viaje"


async def calcular_mision(
    token: str,
    pasajeros: int,
    nivel: NivelServicio,
    distancia_base_km: float,
    tiempo_base_h: float,
    db: AsyncIOMotorDatabase,
) -> dict:
    """Calcula la planeación operativa completa (ida y vuelta).

    Pipeline:
    1. Proyecta distancia/tiempo operativo (× factor × 2 para round-trip).
    2. Selecciona la flota óptima.
    3. Ejecuta las tres validaciones de viabilidad.
    4. Persiste el resultado en la sesión (acumulativo).

    Returns:
        Dict con claves 'planeacion', 'operacion', 'validaciones'.

    Raises:
        ValueError con detalles si alguna validación falla.
    """
    factor_dist = nivel.parametros.factor_distancia
    buffer_tiempo = nivel.parametros.buffer_tiempo

    distancia_operativa = round(distancia_base_km * factor_dist * 2, 2)
    tiempo_operativo = round(tiempo_base_h * (1 + buffer_tiempo) * 2, 4)

    planeacion = {
        "tipo_servicio": "point_to_point",
        "distancia_base_km": distancia_base_km,
        "factor_distancia": factor_dist,
        "distancia_operativa_km": distancia_operativa,
        "tiempo_estimado_h": tiempo_base_h,
        "buffer_tiempo": buffer_tiempo,
        "tiempo_operativo_h": tiempo_operativo,
    }

    operacion = await seleccionar_flota(pasajeros, nivel, db)

    autonomia = operacion["vehiculo"]["autonomia_total"]
    capacidad_vehiculo = operacion["vehiculo"]["capacidad_pasajeros"]
    unidades = operacion["unidades"]

    val_capacidad = validar_capacidad(pasajeros, capacidad_vehiculo, unidades)
    val_autonomia = validar_autonomia(distancia_operativa, autonomia)
    val_tiempo = await validar_tiempo_operacion(tiempo_operativo, db)

    validaciones = {
        "capacidad": val_capacidad,
        "autonomia": val_autonomia,
        "tiempo_operacion": val_tiempo,
    }

    resultado = {
        "planeacion": planeacion,
        "operacion": operacion,
        "validaciones": validaciones,
    }

    errores = [
        f"Capacidad insuficiente: se requieren {val_capacidad['requerida']} pasajeros "
        f"pero la flota cubre {val_capacidad['capacidad_total']}."
        for _ in [None] if not val_capacidad["valido"]
    ] + [
        f"Autonomía insuficiente: la ruta requiere {val_autonomia['minimo_requerido_km']} km "
        f"pero el vehículo tiene {val_autonomia['autonomia_vehiculo_km']} km."
        for _ in [None] if not val_autonomia["valido"]
    ] + [
        f"Tiempo de operación excede límite: {val_tiempo['estimado_h']}h > "
        f"{val_tiempo['maximo_permitido_h']}h máximo permitido."
        for _ in [None] if not val_tiempo["valido"]
    ]

    await db[_COLLECTION].update_one(
        {"token": token},
        {
            "$set": {
                "planeacion": planeacion,
                "operacion": operacion,
                "validaciones": validaciones,
                "viaje_viable": len(errores) == 0,
                "errores_viabilidad": errores,
                "fase_actual": "planeacion",
                "actualizado_en": datetime.now(timezone.utc),
            }
        },
    )

    if errores:
        raise ValueError(" | ".join(errores))

    return resultado
