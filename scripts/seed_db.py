"""Script de seeding: limpia colecciones e inserta catálogos usando modelos Pydantic."""

import asyncio
import sys
from pathlib import Path

# Añade la raíz del proyecto al path para poder importar api.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient

from api.config import settings
from api.models.costos import CostosFijos, CostosOperativos
from api.models.nivel_servicio import NivelServicio
from api.models.vehiculo import Vehiculo

VEHICULOS_DATA = [
    {
        "_id": "scania_k400",
        "tipo": "autobus",
        "modelo": "Scania K400",
        "capacidad": {"pasajeros": 48, "peso_max_kg": 18000.0},
        "combustible": {
            "tipo": "diesel",
            "capacidad_tanque_l": 400.0,
            "rendimiento_km_l": 4.5,
        },
        "operacion": {
            "velocidad_promedio_kmh": 80.0,
            "autonomia_km": 1800.0,
            "factor_seguridad_combustible": 0.9,
        },
        "mantenimiento": {"intervalo_km": 15000.0, "costo_km": 0.85},
        "estado": "activo",
    }
]

COSTOS_VARIABLES_DATA = [
    {
        "_id": "costos_variables_std",
        "combustible": {"precio_litro": 23.5},
        "operador": {"costo_hora": 120.0},
        "mantenimiento": {"costo_km": 0.85},
        "otros": {"peajes_estimados_km": 0.30, "costo_limpieza_servicio": 250.0},
    }
]

COSTOS_FIJOS_DATA = [
    {
        "_id": "costos_fijos_scania_k400",
        "vehiculo_id": "scania_k400",
        "seguro": {"tipo": "amplia", "costo_anual": 85000.0},
        "impuesto_circulacion_anual": 4200.0,
        "cuotas_sindicato_anual": 12000.0,
        "total_anual": 101200.0,
    }
]

NIVELES_SERVICIO_DATA = [
    {
        "_id": "empresarial",
        "nombre": "Empresarial",
        "descripcion": "Servicio de alta calidad para viajes corporativos",
        "parametros": {
            "factor_costo": 1.35,
            "buffer_tiempo": 0.15,
            "factor_distancia": 1.05,
        },
        "requisitos": {
            "capacidad_minima": 20,
            "aire_acondicionado": True,
            "edad_max_vehiculo_anios": 5,
        },
    },
    {
        "_id": "estandar",
        "nombre": "Estándar",
        "descripcion": "Servicio de transporte regular para grupos",
        "parametros": {
            "factor_costo": 1.10,
            "buffer_tiempo": 0.10,
            "factor_distancia": 1.00,
        },
        "requisitos": {
            "capacidad_minima": 10,
            "aire_acondicionado": False,
            "edad_max_vehiculo_anios": 10,
        },
    },
]


async def seed_vehiculos(db) -> None:
    docs = [Vehiculo(**d).model_dump(by_alias=True) for d in VEHICULOS_DATA]
    await db["vehiculos"].insert_many(docs)
    print(f"  vehiculos: {len(docs)} documento(s) insertado(s).")


async def seed_costos_variables(db) -> None:
    docs = [CostosOperativos(**d).model_dump(by_alias=True) for d in COSTOS_VARIABLES_DATA]
    await db["costos_variables"].insert_many(docs)
    print(f"  costos_variables: {len(docs)} documento(s) insertado(s).")


async def seed_costos_fijos(db) -> None:
    docs = [CostosFijos(**d).model_dump(by_alias=True) for d in COSTOS_FIJOS_DATA]
    await db["costos_fijos"].insert_many(docs)
    print(f"  costos_fijos: {len(docs)} documento(s) insertado(s).")


async def seed_niveles_servicio(db) -> None:
    docs = [NivelServicio(**d).model_dump(by_alias=True) for d in NIVELES_SERVICIO_DATA]
    await db["niveles_servicio"].insert_many(docs)
    print(f"  niveles_servicio: {len(docs)} documento(s) insertado(s).")


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

    await seed_vehiculos(db)
    await seed_costos_variables(db)
    await seed_costos_fijos(db)
    await seed_niveles_servicio(db)

    print("Seed completado exitosamente.")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed_data())
