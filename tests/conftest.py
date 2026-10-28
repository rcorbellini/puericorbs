"""A demonstração semeada numa pasta temporária, e um cliente por endereço (cada domínio é um consultório)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from puericorbs import config, seed
from puericorbs.server import create_app

H = {"X-PC": "1"}


@pytest.fixture(scope="session")
def settings(tmp_path_factory):
    s = config.load(tmp_path_factory.mktemp("dados"))
    seed.run(s, reset=True)
    return s


@pytest.fixture()
def fresh(tmp_path):
    """Uma demonstração só deste teste (para os que mudam dados)."""
    s = config.load(tmp_path)
    seed.run(s, reset=True)
    return s


def client(settings, host: str, who: str | None = None) -> TestClient:
    c = TestClient(create_app(settings), base_url=f"http://{host}")
    if who:
        r = c.post("/api/auth/demo", json={"email": who}, headers=H)
        assert r.status_code == 200, r.text
    return c
