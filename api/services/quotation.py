"""Motor de cotización: combina vehículo, costos, nivel de servicio y ruta."""

from api.models.costos import CostosOperativos
from api.models.nivel_servicio import NivelServicio
from api.models.vehiculo import Vehiculo


def cotizar_servicio(
    vehiculo: Vehiculo,
    costos: CostosOperativos,
    nivel: NivelServicio,
    distancia_km: float,
    tiempo_h: float,
) -> dict:
    """Calcula la cotización de un servicio de transporte.

    Retorna un dict con el desglose de costos y el total.
    """
    dist_op = distancia_km * nivel.parametros.factor_distancia
    tiempo_op = tiempo_h * (1 + nivel.parametros.buffer_tiempo)

    litros = dist_op / vehiculo.combustible.rendimiento_km_l
    costo_combustible = litros * costos.combustible.precio_litro

    costo_operador = tiempo_op * costos.operador.costo_hora

    costo_mantenimiento = dist_op * costos.mantenimiento.costo_km

    costo_peajes = dist_op * costos.otros.peajes_estimados_km
    costo_limpieza = costos.otros.costo_limpieza_servicio

    subtotal = (
        costo_combustible
        + costo_operador
        + costo_mantenimiento
        + costo_peajes
        + costo_limpieza
    )

    total = subtotal * nivel.parametros.factor_costo

    return {
        "vehiculo_id": vehiculo.id,
        "nivel_servicio": nivel.nombre,
        "distancia_operativa_km": round(dist_op, 2),
        "tiempo_operativo_h": round(tiempo_op, 4),
        "desglose": {
            "combustible": round(costo_combustible, 2),
            "operador": round(costo_operador, 2),
            "mantenimiento": round(costo_mantenimiento, 2),
            "peajes": round(costo_peajes, 2),
            "limpieza": round(costo_limpieza, 2),
        },
        "subtotal": round(subtotal, 2),
        "total": round(total, 2),
    }
