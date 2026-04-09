"""Tests Phase 7: cost_engine — costeo granular, supuestos y KPIs."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from api.models.nivel_servicio import NivelServicio


# ---------------------------------------------------------------------------
# Fixtures compartidos
# ---------------------------------------------------------------------------

@pytest.fixture
def nivel_economico():
    return NivelServicio.model_validate({
        "_id": "economico",
        "nombre": "Económico",
        "descripcion": "Básico",
        "parametros": {"factor_costo": 1.0, "buffer_tiempo": 0.1, "factor_distancia": 1.0},
        "requisitos": {"capacidad_minima": 20, "aire_acondicionado": False, "edad_max_vehiculo_anios": 12},
    })


@pytest.fixture
def nivel_empresarial():
    return NivelServicio.model_validate({
        "_id": "empresarial",
        "nombre": "Empresarial",
        "descripcion": "Premium",
        "parametros": {"factor_costo": 1.5, "buffer_tiempo": 0.2, "factor_distancia": 1.15},
        "requisitos": {"capacidad_minima": 40, "aire_acondicionado": True, "edad_max_vehiculo_anios": 5},
    })


_COSTOS_DOC = {
    "_id": "costos_std",
    "combustible": {"precio_litro": 23.5},
    "operador": {"costo_hora": 250.0},
    "mantenimiento": {"costo_km": 2.5},
    "otros": {"peajes_estimados_km": 1.2, "costo_limpieza_servicio": 300.0},
}

_OPERACION_1_UNIDAD = {
    "vehiculo": {
        "id": "scania_k310",
        "tipo": "autobus",
        "modelo": "Scania K310",
        "capacidad_pasajeros": 40,
        "rendimiento_km_l": 3.2,
        "tanque_l": 350.0,
        "costo_mantenimiento_km": 0.10,
        "autonomia_total": 1008.0,
    },
    "unidades": 1,
}

_OPERACION_2_UNIDADES = {**_OPERACION_1_UNIDAD, "unidades": 2}


def _make_db(costos_doc=_COSTOS_DOC):
    db = MagicMock()
    col = MagicMock()
    col.find_one = AsyncMock(return_value=costos_doc)
    db.__getitem__ = MagicMock(return_value=col)
    return db


# ---------------------------------------------------------------------------
# Tests: calcular_costeo — estructura básica
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_costeo_retorna_supuestos_y_costeo(nivel_economico):
    from api.services.cost_engine import calcular_costeo
    db = _make_db()
    resultado = await calcular_costeo(
        operacion=_OPERACION_1_UNIDAD,
        nivel=nivel_economico,
        distancia_operativa_km=400.0,
        tiempo_operativo_h=6.0,
        pasajeros=35,
        db=db,
    )
    assert "supuestos" in resultado
    assert "costeo" in resultado


@pytest.mark.asyncio
async def test_costeo_sin_costos_lanza_error(nivel_economico):
    from api.services.cost_engine import calcular_costeo
    db = _make_db(costos_doc=None)
    with pytest.raises(ValueError, match="costos operativos"):
        await calcular_costeo(
            operacion=_OPERACION_1_UNIDAD,
            nivel=nivel_economico,
            distancia_operativa_km=400.0,
            tiempo_operativo_h=6.0,
            pasajeros=35,
            db=db,
        )


# ---------------------------------------------------------------------------
# Tests: cálculos de combustible
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_consumo_combustible_calculo_correcto(nivel_economico):
    """consumo = (distancia / rendimiento) × unidades."""
    from api.services.cost_engine import calcular_costeo
    db = _make_db()
    # 400 / 3.2 * 1 = 125.0 litros
    resultado = await calcular_costeo(
        operacion=_OPERACION_1_UNIDAD,
        nivel=nivel_economico,
        distancia_operativa_km=400.0,
        tiempo_operativo_h=6.0,
        pasajeros=35,
        db=db,
    )
    assert resultado["costeo"]["consumo_combustible_l"] == 125.0
    # 125 * 23.5 = 2937.5
    assert resultado["costeo"]["costo_combustible"] == 2937.5


@pytest.mark.asyncio
async def test_consumo_combustible_multiples_unidades(nivel_economico):
    """Con 2 unidades el consumo se dobla."""
    from api.services.cost_engine import calcular_costeo
    db = _make_db()
    resultado = await calcular_costeo(
        operacion=_OPERACION_2_UNIDADES,
        nivel=nivel_economico,
        distancia_operativa_km=400.0,
        tiempo_operativo_h=6.0,
        pasajeros=70,
        db=db,
    )
    assert resultado["costeo"]["consumo_combustible_l"] == 250.0
    assert resultado["costeo"]["costo_combustible"] == 5875.0


# ---------------------------------------------------------------------------
# Tests: costo operador y mantenimiento
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_costo_operador_por_unidad(nivel_economico):
    """costo_operador = tiempo_h * costo_hora * unidades."""
    from api.services.cost_engine import calcular_costeo
    db = _make_db()
    # 6.0 * 250.0 * 1 = 1500.0
    resultado = await calcular_costeo(
        operacion=_OPERACION_1_UNIDAD,
        nivel=nivel_economico,
        distancia_operativa_km=400.0,
        tiempo_operativo_h=6.0,
        pasajeros=35,
        db=db,
    )
    assert resultado["costeo"]["costo_operador"] == 1500.0


@pytest.mark.asyncio
async def test_costo_mantenimiento_usa_tasa_vehiculo(nivel_economico):
    """Usa costo_mantenimiento_km del vehículo, no la tasa global."""
    from api.services.cost_engine import calcular_costeo
    db = _make_db()
    # 400 * 0.10 * 1 = 40.0 (tasa vehiculo=0.10 vs global=2.5)
    resultado = await calcular_costeo(
        operacion=_OPERACION_1_UNIDAD,
        nivel=nivel_economico,
        distancia_operativa_km=400.0,
        tiempo_operativo_h=6.0,
        pasajeros=35,
        db=db,
    )
    assert resultado["costeo"]["costo_mantenimiento"] == 40.0


# ---------------------------------------------------------------------------
# Tests: KPIs y factor de servicio
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_factor_servicio_aplicado_en_total(nivel_empresarial):
    """costo_total = subtotal * factor_costo del nivel."""
    from api.services.cost_engine import calcular_costeo
    db = _make_db()
    resultado = await calcular_costeo(
        operacion=_OPERACION_1_UNIDAD,
        nivel=nivel_empresarial,
        distancia_operativa_km=400.0,
        tiempo_operativo_h=6.0,
        pasajeros=40,
        db=db,
    )
    c = resultado["costeo"]
    expected_total = round(c["subtotal"] * 1.5, 2)
    assert c["costo_total"] == expected_total
    assert c["factor_servicio"] == 1.5


@pytest.mark.asyncio
async def test_kpi_costo_por_pasajero(nivel_economico):
    """costo_por_pasajero = costo_total / pasajeros."""
    from api.services.cost_engine import calcular_costeo
    db = _make_db()
    resultado = await calcular_costeo(
        operacion=_OPERACION_1_UNIDAD,
        nivel=nivel_economico,
        distancia_operativa_km=400.0,
        tiempo_operativo_h=6.0,
        pasajeros=35,
        db=db,
    )
    c = resultado["costeo"]
    expected = round(c["costo_total"] / 35, 2)
    assert c["costo_por_pasajero"] == expected


@pytest.mark.asyncio
async def test_kpi_costo_por_km(nivel_economico):
    """costo_por_km = costo_total / distancia_operativa."""
    from api.services.cost_engine import calcular_costeo
    db = _make_db()
    resultado = await calcular_costeo(
        operacion=_OPERACION_1_UNIDAD,
        nivel=nivel_economico,
        distancia_operativa_km=400.0,
        tiempo_operativo_h=6.0,
        pasajeros=35,
        db=db,
    )
    c = resultado["costeo"]
    expected = round(c["costo_total"] / 400.0, 2)
    assert c["costo_por_km"] == expected


# ---------------------------------------------------------------------------
# Tests: snapshot de supuestos
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_supuestos_captura_precio_combustible(nivel_economico):
    from api.services.cost_engine import calcular_costeo
    db = _make_db()
    resultado = await calcular_costeo(
        operacion=_OPERACION_1_UNIDAD,
        nivel=nivel_economico,
        distancia_operativa_km=400.0,
        tiempo_operativo_h=6.0,
        pasajeros=35,
        db=db,
    )
    s = resultado["supuestos"]
    assert s["precio_combustible"] == 23.5
    assert s["factor_servicio"] == 1.0
    assert "resumen_flota" in s
    assert "Scania K310" in s["resumen_flota"]
    assert s["autonomia_segura"] == 0.20
