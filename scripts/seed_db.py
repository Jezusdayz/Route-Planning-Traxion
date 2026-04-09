"""Script de seeding: limpia colecciones e inserta catálogos usando modelos Pydantic."""

import asyncio
import sys
from pathlib import Path

# Añade la raíz del proyecto al path para poder importar api.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from motor.motor_asyncio import AsyncIOMotorClient

from api.config import settings
from api.models.ciudad import Ciudad
from api.models.costos import CostosFijos, CostosOperativos
from api.models.nivel_servicio import NivelServicio
from api.models.ruta import Ruta
from api.models.seguridad import SeguridadOperativa
from api.models.vehiculo import Vehiculo

VEHICULOS_DATA = [
    {
        "_id": "scania_k400",
        "tipo": "autobus",
        "modelo": "Scania K400",
        "capacidad": {"pasajeros": 48, "peso_max_kg": 18000.0},
        "combustible": {"tipo": "diesel", "capacidad_tanque_l": 400.0, "rendimiento_km_l": 4.5},
        "operacion": {"velocidad_promedio_kmh": 80.0, "autonomia_km": 1800.0, "factor_seguridad_combustible": 0.9},
        "mantenimiento": {"intervalo_km": 15000.0, "costo_km": 0.85},
        "estado": "activo",
    },
    {
        "_id": "mercedes_travego",
        "tipo": "autobus",
        "modelo": "Mercedes-Benz Travego",
        "capacidad": {"pasajeros": 52, "peso_max_kg": 19500.0},
        "combustible": {"tipo": "diesel", "capacidad_tanque_l": 420.0, "rendimiento_km_l": 4.2},
        "operacion": {"velocidad_promedio_kmh": 85.0, "autonomia_km": 1764.0, "factor_seguridad_combustible": 0.9},
        "mantenimiento": {"intervalo_km": 15000.0, "costo_km": 0.90},
        "estado": "activo",
    },
    {
        "_id": "volvo_9700",
        "tipo": "autobus",
        "modelo": "Volvo 9700",
        "capacidad": {"pasajeros": 55, "peso_max_kg": 20000.0},
        "combustible": {"tipo": "diesel", "capacidad_tanque_l": 450.0, "rendimiento_km_l": 4.3},
        "operacion": {"velocidad_promedio_kmh": 83.0, "autonomia_km": 1935.0, "factor_seguridad_combustible": 0.9},
        "mantenimiento": {"intervalo_km": 20000.0, "costo_km": 0.88},
        "estado": "activo",
    },
    {
        "_id": "irizar_i6",
        "tipo": "autobus",
        "modelo": "Irizar i6",
        "capacidad": {"pasajeros": 50, "peso_max_kg": 18500.0},
        "combustible": {"tipo": "diesel", "capacidad_tanque_l": 390.0, "rendimiento_km_l": 4.4},
        "operacion": {"velocidad_promedio_kmh": 82.0, "autonomia_km": 1716.0, "factor_seguridad_combustible": 0.9},
        "mantenimiento": {"intervalo_km": 15000.0, "costo_km": 0.87},
        "estado": "activo",
    },
    {
        "_id": "dina_olimpico",
        "tipo": "autobus",
        "modelo": "DINA Olímpico",
        "capacidad": {"pasajeros": 44, "peso_max_kg": 16000.0},
        "combustible": {"tipo": "diesel", "capacidad_tanque_l": 350.0, "rendimiento_km_l": 4.0},
        "operacion": {"velocidad_promedio_kmh": 75.0, "autonomia_km": 1400.0, "factor_seguridad_combustible": 0.88},
        "mantenimiento": {"intervalo_km": 12000.0, "costo_km": 0.80},
        "estado": "activo",
    },
    {
        "_id": "scania_k310",
        "tipo": "autobus",
        "modelo": "Scania K310",
        "capacidad": {"pasajeros": 40, "peso_max_kg": 15000.0},
        "combustible": {"tipo": "diesel", "capacidad_tanque_l": 300.0, "rendimiento_km_l": 4.8},
        "operacion": {"velocidad_promedio_kmh": 78.0, "autonomia_km": 1440.0, "factor_seguridad_combustible": 0.9},
        "mantenimiento": {"intervalo_km": 15000.0, "costo_km": 0.78},
        "estado": "activo",
    },
    {
        "_id": "mercedes_ofc1721",
        "tipo": "autobus",
        "modelo": "Mercedes-Benz OF-C 1721",
        "capacidad": {"pasajeros": 36, "peso_max_kg": 14000.0},
        "combustible": {"tipo": "diesel", "capacidad_tanque_l": 280.0, "rendimiento_km_l": 5.0},
        "operacion": {"velocidad_promedio_kmh": 72.0, "autonomia_km": 1400.0, "factor_seguridad_combustible": 0.88},
        "mantenimiento": {"intervalo_km": 12000.0, "costo_km": 0.75},
        "estado": "activo",
    },
    {
        "_id": "volvo_b8r",
        "tipo": "autobus",
        "modelo": "Volvo B8R",
        "capacidad": {"pasajeros": 45, "peso_max_kg": 17000.0},
        "combustible": {"tipo": "diesel", "capacidad_tanque_l": 370.0, "rendimiento_km_l": 4.6},
        "operacion": {"velocidad_promedio_kmh": 80.0, "autonomia_km": 1702.0, "factor_seguridad_combustible": 0.9},
        "mantenimiento": {"intervalo_km": 18000.0, "costo_km": 0.82},
        "estado": "activo",
    },
    {
        "_id": "yutong_zk6122",
        "tipo": "autobus",
        "modelo": "Yutong ZK6122H9",
        "capacidad": {"pasajeros": 53, "peso_max_kg": 19000.0},
        "combustible": {"tipo": "diesel", "capacidad_tanque_l": 380.0, "rendimiento_km_l": 4.7},
        "operacion": {"velocidad_promedio_kmh": 78.0, "autonomia_km": 1786.0, "factor_seguridad_combustible": 0.88},
        "mantenimiento": {"intervalo_km": 10000.0, "costo_km": 0.72},
        "estado": "activo",
    },
    {
        "_id": "scania_k360",
        "tipo": "autobus",
        "modelo": "Scania K360",
        "capacidad": {"pasajeros": 46, "peso_max_kg": 17500.0},
        "combustible": {"tipo": "diesel", "capacidad_tanque_l": 360.0, "rendimiento_km_l": 4.6},
        "operacion": {"velocidad_promedio_kmh": 80.0, "autonomia_km": 1656.0, "factor_seguridad_combustible": 0.9},
        "mantenimiento": {"intervalo_km": 15000.0, "costo_km": 0.82},
        "estado": "activo",
    },
    {
        "_id": "mercedes_multiaxle",
        "tipo": "autobus",
        "modelo": "Mercedes-Benz Multi-Axle",
        "capacidad": {"pasajeros": 59, "peso_max_kg": 22000.0},
        "combustible": {"tipo": "diesel", "capacidad_tanque_l": 500.0, "rendimiento_km_l": 3.9},
        "operacion": {"velocidad_promedio_kmh": 82.0, "autonomia_km": 1950.0, "factor_seguridad_combustible": 0.88},
        "mantenimiento": {"intervalo_km": 20000.0, "costo_km": 0.95},
        "estado": "activo",
    },
    {
        "_id": "irizar_pb",
        "tipo": "autobus",
        "modelo": "Irizar PB",
        "capacidad": {"pasajeros": 57, "peso_max_kg": 21000.0},
        "combustible": {"tipo": "diesel", "capacidad_tanque_l": 480.0, "rendimiento_km_l": 4.1},
        "operacion": {"velocidad_promedio_kmh": 84.0, "autonomia_km": 1968.0, "factor_seguridad_combustible": 0.9},
        "mantenimiento": {"intervalo_km": 18000.0, "costo_km": 0.92},
        "estado": "activo",
    },
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
    },
    {
        "_id": "costos_fijos_mercedes_travego",
        "vehiculo_id": "mercedes_travego",
        "seguro": {"tipo": "amplia", "costo_anual": 92000.0},
        "impuesto_circulacion_anual": 4500.0,
        "cuotas_sindicato_anual": 12000.0,
        "total_anual": 108500.0,
    },
    {
        "_id": "costos_fijos_volvo_9700",
        "vehiculo_id": "volvo_9700",
        "seguro": {"tipo": "amplia", "costo_anual": 98000.0},
        "impuesto_circulacion_anual": 5000.0,
        "cuotas_sindicato_anual": 12000.0,
        "total_anual": 115000.0,
    },
    {
        "_id": "costos_fijos_irizar_pb",
        "vehiculo_id": "irizar_pb",
        "seguro": {"tipo": "amplia", "costo_anual": 95000.0},
        "impuesto_circulacion_anual": 4800.0,
        "cuotas_sindicato_anual": 12000.0,
        "total_anual": 111800.0,
    },
]

