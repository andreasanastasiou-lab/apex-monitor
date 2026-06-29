import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
_EXPIRE_HOURS = 8


def _secret() -> str:
    return os.environ.get("JWT_SECRET_KEY", "")


def create_access_token(username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=_EXPIRE_HOURS)
    payload = {"sub": username, "role": role, "exp": expire}
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, _secret(), algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_current_user(token: str) -> Optional[dict]:
    payload = verify_token(token)
    if payload is None:
        return None
    return {"username": payload.get("sub"), "role": payload.get("role")}
