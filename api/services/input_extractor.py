"""Paso 1 del pipeline: extracción de entidades via IA (FASE 0)."""

import json
import re

from api.services.agent_loader import get_system_prompt
from api.services.ai_factory import chat_completion

_CAMPOS_DEFAULTS = {
    "origen_texto": None,
    "destino_texto": None,
    "pasajeros": None,
    "nivel_servicio": None,
    "duracion_estimada_horas": None,
}


def _extraer_json(texto: str) -> dict:
    """Extrae el primer bloque JSON del texto del modelo."""
    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if not match:
        raise ValueError(f"Respuesta del modelo sin JSON válido: {texto!r}")
    return json.loads(match.group())


async def extraer_input(
    mensaje_usuario: str,
    estado_actual: dict | None = None,
) -> dict:
    """Llama a la IA en FASE 0 y devuelve el input_usuario normalizado.

    Args:
        mensaje_usuario: Texto libre del usuario.
        estado_actual: Estado actual de la sesión (rama input_usuario del Gran JSON).

    Returns:
        Dict con las claves de input_usuario detectadas.
    """
    system_prompt = get_system_prompt("extraccion")

    contexto = json.dumps(estado_actual or {}, ensure_ascii=False)
    user_content = (
        f"Estado actual del viaje:\n{contexto}\n\n"
        f"Mensaje del usuario:\n{mensaje_usuario}"
    )

    respuesta = await chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        response_format="json_object",
    )

    datos = _extraer_json(respuesta)

    # Normalizar: extraer solo input_usuario si el modelo lo anidó
    input_data = datos.get("input_usuario", datos)

    return {**_CAMPOS_DEFAULTS, **input_data}
