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


@pytest.fixture(autouse=True)
def _sem_tentativas_antigas():
    """As senhas erradas ficam na memória do processo: cada teste começa do zero."""
    from puericorbs import auth
    auth._failures.clear()
    yield


def outro_consultorio(s, domain: str | None = None) -> int:
    """Um consultório de fora (a "Dra. Outra", com a conta outra@demo.test), que nasce com a pediatra na
    administração dele: as fronteiras entre consultórios se testam contra ele."""
    from puericorbs.db import connect_platform
    from puericorbs.practices import create_practice
    pconn = connect_platform(s.data_dir)
    try:
        return create_practice(pconn, s.data_dir, name="Dra. Outra", slug="draoutra", clinician_name="Dra. Outra",
                               clinician_email="outra@demo.test", password="demo1234", domain=domain)
    finally:
        pconn.close()
