"""Router WebSocket: chat con pipeline orquestado — Gatekeeper + re-cálculo + FASE 8."""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.database import get_db
from api.services.agent_loader import get_system_prompt
from api.services.ai_factory import chat_completion
from api.services.auth import validate_token
from api.services.gatekeeper import gatekeeper
from api.services.pipeline import recalcular_viaje
from api.services.resultado_builder import construir_resultado, persistir_resultado
from api.services.session_manager import append_historial, expire_session, get_session, incrementar_metricas, update_seccion

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


async def _send(ws: WebSocket, data: dict) -> None:
    await ws.send_text(json.dumps(data, ensure_ascii=False, default=str))


async def _thinking(ws: WebSocket, fase: str, activo: bool) -> None:
    await _send(ws, {"type": "status", "is_thinking": activo, "fase": fase})


def _gran_json(sesion: dict) -> str:
    """Serializa la sesión completa (sin _id ni historial) para el Gran JSON de Tracy."""
    datos = {k: v for k, v in sesion.items() if k not in ("_id", "historial")}
    return json.dumps(datos, ensure_ascii=False, default=str)


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.websocket("/chat/{token}")
async def chat_viaje(websocket: WebSocket, token: str):
    db = get_db()

    sesion = await validate_token(token, db)
    if sesion is None:
        await websocket.close(code=4401, reason="Token inválido o expirado")
        return

    await websocket.accept()

    # Bienvenida usando secciones canónicas del Gran JSON
    input_u = sesion.get("input_usuario") or {}
    resultado_s = sesion.get("resultado") or {}
    costeo_s = sesion.get("costeo") or {}
    costo_total = resultado_s.get("costo_total") or costeo_s.get("costo_total_cotizacion", 0.0)

    bienvenida = {
        "tipo": "bienvenida",
        "mensaje": (
            f"¡Hola! Tu viaje de {input_u.get('origen_texto', '')} "
            f"a {input_u.get('destino_texto', '')} "
            f"ha sido cotizado exitosamente. "
            f"Total: ${costo_total:,.2f} MXN. "
            "¿Deseas ajustar algún detalle del viaje?"
        ),
        "costeo": costeo_s,
    }
    await _send(websocket, bienvenida)

    try:
        while True:
            mensaje = await websocket.receive_text()

            # Registrar mensaje del usuario en historial de auditoría
            await append_historial(db=db, token=token, entry={
                "role": "user",
                "mensaje": mensaje,
                "timestamp": _ts(),
            })

            # ── FASE 0: Gatekeeper de Intención (con reintentos) ──────────────
            await _thinking(websocket, "gatekeeper", True)
            try:
                gate_result = await gatekeeper(mensaje, sesion.get("input_usuario") or {})
                gate = gate_result
            except Exception as exc:
                logger.warning("Error en gatekeeper: %s", exc)
                await _thinking(websocket, "gatekeeper", False)
                await _send(websocket, {
                    "tipo": "error",
                    "mensaje": f"No pude procesar tu solicitud en este momento: {exc}",
                })
                continue
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
            tokens_fase8_entrada = tokens_fase8_salida = 0
            try:
                system_prompt = get_system_prompt("explicacion")
                fase8_result = await chat_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": _gran_json(sesion)},
                    ]
                )
                tokens_fase8_entrada = fase8_result.tokens_entrada
                tokens_fase8_salida = fase8_result.tokens_salida
                respuesta_datos = (
                    json.loads(fase8_result.text)
                    if fase8_result.text.strip().startswith("{")
                    else {
                        "mensaje_usuario": fase8_result.text,
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

            # Persistir sección explicacion en sesión
            await update_seccion(token, "explicacion", respuesta_datos, db)

            # Acumular métricas de tokens en la sesión
            await incrementar_metricas(
                token,
                tokens_entrada=tokens_fase8_entrada,
                tokens_salida=tokens_fase8_salida,
                db=db,
            )

            # Registrar respuesta de Tracy en historial de auditoría
            await append_historial(db=db, token=token, entry={
                "role": "tracy",
                "mensaje": respuesta_datos.get("mensaje_usuario", ""),
                "timestamp": _ts(),
            })

            # Leer métricas acumuladas para incluir en respuesta
            sesion_metricas = await get_session(token, db)
            metricas_actuales = sesion_metricas.get("metricas", {})

            await _send(websocket, {
                "tipo": "respuesta",
                "resultado": resultado,
                "metricas": {
                    "tokens_entrada": tokens_fase8_entrada,
                    "tokens_salida": tokens_fase8_salida,
                    "tokens_entrada_total": metricas_actuales.get("tokens_entrada_total", 0),
                    "tokens_salida_total": metricas_actuales.get("tokens_salida_total", 0),
                    "llamadas_ia_total": metricas_actuales.get("llamadas_ia", 0),
                },
                **respuesta_datos,
            })

    except WebSocketDisconnect:
        await expire_session(token, db)

