"""Tests Phase 5: AIFactory, AgentLoader, input_extractor, normalizer."""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from api.services.ai_factory import ChatResult


def _mock_chat_result(text: str, proveedor: str = "openai", modelo: str = "test") -> ChatResult:
    """Helper para crear un ChatResult de prueba."""
    return ChatResult(text=text, tokens_entrada=10, tokens_salida=5, proveedor=proveedor, modelo=modelo)


# ---------------------------------------------------------------------------
# Tests: AIFactory
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ai_factory_openai_compatible():
    """AIFactory debe llamar al endpoint OpenAI-compatible y retornar contenido."""
    openai_response = {
        "choices": [{"message": {"content": '{"origen_texto": "Monterrey"}'}}]
    }

    with patch("api.services.ai_factory.settings") as mock_settings, \
         patch("api.services.ai_factory.get_client") as mock_client:

        mock_settings.ai_provider = "openai"
        mock_settings.ai_model = "gpt-4o-mini"
        mock_settings.ai_base_url = "https://api.openai.com/v1"
        mock_settings.ai_api_key = "sk-test"

        client_mock = AsyncMock()
        client_mock.__aenter__ = AsyncMock(return_value=client_mock)
        client_mock.__aexit__ = AsyncMock(return_value=False)
        resp_mock = MagicMock()
        resp_mock.raise_for_status = MagicMock()
        resp_mock.json = MagicMock(return_value=openai_response)
        client_mock.post = AsyncMock(return_value=resp_mock)
        mock_client.return_value = client_mock

        from api.services.ai_factory import chat_completion
        result = await chat_completion([{"role": "user", "content": "hola"}])

    assert result.text == '{"origen_texto": "Monterrey"}'
    assert result.proveedor == "openai"
    assert result.tokens_entrada == 0


@pytest.mark.asyncio
async def test_ai_factory_anthropic():
    """AIFactory debe adaptar mensajes al formato Anthropic."""
    anthropic_response = {
        "content": [{"text": "Hola desde Anthropic"}]
    }

    with patch("api.services.ai_factory.settings") as mock_settings, \
         patch("api.services.ai_factory.get_client") as mock_client:

        mock_settings.ai_provider = "anthropic"
        mock_settings.ai_model = "claude-3-haiku-20240307"
        mock_settings.ai_base_url = ""
        mock_settings.ai_api_key = "sk-ant-test"

        client_mock = AsyncMock()
        client_mock.__aenter__ = AsyncMock(return_value=client_mock)
        client_mock.__aexit__ = AsyncMock(return_value=False)
        resp_mock = MagicMock()
        resp_mock.raise_for_status = MagicMock()
        resp_mock.json = MagicMock(return_value=anthropic_response)
        client_mock.post = AsyncMock(return_value=resp_mock)
        mock_client.return_value = client_mock

        from api.services.ai_factory import chat_completion
        result = await chat_completion([
            {"role": "system", "content": "Eres Tracy"},
            {"role": "user", "content": "hola"},
        ])

    assert result.text == "Hola desde Anthropic"
    assert result.proveedor == "anthropic"
    # Verifica que se usó el endpoint de Anthropic
    call_args = client_mock.post.call_args
    assert "anthropic.com" in call_args[0][0]


@pytest.mark.asyncio
async def test_ai_factory_proveedor_invalido():
    """Proveedor no soportado debe lanzar ValueError."""
    with patch("api.services.ai_factory.settings") as mock_settings:
        mock_settings.ai_provider = "proveedor_imaginario"
        mock_settings.ai_model = "modelo-x"

        from api.services.ai_factory import chat_completion
        with pytest.raises(ValueError, match="no soportado"):
            await chat_completion([{"role": "user", "content": "test"}])


# ---------------------------------------------------------------------------
# Tests: AgentLoader
# ---------------------------------------------------------------------------

def test_agent_loader_carga_coordinator():
    """load_agent('coordinator') debe retornar contenido del archivo .md."""
    from api.services.agent_loader import load_agent
    contenido = load_agent("coordinator")
    assert "Tracy" in contenido
    assert "FASE" in contenido


def test_agent_loader_archivo_inexistente():
    """load_agent con nombre inválido debe lanzar FileNotFoundError."""
    from api.services.agent_loader import load_agent
    with pytest.raises(FileNotFoundError):
        load_agent("agente_que_no_existe")


