"""Motor de costeo granular: calcula costos por tipo de unidad y consolida supuestos."""

import math
from decimal import ROUND_HALF_UP, Decimal

from motor.motor_asyncio import AsyncIOMotorDatabase

from api.models.nivel_servicio import NivelServicio


def _r(value: float, decimals: int = 2) -> float:
    """Redondea usando ROUND_HALF_UP para precisión financiera."""
    d = Decimal(str(value)).quantize(
        Decimal("0." + "0" * decimals), rounding=ROUND_HALF_UP
    )
    return float(d)


async def calcular_costeo(
    operacion: dict,
    nivel: NivelServicio,
    distancia_operativa_km: float,
    tiempo_operativo_h: float,
    pasajeros: int,
    db: AsyncIOMotorDatabase,
) -> dict:
    """Calcula el costeo granular de la misión y construye el snapshot de supuestos.

    Args:
        operacion: Dict retornado por ``seleccionar_flota`` con claves
            ``vehiculo`` y ``unidades``.
        nivel: Nivel de servicio con ``parametros.factor_costo``.
        distancia_operativa_km: Distancia ya procesada (round-trip con factor).
        tiempo_operativo_h: Tiempo ya procesado (round-trip con buffer).
        pasajeros: Cantidad total de pasajeros del servicio.
        db: Conexión a MongoDB.

    Returns:
        Dict con claves ``supuestos`` y ``costeo``.

    Raises:
        ValueError si no se encuentran costos variables en la base de datos.
    """
    vehiculo = operacion["vehiculo"]
    unidades: int = operacion["unidades"]

    costos_doc = await db["costos_variables"].find_one({})
    if costos_doc is None:
        raise ValueError("No se encontraron costos operativos en la base de datos.")

    precio_combustible: float = costos_doc["combustible"]["precio_litro"]
    costo_hora_operador: float = costos_doc["operador"]["costo_hora"]
    costo_km_global: float = costos_doc["mantenimiento"]["costo_km"]
    peajes_km: float = costos_doc["otros"]["peajes_estimados_km"]
    costo_limpieza_unitario: float = costos_doc["otros"]["costo_limpieza_servicio"]

    rendimiento: float = vehiculo["rendimiento_km_l"]
    costo_mant_km: float = vehiculo.get("costo_mantenimiento_km", costo_km_global)

    consumo_por_unidad = distancia_operativa_km / rendimiento
    consumo_total_l = _r(consumo_por_unidad * unidades)
    costo_combustible = _r(consumo_total_l * precio_combustible)

    costo_operador = _r(tiempo_operativo_h * costo_hora_operador * unidades)

    costo_mantenimiento = _r(distancia_operativa_km * costo_mant_km * unidades)

    costo_peajes = _r(distancia_operativa_km * peajes_km)
    costo_limpieza = _r(costo_limpieza_unitario * unidades)
    otros_costos_fijos = _r(costo_peajes + costo_limpieza)

    subtotal_operativo = _r(
        costo_combustible + costo_operador + costo_mantenimiento + otros_costos_fijos
    )

    factor_servicio: float = nivel.parametros.factor_costo
    costo_total = _r(subtotal_operativo * factor_servicio)

    costo_por_pasajero = _r(costo_total / pasajeros) if pasajeros > 0 else 0.0
    costo_por_km = _r(costo_total / distancia_operativa_km) if distancia_operativa_km > 0 else 0.0

    resumen_flota = (
        f"{unidades}x {vehiculo['modelo']} ({rendimiento} km/l)"
    )

    supuestos = {
        "precio_combustible": precio_combustible,
        "resumen_flota": resumen_flota,
        "costo_mantenimiento_promedio_km": costo_mant_km,
        "factor_distancia_aplicado": nivel.parametros.factor_distancia,
        "buffer_tiempo_aplicado": nivel.parametros.buffer_tiempo,
        "factor_servicio": factor_servicio,
        "autonomia_segura_reserva": 0.20,
    }

    costeo = {
        "consumo_combustible_total_l": consumo_total_l,
        "costo_combustible": costo_combustible,
        "costo_operador": costo_operador,
        "costo_mantenimiento": costo_mantenimiento,
        "otros_costos_fijos": otros_costos_fijos,
        "subtotal_operativo": subtotal_operativo,
        "factor_servicio_multiplicador": factor_servicio,
        "costo_total_cotizacion": costo_total,
        "costo_por_pasajero": costo_por_pasajero,
        "costo_por_km": costo_por_km,
    }

    return {"supuestos": supuestos, "costeo": costeo}
