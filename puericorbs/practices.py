"""Criar uma prática: a linha na plataforma, o domínio, a conta do pediatra e o banco dela com o começo pronto
(o catálogo de serviços, a grade de segunda a sexta e as vagas protegidas para a criança doente)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import HTTPException

from . import auth, catalog, tenancy
from .db import connect_practice, insert, now_iso, one, transaction

ACCENTS = ("agua", "azul", "coral", "lavanda")


def init_practice_db(conn: sqlite3.Connection) -> None:
    """O começo de toda prática nova. Só roda num banco sem serviços."""
    if one(conn, "SELECT id FROM services LIMIT 1"):
        return
    with transaction(conn):
        for s in catalog.default_services():
            insert(conn, "services", {**{k: v for k, v in s.items() if k != "config"},
                                      "config": json.dumps(s["config"], ensure_ascii=False),
                                      "active": 0 if s["kind"] == "telehealth" else 1, "updated_at": now_iso()})
        for wd in range(5):  # segunda a sexta
            insert(conn, "availability", {"weekday": wd, "start_min": 8 * 60, "end_min": 12 * 60})
            insert(conn, "availability", {"weekday": wd, "start_min": 14 * 60, "end_min": 17 * 60 + 20})
            # a vaga da criança que adoece no dia: uma no fim de cada turno, do tamanho da consulta por doença
            insert(conn, "reserved_slots", {"weekday": wd, "start_min": 11 * 60 + 30, "duration_min": 30})
            insert(conn, "reserved_slots", {"weekday": wd, "start_min": 16 * 60 + 50, "duration_min": 30})


def create_practice(pconn: sqlite3.Connection, data_dir: Path, *, name: str, slug: str, clinician_name: str,
                    clinician_email: str, password: str | None, domain: str | None = None, accent: str = "agua",
                    registry: str | None = None, bio: str | None = None, clinic_id: int | None = None,
                    address: str | None = None, phone: str | None = None) -> int:
    slug = slug.strip().lower()
    if not tenancy.SLUG.match(slug):
        raise HTTPException(400, "O endereço curto só aceita letras minúsculas, números e hífen (ex.: dramarina).")
    if one(pconn, "SELECT id FROM practices WHERE slug = ?", (slug,)):
        raise HTTPException(409, f"Já existe uma prática com o endereço “{slug}”.")
    host = tenancy.normalize_host(domain) if domain else None
    if host and one(pconn, "SELECT host FROM domains WHERE host = ?", (host,)):
        raise HTTPException(409, f"O domínio {host} já aponta para outra prática.")
    if accent not in ACCENTS:
        accent = "agua"
    with transaction(pconn):
        pid = insert(pconn, "practices", {"slug": slug, "name": name.strip(), "registry": registry, "bio": bio,
                                          "accent": accent, "clinic_id": clinic_id, "address": address,
                                          "phone": phone, "created_at": now_iso()})
        if host:
            insert(pconn, "domains", {"host": host, "practice_id": pid, "created_at": now_iso()})
        user = one(pconn, "SELECT id FROM users WHERE email = ?", (clinician_email.strip().lower(),))
        uid = user["id"] if user else insert(pconn, "users", {
            "email": clinician_email.strip().lower(), "name": clinician_name.strip(),
            "password_hash": auth.hash_password(password) if password else None, "created_at": now_iso()})
        pconn.execute("INSERT OR REPLACE INTO memberships (user_id, practice_id, role) VALUES (?, ?, 'clinician')",
                      (uid, pid))
    conn = connect_practice(data_dir, pid)
    try:
        init_practice_db(conn)
    finally:
        conn.close()
    return pid
