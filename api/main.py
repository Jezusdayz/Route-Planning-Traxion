from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.database import get_db, lifespan

app = FastAPI(title="Route Planning API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def health_check():
    return {"status": "ok", "environment": settings.environment}


@app.get("/db-status")
async def db_status():
    db = get_db()
    await db.command("ping")
    return {"status": "connected", "database": settings.mongodb_db_name}
