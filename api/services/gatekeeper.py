"""Gatekeeper de Intención (FASE 0): filtra y valida la intención del usuario en el chat.

Utiliza el agente coordinador (FASE 0) con reintentos para garantizar que la IA
devuelva un JSON válido con la estructura esperada. Aplica validación Pydantic
para evitar que la IA invente campos o tipos incorrectos.
"""

import json
import logging
import re

from pydantic import BaseModel, ConfigDict, ValidationError

from api.services.agent_loader import get_system_prompt
from api.services.ai_factory import chat_completion

logger = logging.getLogger(__name__)


class InputUsuario(BaseModel):
    """Campos que el usuario puede modificar vía chat."""

    model_config = ConfigDict(extra="ignore")

    origen_texto: str | None = None
    destino_texto: str | None = None
    pasajeros: int | None = None
    nivel_servicio: str | None = None
    duracion_estimada_horas: float | None = None


class GatekeeperResponse(BaseModel):
    """Respuesta estructurada del Gatekeeper de Intención."""

    model_config = ConfigDict(extra="ignore")

    entendido: bool
    cambio_detectado: bool = False
    input_usuario: InputUsuario | None = None


def _extraer_json(texto: str) -> dict:
    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if not match:
        raise ValueError(f"Respuesta sin JSON válido: {texto!r}")
    return json.loads(match.group())


_FALLBACK = GatekeeperResponse(entendido=False, cambio_detectado=False, input_usuario=None)


async def gatekeeper(
    mensaje: str,
    estado_actual: dict,
    max_reintentos: int = 3,
) -> GatekeeperResponse:
    """Analiza el mensaje del usuario con FASE 0 y aplica validación Pydantic.

    Realiza hasta ``max_reintentos`` llamadas a la IA si la respuesta no es válida
    (JSON malformado, ``entendido=False`` o falla de validación Pydantic).

    Args:
        mensaje: Texto libre enviado por el usuario.
        estado_actual: Rama ``input_usuario`` del Gran JSON de sesión actual.
        max_reintentos: Máximo de intentos antes de retornar fallback.

    Returns:
        ``GatekeeperResponse`` con entendido=True si tuvo éxito, o el fallback
        (entendido=False) si todos los intentos fallaron.
    """
    system_prompt = get_system_prompt("extraccion")
    contexto = json.dumps(estado_actual or {}, ensure_ascii=False)

    for intento in range(max_reintentos):
        nota = (
            f"\n\nNota: Reintento {intento}/{max_reintentos - 1}. "
            "Responde ÚNICAMENTE con JSON válido según el esquema."
            if intento > 0
            else ""
        )
        user_content = (
            f"Estado actual del viaje:\n{contexto}\n\n"
            f"Mensaje del usuario:\n{mensaje}{nota}"
        )

        try:
            respuesta = await chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                response_format="json_object",
            )
            datos = _extraer_json(respuesta.text)
            gate = GatekeeperResponse(**datos)

            if gate.entendido:
                return gate

            logger.debug("Gatekeeper intento %d: entendido=False", intento + 1)

        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            logger.debug("Gatekeeper intento %d falló: %s", intento + 1, exc)

    return _FALLBACK
