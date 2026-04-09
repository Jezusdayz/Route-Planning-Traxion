"""Script de seeding: limpia colecciones e inserta catálogos usando modelos Pydantic."""

import asyncio
import sys
from pathlib import Path

# Añade la raíz del proyecto al path para poder importar api.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient

from api.config import settings


async def seed_data():
    client = AsyncIOMotorClient(settings.mongodb_url)
    db = client[settings.mongodb_db_name]

    collections = [
        "vehiculos",
        "costos_variables",
        "costos_fijos",
        "niveles_servicio",
        "seguridad",
        "ciudades",
        "rutas",
    ]
    for col in collections:
        await db[col].drop()

    print("Seed completado exitosamente.")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed_data())
