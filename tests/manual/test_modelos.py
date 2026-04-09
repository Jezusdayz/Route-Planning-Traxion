#!/usr/bin/env python
"""
Test de compatibilidad multi-modelo — Tracy AI Engine

Valida qué modelos de Google Gemini/Gemma pueden ejecutar el pipeline de Tracy:
  - FASE 0: extracción de entidades (requiere JSON válido)
  - FASE 8: generación de propuesta comercial (requiere texto coherente)

No requiere servidor corriendo. Llama al motor de IA directamente.

Uso:
    python tests/manual/test_modelos.py
    python tests/manual/test_modelos.py --delay 15   # seg entre llamadas por modelo
    python tests/manual/test_modelos.py --fase0-only  # solo probar extracción JSON
"""

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime

# ── Setup de path para importar api.* ────────────────────────────────────────
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from api.services.ai_factory import _gemini_chat  # noqa: E402
from api.services.agent_loader import get_system_prompt  # noqa: E402

# ── Modelos a probar ──────────────────────────────────────────────────────────

MODELOS = [
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-robotics-er-1.5-preview",
    "gemma-4-26b-a4b-it",
    "gemma-4-31b-it",
]

# ── Fixtures de prueba ────────────────────────────────────────────────────────

_MENSAJE_USUARIO = "quiero cambiar el destino a Monterrey y subir a 45 pasajeros"

_ESTADO_ACTUAL = json.dumps({
    "origen_texto": "Ciudad de Mexico",
    "destino_texto": "Pachuca",
    "pasajeros": 30,
    "nivel_servicio": "economico",
}, ensure_ascii=False)

_GRAN_JSON_SAMPLE = json.dumps({
    "token": "test-token-000",
    "activa": True,
    "input_usuario": {
        "origen_texto": "Ciudad de Mexico",
        "destino_texto": "Monterrey",
        "pasajeros": 45,
        "nivel_servicio": "ejecutivo",
        "duracion_estimada_horas": 10,
    },
    "normalizacion": {
        "origen": {"ciudad": "CDMX", "lat": 19.4326, "lon": -99.1332},
        "destino": {"ciudad": "Monterrey", "lat": 25.6866, "lon": -100.3161},
    },
    "planeacion": {
        "tipo_servicio": "point_to_point",
        "distancia_base_km": 900,
        "factor_distancia": 1.15,
        "distancia_operativa_km": 1035,
        "tiempo_estimado_h": 9,
        "buffer_tiempo": 1.2,
        "tiempo_operativo_h": 10.8,
    },
    "operacion": {
        "vehiculo": {
            "tipo": "Autobus ejecutivo",
            "modelo": "Volvo 9700",
            "capacidad_pasajeros": 55,
            "rendimiento_km_l": 3.0,
            "tanque_l": 450,
            "autonomia_total": 1350,
        },
        "unidades": 1,
    },
    "validaciones": {
        "capacidad": {"requerida": 45, "vehiculo": 55, "valido": True},
        "autonomia": {"distancia_total": 1035, "autonomia_vehiculo": 1350, "valido": True},
        "tiempo_operacion": {"maximo_permitido": 12, "estimado": 10.8, "valido": True},
    },
    "supuestos": {
        "precio_combustible": 23.5,
        "resumen_flota": "1x Autobus ejecutivo (3.0 km/l)",
        "costo_mantenimiento_promedio_km": 15.0,
        "factor_distancia_aplicado": 1.15,
        "buffer_tiempo_aplicado": 1.2,
        "factor_servicio": 1.3,
        "autonomia_segura_reserva": 0.20,
    },
    "costeo": {
        "consumo_combustible_total_l": 345.0,
        "costo_combustible": 8107.5,
        "costo_operador": 5400.0,
        "costo_mantenimiento": 15525.0,
        "otros_costos_fijos": 4000.0,
        "subtotal_operativo": 33032.5,
        "factor_servicio_multiplicador": 1.3,
        "costo_total_cotizacion": 42942.25,
        "costo_por_pasajero": 954.27,
        "costo_por_km": 41.49,
    },
    "resultado": {
        "vehiculo_seleccionado": "Autobus ejecutivo",
        "unidades": 1,
        "distancia_total_km": 1035,
        "tiempo_total_h": 10.8,
        "costo_total": 42942.25,
    },
}, ensure_ascii=False)

# ── Colores ───────────────────────────────────────────────────────────────────

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

# ── Resultado por modelo ──────────────────────────────────────────────────────


