"""Tests para endpoints Phase 4: POST /cotizar/iniciar y WebSocket /chat/{token}."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from api.database import get_db
from api.main import app


# ---------------------------------------------------------------------------
# Helper: crea mock de colección Motor y el dispatch de DB
# ---------------------------------------------------------------------------

def _make_col(find_one_val=None):
    col = MagicMock()
    col.find_one = AsyncMock(return_value=find_one_val)
    col.update_one = AsyncMock()
    col.insert_one = AsyncMock()
    return col


def _make_db(nivel_doc, vehiculo_doc, costos_doc):
    """Devuelve un mock de Motor DB parametrizado."""
    geocoded_col = _make_col({"nombre": "x", "lat": 25.68, "lon": -100.31})

    def dispatch(name):
        if name == "ciudades_geocoded":
            return geocoded_col
        if name == "niveles_servicio":
            return _make_col(nivel_doc)
        if name == "vehiculos":
            return _make_col(vehiculo_doc)
        if name == "costos_variables":
            return _make_col(costos_doc)
        return _make_col(None)

    db_mock = MagicMock()
    db_mock.__getitem__ = MagicMock(side_effect=dispatch)
    return db_mock


# ---------------------------------------------------------------------------
# Datos de prueba
# ---------------------------------------------------------------------------

_NIVEL_DOC = {
    "_id": "economico",
    "nombre": "Económico",
    "descripcion": "Servicio básico",
    "parametros": {"factor_costo": 1.0, "buffer_tiempo": 0.1, "factor_distancia": 1.0},
    "requisitos": {"capacidad_minima": 20, "aire_acondicionado": False, "edad_max_vehiculo_anios": 12},
}

_VEHICULO_DOC = {
    "_id": "scania_k400",
    "tipo": "autobus",
    "modelo": "Scania K400",
    "capacidad": {"pasajeros": 48, "peso_max_kg": 18000},
    "combustible": {"tipo": "diesel", "capacidad_tanque_l": 400, "rendimiento_km_l": 3.5},
    "operacion": {"velocidad_promedio_kmh": 90, "autonomia_km": 1400, "factor_seguridad_combustible": 0.1},
    "mantenimiento": {"intervalo_km": 15000, "costo_km": 0.12},
    "estado": "activo",
}

_COSTOS_DOC = {
    "_id": "costos_generales",
    "combustible": {"precio_litro": 24.5},
    "operador": {"costo_hora": 150},
    "mantenimiento": {"costo_km": 0.12},
    "otros": {"peajes_estimados_km": 0.15, "costo_limpieza_servicio": 300},
}

_ORS_RESPONSE = {
    "routes": [{"summary": {"distance": 450000, "duration": 18000}}]
}

_PAYLOAD = {
    "origen": "Monterrey",
    "destino": "Guadalajara",
    "pasajeros": 30,
    "nivel_servicio": "economico",
    "fecha_servicio": "2026-05-01",
    "hora_salida": "08:00:00",
}


def _ors_patch():
    """Context manager que mockea la llamada HTTP a ORS."""
    client_mock = AsyncMock()
    client_mock.__aenter__ = AsyncMock(return_value=client_mock)
    client_mock.__aexit__ = AsyncMock(return_value=False)
    resp_mock = MagicMock()
    resp_mock.raise_for_status = MagicMock()
    resp_mock.json = MagicMock(return_value=_ORS_RESPONSE)
    client_mock.post = AsyncMock(return_value=resp_mock)
    return patch("api.services.routing.get_client", return_value=client_mock)


# ---------------------------------------------------------------------------
# Tests: POST /cotizar/iniciar
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cotizar_iniciar_exitoso():
    """El endpoint debe retornar token, ws_url y resumen_cotizacion."""
    db_mock = _make_db(_NIVEL_DOC, _VEHICULO_DOC, _COSTOS_DOC)
    app.dependency_overrides[get_db] = lambda: db_mock

    try:
        with _ors_patch(), TestClient(app) as client:
            response = client.post("/cotizar/iniciar", json=_PAYLOAD)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "success"
    assert "token" in data
    assert data["ws_url"].startswith("ws://")
    assert data["costeo"]["costo_total"] > 0


@pytest.mark.asyncio
async def test_cotizar_iniciar_nivel_invalido():
    """Si el nivel de servicio no existe en BD, debe retornar 422."""
    db_mock = _make_db(None, _VEHICULO_DOC, _COSTOS_DOC)
    app.dependency_overrides[get_db] = lambda: db_mock

    try:
        with _ors_patch(), TestClient(app) as client:
            response = client.post("/cotizar/iniciar", json=_PAYLOAD)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_cotizar_iniciar_sin_vehiculos_disponibles():
    """Si no hay vehículos disponibles, debe retornar 422."""
    db_mock = _make_db(_NIVEL_DOC, None, _COSTOS_DOC)
    app.dependency_overrides[get_db] = lambda: db_mock

    try:
        with _ors_patch(), TestClient(app) as client:
            response = client.post("/cotizar/iniciar", json=_PAYLOAD)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# Tests: WebSocket /chat/{token}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ws_token_invalido():
    """Con token inválido el servidor debe cerrar la conexión (código 4401)."""
    db_mock = _make_db(None, None, None)
    app.dependency_overrides[get_db] = lambda: db_mock

    try:
        with patch("api.routers.chat.get_db", return_value=db_mock), \
             TestClient(app) as client:
            with pytest.raises(Exception):
                with client.websocket_connect("/chat/token-falso") as ws:
                    ws.receive_text()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ws_token_valido_bienvenida():
    """Con token válido el servidor debe enviar mensaje de bienvenida."""
    from datetime import datetime, timezone, timedelta

    sesion_doc = {
        "token": "token-valido-123",
        "activa": True,
        "expira_en": datetime.now(timezone.utc) + timedelta(hours=1),
        "input_usuario": {
            "origen_texto": "Monterrey",
            "destino_texto": "Guadalajara",
            "pasajeros": 30,
            "nivel_servicio": "economico",
        },
        "costeo": {"costo_total": 12500.50},
    }

    db_mock = MagicMock()
    sesiones_col = _make_col(sesion_doc)
    db_mock.__getitem__ = MagicMock(return_value=sesiones_col)
    app.dependency_overrides[get_db] = lambda: db_mock

    try:
        with patch("api.routers.chat.validate_token", AsyncMock(return_value=sesion_doc)), \
             patch("api.routers.chat.get_db", return_value=db_mock), \
             TestClient(app) as client:
            with client.websocket_connect("/chat/token-valido-123") as ws:
                msg = json.loads(ws.receive_text())
                assert msg["tipo"] == "bienvenida"
                assert "Monterrey" in msg["mensaje"]
                assert "Guadalajara" in msg["mensaje"]
    finally:
        app.dependency_overrides.clear()

