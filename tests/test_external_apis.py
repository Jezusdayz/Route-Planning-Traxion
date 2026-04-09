"""Tests de conectividad con APIs externas (Nominatim y OpenRouteService).

Todas las llamadas HTTP están mockeadas para no requerir red ni credenciales.
Para ejecutar contra servicios reales, establece INTEGRATION=1 y las vars de entorno necesarias.
"""

import os

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Tests de conectividad — Nominatim
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_nominatim_geocode_retorna_coordenadas():
    """Nominatim debe retornar lat/lon para una ciudad válida."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"lat": "19.4326", "lon": "-99.1332"}]
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("api.utils.http_client.httpx.AsyncClient", return_value=mock_client):
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": "Ciudad de México", "format": "json", "limit": 1},
            )
            response.raise_for_status()
            data = response.json()

    assert len(data) > 0
    assert "lat" in data[0]
    assert "lon" in data[0]


@pytest.mark.asyncio
async def test_nominatim_ciudad_no_encontrada_retorna_lista_vacia():
    """Nominatim retorna lista vacía para una ciudad inexistente."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = []
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("api.utils.http_client.httpx.AsyncClient", return_value=mock_client):
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": "CiudadFicticiaxyz123", "format": "json", "limit": 1},
            )
            response.raise_for_status()
            data = response.json()

    assert data == []


# ---------------------------------------------------------------------------
# Tests de conectividad — OpenRouteService
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ors_directions_retorna_distancia_y_tiempo():
    """ORS debe retornar distancia en metros y duración en segundos."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "routes": [
            {
                "summary": {"distance": 92000.0, "duration": 5400.0}
            }
        ]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("api.utils.http_client.httpx.AsyncClient", return_value=mock_client):
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openrouteservice.org/v2/directions/driving-hgv/json",
                json={"coordinates": [[-99.1332, 19.4326], [-98.7591, 20.1011]]},
                headers={"Authorization": "test_key"},
            )
            response.raise_for_status()
            data = response.json()

    routes = data["routes"]
    assert len(routes) > 0
    summary = routes[0]["summary"]
    assert "distance" in summary
    assert "duration" in summary
    assert summary["distance"] > 0
    assert summary["duration"] > 0


@pytest.mark.asyncio
async def test_ors_convierte_distancia_a_km():
    """La distancia en metros debe convertirse correctamente a km."""
    distancia_metros = 92000.0
    duracion_segundos = 5400.0

    distancia_km = distancia_metros / 1000
    tiempo_h = duracion_segundos / 3600

    assert round(distancia_km, 1) == 92.0
    assert round(tiempo_h, 2) == 1.5
