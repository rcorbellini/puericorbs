"""Os bancos: um da plataforma e um por prática.

O banco da plataforma guarda quem entra (usuários e sessões), as práticas, os domínios e quem trabalha em cada prática.
Nenhum dado de paciente mora nele. Cada prática (o consultório de um pediatra) tem o próprio arquivo, em
`data/practices/p<id>/practice.db`, com as famílias, a agenda, o prontuário, os arquivos e o dinheiro: o isolamento
"cada pediatra só vê os seus" é físico, não um filtro que alguém pode esquecer.

Mudar um esquema: suba a versão, ponha a coluna no texto do esquema (banco novo nasce no esquema atual) e acrescente a
migração em MIGRATIONS, que roda nos bancos antigos ao abrir.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterator

PLATFORM_VERSION = 1
PLATFORM_SCHEMA = """
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  name TEXT NOT NULL,
  password_hash TEXT,
  is_platform_admin INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE TABLE sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  user_agent TEXT
);
CREATE TABLE clinics (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE practices (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT 'Pediatra',
  registry TEXT,
  bio TEXT,
  address TEXT,
  phone TEXT,
  accent TEXT NOT NULL DEFAULT 'agua',
  clinic_id INTEGER REFERENCES clinics(id),
  created_at TEXT NOT NULL
);
CREATE TABLE domains (
  host TEXT PRIMARY KEY,
  practice_id INTEGER NOT NULL REFERENCES practices(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL
);
CREATE TABLE memberships (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  practice_id INTEGER NOT NULL REFERENCES practices(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('clinician', 'receptionist')),
  PRIMARY KEY (user_id, practice_id)
);
"""
PLATFORM_MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {}

PRACTICE_VERSION = 1
PRACTICE_SCHEMA = """
CREATE TABLE settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE families (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  notes TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE guardians (
  id INTEGER PRIMARY KEY,
  family_id INTEGER NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  user_id INTEGER,
  name TEXT NOT NULL,
  relation TEXT NOT NULL DEFAULT 'responsável',
  cpf TEXT,
  phone TEXT,
  email TEXT,
  is_legal INTEGER NOT NULL DEFAULT 1,
  is_financial INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
CREATE INDEX guardians_user ON guardians(user_id);
CREATE TABLE patients (
  id INTEGER PRIMARY KEY,
  family_id INTEGER NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  sex TEXT NOT NULL CHECK (sex IN ('F', 'M')),
  birth_date TEXT NOT NULL,
  gestational_weeks INTEGER,
  birth_weight_g INTEGER,
  birth_length_cm REAL,
  birth_head_cm REAL,
  birth_type TEXT,
  allergies TEXT,
  conditions TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE services (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  kind TEXT NOT NULL,
  duration_min INTEGER NOT NULL,
  price_cents INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1,
  version INTEGER NOT NULL DEFAULT 1,
  position INTEGER NOT NULL DEFAULT 0,
  config TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL
);
CREATE TABLE availability (
  id INTEGER PRIMARY KEY,
  weekday INTEGER NOT NULL,
  start_min INTEGER NOT NULL,
  end_min INTEGER NOT NULL
);
CREATE TABLE reserved_slots (
  id INTEGER PRIMARY KEY,
  weekday INTEGER NOT NULL,
  start_min INTEGER NOT NULL,
  duration_min INTEGER NOT NULL
);
CREATE TABLE schedule_exceptions (
  id INTEGER PRIMARY KEY,
  day TEXT NOT NULL,
  reason TEXT
);
CREATE TABLE plans (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  price_cents INTEGER NOT NULL,
  months INTEGER NOT NULL DEFAULT 12,
  entry_rule TEXT,
  max_entry_age_m INTEGER,
  auto_renew INTEGER NOT NULL DEFAULT 1,
  sibling_discount_pct INTEGER NOT NULL DEFAULT 0,
  discount_pct INTEGER NOT NULL DEFAULT 0,
  benefits TEXT NOT NULL DEFAULT '[]',
  perks TEXT NOT NULL DEFAULT '[]',
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL
);
CREATE TABLE memberships (
  id INTEGER PRIMARY KEY,
  plan_id INTEGER NOT NULL REFERENCES plans(id),
  patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  started_on TEXT NOT NULL,
  ends_on TEXT NOT NULL,
  billing TEXT NOT NULL,
  due_day INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'ativo',
  paused_until TEXT,
  price_cents INTEGER NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE appointments (
  id INTEGER PRIMARY KEY,
  patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  service_id INTEGER NOT NULL REFERENCES services(id),
  service_version INTEGER NOT NULL DEFAULT 1,
  start_at TEXT NOT NULL,
  end_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'agendado',
  kind TEXT NOT NULL DEFAULT 'normal',
  source TEXT NOT NULL DEFAULT 'recepcao',
  price_cents INTEGER NOT NULL DEFAULT 0,
  membership_id INTEGER REFERENCES memberships(id),
  arrived_at TEXT,
  notes TEXT,
  created_at TEXT NOT NULL,
  created_by INTEGER
);
CREATE INDEX appointments_start ON appointments(start_at);
CREATE INDEX appointments_patient ON appointments(patient_id);
CREATE TABLE encounters (
  id INTEGER PRIMARY KEY,
  appointment_id INTEGER REFERENCES appointments(id),
  patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  service_id INTEGER REFERENCES services(id),
  status TEXT NOT NULL DEFAULT 'aberta',
  started_at TEXT NOT NULL,
  finished_at TEXT,
  notes TEXT NOT NULL DEFAULT '{}',
  cid TEXT,
  conduct TEXT,
  family_summary TEXT,
  summary_released INTEGER NOT NULL DEFAULT 0,
  clinician_id INTEGER
);
CREATE TABLE measurements (
  id INTEGER PRIMARY KEY,
  patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  encounter_id INTEGER REFERENCES encounters(id),
  taken_on TEXT NOT NULL,
  weight_kg REAL,
  length_cm REAL,
  head_cm REAL,
  source TEXT NOT NULL DEFAULT 'consulta'
);
CREATE TABLE immunizations (
  id INTEGER PRIMARY KEY,
  patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  code TEXT NOT NULL,
  applied_on TEXT NOT NULL,
  lot TEXT,
  place TEXT,
  source TEXT NOT NULL DEFAULT 'consultorio',
  UNIQUE (patient_id, code)
);
CREATE TABLE milestone_checks (
  id INTEGER PRIMARY KEY,
  patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  code TEXT NOT NULL,
  achieved_on TEXT NOT NULL,
  marked_by TEXT NOT NULL,
  marker_name TEXT,
  UNIQUE (patient_id, code)
);
CREATE TABLE care_items (
  id INTEGER PRIMARY KEY,
  patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  detail TEXT,
  due_from TEXT,
  due_to TEXT,
  owner TEXT NOT NULL DEFAULT 'familia',
  visibility TEXT NOT NULL DEFAULT 'family',
  status TEXT NOT NULL DEFAULT 'pendente',
  encounter_id INTEGER REFERENCES encounters(id),
  file_id INTEGER,
  created_at TEXT NOT NULL,
  done_at TEXT
);
CREATE TABLE files (
  id INTEGER PRIMARY KEY,
  family_id INTEGER NOT NULL REFERENCES families(id) ON DELETE CASCADE,
  patient_id INTEGER REFERENCES patients(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  note TEXT,
  original_name TEXT,
  stored_name TEXT NOT NULL,
  mime TEXT,
  size INTEGER,
  visibility TEXT NOT NULL,
  uploaded_by INTEGER,
  uploader_role TEXT NOT NULL,
  uploader_name TEXT,
  care_item_id INTEGER REFERENCES care_items(id),
  encounter_id INTEGER REFERENCES encounters(id),
  needs_review INTEGER NOT NULL DEFAULT 0,
  reviewed_at TEXT,
  review_note TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE charges (
  id INTEGER PRIMARY KEY,
  family_id INTEGER NOT NULL REFERENCES families(id),
  patient_id INTEGER REFERENCES patients(id),
  membership_id INTEGER REFERENCES memberships(id),
  appointment_id INTEGER REFERENCES appointments(id),
  description TEXT NOT NULL,
  amount_cents INTEGER NOT NULL,
  due_on TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'aberta',
  method TEXT,
  paid_on TEXT,
  invoice TEXT NOT NULL DEFAULT 'emitir',
  created_at TEXT NOT NULL
);
CREATE INDEX charges_due ON charges(due_on);
CREATE TABLE expenses (
  id INTEGER PRIMARY KEY,
  description TEXT NOT NULL,
  category TEXT,
  amount_cents INTEGER NOT NULL,
  spent_on TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY,
  at TEXT NOT NULL,
  user_id INTEGER,
  role TEXT,
  action TEXT NOT NULL,
  entity TEXT,
  entity_id INTEGER,
  ip TEXT
);
"""
PRACTICE_MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {}


def now_iso(tz=None) -> str:
    """O agora na hora local (sem fuso no texto): é assim que todo horário fica guardado."""
    return datetime.now(tz).replace(tzinfo=None, microsecond=0).isoformat(timespec="seconds")


def _open(path: Path, schema: str, version: int, migrations: dict) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 15000")
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current == 0:
        # executescript confirma sozinho cada comando; com o IF NOT EXISTS, um arquivo que parou no meio se completa
        conn.executescript(schema.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ").replace(
            "CREATE INDEX ", "CREATE INDEX IF NOT EXISTS "))
        conn.execute(f"PRAGMA user_version = {version}")
    elif current < version:
        for target in range(current + 1, version + 1):
            with transaction(conn):
                migrations[target](conn)
            conn.execute(f"PRAGMA user_version = {target}")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """BEGIN IMMEDIATE … COMMIT, com ROLLBACK no erro. Dentro de outra transação, só repassa."""
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def platform_path(data_dir: Path) -> Path:
    return data_dir / "platform.db"


def practice_dir(data_dir: Path, practice_id: int) -> Path:
    return data_dir / "practices" / f"p{int(practice_id)}"


def connect_platform(data_dir: Path) -> sqlite3.Connection:
    return _open(platform_path(data_dir), PLATFORM_SCHEMA, PLATFORM_VERSION, PLATFORM_MIGRATIONS)


def connect_practice(data_dir: Path, practice_id: int) -> sqlite3.Connection:
    return _open(practice_dir(data_dir, practice_id) / "practice.db", PRACTICE_SCHEMA, PRACTICE_VERSION,
                 PRACTICE_MIGRATIONS)


def one(conn: sqlite3.Connection, sql: str, args: tuple = ()) -> dict | None:
    row = conn.execute(sql, args).fetchone()
    return dict(row) if row else None


def many(conn: sqlite3.Connection, sql: str, args: tuple = ()) -> list[dict]:
    return [dict(r) for r in conn.execute(sql, args).fetchall()]


def insert(conn: sqlite3.Connection, table: str, values: dict) -> int:
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    return conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(values.values())).lastrowid


def update(conn: sqlite3.Connection, table: str, row_id: int, values: dict) -> None:
    if not values:
        return
    sets = ", ".join(f"{k} = ?" for k in values)
    conn.execute(f"UPDATE {table} SET {sets} WHERE id = ?", (*values.values(), row_id))