class ModelResult:
    def __init__(self, modelo: str):
        self.modelo = modelo
        self.fase0_ok: bool | None = None
        self.fase8_ok: bool | None = None
        self.fase0_tokens_in: int = 0
        self.fase0_tokens_out: int = 0
        self.fase8_tokens_in: int = 0
        self.fase8_tokens_out: int = 0
        self.fase0_latencia_ms: int = 0
        self.fase8_latencia_ms: int = 0
        self.fase0_snippet: str = ""
        self.fase8_snippet: str = ""
        self.fase0_error: str = ""
        self.fase8_error: str = ""

    def _estado(self, ok: bool | None) -> str:
        if ok is True:
            return f"{GREEN}✅ OK{RESET}"
        if ok is False:
            return f"{RED}❌ FALLO{RESET}"
        return f"{YELLOW}⚠ SKIP{RESET}"

    def resumen(self) -> str:
        f0 = self._estado(self.fase0_ok)
        f8 = self._estado(self.fase8_ok)
        tok_f0 = f"({self.fase0_tokens_in}→{self.fase0_tokens_out}tok, {self.fase0_latencia_ms}ms)"
        tok_f8 = f"({self.fase8_tokens_in}→{self.fase8_tokens_out}tok, {self.fase8_latencia_ms}ms)"
        lines = [
            f"  {BOLD}{self.modelo}{RESET}",
            f"    FASE 0 {f0}  {tok_f0}",
        ]
        if self.fase0_snippet:
            lines.append(f"      → {self.fase0_snippet[:80]}")
        if self.fase0_error:
            lines.append(f"      ✗ {self.fase0_error[:100]}")
        lines.append(f"    FASE 8 {f8}  {tok_f8}")
        if self.fase8_snippet:
            lines.append(f"      → {self.fase8_snippet[:80]}")
        if self.fase8_error:
            lines.append(f"      ✗ {self.fase8_error[:100]}")
        return "\n".join(lines)


# ── Probes ────────────────────────────────────────────────────────────────────

_RATE_KEYWORDS = ("rate", "quota", "429", "resource_exhausted", "too many", "unavailable")
_UNAVAILABLE_KEYWORDS = ("not found", "404", "invalid", "unsupported", "not supported")


def _es_rate_limit(err: str) -> bool:
    el = err.lower()
    return any(k in el for k in _RATE_KEYWORDS)


def _es_no_disponible(err: str) -> bool:
    el = err.lower()
    return any(k in el for k in _UNAVAILABLE_KEYWORDS)


async def probe_fase0(modelo: str, result: ModelResult) -> None:
    """FASE 0: Extracción de entidades. Requiere JSON con campo 'entendido'."""
    system_prompt = get_system_prompt("extraccion")
    user_content = (
        f"Estado actual del viaje:\n{_ESTADO_ACTUAL}\n\n"
        f"Mensaje del usuario:\n{_MENSAJE_USUARIO}"
    )
    t0 = time.monotonic()
    try:
        resp = await _gemini_chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            model=modelo,
            response_format="json_object",
        )
        latencia = int((time.monotonic() - t0) * 1000)
        result.fase0_tokens_in = resp.tokens_entrada
        result.fase0_tokens_out = resp.tokens_salida
        result.fase0_latencia_ms = latencia

        # Validar JSON con campo 'entendido'
        texto = resp.text.strip()
        datos = json.loads(texto) if texto.startswith("{") else {}
        assert "entendido" in datos, f"JSON sin campo 'entendido': {texto[:120]}"
        result.fase0_ok = True
        result.fase0_snippet = f"entendido={datos['entendido']}, cambio={datos.get('cambio_detectado')}"

    except AssertionError as e:
        result.fase0_ok = False
        result.fase0_error = str(e)
    except Exception as e:
        err = str(e)
        if _es_rate_limit(err):
            result.fase0_ok = None   # WARN: infra, no capacidad del modelo
            result.fase0_error = f"[RATE LIMIT] {err[:80]}"
        elif _es_no_disponible(err):
            result.fase0_ok = None   # SKIP: modelo no disponible en esta cuenta/región
            result.fase0_error = f"[NO DISPONIBLE] {err[:80]}"
        else:
            result.fase0_ok = False
            result.fase0_error = err[:100]


