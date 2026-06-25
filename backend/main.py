import uvicorn
from fastapi import FastAPI
from dotenv import load_dotenv

from api.routes import router
from scheduler import start_scheduler

load_dotenv()

app = FastAPI(title="Apex Monitor", version="0.1.0")
app.include_router(router)


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
