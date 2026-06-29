from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth.db import (
    create_user,
    deactivate_user,
    get_audit_log,
    get_user,
    is_locked,
    list_users,
    log_action,
    update_user_role,
    verify_password,
)
from auth.jwt import create_access_token
from auth.middleware import require_admin, require_auth

router = APIRouter(prefix="/auth")


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str


class UpdateRoleRequest(BaseModel):
    role: str


@router.post("/login")
def login(body: LoginRequest, request: Request):
    ip = request.client.host if request.client else "unknown"
    if is_locked(body.username):
        log_action(body.username, "login", ip, False)
        raise HTTPException(status_code=423, detail="Account locked — try again later")
    if not verify_password(body.username, body.password):
        log_action(body.username, "login", ip, False)
        raise HTTPException(status_code=401, detail="Invalid username or password")
    user = get_user(body.username)
    token = create_access_token(body.username, user["role"])
    log_action(body.username, "login", ip, True)
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user["role"],
        "username": body.username,
    }


@router.post("/logout")
def logout(request: Request, current_user: dict = Depends(require_auth)):
    ip = request.client.host if request.client else "unknown"
    log_action(current_user["username"], "logout", ip, True)
    return {"success": True}


@router.get("/me")
def me(current_user: dict = Depends(require_auth)):
    return {"username": current_user["username"], "role": current_user["role"]}


@router.get("/users")
def get_users(current_user: dict = Depends(require_admin)):
    return list_users()


@router.post("/users")
def new_user(body: CreateUserRequest, current_user: dict = Depends(require_admin)):
    if not create_user(body.username, body.password, body.role):
        raise HTTPException(status_code=409, detail="Username already exists or invalid role")
    return {"success": True}


@router.put("/users/{username}/role")
def set_role(
    username: str,
    body: UpdateRoleRequest,
    current_user: dict = Depends(require_admin),
):
    if not update_user_role(username, body.role):
        raise HTTPException(status_code=404, detail="User not found or invalid role")
    return {"success": True}


@router.delete("/users/{username}")
def delete_user(username: str, current_user: dict = Depends(require_admin)):
    if not deactivate_user(username):
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True}


@router.get("/audit-log")
def audit_log(current_user: dict = Depends(require_admin)):
    return get_audit_log()
