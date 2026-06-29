import json
import logging
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

_logger = logging.getLogger(__name__)

from passlib.context import CryptContext

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "users.db"
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _conn() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                username        TEXT UNIQUE NOT NULL,
                password_hash   TEXT NOT NULL,
                role            TEXT NOT NULL,
                is_active       INTEGER DEFAULT 1,
                failed_attempts INTEGER DEFAULT 0,
                locked_until    TEXT,
                created_at      TEXT,
                last_login      TEXT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                username    TEXT,
                action      TEXT,
                ip_address  TEXT,
                timestamp   TEXT,
                success     INTEGER
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT UNIQUE NOT NULL,
                ip          TEXT NOT NULL,
                type        TEXT NOT NULL,
                group_name  TEXT,
                location    TEXT,
                owner       TEXT,
                notes       TEXT,
                monitors    TEXT,
                ports       TEXT,
                is_active   INTEGER DEFAULT 1,
                created_at  TEXT,
                updated_at  TEXT
            )
        """)


def get_user(username: str) -> Optional[dict]:
    with _conn() as db:
        row = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
    return dict(row) if row else None


def create_user(username: str, password: str, role: str) -> bool:
    if role not in ("admin", "viewer"):
        return False
    hashed = _pwd_ctx.hash(password)
    try:
        with _conn() as db:
            db.execute(
                """INSERT INTO users (username, password_hash, role, created_at)
                   VALUES (?, ?, ?, ?)""",
                (username, hashed, role, datetime.utcnow().isoformat()),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def is_locked(username: str) -> bool:
    user = get_user(username)
    if not user:
        return False
    locked_until = user.get("locked_until")
    if not locked_until:
        return False
    try:
        lock_dt = datetime.fromisoformat(locked_until)
        if datetime.utcnow() < lock_dt:
            return True
        # Lock expired — clear it
        with _conn() as db:
            db.execute(
                "UPDATE users SET locked_until = NULL, failed_attempts = 0 WHERE username = ?",
                (username,),
            )
    except (ValueError, TypeError):
        pass
    return False


def verify_password(username: str, password: str) -> bool:
    user = get_user(username)
    if not user or not user.get("is_active"):
        return False
    if is_locked(username):
        return False
    ok = _pwd_ctx.verify(password, user["password_hash"])
    with _conn() as db:
        if ok:
            db.execute(
                "UPDATE users SET failed_attempts = 0, last_login = ? WHERE username = ?",
                (datetime.utcnow().isoformat(), username),
            )
        else:
            attempts = user["failed_attempts"] + 1
            locked_until = None
            if attempts >= 5:
                locked_until = (datetime.utcnow() + timedelta(minutes=15)).isoformat()
            db.execute(
                "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE username = ?",
                (attempts, locked_until, username),
            )
    return ok


def log_action(username: str, action: str, ip_address: str, success: bool) -> None:
    with _conn() as db:
        db.execute(
            """INSERT INTO audit_log (username, action, ip_address, timestamp, success)
               VALUES (?, ?, ?, ?, ?)""",
            (username, action, ip_address, datetime.utcnow().isoformat(), int(success)),
        )


def get_audit_log(limit: int = 100) -> list[dict]:
    with _conn() as db:
        rows = db.execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def list_users() -> list[dict]:
    with _conn() as db:
        rows = db.execute(
            """SELECT id, username, role, is_active, failed_attempts,
                      locked_until, created_at, last_login
               FROM users"""
        ).fetchall()
    return [dict(r) for r in rows]


def update_user_role(username: str, role: str) -> bool:
    if role not in ("admin", "viewer"):
        return False
    with _conn() as db:
        affected = db.execute(
            "UPDATE users SET role = ? WHERE username = ?", (role, username)
        ).rowcount
    return affected > 0


def deactivate_user(username: str) -> bool:
    with _conn() as db:
        affected = db.execute(
            "UPDATE users SET is_active = 0 WHERE username = ?", (username,)
        ).rowcount
    return affected > 0


# ── Device inventory ─────────────────────────────────────────────────────────

def _parse_device_row(row) -> dict:
    d = dict(row)
    for field in ("monitors", "ports"):
        val = d.get(field)
        if val:
            try:
                d[field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                d[field] = []
        else:
            d[field] = []
    return d


def get_all_devices() -> list:
    with _conn() as db:
        rows = db.execute(
            "SELECT * FROM devices WHERE is_active = 1 ORDER BY name"
        ).fetchall()
    return [_parse_device_row(r) for r in rows]


def get_device(name: str) -> Optional[dict]:
    with _conn() as db:
        row = db.execute(
            "SELECT * FROM devices WHERE name = ? AND is_active = 1", (name,)
        ).fetchone()
    return _parse_device_row(row) if row else None


def add_device(device: dict) -> bool:
    required = {"name", "ip", "type"}
    if not required.issubset(device):
        return False
    now = datetime.utcnow().isoformat()
    try:
        with _conn() as db:
            db.execute(
                """INSERT INTO devices
                   (name, ip, type, group_name, location, owner, notes,
                    monitors, ports, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    device["name"], device["ip"], device["type"],
                    device.get("group_name"), device.get("location"),
                    device.get("owner"), device.get("notes"),
                    json.dumps(device.get("monitors", [])),
                    json.dumps(device.get("ports", [])),
                    now, now,
                ),
            )
        return True
    except sqlite3.IntegrityError:
        return False


