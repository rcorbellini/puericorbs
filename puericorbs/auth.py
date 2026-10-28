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

# As senhas erradas, por endereço e por conta, numa janela de 15 minutos. Ficam na memória do processo (um reinício
# zera), o que basta para segurar quem tenta adivinhar senha pela internet.
WINDOW = timedelta(minutes=15)
MAX_BY_IP = 10
MAX_BY_EMAIL = 20
_failures: dict[str, list[datetime]] = {}


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
        # a conta que não existe (ou sem senha) gasta o mesmo tempo: o relógio não diz quais e-mails têm conta
        hashlib.scrypt(password.encode(), salt=b"puericorbs-falsa", n=2**14, r=8, p=1, dklen=32)
        return False
    _, n, r, p, salt, dk = stored.split("$")
    test = hashlib.scrypt(password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=32)
    return hmac.compare_digest(test, _unb64(dk))


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_session(pconn: sqlite3.Connection, user_id: int, user_agent: str | None, days: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.now() + timedelta(days=days)).replace(microsecond=0).isoformat()
    pconn.execute("INSERT INTO sessions (token_hash, user_id, created_at, expires_at, user_agent) VALUES (?, ?, ?, ?, ?)",
                  (token_hash(token), user_id, now_iso(), expires, (user_agent or "")[:200]))
    return token


def session_user(pconn: sqlite3.Connection, token: str | None) -> dict | None:
    """O dono da sessão. Em `acting`, quem a administração está vendo (o context.py decide se ainda vale)."""
    if not token:
        return None
    row = one(pconn, """SELECT u.*, s.expires_at, s.as_practice_id, s.as_user_id, s.as_guardian_id
                        FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?""", (token_hash(token),))
    if not row or row["expires_at"] < now_iso():
        return None
    row.pop("password_hash", None)
    acting = {k: row.pop(k) for k in ("as_practice_id", "as_user_id", "as_guardian_id")}
    row["acting"] = acting if acting["as_practice_id"] else None
    return row


def set_acting(pconn: sqlite3.Connection, token: str, practice_id: int | None = None, user_id: int | None = None,
               guardian_id: int | None = None) -> None:
    """Liga o "vendo como" da sessão (sem argumentos, desliga). Só a administração chega aqui (api_admin.py)."""
    pconn.execute("UPDATE sessions SET as_practice_id = ?, as_user_id = ?, as_guardian_id = ? WHERE token_hash = ?",
                  (practice_id, user_id, guardian_id, token_hash(token)))


def end_session(pconn: sqlite3.Connection, token: str | None) -> None:
    if token:
        pconn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))


def _recent(key: str) -> list[datetime]:
    cutoff = datetime.now() - WINDOW
    hits = [t for t in _failures.get(key, []) if t > cutoff]
    if hits:
        _failures[key] = hits
    else:
        _failures.pop(key, None)
    return hits


def throttled(ip: str, email: str) -> bool:
    """Já errou demais: por este endereço ou nesta conta."""
    return len(_recent(f"ip:{ip}")) >= MAX_BY_IP or len(_recent(f"email:{email.lower()}")) >= MAX_BY_EMAIL


def failed(ip: str, email: str) -> None:
    if len(_failures) > 5000:  # muita gente diferente errando: a janela recomeça para não crescer sem fim
        _failures.clear()
    now = datetime.now()
    for key in (f"ip:{ip}", f"email:{email.lower()}"):
        _failures.setdefault(key, []).append(now)
