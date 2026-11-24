"""Testes contra PostgreSQL real (banco descartável ejmf_test)."""
import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

URL_BASE = os.environ.get("EJMF_TEST_DATABASE_URL", "postgresql+psycopg://ejmf:ejmf@localhost:5433/ejmf_test")
os.environ["EJMF_DATABASE_URL"] = URL_BASE
os.environ["EJMF_AMBIENTE"] = "teste"
os.environ.setdefault("EJMF_CHAVE_SECRETA", "chave-de-teste-" + "x" * 40)

SENHA = "senha-sintetica-123"


def _recriar_banco() -> None:
    url = make_url(URL_BASE)
    adm = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with adm.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{url.database}"'))
    adm.dispose()


@pytest.fixture(scope="session", autouse=True)
def banco():
    from alembic import command
    from alembic.config import Config as AlembicConfig

    from app.core.banco import fabrica_sessao, reiniciar_motor
    from app.core.config import obter_config
    from app.servicos import semente

    obter_config.cache_clear()
    reiniciar_motor()
    _recriar_banco()
    cfg = AlembicConfig(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "migracoes"))
    command.upgrade(cfg, "head")
    with fabrica_sessao()() as db:
        semente.semear(db)
        db.commit()
    yield
    reiniciar_motor()


@pytest.fixture(autouse=True)
def _limpar_limites():
    from app.servicos.autenticacao import limitador_login
    limitador_login.limpar()
    yield


@pytest.fixture
def db():
    from app.core.banco import fabrica_sessao
    with fabrica_sessao()() as s:
        yield s


@pytest.fixture
def app_cliente():
    from fastapi.testclient import TestClient

    from app.main import app
    def _novo() -> TestClient:
        return TestClient(app, headers={"X-Requested-With": "ejmf"})
    return _novo


def criar(db, perfis=("advogado_admin",), senha=SENHA, email=None):
    from app.servicos import auditoria
    from app.servicos.autenticacao import criar_usuario
    from app.servicos.semente import obter_escritorio
    email = email or f"u{uuid.uuid4().hex[:10]}@example.com"
    u = criar_usuario(db, auditoria.Ator(tipo="sistema", escritorio_id=obter_escritorio(db).id),
                      email=email, nome="Usuário Sintético", senha=senha, perfis=list(perfis))
    db.commit()
    return u


@pytest.fixture
def admin(db, app_cliente):
    u = criar(db)
    c = app_cliente()
    r = c.post("/api/v1/auth/login", json={"email": u.email, "senha": SENHA})
    assert r.status_code == 200, r.text
    return c, u


@pytest.fixture
def operador(db, app_cliente):
    u = criar(db, perfis=("operador",))
    c = app_cliente()
    assert c.post("/api/v1/auth/login", json={"email": u.email, "senha": SENHA}).status_code == 200
    return c, u
