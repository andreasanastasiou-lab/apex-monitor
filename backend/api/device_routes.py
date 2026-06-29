import ipaddress
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth.db import (add_device, delete_device, get_all_devices, get_device,
                     migrate_from_config, update_device)
from auth.middleware import require_admin

_CONFIG_PATH = str(Path(__file__).resolve().parent.parent / "config.yaml")

router = APIRouter(dependencies=[Depends(require_admin)])


class DeviceCreate(BaseModel):
    name: str
    ip: str
    type: str
    group_name: Optional[str] = None
    location: Optional[str] = None
    owner: Optional[str] = None
    notes: Optional[str] = None
    monitors: List[str] = []
    ports: List[int] = []


class DeviceUpdate(BaseModel):
    ip: Optional[str] = None
    type: Optional[str] = None
    group_name: Optional[str] = None
    location: Optional[str] = None
    owner: Optional[str] = None
    notes: Optional[str] = None
    monitors: Optional[List[str]] = None
    ports: Optional[List[int]] = None


def _valid_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def _group_devices(devices: list) -> dict:
    groups: dict = {}
    for d in devices:
        g = d.get("group_name") or "Ungrouped"
        groups.setdefault(g, []).append(d)
    return groups


@router.get("/devices/inventory")
def list_inventory():
    devices = get_all_devices()
    return {"groups": _group_devices(devices), "total": len(devices)}


@router.post("/devices/inventory/migrate")
def run_migration():
    count = migrate_from_config(_CONFIG_PATH)
    return {"migrated": count}


@router.post("/devices/inventory")
def create_device(body: DeviceCreate):
    if not _valid_ip(body.ip):
        raise HTTPException(status_code=422, detail="Invalid IP address")
    ok = add_device(body.model_dump())
    if not ok:
        raise HTTPException(status_code=409, detail="A device with that name already exists")
    return {"success": True, "device": get_device(body.name)}


@router.put("/devices/inventory/{name}")
def edit_device(name: str, body: DeviceUpdate):
    if body.ip is not None and not _valid_ip(body.ip):
        raise HTTPException(status_code=422, detail="Invalid IP address")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    ok = update_device(name, updates)
    if not ok:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"success": True, "device": get_device(name)}


@router.delete("/devices/inventory/{name}")
def remove_device(name: str):
    ok = delete_device(name)
    if not ok:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"success": True}
