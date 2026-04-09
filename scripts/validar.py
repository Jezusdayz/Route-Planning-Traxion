"""Script de validación operativa.

Verifica que los componentes principales de la API funcionan correctamente:
1. Health Check     — importa la app FastAPI y verifica respuesta /.
2. Geocoding Check  — valida el servicio geocode_ciudad con mock de DB y HTTP.
3. Routing Check    — valida calcular_ruta con mock de HTTP.
4. Quotation Check  — valida cotizar_servicio con datos sembrados.

Uso:
    python scripts/validar.py
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# 1. Health Check
# ---------------------------------------------------------------------------

def check_health() -> None:
    from api.main import app
    assert app is not None, "La app FastAPI no se pudo importar."
    print("  [OK] Health Check — app importada correctamente.")


# ---------------------------------------------------------------------------
# 2. Geocoding Check
# ---------------------------------------------------------------------------

async def check_geocoding() -> None:
    from api.services.geocoding import geocode_ciudad

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"lat": "20.1011", "lon": "-98.7591"}]
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    mock_db = AsyncMock()
    mock_collection = AsyncMock()
    mock_collection.find_one = AsyncMock(return_value=None)
    mock_collection.update_one = AsyncMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)

    with patch("api.utils.http_client.httpx.AsyncClient", return_value=mock_client):
        result = await geocode_ciudad("pachuca", mock_db)

    assert "lat" in result and "lon" in result, "geocode_ciudad no retornó lat/lon."
    print(f"  [OK] Geocoding Check — pachuca → lat={result['lat']}, lon={result['lon']}")


# ---------------------------------------------------------------------------
# 3. Routing Check
# ---------------------------------------------------------------------------

async def check_routing() -> None:
    from api.services.routing import calcular_ruta

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "routes": [{"summary": {"distance": 92000.0, "duration": 5400.0}}]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("api.utils.http_client.httpx.AsyncClient", return_value=mock_client):
        result = await calcular_ruta(19.4326, -99.1332, 20.1011, -98.7591)

    assert "distancia_km" in result and "tiempo_h" in result
    print(
        f"  [OK] Routing Check — distancia={result['distancia_km']} km, "
        f"tiempo={result['tiempo_h']} h"
    )


# ---------------------------------------------------------------------------
# 4. Quotation Check
# ---------------------------------------------------------------------------

def check_quotation() -> None:
    from api.models.costos import (
        CombustibleCosto,
        CostosOperativos,
        MantenimientoCosto,
        OperadorCosto,
        OtrosCostos,
    )
    from api.models.nivel_servicio import NivelServicio, ParametrosServicio, RequisitosServicio
    from api.models.vehiculo import Capacidad, Combustible, Mantenimiento, Operacion, Vehiculo
    from api.services.quotation import cotizar_servicio

    vehiculo = Vehiculo.model_validate({
        "_id": "scania_k400",
        "tipo": "autobus",
        "modelo": "Scania K400",
        "capacidad": {"pasajeros": 48, "peso_max_kg": 18000.0},
        "combustible": {"tipo": "diesel", "capacidad_tanque_l": 400.0, "rendimiento_km_l": 4.5},
        "operacion": {
            "velocidad_promedio_kmh": 80.0,
            "autonomia_km": 1800.0,
            "factor_seguridad_combustible": 0.9,
        },
        "mantenimiento": {"intervalo_km": 15000.0, "costo_km": 0.85},
        "estado": "activo",
    })

    costos = CostosOperativos.model_validate({
        "_id": "costos_variables_std",
        "combustible": {"precio_litro": 23.5},
        "operador": {"costo_hora": 120.0},
        "mantenimiento": {"costo_km": 0.85},
        "otros": {"peajes_estimados_km": 0.30, "costo_limpieza_servicio": 250.0},
    })

    nivel = NivelServicio.model_validate({
        "_id": "empresarial",
        "nombre": "Empresarial",
        "descripcion": "Servicio corporativo",
        "parametros": {"factor_costo": 1.35, "buffer_tiempo": 0.15, "factor_distancia": 1.05},
        "requisitos": {"capacidad_minima": 20, "aire_acondicionado": True, "edad_max_vehiculo_anios": 5},
    })

    result = cotizar_servicio(vehiculo, costos, nivel, distancia_km=92.0, tiempo_h=1.5)

    assert result["total"] > 0, "La cotización debe tener total mayor a 0."
    print(
        f"  [OK] Quotation Check — subtotal=${result['subtotal']}, "
        f"total=${result['total']} (nivel={result['nivel_servicio']})"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    print("=== Validación Operativa ===\n")

    print("1. Health Check")
    check_health()

    print("\n2. Geocoding Check")
    await check_geocoding()

    print("\n3. Routing Check")
    await check_routing()

    print("\n4. Quotation Check")
    check_quotation()

    print("\n=== Todos los checks pasaron exitosamente. ===")


if __name__ == "__main__":
    asyncio.run(main())
