"""Servicio de geocodificación con cache en MongoDB (get-or-create)."""

from motor.motor_asyncio import AsyncIOMotorDatabase

from api.utils.http_client import get_client

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_COLLECTION = "ciudades_geocoded"


async def geocode_ciudad(nombre: str, db: AsyncIOMotorDatabase) -> dict:
    """Retorna coordenadas {'lat': float, 'lon': float} para una ciudad.

    Primero consulta el cache en MongoDB; si no existe, llama a Nominatim
    y guarda el resultado antes de devolverlo.
    """
    cached = await db[_COLLECTION].find_one({"nombre": nombre})
    if cached:
        return {"lat": cached["lat"], "lon": cached["lon"]}

    async with get_client() as client:
        response = await client.get(
            _NOMINATIM_URL,
            params={"q": nombre, "format": "json", "limit": 1},
        )
        response.raise_for_status()
        data = response.json()

    if not data:
        raise ValueError(f"Ciudad no encontrada en Nominatim: {nombre!r}")

    lat = float(data[0]["lat"])
    lon = float(data[0]["lon"])

    await db[_COLLECTION].update_one(
        {"nombre": nombre},
        {"$set": {"nombre": nombre, "lat": lat, "lon": lon}},
        upsert=True,
    )

    return {"lat": lat, "lon": lon}
