from sqlalchemy import select

from app.modelos import Auditoria


def test_operador_nao_gerencia_usuarios_e_tentativa_fica_auditada(operador, db):
    c, u = operador
    r = c.post("/api/v1/usuarios", json={"email": "x@example.com", "nome": "X", "senha": "y" * 12, "perfis": ["operador"]})
    assert r.status_code == 403
    assert c.get("/api/v1/usuarios").status_code == 403
    assert c.get("/api/v1/auditoria").status_code == 403
    neg = db.execute(select(Auditoria).where(Auditoria.operacao == "acesso.negado", Auditoria.ator_id == str(u.id))).scalars().all()
    assert len(neg) == 3


def test_operador_le_painel_e_departamentos(operador):
    c, _ = operador
    assert c.get("/api/v1/painel").status_code == 200
    assert c.get("/api/v1/departamentos").status_code == 200
    assert c.put("/api/v1/configuracoes/institucional.cnpj", json={"valor": "1"}).status_code == 403


def test_admin_cria_usuario_com_perfil(admin):
    c, _ = admin
    r = c.post("/api/v1/usuarios", json={"email": "novo.operador@example.com", "nome": "Operador Sintético",
                                         "senha": "senha-longa-sintetica", "perfis": ["operador"]})
    assert r.status_code == 201 and r.json()["perfis"] == ["operador"]
    assert c.post("/api/v1/usuarios", json={"email": "novo.operador@example.com", "nome": "Dup",
                                            "senha": "senha-longa-sintetica", "perfis": ["operador"]}).status_code == 400
    assert c.post("/api/v1/usuarios", json={"email": "p@example.com", "nome": "Pessoa", "senha": "senha-longa-sintetica",
                                            "perfis": ["inexistente"]}).status_code == 400


def test_admin_nao_remove_proprio_acesso(admin):
    c, u = admin
    assert c.patch(f"/api/v1/usuarios/{u.id}", json={"ativo": False}).status_code == 400
    assert c.patch(f"/api/v1/usuarios/{u.id}", json={"perfis": ["operador"]}).status_code == 400


def test_perfis_cliente_e_agente_sem_permissoes(admin):
    c, _ = admin
    perfis = {p["codigo"]: p for p in c.get("/api/v1/perfis").json()}
    assert perfis["cliente"]["permissoes"] == [] and perfis["agente_ia"]["permissoes"] == []
