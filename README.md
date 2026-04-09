# Route-Planning-Traxion
Route Planning Solution for Traxion's Hackaton

## API (FastAPI)

### Requisitos previos
- Python 3.12+
- MongoDB corriendo localmente en `mongodb://localhost:27017`
- (Opcional) [ngrok](https://ngrok.com/) para exponer la API

### Configuración del entorno

```bash
# 1. Crear y activar entorno virtual
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS

# 2. Instalar dependencias
pip install -r api/requirements.txt

# 3. Crear archivo de variables de entorno
copy api\.env.sample api\.env   # Windows
# cp api/.env.sample api/.env   # Linux / macOS
```

Edita `api/.env` y ajusta los valores:

```
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=traxion
ENVIRONMENT=development
ORS_API_KEY=your_openrouteservice_api_key_here
USER_AGENT=route-planning-traxion/1.0
```

### Variables de entorno

| Variable | Descripción | Requerida |
|----------|-------------|-----------|
| `MONGODB_URL` | URL de conexión a MongoDB | ✅ |
| `MONGODB_DB_NAME` | Nombre de la base de datos | ✅ |
| `ENVIRONMENT` | Entorno de ejecución (`development` / `production`) | ✅ |
| `ORS_API_KEY` | Clave de API para [OpenRouteService](https://openrouteservice.org/) (geocodificación/rutas) | ✅ en producción |
| `USER_AGENT` | Identificador de la aplicación para requests a Nominatim | ✅ en producción |

> En producción/nube, inyecta las variables directamente en el entorno del sistema — no se usa el archivo `.env`.

### Ejecutar la API localmente

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Endpoints disponibles:
| Endpoint | Descripción |
|----------|-------------|
| `GET /` | Health check — devuelve estado y entorno activo |
| `GET /db-status` | Verifica conexión a MongoDB |
| `GET /docs` | Documentación interactiva (Swagger UI) |

### Exponer la API con ngrok

```bash
ngrok http 8000
```

ngrok generará una URL pública (ej. `https://xxxx.ngrok-free.app`) que puede usarse como entorno de pruebas en la nube.
