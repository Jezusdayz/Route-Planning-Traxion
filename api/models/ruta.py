from datetime import date

from pydantic import BaseModel, Field


class Ruta(BaseModel):
    id: str = Field(..., alias="_id")
    origen: str
    destino: str
    distancia_km: float
    tiempo_h: float
    distancia_operativa_km: float
    tiempo_operativo_h: float
    ultima_actualizacion: date
