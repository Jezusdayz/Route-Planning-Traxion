from typing import Optional

from pydantic import BaseModel, Field


class Ciudad(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    nombre: str
    lat: float
    lon: float
    pais: str