async def probe_fase8(modelo: str, result: ModelResult) -> None:
    """FASE 8: Generación de propuesta comercial. Requiere texto no vacío."""
    system_prompt = get_system_prompt("explicacion")
    t0 = time.monotonic()
    try:
        resp = await _gemini_chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _GRAN_JSON_SAMPLE},
            ],
            model=modelo,
            response_format=None,
        )
        latencia = int((time.monotonic() - t0) * 1000)
        result.fase8_tokens_in = resp.tokens_entrada
        result.fase8_tokens_out = resp.tokens_salida
        result.fase8_latencia_ms = latencia

        texto = resp.text.strip()
        assert len(texto) > 20, f"Respuesta muy corta o vacía: {texto!r}"
        result.fase8_ok = True
        result.fase8_snippet = texto[:80]

    except AssertionError as e:
        result.fase8_ok = False
        result.fase8_error = str(e)
    except Exception as e:
        err = str(e)
        if _es_rate_limit(err):
            result.fase8_ok = None   # WARN: infra
            result.fase8_error = f"[RATE LIMIT] {err[:80]}"
        elif _es_no_disponible(err):
            result.fase8_ok = None   # SKIP: modelo no disponible
            result.fase8_error = f"[NO DISPONIBLE] {err[:80]}"
        else:
            result.fase8_ok = False
            result.fase8_error = err[:100]


# ── Runner ────────────────────────────────────────────────────────────────────

async def main(delay: int, fase0_only: bool) -> int:
    print(f"\n{BOLD}{CYAN}══════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}{CYAN}   Tracy — Test de Compatibilidad Multi-Modelo         {RESET}")
    print(f"{BOLD}{CYAN}══════════════════════════════════════════════════════{RESET}\n")
    log(f"Probando {len(MODELOS)} modelos | delay={delay}s | fase0_only={fase0_only}", CYAN)

    resultados: list[ModelResult] = []

    for i, modelo in enumerate(MODELOS):
        log(f"[{i+1}/{len(MODELOS)}] Probando {modelo}…", BOLD)
        r = ModelResult(modelo)

        # FASE 0
        log(f"  FASE 0 (extracción JSON)…", YELLOW)
        await probe_fase0(modelo, r)
        estado_f0 = "✅" if r.fase0_ok else "❌"
        log(f"  {estado_f0} FASE 0: {r.fase0_snippet or r.fase0_error}", GREEN if r.fase0_ok else RED)

        await asyncio.sleep(delay)

        # FASE 8 (opcional)
        if not fase0_only:
            log(f"  FASE 8 (propuesta comercial)…", YELLOW)
            await probe_fase8(modelo, r)
            estado_f8 = "✅" if r.fase8_ok else "❌"
            log(f"  {estado_f8} FASE 8: {r.fase8_snippet[:60] if r.fase8_ok else r.fase8_error}", GREEN if r.fase8_ok else RED)
            await asyncio.sleep(delay)

        resultados.append(r)

    # ── Resumen final ─────────────────────────────────────────────────────────
    print(f"\n{BOLD}{CYAN}══════════════════════════════════════════════════════{RESET}")
    print(f"{BOLD}  Resultados por modelo{RESET}")
    print(f"{BOLD}{CYAN}══════════════════════════════════════════════════════{RESET}\n")

    aptos = []
    parciales = []
    no_aptos = []

    for r in resultados:
        print(r.resumen())
        print()
        f0 = r.fase0_ok is True
        f8 = r.fase8_ok is True or fase0_only
        if f0 and f8:
            aptos.append(r.modelo)
        elif f0 or f8:
            parciales.append(r.modelo)
        else:
            no_aptos.append(r.modelo)

    print(f"{BOLD}{CYAN}── Conclusión ───────────────────────────────────────────{RESET}")
    if aptos:
        print(f"{GREEN}{BOLD}Aptos para producción ({len(aptos)}): {', '.join(aptos)}{RESET}")
    if parciales:
        print(f"{YELLOW}{BOLD}Aptos parciales ({len(parciales)}): {', '.join(parciales)}{RESET}")
    if no_aptos:
        print(f"{RED}{BOLD}No aptos ({len(no_aptos)}): {', '.join(no_aptos)}{RESET}")
    print()

    return 0 if not no_aptos else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test multi-modelo Tracy AI")
    parser.add_argument("--delay", type=int, default=12,
                        help="Segundos entre llamadas (default: 12, evitar rate-limit)")
    parser.add_argument("--fase0-only", action="store_true",
                        help="Solo probar FASE 0 (extracción JSON, más rápido)")
    args = parser.parse_args()

    exit_code = asyncio.run(main(args.delay, args.fase0_only))
    sys.exit(exit_code)
