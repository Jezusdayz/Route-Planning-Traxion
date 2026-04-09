from pydantic import BaseModel, Field


class PasajerosSeguridad(BaseModel):
    tiempo_maximo_a_bordo_horas: float
    tiempo_recomendado_descanso_horas: float


class OperadorSeguridad(BaseModel):
    max_horas_conduccion_continua: float
    max_horas_jornada: float


class VehiculoSeguridad(BaseModel):
    factor_autonomia_segura: float
    margen_combustible_reserva: float


class ServicioSeguridad(BaseModel):
    tiempo_maximo_espera_min: int
    buffer_arribo: float


class RutaSeguridad(BaseModel):
    factor_distancia_operativa: float
    factor_tiempo_operativo: float


class SeguridadOperativa(BaseModel):
    id: str = Field(..., alias="_id")
    pasajeros: PasajerosSeguridad
    operador: OperadorSeguridad
    vehiculo: VehiculoSeguridad
    servicio: ServicioSeguridad
    ruta: RutaSeguridad
