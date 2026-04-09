"""Motor de IA multi-proveedor usando httpx.

Soporta cualquier proveedor compatible con OpenAI Chat Completions
(OpenAI, GitHub Models, Azure OpenAI, Ollama), Anthropic Messages API
y Google Gemini via google-generativeai SDK.
"""

import json
from typing import NamedTuple

from api.config import settings
from api.utils.http_client import get_client

_OPENAI_COMPAT = {"openai", "github", "azure", "ollama"}


class ChatResult(NamedTuple):
    """Resultado de una llamada al proveedor de IA con métricas de tokens y auditoría."""
    text: str
    tokens_entrada: int
    tokens_salida: int
    proveedor: str   # proveedor de IA utilizado (solo auditoría, nunca al LLM)
    modelo: str      # modelo exacto utilizado (solo auditoría, nunca al LLM)


async def chat_completion(
    messages: list[dict],
    model: str | None = None,
    response_format: str | None = None,
) -> ChatResult:
    """Envía una solicitud de chat al proveedor de IA configurado.

    Args:
        messages: Lista de mensajes con roles 'system', 'user', 'assistant'.
        model: Override del modelo (usa settings.ai_model si es None).
        response_format: Si es 'json_object', solicita respuesta JSON.

    Returns:
        ChatResult con texto de respuesta y métricas de tokens.
    """
    provider = settings.ai_provider.lower()
    target_model = model or settings.ai_model

    if provider in _OPENAI_COMPAT:
        return await _openai_chat(messages, target_model, response_format, provider_name=provider)
    if provider == "anthropic":
        return await _anthropic_chat(messages, target_model)
    if provider == "gemini":
        return await _gemini_chat(messages, target_model, response_format)

    raise ValueError(f"Proveedor de IA no soportado: {provider!r}")


async def _openai_chat(
    messages: list[dict],
    model: str,
    response_format: str | None,
    provider_name: str,
) -> ChatResult:
    url = f"{settings.ai_base_url.rstrip('/')}/chat/completions"
    payload: dict = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "top_p": 0.25,
    }
    if response_format == "json_object":
        payload["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {settings.ai_api_key}",
        "Content-Type": "application/json",
    }

    async with get_client() as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

    usage = data.get("usage", {})
    return ChatResult(
        text=data["choices"][0]["message"]["content"],
        tokens_entrada=usage.get("prompt_tokens", 0),
        tokens_salida=usage.get("completion_tokens", 0),
        proveedor=provider_name,
        modelo=model,
    )


async def _anthropic_chat(messages: list[dict], model: str) -> ChatResult:
    """Adapta mensajes al formato Anthropic Messages API."""
    system_content = ""
    user_messages = []

    for msg in messages:
        if msg["role"] == "system":
            system_content = msg["content"]
        else:
            user_messages.append({"role": msg["role"], "content": msg["content"]})

    payload: dict = {
        "model": model,
        "max_tokens": 2048,
        "temperature": 0.2,
        "top_p": 0.25,
        "messages": user_messages,
    }
    if system_content:
        payload["system"] = system_content

    headers = {
        "x-api-key": settings.ai_api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    async with get_client() as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    usage = data.get("usage", {})
    return ChatResult(
        text=data["content"][0]["text"],
        tokens_entrada=usage.get("input_tokens", 0),
        tokens_salida=usage.get("output_tokens", 0),
        proveedor="anthropic",
        modelo=model,
    )


async def _gemini_chat(messages: list[dict], model: str, response_format: str | None) -> ChatResult:
    """Adapta mensajes al Google Gemini SDK (google-generativeai)."""
    import google.generativeai as genai  # lazy import — solo cuando se usa Gemini
    from google.generativeai.types import HarmCategory, HarmBlockThreshold

    genai.configure(api_key=settings.ai_api_key)

    system_content = next(
        (m["content"] for m in messages if m["role"] == "system"), ""
    )
    user_content = next(
        (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
    )

    gen_config: dict = {
        "temperature": 0.2,
        "top_p": 0.25,
    }
    if response_format == "json_object":
        gen_config["response_mime_type"] = "application/json"

    safety_settings = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_LOW_AND_ABOVE,
    }

    gen_model = genai.GenerativeModel(
        model_name=model,
        system_instruction=system_content or None,
        generation_config=gen_config,
        safety_settings=safety_settings,
    )

    response = await gen_model.generate_content_async(user_content)

    usage = response.usage_metadata
    return ChatResult(
        text=response.text,
        tokens_entrada=getattr(usage, "prompt_token_count", 0) or 0,
        tokens_salida=getattr(usage, "candidates_token_count", 0) or 0,
        proveedor="gemini",
        modelo=model,
    )
