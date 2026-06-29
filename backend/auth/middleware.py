from fastapi import HTTPException, Request

from auth.jwt import get_current_user


def require_auth(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth_header[7:].strip()
    user = get_current_user(token)
    if user is None:
        raise HTTPException(status_code=401, detail="Token expired or invalid")
    return user


def require_admin(request: Request) -> dict:
    user = require_auth(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
