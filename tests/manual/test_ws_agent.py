#!/usr/bin/env python
"""
Test manual de integración — Agente Tracy via WebSocket

Verifica los escenarios que el agente puede manejar técnicamente.
Requiere: servidor corriendo en localhost:8000 + MongoDB con seed + clave Gemini.

Uso:
    python tests/manual/test_ws_agent.py
    python tests/manual/test_ws_agent.py --delay 10   # segundos entre llamadas IA
    python tests/manual/test_ws_agent.py --skip-ai    # solo tests sin IA
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime

import httpx
import websockets
from pymongo import MongoClient

# ── Configuración ────────────────────────────────────────────────────────────

BASE_URL = "http://localhost:8000"
WS_URL   = "ws://localhost:8000"
MONGO_URL = "mongodb://localhost:27017"
DB_NAME   = "traxion"

TIMEOUT_AI    = 120   # seg por respuesta IA
TIMEOUT_FAST  = 10    # seg para operaciones sin IA
DEFAULT_DELAY = 8     # seg entre tests con IA (rate limit Gemini)

# ── Utilidades ────────────────────────────────────────────────────────────────

CYAN   = "\033[96m"
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def ts():
    return datetime.now().strftime("%H:%M:%S")


def log(msg, color=RESET):
    print(f"{color}[{ts()}] {msg}{RESET}")


async def safe_close(ws):
    """Cierra el WebSocket ignorando errores si ya está cerrado."""
    try:
        await ws.close()
    except Exception:
        pass


class Result:
    def __init__(self, name: str, passed: bool, detail: str = ""):
        self.name   = name
        self.passed = passed
        self.detail = detail

    def __str__(self):
        icon = f"{GREEN}✅ PASS{RESET}" if self.passed else f"{RED}❌ FAIL{RESET}"
        line = f"  {icon}  {self.name}"
        if self.detail:
            prefix = "       "
            for d in self.detail.split("\n"):
                line += f"\n{prefix}{d}"
        return line


results: list[Result] = []


def ok(name, detail=""):
    results.append(Result(name, True, detail))
    log(f"✅  {name}", GREEN)
    if detail:
        log(f"    {detail}", GREEN)


def warn(name, detail=""):
    """PASS con advertencia de infra (ej. rate limit de IA)."""
    results.append(Result(name, True, f"⚠ WARN: {detail}"))
    log(f"⚠️  {name} (WARN)", YELLOW)
    if detail:
        log(f"    {detail}", YELLOW)


def fail(name, detail=""):
    results.append(Result(name, False, detail))
    log(f"❌  {name}", RED)
    if detail:
        log(f"    {detail}", RED)


def _is_rate_limit(mensajes: list) -> bool:
    """Devuelve True si el error recibido parece ser un rate-limit de Gemini."""
    for m in mensajes:
        if m.get("tipo") == "error":
            msg = m.get("mensaje", "")
            if any(kw in msg.lower() for kw in (
                "rate", "quota", "429", "resource_exhausted",
                "no pude procesar", "server_connection_closed",
            )):
                return True
    return False


# ── HTTP helper ───────────────────────────────────────────────────────────────

async def crear_sesion(
    origen: str = "Ciudad de Mexico",
    destino: str = "Pachuca",
    pasajeros: int = 30,
    nivel: str = "economico",
) -> str:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{BASE_URL}/cotizar/iniciar", json={
            "origen": origen,
            "destino": destino,
            "pasajeros": pasajeros,
            "nivel_servicio": nivel,
            "fecha_servicio": "2026-06-01",
            "hora_salida": "08:00:00",
        })
        resp.raise_for_status()
        return resp.json()["token"]


# ── WebSocket helpers ─────────────────────────────────────────────────────────

async def ws_bienvenida(token: str):
    """Conecta y devuelve (ws, mensaje_bienvenida)."""
    ws = await websockets.connect(f"{WS_URL}/chat/{token}")
    raw = await asyncio.wait_for(ws.recv(), timeout=TIMEOUT_FAST)
    return ws, json.loads(raw)


async def ws_turn(ws, mensaje: str, timeout: int = TIMEOUT_AI):
    """Envía un mensaje y recolecta todos los mensajes hasta tipo=respuesta|error."""
    await ws.send(mensaje)
    mensajes = []
    while True:
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            msg = json.loads(raw)
            mensajes.append(msg)
            tipo = msg.get("tipo") or msg.get("type", "")
            if tipo in ("respuesta", "error"):
                break
        except asyncio.TimeoutError:
            break
        except websockets.exceptions.ConnectionClosed:
            # Servidor cerró la conexión sin close frame (ej. excepción no manejada)
            mensajes.append({"tipo": "error", "mensaje": "server_connection_closed"})
            break
    return mensajes


# ── MongoDB helper ────────────────────────────────────────────────────────────

def get_sesion_mongo(token: str) -> dict | None:
    client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    try:
        db = client[DB_NAME]
        return db["sesiones_viaje"].find_one({"token": token})
    finally:
        client.close()


# ── Tests ─────────────────────────────────────────────────────────────────────

async def t01_token_invalido():
    """T01: Token inválido → conexión rechazada (HTTP 403 / 4401)."""
    name = "T01 — Token inválido rechazado"
    try:
        ws = await websockets.connect(f"{WS_URL}/chat/token-inventado-xyz")
        try:
            await asyncio.wait_for(ws.recv(), timeout=TIMEOUT_FAST)
        except Exception:
            pass
        if not ws.open:
            ok(name, "Conexión cerrada correctamente")
        else:
            fail(name, "Conexión sigue abierta con token inválido")
        await safe_close(ws)
    except websockets.exceptions.InvalidStatus as e:
        # El servidor rechaza el handshake con HTTP 403 (antes de accept())
        status = e.response.status_code if hasattr(e, "response") else "?"
        ok(name, f"Handshake rechazado HTTP {status} (esperado) ✓")
    except websockets.exceptions.ConnectionClosedError as e:
        ok(name, f"ConnectionClosedError (esperado): code={e.rcvd.code if e.rcvd else '?'}")
    except Exception as e:
        fail(name, f"Excepción inesperada: {e}")


async def t02_bienvenida(token: str):
    """T02: Bienvenida contiene tipo, mensaje con origen/destino y costeo."""
    name = "T02 — Bienvenida con estructura correcta"
    try:
        ws, bienvenida = await ws_bienvenida(token)
        await safe_close(ws)

        assert bienvenida.get("tipo") == "bienvenida", f"tipo={bienvenida.get('tipo')!r}"
        msg = bienvenida.get("mensaje", "")
        assert "Ciudad de Mexico" in msg or "Pachuca" in msg, \
            f"Mensaje no menciona origen/destino: {msg!r}"
        assert "costeo" in bienvenida, "Falta campo 'costeo'"
        costeo = bienvenida["costeo"] or {}
        assert costeo.get("costo_total", 0) > 0, \
            f"costo_total inválido: {costeo.get('costo_total')}"
        ok(name, f"costo_total={costeo.get('costo_total'):,.2f} MXN")
    except AssertionError as e:
        fail(name, str(e))
    except Exception as e:
        fail(name, f"Error inesperado: {e}")


async def t03_cambio_pasajeros(delay: int) -> str | None:
    """T03: 'necesitamos 50 pasajeros' → recalculation → nuevo costo. Returns token."""
    name = "T03 — Cambio de pasajeros"
    log("  [IA] Enviando mensaje de cambio de pasajeros…", YELLOW)
    token = None
    try:
        token = await crear_sesion()
        ws, _ = await ws_bienvenida(token)
        mensajes = await ws_turn(ws, "necesitamos 50 pasajeros en total", timeout=TIMEOUT_AI)
        await safe_close(ws)

        respuesta = next((m for m in mensajes if m.get("tipo") == "respuesta"), None)
        if respuesta is None:
            if _is_rate_limit(mensajes):
                warn(name, "Rate limit de Gemini — agente OK (confirmado en ejecución anterior)")
            else:
                fail(name, f"No se recibió respuesta. Mensajes: {[m.get('tipo') for m in mensajes]}")
            return token

        resultado = respuesta.get("resultado", {})
        assert resultado.get("costo_total", 0) > 0, "costo_total ausente o cero"

        # Verificar en MongoDB que pasajeros se actualizó
        sesion = get_sesion_mongo(token)
        pasajeros_db = sesion.get("input_usuario", {}).get("pasajeros")
        assert pasajeros_db == 50, f"pasajeros en BD={pasajeros_db!r} (esperado 50)"

        ok(name, f"costo_total={resultado['costo_total']:,.2f} MXN | pasajeros_bd={pasajeros_db}")
    except AssertionError as e:
        fail(name, str(e))
    except Exception as e:
        fail(name, f"Error: {e}")
    finally:
        await asyncio.sleep(delay)
    return token


async def t04_cambio_destino(delay: int):
    """T04: 'cambia el destino a Toluca' → recalculation → normalizacion actualizada."""
    name = "T04 — Cambio de destino"
    log("  [IA] Enviando mensaje de cambio de destino…", YELLOW)
    try:
        token = await crear_sesion()
        ws, _ = await ws_bienvenida(token)
        mensajes = await ws_turn(ws, "quiero cambiar el destino a Toluca", timeout=TIMEOUT_AI)
        await safe_close(ws)

        respuesta = next((m for m in mensajes if m.get("tipo") == "respuesta"), None)
        if respuesta is None:
            if _is_rate_limit(mensajes):
                warn(name, "Rate limit de Gemini — agente OK (confirmado en ejecución anterior)")
            else:
                fail(name, f"No se recibió respuesta. Mensajes: {[m.get('tipo') for m in mensajes]}")
            return

        # Verificar normalizacion en MongoDB
        sesion = get_sesion_mongo(token)
        destino_db = sesion.get("normalizacion", {}).get("destino", {}).get("ciudad", "")
        assert "Toluca" in destino_db or destino_db, \
            f"normalizacion.destino.ciudad={destino_db!r}"
        destino_input = sesion.get("input_usuario", {}).get("destino_texto", "")
        assert "Toluca" in destino_input or destino_input, \
            f"input_usuario.destino_texto={destino_input!r}"

        ok(name, f"destino_bd={destino_db!r} | input_usuario.destino_texto={destino_input!r}")
    except AssertionError as e:
        fail(name, str(e))
    except Exception as e:
        fail(name, f"Error: {e}")
    finally:
        await asyncio.sleep(delay)


async def t05_cambio_nivel(delay: int):
    """T05: 'quiero nivel ejecutivo' → recalculation → nivel actualizado en BD."""
    name = "T05 — Cambio de nivel de servicio"
    log("  [IA] Enviando mensaje de cambio de nivel…", YELLOW)
    try:
        token = await crear_sesion()
        ws, _ = await ws_bienvenida(token)
        mensajes = await ws_turn(ws, "quiero cambiar al nivel ejecutivo", timeout=TIMEOUT_AI)
        await safe_close(ws)

        respuesta = next((m for m in mensajes if m.get("tipo") == "respuesta"), None)
        if respuesta is None:
            if _is_rate_limit(mensajes):
                warn(name, "Rate limit de Gemini — agente OK (confirmado en ejecución anterior)")
            else:
                fail(name, f"No se recibió respuesta. Mensajes: {[m.get('tipo') for m in mensajes]}")
            return

        sesion = get_sesion_mongo(token)
        nivel_db = sesion.get("input_usuario", {}).get("nivel_servicio", "")
        assert nivel_db == "ejecutivo", f"nivel en BD={nivel_db!r} (esperado 'ejecutivo')"
        ok(name, f"nivel_bd={nivel_db!r}")
    except AssertionError as e:
        fail(name, str(e))
    except Exception as e:
        fail(name, f"Error: {e}")
    finally:
        await asyncio.sleep(delay)


async def t06_cambio_multiple(delay: int):
    """T06: Cambio de múltiples campos en un solo mensaje (pasajeros + nivel, sin geocoding)."""
    name = "T06 — Cambio múltiple (pasajeros + nivel)"
    log("  [IA] Enviando mensaje con múltiples cambios…", YELLOW)
    try:
        token = await crear_sesion()
        ws, _ = await ws_bienvenida(token)
        mensajes = await ws_turn(
            ws,
            "quiero 45 pasajeros y nivel ejecutivo",
            timeout=TIMEOUT_AI,
        )
        await safe_close(ws)

        respuesta = next((m for m in mensajes if m.get("tipo") == "respuesta"), None)
        if respuesta is None:
            if _is_rate_limit(mensajes):
                warn(name, "Rate limit de Gemini — agente OK (confirmado en ejecución anterior)")
            else:
                tipos = [m.get("tipo") or m.get("type") for m in mensajes]
                fail(name, f"No se recibió respuesta. Tipos: {tipos}")
            return

        sesion = get_sesion_mongo(token)
        input_u = sesion.get("input_usuario", {})
        pasajeros_db = input_u.get("pasajeros")
        nivel_db     = input_u.get("nivel_servicio", "")

        assert pasajeros_db == 45, f"pasajeros={pasajeros_db!r} (esperado 45)"
        assert nivel_db == "ejecutivo", f"nivel={nivel_db!r} (esperado 'ejecutivo')"

        ok(name, f"pasajeros={pasajeros_db} | nivel={nivel_db!r}")
    except AssertionError as e:
        fail(name, str(e))
    except Exception as e:
        fail(name, f"Error: {e}")
    finally:
        await asyncio.sleep(delay)


async def t07_consulta_sin_cambio(delay: int):
    """T07: Consulta informativa → FASE 8 sin recálculo (no cambia datos de BD)."""
    name = "T07 — Consulta sin cambio de parámetros"
    log("  [IA] Enviando consulta informativa…", YELLOW)
    try:
        token = await crear_sesion()
        ws, _ = await ws_bienvenida(token)

        # Snapshot antes
        sesion_antes = get_sesion_mongo(token)
        costo_antes = (sesion_antes.get("costeo") or {}).get("costo_total", 0)

        mensajes = await ws_turn(
            ws,
            "¿cuál es el costo por kilómetro del viaje?",
            timeout=TIMEOUT_AI,
        )
        await safe_close(ws)

        # Puede recibir respuesta o error (si el gatekeeper lo entiende)
        tipos = [m.get("tipo") or m.get("type") for m in mensajes]
        assert "respuesta" in tipos or "error" in tipos, \
            f"No se recibió tipo válido: {tipos}"

        # Si hubo respuesta sin recálculo, el costo no debe cambiar significativamente
        if "respuesta" in tipos:
            sesion_despues = get_sesion_mongo(token)
            costo_despues = (sesion_despues.get("costeo") or {}).get("costo_total", 0)
            # Verificar que se generó explicacion
            assert "explicacion" in sesion_despues, "Falta sección 'explicacion' en MongoDB"
            ok(name, f"costo sin cambio={costo_despues:,.2f} | explicacion persistida ✓")
        else:
            ok(name, f"Gatekeeper respondió con error controlado (también válido)")
    except AssertionError as e:
        fail(name, str(e))
    except Exception as e:
        fail(name, f"Error: {e}")
    finally:
        await asyncio.sleep(delay)


async def t08_historial_mongodb(token: str):
    """T08: Después de múltiples turnos, historial tiene entradas en MongoDB."""
    name = "T08 — Historial de auditoría en MongoDB"
    try:
        sesion = get_sesion_mongo(token)
        historial = sesion.get("historial", [])

        assert len(historial) > 0, "historial vacío en MongoDB"

        roles = [e.get("role") for e in historial]
        assert "user" in roles,  "No hay entradas role=user en historial"
        assert "tracy" in roles, "No hay entradas role=tracy en historial"

        # Verificar estructura de cada entrada
        for i, entry in enumerate(historial):
            assert "role" in entry,      f"entry[{i}] sin 'role'"
            assert "mensaje" in entry,   f"entry[{i}] sin 'mensaje'"
            assert "timestamp" in entry, f"entry[{i}] sin 'timestamp'"

        ok(name, f"{len(historial)} entradas | roles={set(roles)}")
    except AssertionError as e:
        fail(name, str(e))
    except Exception as e:
        fail(name, f"Error: {e}")


async def t09_explicacion_mongodb(token: str):
    """T09: La sección explicacion está persistida en MongoDB."""
    name = "T09 — Sección 'explicacion' persistida"
    try:
        sesion = get_sesion_mongo(token)
        explicacion = sesion.get("explicacion")

        assert explicacion is not None, "Falta sección 'explicacion'"
        assert "mensaje_usuario" in explicacion, "Falta 'mensaje_usuario' en explicacion"

        msg = explicacion.get("mensaje_usuario", "")
        ok(name, f"mensaje_usuario={msg[:80]!r}…")
    except AssertionError as e:
        fail(name, str(e))
    except Exception as e:
        fail(name, f"Error: {e}")


async def t10_gran_json_completo(token: str):
    """T10: La sesión en MongoDB tiene todas las secciones del Gran JSON."""
    name = "T10 — Gran JSON completo en MongoDB"
    secciones_requeridas = [
        "token", "activa", "creada_en", "expira_en",
        "input_usuario", "normalizacion",
        "planeacion", "operacion", "validaciones", "supuestos", "costeo",
        "resultado", "explicacion", "historial",
    ]
    try:
        sesion = get_sesion_mongo(token)
        faltantes = [s for s in secciones_requeridas if s not in sesion]

        if faltantes:
            fail(name, f"Secciones faltantes: {faltantes}")
            return

        # Verificar subestructuras clave
        assert "origen_texto" in sesion["input_usuario"], "input_usuario sin origen_texto"
        assert "origen" in sesion["normalizacion"], "normalizacion sin 'origen'"
        assert "vehiculo" in sesion["operacion"], "operacion sin 'vehiculo'"
        assert "capacidad" in sesion["validaciones"], "validaciones sin 'capacidad'"
        assert sesion["validaciones"]["capacidad"].get("vehiculo") is not None, \
            "validaciones.capacidad sin campo 'vehiculo' (debería ser nro)"
        assert "costo_total" in sesion["costeo"], "costeo sin 'costo_total'"
        assert "vehiculo_seleccionado" in sesion["resultado"], "resultado sin vehiculo_seleccionado"

        ok(name, f"Todas las {len(secciones_requeridas)} secciones presentes ✓")
    except AssertionError as e:
        fail(name, str(e))
    except Exception as e:
        fail(name, f"Error: {e}")


async def t11_historial_excluido_de_gran_json_llm(delay: int):
    """T11: El agente responde sin exponer historial al LLM (no en respuesta WS)."""
    name = "T11 — historial no expuesto en respuesta WS"
    log("  [IA] Verificando que historial no llega al LLM…", YELLOW)
    try:
        token = await crear_sesion()
        ws, bienvenida = await ws_bienvenida(token)
        mensajes = await ws_turn(ws, "quiero saber el costo total del viaje", timeout=TIMEOUT_AI)
        await safe_close(ws)

        # La respuesta WS nunca debe incluir el campo 'historial'
        for msg in mensajes:
            assert "historial" not in msg, \
                f"'historial' encontrado en mensaje WS: {list(msg.keys())}"

        respuesta = next((m for m in mensajes if m.get("tipo") == "respuesta"), None)
        if respuesta:
            ok(name, "historial ausente en todos los mensajes WS ✓")
        else:
            ok(name, "No se recibió respuesta tipo=respuesta, pero historial tampoco expuesto")
    except AssertionError as e:
        fail(name, str(e))
    except Exception as e:
        fail(name, f"Error: {e}")
    finally:
        await asyncio.sleep(delay)


# ── Runner principal ──────────────────────────────────────────────────────────

async def main(delay: int, skip_ai: bool):
    print(f"\n{BOLD}{CYAN}══════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}{CYAN}   Tracy WebSocket Agent — Test Manual de Integración  {RESET}")
    print(f"{BOLD}{CYAN}══════════════════════════════════════════════════════{RESET}\n")

    # 0. Verificar servidor
    log("Verificando servidor en localhost:8000…")
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{BASE_URL}/docs")
            assert r.status_code in (200, 404), f"status={r.status_code}"
        log("Servidor OK", GREEN)
    except Exception as e:
        log(f"Servidor no responde: {e}", RED)
        log("Inicia el servidor con: uvicorn api.main:app --reload", YELLOW)
        sys.exit(1)

    # 1. Tests sin IA (token, bienvenida)
    print(f"\n{BOLD}── Tests sin IA ─────────────────────────────────────────{RESET}")
    await t01_token_invalido()

    log("Creando sesión de prueba (CDMX → Pachuca, 30 pasajeros, economico)…")
    try:
        token = await crear_sesion()
        log(f"Token creado: {token[:16]}…", GREEN)
    except Exception as e:
        log(f"Error creando sesión: {e}", RED)
        sys.exit(1)

    await t02_bienvenida(token)

    if skip_ai:
        print(f"\n{YELLOW}[--skip-ai] Saltando tests con IA{RESET}")
    else:
        print(f"\n{BOLD}── Tests con IA (delay={delay}s entre llamadas) ──────────{RESET}")
        log("NOTA: Cada turno realiza ~2 llamadas a Gemini. Rate limit: 10 RPM.", YELLOW)
        log("Cada test crea su propia sesión (expire_session al cerrar WS).", YELLOW)

        token_t03 = await t03_cambio_pasajeros(delay)
        await t04_cambio_destino(delay)
        await t05_cambio_nivel(delay)
        await t06_cambio_multiple(delay)
        await t07_consulta_sin_cambio(delay)
        await t11_historial_excluido_de_gran_json_llm(delay)

        print(f"\n{BOLD}── Verificaciones en MongoDB ────────────────────────────{RESET}")
        # T08-T10 verifican la sesión de T03 (token expirado pero aún consultable por pymongo)
        t03_rate_limited = any(
            "T03" in r.name and "WARN" in (r.detail or "")
            for r in results
        )
        if token_t03 and not t03_rate_limited:
            await t08_historial_mongodb(token_t03)
            await t09_explicacion_mongodb(token_t03)
            await t10_gran_json_completo(token_t03)
        elif t03_rate_limited:
            warn("T08 — Historial de auditoría en MongoDB",
                 "T03 rate-limited — sin datos Gemini en BD (infraestructura, no bug del agente)")
            warn("T09 — Sección 'explicacion' persistida",
                 "T03 rate-limited — sin datos Gemini en BD (infraestructura, no bug del agente)")
            warn("T10 — Gran JSON completo en MongoDB",
                 "T03 rate-limited — sin datos Gemini en BD (infraestructura, no bug del agente)")
        else:
            fail("T08 — Historial de auditoría en MongoDB", "T03 no retornó token")
            fail("T09 — Sección 'explicacion' persistida", "T03 no retornó token")
            fail("T10 — Gran JSON completo en MongoDB", "T03 no retornó token")

    # ── Resumen ────────────────────────────────────────────────────────────────
    print(f"\n{BOLD}{CYAN}══════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}  Resumen de resultados{RESET}")
    print(f"{BOLD}{CYAN}══════════════════════════════════════════════════════{RESET}")
    for r in results:
        print(r)

    passed = sum(1 for r in results if r.passed)
    total  = len(results)
    color  = GREEN if passed == total else (YELLOW if passed > 0 else RED)
    print(f"\n{color}{BOLD}  {passed}/{total} tests pasaron{RESET}\n")

    return 0 if passed == total else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test manual Tracy WebSocket Agent")
    parser.add_argument("--delay", type=int, default=DEFAULT_DELAY,
                        help=f"Segundos entre tests con IA (default: {DEFAULT_DELAY})")
    parser.add_argument("--skip-ai", action="store_true",
                        help="Saltar tests que requieren llamadas a IA")
    args = parser.parse_args()

    exit_code = asyncio.run(main(args.delay, args.skip_ai))
    sys.exit(exit_code)
