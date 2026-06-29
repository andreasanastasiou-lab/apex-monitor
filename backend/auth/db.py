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
