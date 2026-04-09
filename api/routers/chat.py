"""Router WebSocket: chat con pipeline IA — extracción, normalización y explicación."""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.database import get_db
from api.services.agent_loader import get_system_prompt
from api.services.ai_factory import chat_completion
from api.services.auth import validate_token
from api.services.input_extractor import extraer_input
from api.services.normalizer import normalizar
from api.services.session_manager import expire_session

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


async def _send(ws: WebSocket, data: dict) -> None:
    await ws.send_text(json.dumps(data, ensure_ascii=False))


async def _thinking(ws: WebSocket, fase: str, activo: bool) -> None:
    await _send(ws, {"type": "status", "is_thinking": activo, "fase": fase})


@router.websocket("/chat/{token}")
async def chat_viaje(websocket: WebSocket, token: str):
    db = get_db()

    sesion = await validate_token(token, db)
    if sesion is None:
        await websocket.close(code=4401, reason="Token inválido o expirado")
        return

    await websocket.accept()

    bienvenida = {
        "tipo": "bienvenida",
        "mensaje": (
            f"¡Hola! Tu viaje de {sesion['origen']} a {sesion['destino']} "
            f"ha sido cotizado exitosamente. "
            f"Distancia: {sesion['distancia_km']} km. "
            f"Total: ${sesion['cotizacion']['total']:,.2f} MXN. "
            "¿Deseas ajustar algún detalle del viaje?"
        ),
        "cotizacion": sesion.get("cotizacion"),
    }
    await _send(websocket, bienvenida)

    try:
        while True:
            mensaje = await websocket.receive_text()

            # Paso 1: Extracción (FASE 0) — IA detecta entidades del texto libre
            await _thinking(websocket, "extraccion", True)
            try:
                estado_actual = sesion.get("input_usuario") or {}
                input_usuario = await extraer_input(mensaje, estado_actual)
            except Exception as exc:
                logger.warning("Error en extracción IA: %s", exc)
                await _thinking(websocket, "extraccion", False)
                await _send(websocket, {
                    "tipo": "error",
                    "mensaje": "No pude interpretar tu mensaje. ¿Puedes reformularlo?",
                })
                continue
            await _thinking(websocket, "extraccion", False)

            # Paso 2: Normalización — backend geocodifica y persiste
            await _thinking(websocket, "normalizacion", True)
            try:
                normalizacion = await normalizar(token, input_usuario, db)
            except Exception as exc:
                logger.warning("Error en normalización: %s", exc)
                await _thinking(websocket, "normalizacion", False)
                await _send(websocket, {
                    "tipo": "error",
                    "mensaje": (
                        f"No pude geocodificar las ciudades indicadas: {exc}. "
                        "Verifica los nombres e intenta de nuevo."
                    ),
                })
                continue
            await _thinking(websocket, "normalizacion", False)

            # Paso 3: Explicación (FASE 8) — Tracy genera respuesta comercial
            await _thinking(websocket, "explicacion", True)
            try:
                system_prompt = get_system_prompt("explicacion")
                estado_completo = json.dumps({
                    "sesion": {k: v for k, v in sesion.items() if k != "_id"},
                    "input_usuario": input_usuario,
                    "normalizacion": normalizacion,
                }, ensure_ascii=False)
                respuesta_ia = await chat_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": estado_completo},
                    ]
                )
                respuesta_datos = json.loads(respuesta_ia) if respuesta_ia.strip().startswith("{") else {
                    "mensaje_usuario": respuesta_ia,
                    "justificacion": [],
                    "supuestos_clave": [],
                }
            except Exception as exc:
                logger.warning("Error en explicación IA: %s", exc)
                respuesta_datos = {
                    "mensaje_usuario": (
                        f"He actualizado tu viaje: {input_usuario.get('origen_texto', '')} → "
                        f"{input_usuario.get('destino_texto', '')}. "
                        "¿Confirmas los datos?"
                    ),
                    "justificacion": [],
                    "supuestos_clave": [],
                }
            await _thinking(websocket, "explicacion", False)

            await _send(websocket, {
                "tipo": "respuesta",
                "input_usuario": input_usuario,
                "normalizacion": normalizacion,
                **respuesta_datos,
            })

    except WebSocketDisconnect:
        await expire_session(token, db)
