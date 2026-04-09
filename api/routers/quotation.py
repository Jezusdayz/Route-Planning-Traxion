"""Router HTTP: validación de viaje y cotización con generación de SessionToken."""

from datetime import date, time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.database import get_db
from api.models.nivel_servicio import NivelServicio
from api.services.auth import generate_token
from api.services.geocoding import geocode_ciudad
from api.services.planner import calcular_mision
from api.services.routing import calcular_ruta
from api.services.session_manager import create_session, set_estado, update_seccion

router = APIRouter(prefix="/cotizar", tags=["cotización"])


class InicioViajeRequest(BaseModel):
    origen: str
    destino: str
    pasajeros: int = Field(..., gt=0)
    nivel_servicio: Literal["economico", "empresarial", "ejecutivo", "estandar"]
    fecha_servicio: date
    hora_salida: time


class InicioViajeResponse(BaseModel):
    status: str
    token: str
    normalizacion: dict | None = None
    planeacion: dict | None = None
    operacion: dict | None = None
    validaciones: dict | None = None
    supuestos: dict | None = None
    costeo: dict | None = None
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

    # 4. Crear sesión con input_usuario
    token = generate_token()
    input_usuario = {
        "origen_texto": request.origen,
        "destino_texto": request.destino,
        "pasajeros": request.pasajeros,
        "nivel_servicio": request.nivel_servicio,
        "fecha_servicio": request.fecha_servicio.isoformat(),
        "hora_salida": request.hora_salida.isoformat(),
    }
    await create_session(token, input_usuario, db)
    await set_estado(token, "cotizado", db)

    # 5. Persistir sección normalizacion
    normalizacion = {
        "origen": {"ciudad": request.origen, "lat": coords_origen["lat"], "lon": coords_origen["lon"]},
        "destino": {"ciudad": request.destino, "lat": coords_destino["lat"], "lon": coords_destino["lon"]},
    }
    await update_seccion(token, "normalizacion", normalizacion, db)

    # 6. Planeación operativa + validación + costeo (persiste sus secciones internamente)
    planeacion_result = None
    validaciones_result = None
    supuestos_result = None
    costeo_result = None
    operacion_result = None
    try:
        mision = await calcular_mision(
            token=token,
            pasajeros=request.pasajeros,
            nivel=nivel,
            distancia_base_km=ruta["distancia_km"],
            tiempo_base_h=ruta["tiempo_h"],
            db=db,
        )
        planeacion_result = mision["planeacion"]
        operacion_result = mision["operacion"]
        validaciones_result = mision["validaciones"]
        supuestos_result = mision["supuestos"]
        costeo_result = mision["costeo"]
    except ValueError as e:
        _validation_error(str(e))

    return InicioViajeResponse(
        status="success",
        token=token,
        normalizacion=normalizacion,
        planeacion=planeacion_result,
        operacion=operacion_result,
        validaciones=validaciones_result,
        supuestos=supuestos_result,
        costeo=costeo_result,
        ws_url=f"ws://localhost:8000/chat/{token}",
    )
