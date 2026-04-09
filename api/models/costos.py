from pydantic import BaseModel, Field


class CombustibleCosto(BaseModel):
    precio_litro: float


class OperadorCosto(BaseModel):
    costo_hora: float


class MantenimientoCosto(BaseModel):
    costo_km: float


class OtrosCostos(BaseModel):
    peajes_estimados_km: float
    costo_limpieza_servicio: float


class CostosOperativos(BaseModel):
    id: str = Field(..., alias="_id")
    combustible: CombustibleCosto
    operador: OperadorCosto
    mantenimiento: MantenimientoCosto
    otros: OtrosCostos
