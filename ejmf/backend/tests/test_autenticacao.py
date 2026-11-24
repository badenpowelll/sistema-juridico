import pyotp
from sqlalchemy import select

from app.modelos import Auditoria, Usuario
from tests.conftest import SENHA, criar


def test_login_define_cookie_httponly_e_eu(admin):
    c, u = admin
    r = c.get("/api/v1/auth/eu")
    assert r.status_code == 200
    assert r.json()["email"] == u.email
    assert "painel:ler" in r.json()["permissoes"]


def test_cookie_e_httponly_samesite(db, app_cliente):
    u = criar(db)
    r = app_cliente().post("/api/v1/auth/login", json={"email": u.email, "senha": SENHA})
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_sem_sessao_401(app_cliente):
    assert app_cliente().get("/api/v1/painel").status_code == 401


def test_senha_errada_mensagem_generica_e_auditada(db, app_cliente):
    u = criar(db)
    c = app_cliente()
    r1 = c.post("/api/v1/auth/login", json={"email": u.email, "senha": "errada-errada-errada"})
    r2 = c.post("/api/v1/auth/login", json={"email": "naoexiste@example.com", "senha": "errada-errada-errada"})
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["detail"] == r2.json()["detail"]
    neg = db.execute(select(Auditoria).where(Auditoria.operacao == "auth.login", Auditoria.entidade_id == str(u.id),
                                             Auditoria.resultado == "negado")).scalars().all()
    assert len(neg) == 1
    assert "errada" not in str(neg[0].alteracoes)


def test_bloqueio_apos_cinco_falhas(db, app_cliente):
    u = criar(db)
    c = app_cliente()
    for _ in range(5):
        assert c.post("/api/v1/auth/login", json={"email": u.email, "senha": "errada-errada-x"}).status_code == 401
    r = c.post("/api/v1/auth/login", json={"email": u.email, "senha": SENHA})
    assert r.status_code == 423


def test_rate_limit_por_ip(db, app_cliente, monkeypatch):
    from app.core.config import obter_config
    monkeypatch.setattr(obter_config(), "login_limite_por_minuto_ip", 3)
    c = app_cliente()
    codigos = [c.post("/api/v1/auth/login", json={"email": "x@example.com", "senha": "y" * 12}).status_code for _ in range(4)]
    assert codigos == [401, 401, 401, 429]


def test_csrf_exige_cabecalho(db):
    from fastapi.testclient import TestClient
    from app.main import app
    u = criar(db)
    r = TestClient(app).post("/api/v1/auth/login", json={"email": u.email, "senha": SENHA})
    assert r.status_code == 403


def test_sair_revoga_sessao(admin):
    c, _ = admin
    assert c.post("/api/v1/auth/sair").status_code == 200
    assert c.get("/api/v1/auth/eu").status_code == 401


def test_usuario_inativo_nao_entra(db, app_cliente):
    u = criar(db)
    db.get(Usuario, u.id).ativo = False
    db.commit()
    assert app_cliente().post("/api/v1/auth/login", json={"email": u.email, "senha": SENHA}).status_code == 401


def test_desativar_usuario_derruba_sessoes(admin, db, app_cliente):
    c_admin, _ = admin
    outro = criar(db, perfis=("operador",))
    c_outro = app_cliente()
    c_outro.post("/api/v1/auth/login", json={"email": outro.email, "senha": SENHA})
    assert c_outro.get("/api/v1/auth/eu").status_code == 200
    assert c_admin.patch(f"/api/v1/usuarios/{outro.id}", json={"ativo": False}).status_code == 200
    assert c_outro.get("/api/v1/auth/eu").status_code == 401


def test_revogar_outras_sessoes(db, app_cliente):
    u = criar(db)
    a, b = app_cliente(), app_cliente()
    for c in (a, b):
        c.post("/api/v1/auth/login", json={"email": u.email, "senha": SENHA})
    assert len(a.get("/api/v1/auth/sessoes").json()) == 2
    assert a.post("/api/v1/auth/sessoes/revogar-outras").json()["sessoes_revogadas"] == 1
    assert b.get("/api/v1/auth/eu").status_code == 401
    assert a.get("/api/v1/auth/eu").status_code == 200


def test_trocar_senha(db, app_cliente):
    u = criar(db)
    c = app_cliente()
    c.post("/api/v1/auth/login", json={"email": u.email, "senha": SENHA})
    assert c.post("/api/v1/auth/senha", json={"senha_atual": "errada", "senha_nova": "nova-senha-longa-1"}).status_code == 400
    assert c.post("/api/v1/auth/senha", json={"senha_atual": SENHA, "senha_nova": "nova-senha-longa-1"}).status_code == 200
    assert app_cliente().post("/api/v1/auth/login", json={"email": u.email, "senha": SENHA}).status_code == 401
    assert app_cliente().post("/api/v1/auth/login", json={"email": u.email, "senha": "nova-senha-longa-1"}).status_code == 200


def test_fluxo_mfa_completo(db, app_cliente):
    u = criar(db)
    c = app_cliente()
    c.post("/api/v1/auth/login", json={"email": u.email, "senha": SENHA})
    cfg = c.post("/api/v1/auth/mfa/configurar").json()
    assert cfg["uri"].startswith("otpauth://totp/")
    totp = pyotp.TOTP(cfg["segredo"])
    assert c.post("/api/v1/auth/mfa/ativar", json={"codigo": "000000" if totp.now() != "000000" else "111111"}).status_code == 400
    assert c.post("/api/v1/auth/mfa/ativar", json={"codigo": totp.now()}).status_code == 200
    # segredo fica cifrado no banco
    db.expire_all()
    assert cfg["segredo"] not in (db.get(Usuario, u.id).mfa_segredo_cifrado or "")

    novo = app_cliente()
    r = novo.post("/api/v1/auth/login", json={"email": u.email, "senha": SENHA})
    assert r.json()["mfa_necessario"] is True
    assert novo.get("/api/v1/painel").status_code == 401  # sessão parcial não acessa nada
    assert novo.get("/api/v1/auth/eu").json()["mfa_pendente"] is True
    assert novo.post("/api/v1/auth/mfa/verificar", json={"codigo": "999999" if totp.now() != "999999" else "888888"}).status_code == 401
    assert novo.post("/api/v1/auth/mfa/verificar", json={"codigo": totp.now()}).status_code == 200
    assert novo.get("/api/v1/painel").status_code == 200


def test_mfa_obrigatorio_para_admin(db, app_cliente, monkeypatch):
    from app.core.config import obter_config
    monkeypatch.setattr(obter_config(), "mfa_obrigatorio_admin", True)
    u = criar(db)
    c = app_cliente()
    c.post("/api/v1/auth/login", json={"email": u.email, "senha": SENHA})
    assert c.get("/api/v1/painel").status_code == 403
    assert c.get("/api/v1/auth/eu").json()["mfa_obrigatorio"] is True
    assert c.post("/api/v1/auth/mfa/configurar").status_code == 200
