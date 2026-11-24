import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.servicos import auditoria


def test_cadeia_integra(admin, db):
    c, _ = admin
    r = c.get("/api/v1/auditoria/verificar").json()
    assert r["integra"] is True and r["registros_verificados"] > 0


@pytest.mark.parametrize("sql", ["UPDATE auditoria SET operacao = 'x'", "DELETE FROM auditoria", "TRUNCATE auditoria"])
def test_auditoria_imutavel_no_banco(db, sql):
    with pytest.raises(DBAPIError, match="somente inserção"):
        db.execute(text(sql))
    db.rollback()


def test_adulteracao_detectada(db, admin):
    """Desliga o gatilho dentro de uma transação, adultera e verifica; depois desfaz tudo."""
    conexao = db.connection()
    conexao.execute(text("ALTER TABLE auditoria DISABLE TRIGGER tg_auditoria_imutavel"))
    alvo = conexao.execute(text("SELECT min(id) FROM auditoria")).scalar()
    conexao.execute(text("UPDATE auditoria SET resultado = 'adulterado' WHERE id = :i"), {"i": alvo})
    r = auditoria.verificar_cadeia(db)
    db.rollback()
    assert r["integra"] is False and r["primeiro_registro_invalido"] == alvo
    assert auditoria.verificar_cadeia(db)["integra"] is True


def test_mascaramento():
    m = auditoria.mascarar({"senha": "abc", "cpf": "123.456.789-01", "nome": "Fulano",
                            "lista": [{"api_key": "k"}], "institucional_cnpj": "12345678000199"})
    assert m["senha"] == "***" and m["cpf"].endswith("01") and "456" not in m["cpf"]
    assert m["nome"] == "Fulano" and m["lista"][0]["api_key"] == "***" and m["institucional_cnpj"].endswith("99")


def test_alteracao_de_configuracao_auditada_com_antes_e_depois(admin, db):
    c, u = admin
    assert c.put("/api/v1/configuracoes/operacao.relatorio_diario_hora", json={"valor": "06:45"}).status_code == 200
    regs = c.get("/api/v1/auditoria", params={"operacao": "configuracao.alterar",
                                                "entidade_id": "operacao.relatorio_diario_hora"}).json()
    assert regs[0]["alteracoes"]["depois"] == "06:45"
    assert regs[0]["ator_nome"] == u.nome and regs[0]["trace_id"]
    c.put("/api/v1/configuracoes/operacao.relatorio_diario_hora", json={"valor": "06:30"})


def test_trace_id_propagado(admin):
    c, _ = admin
    r = c.get("/api/v1/painel", headers={"X-Trace-Id": "teste-trace-123"})
    assert r.headers["X-Trace-Id"] == "teste-trace-123"
