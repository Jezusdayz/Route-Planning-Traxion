"""Router WebSocket: chat y seguimiento de sesión de viaje."""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from api.database import get_db
from api.services.auth import validate_token
from api.services.session_manager import expire_session

router = APIRouter(tags=["chat"])


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
            "¿En qué más puedo ayudarte?"
        ),
        "cotizacion": sesion.get("cotizacion"),
    }
    await websocket.send_text(json.dumps(bienvenida, ensure_ascii=False))

    try:
        while True:
            data = await websocket.receive_text()
            respuesta = {
                "tipo": "respuesta",
                "mensaje": f"Recibido: {data}. ¿Tienes alguna otra pregunta sobre tu viaje?",
            }
            await websocket.send_text(json.dumps(respuesta, ensure_ascii=False))
    except WebSocketDisconnect:
        await expire_session(token, db)
