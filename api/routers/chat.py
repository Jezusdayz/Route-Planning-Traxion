"""Router WebSocket: chat con pipeline orquestado — Gatekeeper + re-cálculo + FASE 8."""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.database import get_db
from api.services.agent_loader import get_system_prompt
from api.services.ai_factory import chat_completion
from api.services.auth import validate_token
from api.services.gatekeeper import gatekeeper
from api.services.pipeline import recalcular_viaje
from api.services.resultado_builder import construir_resultado, persistir_resultado
from api.services.session_manager import expire_session, get_session

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


async def _send(ws: WebSocket, data: dict) -> None:
    await ws.send_text(json.dumps(data, ensure_ascii=False, default=str))


async def _thinking(ws: WebSocket, fase: str, activo: bool) -> None:
    await _send(ws, {"type": "status", "is_thinking": activo, "fase": fase})


def _gran_json(sesion: dict) -> str:
    """Serializa la sesión completa (sin _id) para el Gran JSON de Tracy."""
    datos = {k: v for k, v in sesion.items() if k != "_id"}
    return json.dumps(datos, ensure_ascii=False, default=str)


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
        "costeo": sesion.get("costeo"),
    }
    await _send(websocket, bienvenida)

    try:
        while True:
            mensaje = await websocket.receive_text()

            # ── FASE 0: Gatekeeper de Intención (con reintentos) ──────────────
            await _thinking(websocket, "gatekeeper", True)
            gate = await gatekeeper(mensaje, sesion.get("input_usuario") or {})
            await _thinking(websocket, "gatekeeper", False)

            if not gate.entendido:
                await _send(websocket, {
                    "tipo": "error",
                    "mensaje": (
                        "No pude interpretar tu solicitud. "
                        "¿Puedes reformularla de otra manera? "
                        "Por ejemplo: 'quiero cambiar el destino a Puebla' o "
                        "'necesito 45 pasajeros'."
                    ),
                })
                continue

            input_usuario = (
                gate.input_usuario.model_dump(exclude_none=True)
                if gate.input_usuario
                else {}
            )

            # ── Re-cálculo si el usuario detectó un cambio ────────────────────
            if gate.cambio_detectado:
                await _thinking(websocket, "recalculo", True)
                try:
                    await recalcular_viaje(token, input_usuario, db)
                except Exception as exc:
                    logger.warning("Error en re-cálculo: %s", exc)
                    await _thinking(websocket, "recalculo", False)
                    await _send(websocket, {
                        "tipo": "error",
                        "mensaje": f"No pude recalcular el viaje: {exc}",
                    })
                    continue
                await _thinking(websocket, "recalculo", False)

            # ── Construir y persistir resultado ───────────────────────────────
            sesion = await get_session(token, db)
            resultado = construir_resultado(sesion)
            await persistir_resultado(token, resultado, db)

            # Sesión final con resultado incluido
            sesion = await get_session(token, db)

            # ── FASE 8: Explicación persuasiva con Gran JSON completo ─────────
            await _thinking(websocket, "explicacion", True)
            try:
                system_prompt = get_system_prompt("explicacion")
                respuesta_ia = await chat_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": _gran_json(sesion)},
                    ]
                )
                respuesta_datos = (
                    json.loads(respuesta_ia)
                    if respuesta_ia.strip().startswith("{")
                    else {
                        "mensaje_usuario": respuesta_ia,
                        "justificacion": [],
                        "supuestos_clave": [],
                    }
                )
            except Exception as exc:
                logger.warning("Error en explicación IA: %s", exc)
                respuesta_datos = {
                    "mensaje_usuario": (
                        f"Viaje actualizado: {resultado['vehiculo_seleccionado']} "
                        f"× {resultado['unidades']} unidad(es). "
                        f"Total: ${resultado['costo_total']:,.2f} MXN."
                    ),
                    "justificacion": [],
                    "supuestos_clave": [],
                }
            await _thinking(websocket, "explicacion", False)

            await _send(websocket, {
                "tipo": "respuesta",
                "resultado": resultado,
                **respuesta_datos,
            })

    except WebSocketDisconnect:
        await expire_session(token, db)

