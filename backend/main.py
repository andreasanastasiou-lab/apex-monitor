import logging
import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

from api.device_routes import router as device_router
from api.routes import router
from auth.db import create_default_admin, init_db, migrate_from_config
from auth.routes import router as auth_router
from db.influx import test_connection
from monitors.icmp import ping_device
from monitors.port_check import check_port
from scheduler import start_scheduler

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(title="Apex Monitor", version="0.1.0")
app.include_router(router)
app.include_router(auth_router)
app.include_router(device_router)


@app.get("/test/ping/{host}")
def test_ping(host: str):
    return ping_device(host)


@app.get("/test/port/{host}/{port}")
def test_port(host: str, port: int):
    return check_port(host, port)


@app.get("/test/db")
def test_db():
    return {"influxdb_connected": test_connection()}


@app.on_event("startup")
async def startup_event():
    from pathlib import Path

    init_db()
    create_default_admin()

    jwt_key = os.environ.get("JWT_SECRET_KEY", "")
    if not jwt_key or jwt_key == "generate-a-random-32-char-string-here":
        logger.warning(
            "JWT_SECRET_KEY is not set or is using the placeholder default. "
            "Set a strong random secret in backend/.env before deploying."
        )

    config_yaml = str(Path(__file__).resolve().parent / "config.yaml")
    migrated = migrate_from_config(config_yaml)
    if migrated:
        logger.info("Migrated %d device(s) from config.yaml", migrated)
    else:
        logger.info("Device inventory already populated (or config.yaml not found)")

    start_scheduler()


@app.on_event("shutdown")
async def shutdown_event():
    pass


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
