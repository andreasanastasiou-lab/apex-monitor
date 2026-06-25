from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


# TODO: add endpoints for device status, metrics, and alerts
