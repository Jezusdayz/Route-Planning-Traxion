"""Tests Phase 6: fleet_manager, validator, planner y endpoint cotizar con planeacion."""

import math
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.models.nivel_servicio import NivelServicio, ParametrosServicio, RequisitosServicio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def nivel():
    return NivelServicio.model_validate({
        "_id": "economico",
        "nombre": "Económico",
        "descripcion": "Servicio básico",
        "parametros": {"factor_costo": 1.0, "buffer_tiempo": 0.1, "factor_distancia": 1.0},
        "requisitos": {"capacidad_minima": 20, "aire_acondicionado": False, "edad_max_vehiculo_anios": 12},
    })


_VEHICULO_DOC = {
    "_id": "scania_k310",
    "tipo": "autobus",
    "modelo": "Scania K310",
    "capacidad": {"pasajeros": 40, "peso_max_kg": 15000},
    "combustible": {"tipo": "diesel", "capacidad_tanque_l": 350, "rendimiento_km_l": 3.2},
    "operacion": {"velocidad_promedio_kmh": 85, "autonomia_km": 1000, "factor_seguridad_combustible": 0.1},
    "mantenimiento": {"intervalo_km": 12000, "costo_km": 0.10},
    "estado": "activo",
}

_SEGURIDAD_DOC = {
    "_id": "seg_001",
    "pasajeros": {"tiempo_maximo_a_bordo_horas": 8, "tiempo_recomendado_descanso_horas": 1},
    "operador": {"max_horas_conduccion_continua": 4, "max_horas_jornada": 12},
    "vehiculo": {"factor_autonomia_segura": 0.8, "margen_combustible_reserva": 0.1},
    "servicio": {"tiempo_maximo_espera_min": 30, "buffer_arribo": 0.15},
    "ruta": {"factor_distancia_operativa": 1.1, "factor_tiempo_operativo": 1.15},
}


_COSTOS_DOC = {
    "_id": "costos_std",
    "combustible": {"precio_litro": 23.5},
    "operador": {"costo_hora": 250.0},
    "mantenimiento": {"costo_km": 2.5},
    "otros": {"peajes_estimados_km": 1.2, "costo_limpieza_servicio": 300.0},
}


def _make_db(vehiculo_doc=_VEHICULO_DOC, seguridad_doc=_SEGURIDAD_DOC):
    db = MagicMock()

    def dispatch(name):
        col = MagicMock()
        col.update_one = AsyncMock()
        if name == "vehiculos":
            col.find_one = AsyncMock(return_value=vehiculo_doc)
        elif name == "seguridad_operativa":
            col.find_one = AsyncMock(return_value=seguridad_doc)
        elif name == "costos_variables":
            col.find_one = AsyncMock(return_value=_COSTOS_DOC)
        else:
            col.find_one = AsyncMock(return_value=None)
        return col

    db.__getitem__ = MagicMock(side_effect=dispatch)
    return db


# ---------------------------------------------------------------------------
# Tests: validator (funciones puras)
# ---------------------------------------------------------------------------

def test_validar_capacidad_suficiente():
    from api.services.validator import validar_capacidad
    resultado = validar_capacidad(pasajeros=35, capacidad_vehiculo=40, unidades=1)
    assert resultado["valido"] is True
    assert resultado["capacidad_total"] == 40


def test_validar_capacidad_insuficiente():
    from api.services.validator import validar_capacidad
    resultado = validar_capacidad(pasajeros=85, capacidad_vehiculo=40, unidades=2)
    assert resultado["valido"] is False
    assert resultado["capacidad_total"] == 80


def test_validar_autonomia_suficiente():
    from api.services.validator import validar_autonomia
    resultado = validar_autonomia(distancia_operativa_km=500, autonomia_vehiculo_km=1000)
    assert resultado["valido"] is True
    assert resultado["minimo_requerido_km"] == 600.0


def test_validar_autonomia_insuficiente():
    from api.services.validator import validar_autonomia
    resultado = validar_autonomia(distancia_operativa_km=900, autonomia_vehiculo_km=1000)
    assert resultado["valido"] is False
    assert resultado["minimo_requerido_km"] == 1080.0