_DEVICE_UPDATABLE = {"ip", "type", "group_name", "location", "owner", "notes", "monitors", "ports"}


def update_device(name: str, updates: dict) -> bool:
    if not get_device(name):
        return False
    fields = {k: v for k, v in updates.items() if k in _DEVICE_UPDATABLE}
    if not fields:
        return True
    for f in ("monitors", "ports"):
        if f in fields and isinstance(fields[f], list):
            fields[f] = json.dumps(fields[f])
    fields["updated_at"] = datetime.utcnow().isoformat()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    with _conn() as db:
        affected = db.execute(
            f"UPDATE devices SET {set_clause} WHERE name = ? AND is_active = 1",
            list(fields.values()) + [name],
        ).rowcount
    return affected > 0


def delete_device(name: str) -> bool:
    with _conn() as db:
        affected = db.execute(
            "UPDATE devices SET is_active = 0, updated_at = ? WHERE name = ? AND is_active = 1",
            (datetime.utcnow().isoformat(), name),
        ).rowcount
    return affected > 0


def migrate_from_config(config_path: str) -> int:
    import yaml as _yaml
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = _yaml.safe_load(f) or {}
    except FileNotFoundError:
        return 0
    count = 0
    for device in cfg.get("devices", []):
        if not device.get("ip"):
            continue
        d = {
            "name": device.get("name", device["ip"]),
            "ip": device["ip"],
            "type": device.get("type", "workstation"),
            "group_name": device.get("group_name"),
            "location": device.get("location"),
            "owner": device.get("owner"),
            "notes": device.get("notes"),
            "monitors": device.get("monitors", []),
            "ports": device.get("ports", []),
        }
        if add_device(d):
            count += 1
    return count


# ── User management ───────────────────────────────────────────────────────────

def create_default_admin() -> None:
    if list_users():
        return
    password = os.environ.get("APEX_ADMIN_PASSWORD", "")
    generated = False
    if not password:
        password = secrets.token_hex(8)  # exactly 16 hex chars — always < 72 bytes
        generated = True
    create_user("admin", password, "admin")
    _logger.info("Admin user ready — username: admin")
    if generated:
        border = "=" * 60
        print(f"\n{border}")
        print("  Apex Monitor — Default Admin Account Created")
        print(f"  Username : admin")
        print(f"  Password : {password}")
        print("  !! Save this — it will NOT be shown again !!")
        print(f"{border}\n")
