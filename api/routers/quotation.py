"""Router HTTP: validación de viaje y cotización con generación de SessionToken."""

from datetime import date, time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.database import get_db
from api.models.costos import CostosOperativos
from api.models.nivel_servicio import NivelServicio
from api.models.vehiculo import Vehiculo
from api.services.auth import generate_token
from api.services.geocoding import geocode_ciudad
from api.services.quotation import cotizar_servicio
from api.services.routing import calcular_ruta
from api.services.session_manager import create_session

router = APIRouter(prefix="/cotizar", tags=["cotización"])


class InicioViajeRequest(BaseModel):
    origen: str
    destino: str
    pasajeros: int = Field(..., gt=0)
    nivel_servicio: Literal["economico", "empresarial", "ejecutivo", "estandar"]
    fecha_servicio: date
    hora_salida: time


class ResumenCotizacion(BaseModel):
    origen: str
    destino: str
    distancia_km: float
    tiempo_h: float
    nivel_servicio: str
    vehiculo_id: str
    desglose: dict
    subtotal: float
    total: float


class InicioViajeResponse(BaseModel):
    status: str
    token: str
    resumen_cotizacion: ResumenCotizacion
    ws_url: str


def _validation_error(detail: str):
    raise HTTPException(
        status_code=422,
        detail={"error": "VALIDATION_FAILED", "detail": detail, "codigo_error": 422},
    )


@router.post("/iniciar", response_model=InicioViajeResponse)
async def iniciar_viaje(request: InicioViajeRequest, db=Depends(get_db)):
    # 1. Geocodificación
    try:
        coords_origen = await geocode_ciudad(request.origen, db)
    except ValueError:
        _validation_error(
            f"No se pudo geocodificar la ciudad de origen: {request.origen!r}. "
            "Por favor verifique el nombre."
        )

    try:
        coords_destino = await geocode_ciudad(request.destino, db)
    except ValueError:
        _validation_error(
            f"No se pudo geocodificar la ciudad de destino: {request.destino!r}. "
            "Por favor verifique el nombre."
        )

    # 2. Cálculo de ruta
    try:
        ruta = await calcular_ruta(
            coords_origen["lat"], coords_origen["lon"],
            coords_destino["lat"], coords_destino["lon"],
        )
    except Exception:
        _validation_error(
            f"No se pudo calcular la ruta entre {request.origen!r} y {request.destino!r}."
        )

    # 3. Verificar nivel de servicio
    nivel_doc = await db["niveles_servicio"].find_one({"_id": request.nivel_servicio})
    if nivel_doc is None:
        _validation_error(
            f"Nivel de servicio {request.nivel_servicio!r} no existe en el catálogo."
        )
    nivel = NivelServicio.model_validate(nivel_doc)

    # 4. Seleccionar vehículo disponible que cumpla requisitos del nivel
    vehiculo_doc = await db["vehiculos"].find_one({
        "estado": "activo",
        "capacidad.pasajeros": {"$gte": max(request.pasajeros, nivel.requisitos.capacidad_minima)},
    })
    if vehiculo_doc is None:
        _validation_error(
            f"No hay vehículos disponibles para {request.pasajeros} pasajeros "
            f"con nivel {request.nivel_servicio!r}."
        )
    vehiculo = Vehiculo.model_validate(vehiculo_doc)

    # 5. Costos operativos (usar primer registro disponible)
    costos_doc = await db["costos_variables"].find_one({})
    if costos_doc is None:
        _validation_error("No se encontraron costos operativos en el catálogo.")
    costos = CostosOperativos.model_validate(costos_doc)

    # 6. Cotización
    resultado = cotizar_servicio(vehiculo, costos, nivel, ruta["distancia_km"], ruta["tiempo_h"])

    # 7. Crear sesión y token
    token = generate_token()
    await create_session(token, {
        "origen": request.origen,
        "destino": request.destino,
        "pasajeros": request.pasajeros,
        "nivel_servicio": request.nivel_servicio,
        "fecha_servicio": request.fecha_servicio.isoformat(),
        "hora_salida": request.hora_salida.isoformat(),
        "distancia_km": ruta["distancia_km"],
        "tiempo_h": ruta["tiempo_h"],
        "cotizacion": resultado,
    }, db)

    resumen = ResumenCotizacion(
        origen=request.origen,
        destino=request.destino,
        distancia_km=ruta["distancia_km"],
        tiempo_h=ruta["tiempo_h"],
        nivel_servicio=nivel.nombre,
        vehiculo_id=vehiculo.id,
        desglose=resultado["desglose"],
        subtotal=resultado["subtotal"],
        total=resultado["total"],
    )

    return InicioViajeResponse(
        status="success",
        token=token,
        resumen_cotizacion=resumen,
        ws_url=f"ws://localhost:8000/chat/{token}",
    )
