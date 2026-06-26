import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv

from api.routes import router
from db.influx import test_connection
from monitors.icmp import ping_device
from monitors.port_check import check_port
from scheduler import start_scheduler

load_dotenv()

app = FastAPI(title="Apex Monitor", version="0.1.0")
app.include_router(router)


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
