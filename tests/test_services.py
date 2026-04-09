"""Tests de integración para servicios de geocoding, routing y cotización."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from api.models.costos import (
    CombustibleCosto,
    CostosOperativos,
    MantenimientoCosto,
    OperadorCosto,
    OtrosCostos,
)
from api.models.nivel_servicio import NivelServicio, ParametrosServicio, RequisitosServicio
from api.models.vehiculo import Capacidad, Combustible, Mantenimiento, Operacion, Vehiculo
from api.services.geocoding import geocode_ciudad
from api.services.quotation import cotizar_servicio
from api.services.routing import calcular_ruta


# ---------------------------------------------------------------------------
# Fixtures reutilizables
# ---------------------------------------------------------------------------

@pytest.fixture
def vehiculo():
    return Vehiculo.model_validate({
        "_id": "v001",
        "tipo": "autobus",
        "modelo": "Mercedes Sprinter",
        "capacidad": {"pasajeros": 20, "peso_max_kg": 2000},
        "combustible": {"tipo": "diesel", "capacidad_tanque_l": 70, "rendimiento_km_l": 12},
        "operacion": {"velocidad_promedio_kmh": 80, "autonomia_km": 840, "factor_seguridad_combustible": 0.1},
        "mantenimiento": {"intervalo_km": 10000, "costo_km": 0.05},
        "estado": "activo",
    })


@pytest.fixture
def costos():
    return CostosOperativos.model_validate({
        "_id": "c001",
        "combustible": {"precio_litro": 22.5},
        "operador": {"costo_hora": 120},
        "mantenimiento": {"costo_km": 0.05},
        "otros": {"peajes_estimados_km": 0.10, "costo_limpieza_servicio": 250},
    })


@pytest.fixture
def nivel():
    return NivelServicio.model_validate({
        "_id": "ns001",
        "nombre": "Premium",
        "descripcion": "Servicio de alta gama",
        "parametros": {"factor_costo": 1.3, "buffer_tiempo": 0.15, "factor_distancia": 1.1},
        "requisitos": {"capacidad_minima": 10, "aire_acondicionado": True, "edad_max_vehiculo_anios": 5},
    })


# ---------------------------------------------------------------------------
# Tests: geocoding
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_geocode_ciudad_desde_cache():
    """Debe retornar coordenadas del cache sin llamar a Nominatim."""
    db_mock = MagicMock()
    db_mock.__getitem__ = MagicMock(return_value=MagicMock(
        find_one=AsyncMock(return_value={"nombre": "Monterrey", "lat": 25.6866, "lon": -100.3161})
    ))

    resultado = await geocode_ciudad("Monterrey", db_mock)

    assert resultado == {"lat": 25.6866, "lon": -100.3161}


@pytest.mark.asyncio
async def test_geocode_ciudad_desde_nominatim():
    """Debe llamar a Nominatim cuando la ciudad no está en cache."""
    db_mock = MagicMock()
    col_mock = MagicMock(
        find_one=AsyncMock(return_value=None),
        update_one=AsyncMock(),
    )
    db_mock.__getitem__ = MagicMock(return_value=col_mock)

    nominatim_response = [{"lat": "19.4326", "lon": "-99.1332"}]

    with patch("api.services.geocoding.get_client") as mock_get_client:
        client_mock = AsyncMock()
        client_mock.__aenter__ = AsyncMock(return_value=client_mock)
        client_mock.__aexit__ = AsyncMock(return_value=False)
        resp_mock = MagicMock()
        resp_mock.raise_for_status = MagicMock()
        resp_mock.json = MagicMock(return_value=nominatim_response)
        client_mock.get = AsyncMock(return_value=resp_mock)
        mock_get_client.return_value = client_mock

        resultado = await geocode_ciudad("Ciudad de México", db_mock)

    assert resultado == {"lat": 19.4326, "lon": -99.1332}
    col_mock.update_one.assert_awaited_once()


# ---------------------------------------------------------------------------
# Tests: routing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_calcular_ruta():
    """Debe convertir la respuesta de ORS a distancia_km y tiempo_h."""
    ors_response = {
        "routes": [{"summary": {"distance": 350000, "duration": 14400}}]
    }

    with patch("api.services.routing.get_client") as mock_get_client:
        client_mock = AsyncMock()
        client_mock.__aenter__ = AsyncMock(return_value=client_mock)
        client_mock.__aexit__ = AsyncMock(return_value=False)
        resp_mock = MagicMock()
        resp_mock.raise_for_status = MagicMock()
        resp_mock.json = MagicMock(return_value=ors_response)
        client_mock.post = AsyncMock(return_value=resp_mock)
        mock_get_client.return_value = client_mock

        resultado = await calcular_ruta(19.43, -99.13, 20.97, -89.62)

    assert resultado == {"distancia_km": 350.0, "tiempo_h": 4.0}


# ---------------------------------------------------------------------------
# Tests: cotización
# ---------------------------------------------------------------------------

def test_cotizar_servicio_estructura(vehiculo, costos, nivel):
    """El resultado debe contener las claves esperadas con valores positivos."""
    resultado = cotizar_servicio(vehiculo, costos, nivel, distancia_km=300, tiempo_h=3.75)

    assert "total" in resultado
    assert "subtotal" in resultado
    assert "desglose" in resultado
    assert resultado["total"] > 0
    assert resultado["nivel_servicio"] == "Premium"
    assert resultado["vehiculo_id"] == "v001"
    for clave in ("combustible", "operador", "mantenimiento", "peajes", "limpieza"):
        assert clave in resultado["desglose"]


def test_cotizar_servicio_total_mayor_subtotal(vehiculo, costos, nivel):
    """Con factor_costo > 1 el total debe ser mayor que el subtotal."""
    resultado = cotizar_servicio(vehiculo, costos, nivel, distancia_km=300, tiempo_h=3.75)
    assert resultado["total"] > resultado["subtotal"]


def test_cotizar_servicio_distancia_cero(vehiculo, costos, nivel):
    """Con distancia 0 los costos variables deben ser 0 o solo fijos."""
    resultado = cotizar_servicio(vehiculo, costos, nivel, distancia_km=0, tiempo_h=0)
    assert resultado["desglose"]["combustible"] == 0.0
    assert resultado["desglose"]["mantenimiento"] == 0.0
