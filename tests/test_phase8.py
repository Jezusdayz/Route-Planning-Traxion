"""Tests Phase 8: gatekeeper, resultado_builder y pipeline."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Tests: resultado_builder (función pura)
# ---------------------------------------------------------------------------

def test_construir_resultado_completo():
    from api.services.resultado_builder import construir_resultado

    sesion = {
        "operacion": {
            "vehiculo": {"modelo": "Scania K310", "capacidad_pasajeros": 40},
            "unidades": 2,
        },
        "planeacion": {"distancia_operativa_km": 460.0, "tiempo_operativo_h": 7.2},
        "costeo": {"costo_total": 21500.0},
    }
    resultado = construir_resultado(sesion)

    assert resultado["vehiculo_seleccionado"] == "Scania K310"
    assert resultado["unidades"] == 2
    assert resultado["distancia_total_km"] == 460.0
    assert resultado["tiempo_total_h"] == 7.2
    assert resultado["costo_total"] == 21500.0


def test_construir_resultado_datos_parciales():
    """Con sesión vacía debe retornar defaults seguros."""
    from api.services.resultado_builder import construir_resultado

    resultado = construir_resultado({})
    assert resultado["vehiculo_seleccionado"] == "N/A"
    assert resultado["unidades"] == 1
    assert resultado["costo_total"] == 0.0


def test_construir_resultado_sin_costeo():
    from api.services.resultado_builder import construir_resultado

    sesion = {
        "operacion": {"vehiculo": {"modelo": "Sprinter"}, "unidades": 1},
        "planeacion": {"distancia_operativa_km": 300.0, "tiempo_operativo_h": 4.0},
        # sin costeo
    }
    resultado = construir_resultado(sesion)
    assert resultado["costo_total"] == 0.0


@pytest.mark.asyncio
async def test_persistir_resultado_actualiza_sesion():
    from api.services.resultado_builder import persistir_resultado

    col = MagicMock()
    col.update_one = AsyncMock()
    db = MagicMock()
    db.__getitem__ = MagicMock(return_value=col)

    resultado = {"vehiculo_seleccionado": "Scania K310", "costo_total": 20000.0}
    await persistir_resultado("tok-abc", resultado, db)

    col.update_one.assert_called_once()
    call_args = col.update_one.call_args
    set_data = call_args[0][1]["$set"]
    assert set_data["resultado"] == resultado


# ---------------------------------------------------------------------------
# Tests: gatekeeper
# ---------------------------------------------------------------------------

def _gate_json(entendido=True, cambio=True, origen="Puebla", pasajeros=None):
    data = {
        "entendido": entendido,
        "cambio_detectado": cambio,
        "input_usuario": {
            "origen_texto": origen,
            "destino_texto": "Monterrey",
        },
    }
    if pasajeros:
        data["input_usuario"]["pasajeros"] = pasajeros
    return json.dumps(data)


@pytest.mark.asyncio
async def test_gatekeeper_entendido_exitoso():
    from api.services.gatekeeper import gatekeeper

    with patch("api.services.gatekeeper.chat_completion", AsyncMock(return_value=_gate_json())):
        resultado = await gatekeeper("quiero ir a Monterrey desde Puebla", {})

    assert resultado.entendido is True
    assert resultado.cambio_detectado is True
    assert resultado.input_usuario is not None
    assert resultado.input_usuario.origen_texto == "Puebla"


@pytest.mark.asyncio
async def test_gatekeeper_cambio_no_detectado():
    """IA devuelve entendido=True pero cambio_detectado=False (pregunta informativa)."""
    from api.services.gatekeeper import gatekeeper

    respuesta = json.dumps({
        "entendido": True,
        "cambio_detectado": False,
        "input_usuario": None,
    })
    with patch("api.services.gatekeeper.chat_completion", AsyncMock(return_value=respuesta)):
        resultado = await gatekeeper("¿cuánto cuesta el seguro?", {})

    assert resultado.entendido is True
    assert resultado.cambio_detectado is False


@pytest.mark.asyncio
async def test_gatekeeper_reintenta_cuando_no_entendido():
    """Si el primer intento devuelve entendido=False, reintenta y tiene éxito."""
    from api.services.gatekeeper import gatekeeper

    fallo = json.dumps({"entendido": False, "cambio_detectado": False, "input_usuario": None})
    exito = _gate_json(entendido=True, cambio=True)

    with patch(
        "api.services.gatekeeper.chat_completion",
        AsyncMock(side_effect=[fallo, exito]),
    ):
        resultado = await gatekeeper("quiero cambiar el destino", {}, max_reintentos=2)

    assert resultado.entendido is True


@pytest.mark.asyncio
async def test_gatekeeper_fallback_tras_max_reintentos():
    """Después de agotar reintentos retorna fallback con entendido=False."""
    from api.services.gatekeeper import gatekeeper

    fallo = json.dumps({"entendido": False, "cambio_detectado": False, "input_usuario": None})

    with patch(
        "api.services.gatekeeper.chat_completion",
        AsyncMock(return_value=fallo),
    ):
        resultado = await gatekeeper("xyzzy blorp", {}, max_reintentos=3)

    assert resultado.entendido is False
    assert resultado.input_usuario is None


@pytest.mark.asyncio
async def test_gatekeeper_reintenta_tras_json_invalido():
    """Si la IA devuelve texto sin JSON, reintenta."""
    from api.services.gatekeeper import gatekeeper

    json_invalido = "Lo siento, no entendí tu solicitud."
    exito = _gate_json()

    with patch(
        "api.services.gatekeeper.chat_completion",
        AsyncMock(side_effect=[json_invalido, exito]),
    ):
        resultado = await gatekeeper("quiero cambiar el destino", {}, max_reintentos=2)

    assert resultado.entendido is True


@pytest.mark.asyncio
async def test_gatekeeper_ignora_campos_extra():
    """Pydantic con extra=ignore: campos desconocidos no causan error."""
    from api.services.gatekeeper import gatekeeper

    respuesta = json.dumps({
        "entendido": True,
        "cambio_detectado": True,
        "input_usuario": {
            "origen_texto": "Querétaro",
            "campo_inventado": "valor_extra",
        },
    })
    with patch("api.services.gatekeeper.chat_completion", AsyncMock(return_value=respuesta)):
        resultado = await gatekeeper("cambiar origen a Querétaro", {})

    assert resultado.entendido is True
    assert resultado.input_usuario.origen_texto == "Querétaro"


# ---------------------------------------------------------------------------
# Tests: pipeline (recalcular_viaje)
# ---------------------------------------------------------------------------

_NIVEL_DOC = {
    "_id": "economico",
    "nombre": "Económico",
    "descripcion": "Básico",
    "parametros": {"factor_costo": 1.0, "buffer_tiempo": 0.1, "factor_distancia": 1.0},
    "requisitos": {"capacidad_minima": 20, "aire_acondicionado": False, "edad_max_vehiculo_anios": 12},
}

_VEHICULO_DOC = {
    "_id": "scania_k310",
    "tipo": "autobus",
    "modelo": "Scania K310",
    "capacidad": {"pasajeros": 40, "peso_max_kg": 15000},
    "combustible": {"tipo": "diesel", "capacidad_tanque_l": 350, "rendimiento_km_l": 3.2},
    "operacion": {"velocidad_promedio_kmh": 85, "autonomia_km": 1000, "factor_seguridad_combustible": 0.1},
    "mantenimiento": {"intervalo_km": 12000, "costo_km": 0.10},
    "estado": "activo",
}

_SESION_DOC = {
    "token": "tok-test",
    "activa": True,
    "origen": "Guadalajara",
    "destino": "Monterrey",
    "pasajeros": 30,
    "nivel_servicio": "economico",
    "distancia_km": 400.0,
    "tiempo_h": 5.0,
}

_COSTOS_DOC = {
    "_id": "costos_std",
    "combustible": {"precio_litro": 23.5},
    "operador": {"costo_hora": 250.0},
    "mantenimiento": {"costo_km": 2.5},
    "otros": {"peajes_estimados_km": 1.2, "costo_limpieza_servicio": 300.0},
}

_SEGURIDAD_DOC = {
    "_id": "seg_001",
    "pasajeros": {"tiempo_maximo_a_bordo_horas": 8, "tiempo_recomendado_descanso_horas": 1},
    "operador": {"max_horas_conduccion_continua": 4, "max_horas_jornada": 12},
    "vehiculo": {"factor_autonomia_segura": 0.8, "margen_combustible_reserva": 0.1},
    "servicio": {"tiempo_maximo_espera_min": 30, "buffer_arribo": 0.15},
    "ruta": {"factor_distancia_operativa": 1.1, "factor_tiempo_operativo": 1.15},
}


def _make_pipeline_db():
    db = MagicMock()

    def dispatch(name):
        col = MagicMock()
        col.update_one = AsyncMock()
        col.insert_one = AsyncMock()
        if name == "sesiones_viaje":
            col.find_one = AsyncMock(return_value=_SESION_DOC)
        elif name == "ciudades_geocoded":
            col.find_one = AsyncMock(return_value={"nombre": "X", "lat": 20.67, "lon": -103.35})
        elif name == "niveles_servicio":
            col.find_one = AsyncMock(return_value=_NIVEL_DOC)
        elif name == "vehiculos":
            col.find_one = AsyncMock(return_value=_VEHICULO_DOC)
        elif name == "costos_variables":
            col.find_one = AsyncMock(return_value=_COSTOS_DOC)
        elif name == "seguridad_operativa":
            col.find_one = AsyncMock(return_value=_SEGURIDAD_DOC)
        else:
            col.find_one = AsyncMock(return_value=None)
        return col

    db.__getitem__ = MagicMock(side_effect=dispatch)
    return db


_ORS_RESPONSE = {"routes": [{"summary": {"distance": 400000, "duration": 18000}}]}


@pytest.mark.asyncio
async def test_recalcular_viaje_exitoso():
    from api.services.pipeline import recalcular_viaje

    db = _make_pipeline_db()

    client_mock = AsyncMock()
    client_mock.__aenter__ = AsyncMock(return_value=client_mock)
    client_mock.__aexit__ = AsyncMock(return_value=False)
    resp_mock = MagicMock()
    resp_mock.raise_for_status = MagicMock()
    resp_mock.json = MagicMock(return_value=_ORS_RESPONSE)
    client_mock.post = AsyncMock(return_value=resp_mock)

    with patch("api.services.routing.get_client", return_value=client_mock):
        resultado = await recalcular_viaje("tok-test", {"origen_texto": "Puebla"}, db)

    assert "planeacion" in resultado
    assert "costeo" in resultado
    assert resultado["costeo"] is not None


@pytest.mark.asyncio
async def test_recalcular_viaje_sesion_no_encontrada():
    from api.services.pipeline import recalcular_viaje

    db = MagicMock()
    col = MagicMock()
    col.find_one = AsyncMock(return_value=None)
    db.__getitem__ = MagicMock(return_value=col)

    with pytest.raises(ValueError, match="Sesión no encontrada"):
        await recalcular_viaje("tok-inexistente", {}, db)
