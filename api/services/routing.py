"""Servicio de cálculo de rutas usando OpenRouteService."""

from api.config import settings
from api.utils.http_client import get_client

_ORS_URL = "https://api.openrouteservice.org/v2/directions/driving-car"


async def calcular_ruta(
    lat_origen: float,
    lon_origen: float,
    lat_destino: float,
    lon_destino: float,
) -> dict:
    """Calcula distancia y tiempo entre dos coordenadas.

    Retorna {'distancia_km': float, 'tiempo_h': float}.
    Usa OpenRouteService; requiere ORS_API_KEY en config.
    """
    payload = {
        "coordinates": [
            [lon_origen, lat_origen],
            [lon_destino, lat_destino],
        ]
    }
    headers = {"Authorization": settings.ors_api_key}

    async with get_client() as client:
        response = await client.post(_ORS_URL, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    segment = data["routes"][0]["summary"]
    distancia_km = segment["distance"] / 1000
    tiempo_h = segment["duration"] / 3600

    return {"distancia_km": round(distancia_km, 2), "tiempo_h": round(tiempo_h, 4)}
