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

PLATFORM_VERSION = 4
PLATFORM_SCHEMA = """
CREATE TABLE users (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  name TEXT NOT NULL,
  password_hash TEXT,
  is_platform_admin INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
-- as_*: a administração vendo como alguém de um consultório (context.py): a equipe pela conta, a família pelo
-- responsável (comentário fora da tabela: dentro dela, o SQLite não consegue mais apagar coluna)
CREATE TABLE sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  user_agent TEXT,
  as_practice_id INTEGER,
  as_user_id INTEGER,
  as_guardian_id INTEGER
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
  requested_domain TEXT,
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
""" + """
-- o convite (invites.py): da equipe de um consultório (staff), do responsável de uma família (family), de um colega
-- que vai ter o próprio consultório (practice) e da administração da plataforma (admin)
CREATE TABLE invites (
  id INTEGER PRIMARY KEY,
  token_hash TEXT NOT NULL UNIQUE,
  kind TEXT NOT NULL DEFAULT 'staff' CHECK (kind IN ('staff', 'family', 'practice', 'admin')),
  practice_id INTEGER REFERENCES practices(id) ON DELETE CASCADE,
  role TEXT CHECK (role IN ('clinician', 'receptionist')),
  guardian_id INTEGER,
  label TEXT,
  created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  used_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
  revoked_at TEXT,
  new_practice_id INTEGER REFERENCES practices(id) ON DELETE SET NULL
);
-- o que acontece na plataforma (convites, consultórios, domínios, a administração); nunca dado de paciente
CREATE TABLE platform_log (
  id INTEGER PRIMARY KEY,
  at TEXT NOT NULL,
  user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
  practice_id INTEGER REFERENCES practices(id) ON DELETE SET NULL,
  action TEXT NOT NULL,
  detail TEXT,
  ip TEXT
);
-- o link que leva a administração para dentro de um consultório, vendo como alguém dele (api_admin.py): de uso único
-- e curto, porque cada domínio tem a própria sessão e o painel pode estar em outro
CREATE TABLE handoffs (
  token_hash TEXT PRIMARY KEY,
  admin_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  practice_id INTEGER NOT NULL REFERENCES practices(id) ON DELETE CASCADE,
  as_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  as_guardian_id INTEGER,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  used_at TEXT
);
"""


def _table(schema: str, name: str) -> str:
    """O CREATE TABLE de uma tabela, tirado do esquema atual (a migração cria igual a um banco novo)."""
    start = schema.index(f"CREATE TABLE {name} (")
    return schema[start:schema.index(");", start) + 1]


def _platform_v2(conn: sqlite3.Connection) -> None:
    """O convite de primeiro acesso (`invites.py`)."""
    conn.execute("""CREATE TABLE IF NOT EXISTS invites (
      token_hash TEXT PRIMARY KEY,
      practice_id INTEGER NOT NULL REFERENCES practices(id) ON DELETE CASCADE,
      role TEXT NOT NULL CHECK (role IN ('clinician', 'receptionist')),
      created_at TEXT NOT NULL,
      expires_at TEXT NOT NULL,
      used_at TEXT,
      used_by INTEGER REFERENCES users(id) ON DELETE SET NULL)""")


def _platform_v3(conn: sqlite3.Connection) -> None:
    """Os quatro tipos de convite e o registro da plataforma. Os convites que já existem continuam valendo."""
    conn.execute("ALTER TABLE invites RENAME TO invites_v2")
    for name in ("invites", "platform_log"):
        conn.execute(_table(PLATFORM_SCHEMA, name))
    conn.execute("""INSERT INTO invites (token_hash, kind, practice_id, role, created_at, expires_at, used_at, used_by)
                    SELECT token_hash, 'staff', practice_id, role, created_at, expires_at, used_at, used_by
                    FROM invites_v2""")
    conn.execute("DROP TABLE invites_v2")
    conn.execute("ALTER TABLE practices ADD COLUMN requested_domain TEXT")


def _platform_v4(conn: sqlite3.Connection) -> None:
    """A administração vendo como alguém de um consultório: a sessão guarda quem, e o link de entrada leva até lá."""
    for col in ("as_practice_id", "as_user_id", "as_guardian_id"):
        conn.execute(f"ALTER TABLE sessions ADD COLUMN {col} INTEGER")
    conn.execute(_table(PLATFORM_SCHEMA, "handoffs"))


PLATFORM_MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {2: _platform_v2, 3: _platform_v3, 4: _platform_v4}

PRACTICE_VERSION = 3
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
-- a agenda fechada (férias, congresso, folga): de `day` até `end_day`, os dois inclusive; quem fechou fica em created_by
CREATE TABLE schedule_exceptions (
  id INTEGER PRIMARY KEY,
  day TEXT NOT NULL,
  reason TEXT,
  end_day TEXT,
  created_by INTEGER,
  created_at TEXT
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
  created_by INTEGER,
  confirm_asked_at TEXT
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
-- quem viu e fez o quê; actor_id é quem estava de fato, quando a administração entra vendo como alguém (user_id)
CREATE TABLE audit_log (
  id INTEGER PRIMARY KEY,
  at TEXT NOT NULL,
  user_id INTEGER,
  role TEXT,
  action TEXT NOT NULL,
  entity TEXT,
  entity_id INTEGER,
  ip TEXT,
  actor_id INTEGER,
  detail TEXT
);
"""


def _practice_v2(conn: sqlite3.Connection) -> None:
    """O registro guarda quem estava de fato quando a administração entra vendo como alguém."""
    conn.execute("ALTER TABLE audit_log ADD COLUMN actor_id INTEGER")
    conn.execute("ALTER TABLE audit_log ADD COLUMN detail TEXT")


def _practice_v3(conn: sqlite3.Connection) -> None:
    """A agenda fechada por vários dias (e quem fechou) e o pedido de confirmação mandado pela recepção."""
    for col in ("end_day TEXT", "created_by INTEGER", "created_at TEXT"):
        conn.execute(f"ALTER TABLE schedule_exceptions ADD COLUMN {col}")
    conn.execute("ALTER TABLE appointments ADD COLUMN confirm_asked_at TEXT")


PRACTICE_MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {2: _practice_v2, 3: _practice_v3}


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
