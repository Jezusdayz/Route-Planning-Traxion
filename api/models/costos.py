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


class SeguroCosto(BaseModel):
    tipo: str
    costo_anual: float


class CostosFijos(BaseModel):
    id: str = Field(..., alias="_id")
    vehiculo_id: str
    seguro: SeguroCosto
    impuesto_circulacion_anual: float
    cuotas_sindicato_anual: float
    total_anual: float
