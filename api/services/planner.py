"""Motor de planeación operativa: orquesta flota, validación y persistencia."""

from motor.motor_asyncio import AsyncIOMotorDatabase

from api.models.nivel_servicio import NivelServicio
from api.services.cost_engine import calcular_costeo
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
    4. Si viable: calcula costeo granular y supuestos.
    5. Persiste cada sección por separado ($set quirúrgico).

    Returns:
        Dict con claves 'planeacion', 'operacion', 'validaciones',
        'supuestos' y 'costeo'.

    Raises:
        ValueError con detalles si alguna validación falla.
    """
    factor_dist = nivel.parametros.factor_distancia
    buffer_tiempo = nivel.parametros.buffer_tiempo

    distancia_operativa = round(distancia_base_km * factor_dist * 2, 2)
    tiempo_operativo = round(tiempo_base_h * buffer_tiempo * 2, 4)

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

    # Mapear a esquema canónico Gran JSON
    validaciones = {
        "capacidad": {
            "requerida": val_capacidad["requerida"],
            "vehiculo": val_capacidad["capacidad_total"],
            "valido": val_capacidad["valido"],
        },
        "autonomia": {
            "distancia_total": val_autonomia["distancia_total_km"],
            "autonomia_vehiculo": val_autonomia["autonomia_vehiculo_km"],
            "valido": val_autonomia["valido"],
        },
        "tiempo_operacion": {
            "maximo_permitido": val_tiempo["maximo_permitido_h"],
            "estimado": val_tiempo["estimado_h"],
            "valido": val_tiempo["valido"],
        },
    }

    errores = (
        [
            f"Capacidad insuficiente: se requieren {val_capacidad['requerida']} pasajeros "
            f"pero la flota cubre {val_capacidad['capacidad_total']}."
        ]
        if not val_capacidad["valido"]
        else []
    ) + (
        [
            f"Autonomía insuficiente: la ruta requiere {val_autonomia['minimo_requerido_km']} km "
            f"pero el vehículo tiene {val_autonomia['autonomia_vehiculo_km']} km."
        ]
        if not val_autonomia["valido"]
        else []
    ) + (
        [
            f"Tiempo de operación excede límite: {val_tiempo['estimado_h']}h > "
            f"{val_tiempo['maximo_permitido_h']}h máximo permitido."
        ]
        if not val_tiempo["valido"]
        else []
    )

    supuestos: dict | None = None
    costeo: dict | None = None

    if not errores:
        resultado_costeo = await calcular_costeo(
            operacion=operacion,
            nivel=nivel,
            distancia_operativa_km=distancia_operativa,
            tiempo_operativo_h=tiempo_operativo,
            pasajeros=pasajeros,
            db=db,
        )
        supuestos = resultado_costeo["supuestos"]
        costeo = resultado_costeo["costeo"]

    # Operacion canónica para persistencia (incluye autonomia_total para Gran JSON)
    vehiculo = operacion["vehiculo"]
    operacion_persistir = {
        "vehiculo": {
            "tipo": vehiculo["tipo"],
            "modelo": vehiculo["modelo"],
            "capacidad_pasajeros": vehiculo["capacidad_pasajeros"],
            "rendimiento_km_l": vehiculo["rendimiento_km_l"],
            "tanque_l": vehiculo["tanque_l"],
            "autonomia_total": vehiculo["autonomia_total"],
        },
        "unidades": operacion["unidades"],
    }

    await db[_COLLECTION].update_one(
        {"token": token},
        {
            "$set": {
                "planeacion": planeacion,
                "operacion": operacion_persistir,
                "validaciones": validaciones,
                "supuestos": supuestos,
                "costeo": costeo,
            }
        },
    )

    if errores:
        raise ValueError(" | ".join(errores))

    return {
        "planeacion": planeacion,
        "operacion": operacion,
        "validaciones": validaciones,
        "supuestos": supuestos,
        "costeo": costeo,
    }

