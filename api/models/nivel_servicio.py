from pydantic import BaseModel, Field


class ParametrosServicio(BaseModel):
    factor_costo: float
    buffer_tiempo: float
    factor_distancia: float


class RequisitosServicio(BaseModel):
    capacidad_minima: int
    aire_acondicionado: bool
    edad_max_vehiculo_anios: int


class NivelServicio(BaseModel):
    id: str = Field(..., alias="_id")
    nombre: str
    descripcion: str
    parametros: ParametrosServicio
    requisitos: RequisitosServicio