def test_get_system_prompt_extraccion():
    """get_system_prompt('extraccion') debe retornar el prompt de coordinator."""
    from api.services.agent_loader import get_system_prompt
    prompt = get_system_prompt("extraccion")
    assert len(prompt) > 10


def test_get_system_prompt_fase_invalida():
    """Fase sin agente definido debe lanzar ValueError."""
    from api.services.agent_loader import get_system_prompt
    with pytest.raises(ValueError, match="No hay agente"):
        get_system_prompt("fase_desconocida")


# ---------------------------------------------------------------------------
# Tests: input_extractor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_extraer_input_estructura():
    """extraer_input debe retornar dict con las claves de input_usuario."""
    ia_response = json.dumps({
        "input_usuario": {
            "origen_texto": "Monterrey",
            "destino_texto": "Guadalajara",
            "pasajeros": 40,
            "nivel_servicio": "ejecutivo",
            "duracion_estimada_horas": 5,
        }
    })

    with patch("api.services.input_extractor.get_system_prompt", return_value="prompt"), \
         patch("api.services.input_extractor.chat_completion",
               AsyncMock(return_value=_mock_chat_result(ia_response))):

        from api.services.input_extractor import extraer_input
        result = await extraer_input("Necesito ir de Monterrey a Guadalajara con 40 pasajeros")

    assert result["origen_texto"] == "Monterrey"
    assert result["destino_texto"] == "Guadalajara"
    assert result["pasajeros"] == 40
    assert result["nivel_servicio"] == "ejecutivo"


@pytest.mark.asyncio
async def test_extraer_input_respuesta_sin_anidacion():
    """extraer_input debe funcionar si la IA devuelve directamente input_usuario sin anidar."""
    ia_response = json.dumps({
        "origen_texto": "CDMX",
        "destino_texto": "Pachuca",
        "pasajeros": None,
        "nivel_servicio": None,
        "duracion_estimada_horas": None,
    })

    with patch("api.services.input_extractor.get_system_prompt", return_value="prompt"), \
         patch("api.services.input_extractor.chat_completion",
               AsyncMock(return_value=_mock_chat_result(ia_response))):

        from api.services.input_extractor import extraer_input
        result = await extraer_input("Quiero ir de CDMX a Pachuca")

    assert result["origen_texto"] == "CDMX"
    assert result["destino_texto"] == "Pachuca"


# ---------------------------------------------------------------------------
# Tests: normalizer
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_normalizar_geocodifica_y_persiste():
    """normalizar debe geocodificar origen/destino y actualizar la sesión."""
    db_mock = MagicMock()
    col_mock = MagicMock()
    col_mock.find_one = AsyncMock(return_value={"nombre": "x", "lat": 19.43, "lon": -99.13})
    col_mock.update_one = AsyncMock()
    db_mock.__getitem__ = MagicMock(return_value=col_mock)

    input_usuario = {
        "origen_texto": "CDMX",
        "destino_texto": "Pachuca",
        "pasajeros": 38,
        "nivel_servicio": "empresarial",
        "duracion_estimada_horas": 10,
    }

    from api.services.normalizer import normalizar
    result = await normalizar("token-test", input_usuario, db_mock)

    assert "origen" in result
    assert "destino" in result
    assert result["origen"]["ciudad"] == "CDMX"
    assert result["origen"]["lat"] == 19.43
    assert result["destino"]["ciudad"] == "Pachuca"
    col_mock.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_normalizar_ciudad_no_encontrada():
    """normalizar debe propagar error si la ciudad no existe en Nominatim."""
    db_mock = MagicMock()
    col_mock = MagicMock()
    col_mock.find_one = AsyncMock(return_value=None)
    col_mock.update_one = AsyncMock()
    db_mock.__getitem__ = MagicMock(return_value=col_mock)

    input_usuario = {"origen_texto": "CiudadFalsa123", "destino_texto": "OtraFalsa"}

    with patch("api.services.normalizer.geocode_ciudad", AsyncMock(side_effect=ValueError("no encontrada"))):
        from api.services.normalizer import normalizar
        with pytest.raises(ValueError):
            await normalizar("token-test", input_usuario, db_mock)