NIVELES_SERVICIO_DATA = [
    {
        "_id": "empresarial",
        "nombre": "Empresarial",
        "descripcion": "Servicio premium para viajes corporativos con vehículo de lujo y operador certificado",
        "parametros": {
            "factor_costo": 1.50,
            "buffer_tiempo": 0.20,
            "factor_distancia": 1.10,
        },
        "requisitos": {
            "capacidad_minima": 20,
            "aire_acondicionado": True,
            "edad_max_vehiculo_anios": 3,
        },
    },
    {
        "_id": "ejecutivo",
        "nombre": "Ejecutivo",
        "descripcion": "Servicio de alta calidad para ejecutivos y grupos reducidos de negocios",
        "parametros": {
            "factor_costo": 1.35,
            "buffer_tiempo": 0.15,
            "factor_distancia": 1.05,
        },
        "requisitos": {
            "capacidad_minima": 15,
            "aire_acondicionado": True,
            "edad_max_vehiculo_anios": 5,
        },
    },
    {
        "_id": "estandar",
        "nombre": "Estándar",
        "descripcion": "Servicio de transporte regular para grupos con equipamiento básico",
        "parametros": {
            "factor_costo": 1.15,
            "buffer_tiempo": 0.10,
            "factor_distancia": 1.00,
        },
        "requisitos": {
            "capacidad_minima": 10,
            "aire_acondicionado": True,
            "edad_max_vehiculo_anios": 8,
        },
    },
    {
        "_id": "economico",
        "nombre": "Económico",
        "descripcion": "Servicio básico de transporte grupal al menor costo operativo",
        "parametros": {
            "factor_costo": 1.00,
            "buffer_tiempo": 0.05,
            "factor_distancia": 1.00,
        },
        "requisitos": {
            "capacidad_minima": 5,
            "aire_acondicionado": False,
            "edad_max_vehiculo_anios": 12,
        },
    },
]

