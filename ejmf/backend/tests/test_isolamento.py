"""Fase 11: isolamento entre escritórios (ADR-0006).

Um segundo escritório recebe cliente, processo, documento, lançamento e compromisso. Quem é do escritório principal
não vê nada disso em listas, pesquisa, pesquisa no conteúdo, detalhes por id, nem consegue ligar registros seus a ids
do outro escritório.
"""
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.modelos import Escritorio
from app.servicos import agenda, auditoria, clientes, documentos, financeiro, processos

from tests import sinteticos as s

MARCA = "isoladoxq"


@pytest.fixture(scope="module")
def outro():
    from app.core.banco import fabrica_sessao
    with fabrica_sessao()() as db:
        esc = Escritorio(nome="Escritório Sintético B", sigla=f"B{uuid.uuid4().hex[:6]}")
        db.add(esc)
        db.flush()
        ator = auditoria.Ator(tipo="sistema", nome="teste de isolamento", escritorio_id=esc.id)
        cli = clientes.criar(db, ator, esc.id, nome=f"Cliente {MARCA} Sintético", tipo="PF", documento=s.cpf())
        proc = processos.criar(db, ator, esc.id, numero=s.numero(), classe=f"Classe {MARCA}")
        doc, _ = documentos.enviar(db, ator, esc.id, nome=f"{MARCA}.txt", dados=f"conteúdo {MARCA} do outro escritório".encode(),
                                   usuario=None, titulo=f"Documento {MARCA}", cliente_id=cli.id, processo_id=proc.id)
        cat = financeiro.criar_categoria(db, ator, esc.id, f"Honorários {MARCA}", "receita", False)
        lc = financeiro.criar_lancamento(db, ator, esc.id, None, {
            "tipo": "receita", "categoria_id": cat.id, "descricao": f"Receita {MARCA}", "valor": Decimal("123.45"),
            "vencimento": date.today(), "cliente_id": cli.id})
        ini = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(days=1)
        comp = agenda.criar(db, ator, esc.id, {"tipo": "reuniao", "titulo": f"Reunião {MARCA}", "inicio": ini,
                                               "fim": ini + timedelta(hours=1)}, None)
        db.commit()
        ids = {"cliente": cli.id, "processo": proc.id, "documento": doc.id, "categoria": cat.id, "lancamento": lc.id,
               "compromisso": comp.id, "escritorio": esc.id}
    from app.servicos import fila
    with fabrica_sessao()() as db:
        fila.processar(db)  # extração e índice do documento do outro escritório
    return ids


def _vazio(r) -> bool:
    """A resposta não traz nada do outro escritório (a própria pergunta pode voltar ecoada)."""
    assert r.status_code == 200, r.text
    return MARCA not in r.text.replace(f'"{MARCA}"', '""')


def test_listas_e_pesquisas_nao_mostram_o_outro_escritorio(admin, outro, db):
    from sqlalchemy import select

    from app.modelos import TrechoConhecimento, VersaoDocumento
    # controle: o documento do outro escritório foi extraído e indexado, então a pesquisa teria o que achar
    vs = db.execute(select(VersaoDocumento).where(VersaoDocumento.documento_id == outro["documento"])).scalars().all()
    assert any(v.extracao == "concluida" for v in vs), [v.extracao for v in vs]
    assert db.execute(select(TrechoConhecimento).where(TrechoConhecimento.escritorio_id == outro["escritorio"])).first()
    c, _ = admin
    assert _vazio(c.get("/api/v1/clientes", params={"q": MARCA}))
    assert _vazio(c.get("/api/v1/processos", params={"q": MARCA}))
    assert _vazio(c.get("/api/v1/pesquisa", params={"q": MARCA}))
    assert _vazio(c.get("/api/v1/documentos", params={"q": MARCA}))
    assert _vazio(c.get("/api/v1/conhecimento/pesquisa", params={"q": MARCA}))
    assert _vazio(c.get("/api/v1/financeiro/lancamentos"))
    hoje = date.today()
    assert _vazio(c.get("/api/v1/agenda", params={"inicio": hoje.isoformat(), "fim": (hoje + timedelta(days=3)).isoformat()}))
    assert _vazio(c.get("/api/v1/painel"))


def test_detalhe_por_id_do_outro_escritorio_e_404(admin, outro):
    c, _ = admin
    for caminho in (f"/api/v1/clientes/{outro['cliente']}", f"/api/v1/processos/{outro['processo']}",
                    f"/api/v1/documentos/{outro['documento']}", f"/api/v1/documentos/{outro['documento']}/arquivo",
                    f"/api/v1/financeiro/lancamentos/{outro['lancamento']}", f"/api/v1/agenda/{outro['compromisso']}"):
        r = c.get(caminho)
        assert r.status_code == 404, (caminho, r.status_code)
        assert MARCA not in r.text


def test_nao_liga_registro_proprio_a_id_do_outro_escritorio(admin, outro):
    c, _ = admin
    r = c.post("/api/v1/financeiro/lancamentos", json={
        "tipo": "receita", "categoria_id": str(outro["categoria"]), "descricao": "Tentativa sintética", "valor": "10.00",
        "vencimento": date.today().isoformat()})
    assert r.status_code in (404, 422), r.text
    meu = next(x["id"] for x in c.get("/api/v1/financeiro").json()["categorias"] if x["codigo"] == "consultoria")
    r = c.post("/api/v1/financeiro/lancamentos", json={
        "tipo": "receita", "categoria_id": meu, "descricao": "Tentativa sintética", "valor": "10.00",
        "vencimento": date.today().isoformat(), "cliente_id": str(outro["cliente"])})
    assert r.status_code in (404, 422), r.text
    r = c.post("/api/v1/documentos", files={"arquivo": ("x.txt", b"texto sintetico de teste")},
               data={"processo_id": str(outro["processo"])})
    assert r.status_code in (404, 422), r.text
    ini = datetime.now(timezone.utc) + timedelta(days=2)
    r = c.post("/api/v1/agenda", json={"tipo": "reuniao", "titulo": "Tentativa", "inicio": ini.isoformat(),
                                       "fim": (ini + timedelta(hours=1)).isoformat(), "processo_id": str(outro["processo"])})
    assert r.status_code in (404, 422), r.text
    r = c.post(f"/api/v1/processos/{outro['processo']}/anotacoes", json={"texto": "Tentativa"})
    assert r.status_code in (404, 405, 422), r.text