@pytest.mark.asyncio
async def test_validar_tiempo_operacion_dentro_limite():
    from api.services.validator import validar_tiempo_operacion
    db = _make_db()
    resultado = await validar_tiempo_operacion(tiempo_operativo_h=10.0, db=db)
    assert resultado["valido"] is True
    assert resultado["maximo_permitido_h"] == 12.0


@pytest.mark.asyncio
async def test_validar_tiempo_operacion_excede_limite():
    from api.services.validator import validar_tiempo_operacion
    db = _make_db()
    resultado = await validar_tiempo_operacion(tiempo_operativo_h=14.0, db=db)
    assert resultado["valido"] is False


# ---------------------------------------------------------------------------
# Tests: fleet_manager
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_seleccionar_flota_retorna_vehiculo_y_unidades(nivel):
    from api.services.fleet_manager import seleccionar_flota
    db = _make_db()
    resultado = await seleccionar_flota(pasajeros=35, nivel=nivel, db=db)

    assert "vehiculo" in resultado
    assert "unidades" in resultado
    assert resultado["vehiculo"]["modelo"] == "Scania K310"
    assert resultado["unidades"] == math.ceil(35 / 40)  # 1


@pytest.mark.asyncio
async def test_seleccionar_flota_calcula_unidades_multiples(nivel):
    from api.services.fleet_manager import seleccionar_flota
    db = _make_db()
    resultado = await seleccionar_flota(pasajeros=90, nivel=nivel, db=db)
    assert resultado["unidades"] == math.ceil(90 / 40)  # 3


@pytest.mark.asyncio
async def test_seleccionar_flota_sin_vehiculos_disponibles(nivel):
    from api.services.fleet_manager import seleccionar_flota
    db = _make_db(vehiculo_doc=None)
    with pytest.raises(ValueError, match="No hay vehículos"):
        await seleccionar_flota(pasajeros=35, nivel=nivel, db=db)


@pytest.mark.asyncio
async def test_seleccionar_flota_autonomia_total_calculada(nivel):
    """autonomia_total = tanque_l * rendimiento * (1 - factor_seg)."""
    from api.services.fleet_manager import seleccionar_flota
    db = _make_db()
    resultado = await seleccionar_flota(pasajeros=35, nivel=nivel, db=db)
    # 350 * 3.2 * (1 - 0.1) = 1008
    assert resultado["vehiculo"]["autonomia_total"] == 350 * 3.2 * 0.9


# ---------------------------------------------------------------------------
# Tests: planner
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calcular_mision_exitosa(nivel):
    from api.services.planner import calcular_mision
    db = _make_db()

    resultado = await calcular_mision(
        token="test-token",
        pasajeros=35,
        nivel=nivel,
        distancia_base_km=200,
        tiempo_base_h=3.0,
        db=db,
    )

    assert "planeacion" in resultado
    assert "operacion" in resultado
    assert "validaciones" in resultado

    p = resultado["planeacion"]
    assert p["tipo_servicio"] == "point_to_point"
    # factor_distancia=1.0: 200 * 1.0 * 2 = 400
    assert p["distancia_operativa_km"] == 400.0
    # buffer_tiempo=0.1: 3.0 * 1.1 * 2 = 6.6
    assert p["tiempo_operativo_h"] == pytest.approx(6.6, rel=1e-3)

    assert all(v["valido"] for v in resultado["validaciones"].values())


@pytest.mark.asyncio
async def test_calcular_mision_falla_autonomia(nivel):
    """Si la ruta excede la autonomía, calcular_mision debe lanzar ValueError."""
    from api.services.planner import calcular_mision
    db = _make_db()

    with pytest.raises(ValueError, match="Autonomía"):
        await calcular_mision(
            token="test-token",
            pasajeros=35,
            nivel=nivel,
            distancia_base_km=700,  # 700*1.0*2=1400km > 1008km autonomia * 1.2 = 1209.6
            tiempo_base_h=8.0,
            db=db,
        )
