"""A configuração: o puericorbs.toml (no git) e, por cima, o data/config.toml (fora do git)."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    port: int = 8930
    data_dir: Path = ROOT / "data"
    timezone: str = "America/Sao_Paulo"
    demo: bool = True
    platform_hosts: tuple[str, ...] = ("localhost", "127.0.0.1")
    base_domains: tuple[str, ...] = ("localhost",)
    session_days: int = 30
    max_upload_mb: int = 25
    extra: dict = field(default_factory=dict)

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


def load(data_dir: str | Path | None = None) -> Settings:
    """Lê as duas camadas. `PUERICORBS_DATA` (ou o argumento) troca a pasta de dados, como nos testes."""
    raw = _read(ROOT / "puericorbs.toml")
    base = Path(data_dir or os.environ.get("PUERICORBS_DATA") or raw.get("data_dir", "data"))
    if not base.is_absolute():
        base = ROOT / base
    raw.update(_read(base / "config.toml"))
    known = {f for f in Settings.__dataclass_fields__ if f != "extra"}
    values = {k: v for k, v in raw.items() if k in known}
    values["data_dir"] = base
    for key in ("platform_hosts", "base_domains"):
        if key in values:
            values[key] = tuple(h.lower() for h in values[key])
    return replace(Settings(), **values, extra={k: v for k, v in raw.items() if k not in known})
