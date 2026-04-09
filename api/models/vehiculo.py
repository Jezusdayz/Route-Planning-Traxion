from pydantic import BaseModel, Field


class Capacidad(BaseModel):
    pasajeros: int
    peso_max_kg: float


class Combustible(BaseModel):
    tipo: str
    capacidad_tanque_l: float
    rendimiento_km_l: float


class Operacion(BaseModel):
    velocidad_promedio_kmh: float
    autonomia_km: float
    factor_seguridad_combustible: float


class Mantenimiento(BaseModel):
    intervalo_km: float
    costo_km: float


class Vehiculo(BaseModel):
    id: str = Field(..., alias="_id")
    tipo: str
    modelo: str
    capacidad: Capacidad
    combustible: Combustible
    operacion: Operacion
    mantenimiento: Mantenimiento
    estado: str