SEGURIDAD_DATA = [
    {
        "_id": "politica_std",
        "pasajeros": {
            "tiempo_maximo_a_bordo_horas": 8.0,
            "tiempo_recomendado_descanso_horas": 0.5,
        },
        "operador": {
            "max_horas_conduccion_continua": 4.0,
            "max_horas_jornada": 8.0,
        },
        "vehiculo": {
            "factor_autonomia_segura": 0.85,
            "margen_combustible_reserva": 0.10,
        },
        "servicio": {
            "tiempo_maximo_espera_min": 15,
            "buffer_arribo": 0.10,
        },
        "ruta": {
            "factor_distancia_operativa": 1.05,
            "factor_tiempo_operativo": 1.10,
        },
    }
]

CIUDADES_DATA = [
    {"nombre": "cdmx", "lat": 19.4326, "lon": -99.1332, "pais": "México"},
    {"nombre": "pachuca", "lat": 20.1011, "lon": -98.7591, "pais": "México"},
    {"nombre": "queretaro", "lat": 20.5888, "lon": -100.3899, "pais": "México"},
    {"nombre": "puebla", "lat": 19.0414, "lon": -98.2063, "pais": "México"},
]

RUTAS_DATA = [
    {
        "_id": "cdmx_pachuca",
        "origen": "cdmx",
        "destino": "pachuca",
        "distancia_km": 92.0,
        "tiempo_h": 1.5,
        "distancia_operativa_km": 96.6,
        "tiempo_operativo_h": 1.65,
        "ultima_actualizacion": "2026-04-09",
    },
    {
        "_id": "cdmx_queretaro",
        "origen": "cdmx",
        "destino": "queretaro",
        "distancia_km": 215.0,
        "tiempo_h": 3.0,
        "distancia_operativa_km": 225.75,
        "tiempo_operativo_h": 3.30,
        "ultima_actualizacion": "2026-04-09",
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


async def seed_seguridad(db) -> None:
    docs = [SeguridadOperativa(**d).model_dump(by_alias=True) for d in SEGURIDAD_DATA]
    await db["seguridad"].insert_many(docs)
    print(f"  seguridad: {len(docs)} documento(s) insertado(s).")


async def seed_ciudades(db) -> None:
    docs = [Ciudad(**d).model_dump(by_alias=True, exclude_none=True) for d in CIUDADES_DATA]
    await db["ciudades"].insert_many(docs)
    print(f"  ciudades: {len(docs)} documento(s) insertado(s).")


async def seed_rutas(db) -> None:
    from datetime import datetime
    docs = []
    for d in RUTAS_DATA:
        doc = Ruta(**d).model_dump(by_alias=True)
        # BSON no soporta datetime.date — convertir a datetime
        if hasattr(doc.get("ultima_actualizacion"), "year"):
            dt = doc["ultima_actualizacion"]
            doc["ultima_actualizacion"] = datetime(dt.year, dt.month, dt.day)
        docs.append(doc)
    await db["rutas"].insert_many(docs)
    print(f"  rutas: {len(docs)} documento(s) insertado(s).")


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
    await seed_seguridad(db)
    await seed_ciudades(db)
    await seed_rutas(db)

    print("Seed completado exitosamente.")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed_data())
