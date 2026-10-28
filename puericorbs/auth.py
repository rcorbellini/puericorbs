"""Senhas e sessões. A senha vira scrypt (biblioteca padrão); a sessão é um token aleatório no cookie, e o banco
guarda só o hash dele, para que uma cópia do banco não sirva para entrar."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta

from .db import now_iso, one

COOKIE = "pc_session"


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${_b64(salt)}${_b64(dk)}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored or not stored.startswith("scrypt$"):
        return False
    _, n, r, p, salt, dk = stored.split("$")
    test = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=32)
    return hmac.compare_digest(test, _unb64(dk))


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_session(pconn: sqlite3.Connection, user_id: int, user_agent: str | None, days: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.now() + timedelta(days=days)).replace(microsecond=0).isoformat()
    pconn.execute("INSERT INTO sessions (token_hash, user_id, created_at, expires_at, user_agent) VALUES (?, ?, ?, ?, ?)",
                  (_token_hash(token), user_id, now_iso(), expires, (user_agent or "")[:200]))
    return token


def session_user(pconn: sqlite3.Connection, token: str | None) -> dict | None:
    if not token:
        return None
    row = one(pconn, """SELECT u.*, s.expires_at FROM sessions s JOIN users u ON u.id = s.user_id
                        WHERE s.token_hash = ?""", (_token_hash(token),))
    if not row or row["expires_at"] < now_iso():
        return None
    row.pop("password_hash", None)
    return row


def end_session(pconn: sqlite3.Connection, token: str | None) -> None:
    if token:
        pconn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
