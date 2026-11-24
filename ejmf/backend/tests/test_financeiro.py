"""Fase 9 contra PostgreSQL real: contratos de honorários e parcelas, previsto/faturado/recebido, recebimento parcial,
estorno e cancelamento, recibos com o modelo homologado, conciliação de extrato OFX e CSV, lembretes que só aparecem no
portal depois de autorizados, relatórios, exportação, permissões, automação de honorário pendente e funções 26 a 30."""
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.modelos import Aprovacao, Auditoria, Cliente, LembreteCobranca, Lancamento, Minuta, ModeloDocumento, Processo
from app.servicos import automacoes, financeiro as fin, financeiro_relatorios as rel, portal
from app.servicos.ia import funcoes  # noqa: F401  (registra os executores)
from app.servicos.semente import obter_escritorio
from tests import sinteticos as s

API = "/api/v1/financeiro"


# ================================================================ apoio

def _ok(r, status=200):
    assert r.status_code == status, r.text
    return r.json()


def _cliente(c):
    return _ok(c.post("/api/v1/clientes", json={"nome": s.nome(), "tipo": "PF", "documento": s.cpf()}), 201)


def _processo(c, cli=None):
    corpo = {"numero": s.numero(), "classe": "Procedimento Comum Cível"}
    if cli:
        corpo["partes"] = [{"nome": cli["nome"], "polo": "ativo", "cliente_id": cli["id"]}]
    return _ok(c.post("/api/v1/processos", json=corpo), 201)


def _geral(c):
    return _ok(c.get(API))


def _cat(c, codigo):
    return next(x["id"] for x in _geral(c)["categorias"] if x["codigo"] == codigo)


def _conta(c, nome=None, saldo="1000.00", data=None):
    return _ok(c.post(f"{API}/contas", json={"nome": nome or f"Conta sintética {uuid.uuid4().hex[:6]}", "saldo_inicial": saldo,
                                             "data_saldo_inicial": (data or date.today() - timedelta(days=400)).isoformat()}), 201)


def _lancar(c, tipo="receita", cat="honorarios_contratuais", valor="500.00", venc=None, **kw):
    corpo = {"tipo": tipo, "categoria_id": _cat(c, cat), "descricao": kw.pop("descricao", f"Lançamento sintético {tipo}"),
             "valor": valor, "vencimento": (venc or date.today()).isoformat(), **kw}
    return _ok(c.post(f"{API}/lancamentos", json=corpo), 201)


def _liquidar(c, lid, conta, data=None, **kw):
    return _ok(c.post(f"{API}/lancamentos/{lid}/liquidar", json={"data": (data or date.today()).isoformat(), "conta_id": conta, **kw}))


# ================================================================ regras puras

def test_extenso_divisao_e_meses():
    assert fin.extenso("1500") == "mil e quinhentos reais"
    assert fin.extenso("1234.56") == "mil duzentos e trinta e quatro reais e cinquenta e seis centavos"
    assert fin.extenso("1") == "um real" and fin.extenso("0.01") == "um centavo" and fin.extenso("100") == "cem reais"
    assert fin.extenso("2000000") == "dois milhões de reais" and fin.extenso("101") == "cento e um reais"
    assert fin.dividir(Decimal("1000"), 3) == [Decimal("333.33"), Decimal("333.33"), Decimal("333.34")]
    assert sum(fin.dividir(Decimal("999.99"), 7)) == Decimal("999.99")
    assert fin.somar_meses(date(2027, 1, 31), 1) == date(2027, 2, 28) and fin.somar_meses(date(2027, 11, 30), 3) == date(2028, 2, 29)
    assert fin.moeda("1234567.8") == "R$ 1.234.567,80"
    with pytest.raises(fin.ErroFinanceiro):
        fin.dinheiro("abc")


# ================================================================ contratos

def test_contrato_parcelado_mensal_exito_e_cancelamento(db, admin):
    c, _ = admin
    cli = _cliente(c)
    proc = _processo(c, cli)
    base = {"cliente_id": cli["id"], "processo_id": proc["id"], "descricao": "Honorários da ação sintética"}
    ct = _ok(c.post(f"{API}/contratos", json={**base, "modalidade": "parcelado", "valor_fixo": "1000.00", "parcelas": 3,
                                              "primeiro_vencimento": "2027-01-31"}), 201)
    ls = ct["lancamentos"]
    assert [x["valor"] for x in ls] == ["333.33", "333.33", "333.34"]
    assert [x["vencimento"] for x in ls] == ["2027-01-31", "2027-02-28", "2027-03-31"]
    assert all(x["situacao"] == "previsto" and x["processo_id"] == proc["id"] for x in ls) and ls[0]["parcela"] == 1
    assert ct["totais"]["contratado"] == "1000.00" and ct["numero"].count("/") == 1
    m = _ok(c.post(f"{API}/contratos", json={**base, "modalidade": "mensal", "valor_fixo": "300", "parcelas": 12,
                                             "primeiro_vencimento": "2027-01-10"}), 201)
    assert m["totais"]["contratado"] == "3600.00" and len(m["lancamentos"]) == 12
    # erros de modalidade
    assert c.post(f"{API}/contratos", json={**base, "modalidade": "exito"}).status_code == 422
    assert c.post(f"{API}/contratos", json={**base, "modalidade": "parcelado", "valor_fixo": "100", "parcelas": 1,
                                            "primeiro_vencimento": "2027-01-10"}).status_code == 422
    assert c.post(f"{API}/contratos", json={**base, "modalidade": "fixo", "valor_fixo": "100", "percentual_exito": "10",
                                            "primeiro_vencimento": "2027-01-10"}).status_code == 422
    outro = _cliente(c)
    assert c.post(f"{API}/contratos", json={**base, "cliente_id": outro["id"], "modalidade": "exito",
                                            "percentual_exito": "20"}).status_code == 422  # não é parte do processo
    # êxito: a base é informada por pessoa, o sistema só aplica o percentual
    ex = _ok(c.post(f"{API}/contratos", json={**base, "modalidade": "exito", "percentual_exito": "20"}), 201)
    assert ex["lancamentos"] == []
    lc = _ok(c.post(f"{API}/contratos/{ex['id']}/exito", json={"base": "50000.00", "vencimento": "2027-06-30"}), 201)
    assert lc["valor"] == "10000.00" and "20.00% sobre R$ 50.000,00" in lc["observacao"]
    sem_venc = c.post(f"{API}/contratos", json={**base, "modalidade": "fixo", "valor_fixo": "800"})
    assert sem_venc.status_code == 422 and "vencimento" in sem_venc.json()["detail"]
    assert c.post(f"{API}/contratos/{ct['id']}/exito", json={"base": "100", "vencimento": "2027-06-30"}).status_code == 422
    # cancelar cancela só o que não foi recebido
    conta = _conta(c)
    _liquidar(c, ls[0]["id"], conta["id"], data=date.today())
    r = _ok(c.post(f"{API}/contratos/{ct['id']}/encerrar", json={"situacao": "cancelado", "motivo": "Cliente desistiu da ação"}))
    assert r["parcelas_canceladas"] == 2 and r["situacao"] == "cancelado"
    assert [x["situacao"] for x in r["lancamentos"]] == ["liquidado", "cancelado", "cancelado"]
    assert c.post(f"{API}/contratos/{ct['id']}/encerrar", json={"situacao": "encerrado", "motivo": "de novo"}).status_code == 409


# ================================================================ lançamentos

def test_lancamento_valida_vinculos_e_ciclo_previsto_faturado_recebido(db, admin):
    c, u = admin
    cli = _cliente(c)
    proc = _processo(c)
    conta = _conta(c)
    assert c.post(f"{API}/lancamentos", json={"tipo": "receita", "categoria_id": _cat(c, "custas_processuais"), "descricao": "x" * 5,
                                              "valor": "10", "vencimento": "2027-01-01"}).status_code == 422  # categoria de despesa
    assert c.post(f"{API}/lancamentos", json={"tipo": "receita", "categoria_id": _cat(c, "consultoria"), "descricao": "Parecer",
                                              "valor": "0", "vencimento": "2027-01-01"}).status_code == 422
    assert c.post(f"{API}/lancamentos", json={"tipo": "receita", "categoria_id": _cat(c, "consultoria"), "descricao": "Parecer",
                                              "valor": "10", "vencimento": "2027-01-01", "cliente_id": cli["id"],
                                              "processo_id": proc["id"]}).status_code == 422  # cliente não é parte
    assert c.post(f"{API}/lancamentos", json={"tipo": "despesa", "categoria_id": _cat(c, "custas_processuais"), "descricao": "Custas",
                                              "valor": "10", "vencimento": "2027-01-01", "portal_visivel": True,
                                              "cliente_id": cli["id"]}).status_code == 422
    assert c.post(f"{API}/lancamentos", json={"tipo": "receita", "categoria_id": _cat(c, "consultoria"), "descricao": "Parecer",
                                              "valor": "10.001", "vencimento": "2027-01-01"}).status_code == 422  # três casas
    lc = _lancar(c, cat="consultoria", valor="1200.00", venc=date.today() - timedelta(days=3), cliente_id=cli["id"],
                 descricao="Parecer sintético")
    assert lc["vencido"] and lc["dias_atraso"] == 3 and lc["situacao_rotulo"] == "Previsto"
    assert lc["competencia"] == (date.today() - timedelta(days=3)).replace(day=1).isoformat()
    f = _ok(c.post(f"{API}/lancamentos/{lc['id']}/faturar", json={}))
    assert f["situacao"] == "faturado" and f["faturado_em"] == date.today().isoformat()
    assert c.post(f"{API}/lancamentos/{lc['id']}/faturar", json={}).status_code == 409
    # recebimento no futuro não existe
    assert c.post(f"{API}/lancamentos/{lc['id']}/liquidar", json={"data": (date.today() + timedelta(days=1)).isoformat(),
                                                                  "conta_id": conta["id"]}).status_code == 422
    # parcial: desdobra o saldo num lançamento novo, ainda faturado
    r = _liquidar(c, lc["id"], conta["id"], valor="700.00", forma="pix")
    assert r["situacao"] == "liquidado" and r["valor"] == "700.00" and r["situacao_rotulo"] == "Recebido" and r["forma_rotulo"] == "Pix"
    saldo = _ok(c.get(f"{API}/lancamentos/{r['saldo_id']}"))
    assert saldo["valor"] == "500.00" and saldo["situacao"] == "faturado" and saldo["origem_id"] == lc["id"]
    assert "Recebimento parcial" in r["observacao"]
    contas = {x["id"]: x for x in _geral(c)["contas"]}
    assert contas[conta["id"]]["saldo_atual"] == "1700.00"
    # alterar só em aberto; cancelar exige motivo; recebido não cancela
    assert c.patch(f"{API}/lancamentos/{lc['id']}", json={"valor": "1"}).status_code == 409
    assert c.post(f"{API}/lancamentos/{lc['id']}/cancelar", json={"motivo": "Lançado errado"}).status_code == 409
    a = _ok(c.patch(f"{API}/lancamentos/{saldo['id']}", json={"vencimento": "2027-05-20"}))
    assert a["competencia"] == "2027-05-01"
    assert c.post(f"{API}/lancamentos/{saldo['id']}/cancelar", json={"motivo": "x"}).status_code == 422
    cx = _ok(c.post(f"{API}/lancamentos/{saldo['id']}/cancelar", json={"motivo": "Saldo perdoado pelo advogado"}))
    assert cx["situacao"] == "cancelado"
    # estorno volta ao estado anterior
    e = _ok(c.post(f"{API}/lancamentos/{lc['id']}/estornar", json={"motivo": "Pix devolvido pelo banco"}))
    assert e["situacao"] == "faturado" and e["liquidado_em"] is None and "Estornado" in e["observacao"]
    ops = set(db.execute(select(Auditoria.operacao).where(Auditoria.entidade_id == lc["id"])).scalars())
    assert {"financeiro.lancar", "financeiro.faturar", "financeiro.liquidar", "financeiro.estornar"} <= ops
    # listagem com filtros e somas
    lst = _ok(c.get(f"{API}/lancamentos", params={"cliente_id": cli["id"]}))
    assert lst["total"] == 2 and lst["somas"]["receitas_abertas"] == "700.00"  # original estornado + saldo cancelado


def test_permissoes_do_operador(db, admin, operador):
    c, _ = admin
    o, _ = operador
    conta = _conta(c)
    lc = _lancar(o, tipo="despesa", cat="diligencias", valor="80.00", descricao="Cópias sintéticas")
    assert o.post(f"{API}/lancamentos/{lc['id']}/liquidar", json={"data": date.today().isoformat(),
                                                                  "conta_id": conta["id"]}).status_code == 403
    assert o.get(f"{API}/exportar/lancamentos.csv").status_code == 403
    assert o.post(f"{API}/contas/{conta['id']}/extrato", files={"arquivo": ("x.csv", b"data;valor\n")}).status_code == 403
    assert o.patch(f"{API}/contas/{conta['id']}", json={"saldo_inicial": "1"}).status_code == 403
    assert _ok(o.get(API))["pode"] == {"gerenciar": True, "liquidar": False, "conciliar": False, "recibos": False, "cobrar": False,
                                       "exportar": False}
    _liquidar(c, lc["id"], conta["id"])
    assert o.post(f"{API}/lancamentos/{lc['id']}/recibo", json={}).status_code == 403


# ================================================================ recibos

def test_recibo_numerado_com_modelo_homologado(db, admin):
    c, _ = admin
    cli = _cliente(c)
    conta = _conta(c)
    lc = _lancar(c, valor="1500.00", cliente_id=cli["id"], descricao="Honorários da consulta sintética")
    assert c.post(f"{API}/lancamentos/{lc['id']}/recibo", json={}).status_code == 409  # ainda não recebido
    _liquidar(c, lc["id"], conta["id"])
    esc = obter_escritorio(db)
    modelo = db.execute(select(ModeloDocumento).where(ModeloDocumento.escritorio_id == esc.id,
                                                      ModeloDocumento.codigo == "recibo_honorarios")).scalars().all()
    if all(m.situacao != "homologado" for m in modelo):
        r = _ok(c.post(f"{API}/lancamentos/{lc['id']}/recibo", json={}), 201)
        assert r["minuta_id"] is None and "não foi homologado" in r["aviso"]
        _ok(c.post(f"{API}/recibos/{r['id']}/cancelar", json={"motivo": "Gerar de novo com o modelo"}))
        _ok(c.post(f"/api/v1/modelos/{modelo[-1].id}/homologar"))
    r = _ok(c.post(f"{API}/lancamentos/{lc['id']}/recibo", json={"referente": "honorários advocatícios da consulta"}), 201)
    assert r["minuta_id"] and r["valor_extenso"] == "mil e quinhentos reais" and r["aviso"] is None
    m = db.get(Minuta, uuid.UUID(r["minuta_id"]))
    assert "R$ 1.500,00 (mil e quinhentos reais)" in m.conteudo and r["numero"] in m.conteudo and m.situacao == "rascunho"
    assert c.post(f"{API}/lancamentos/{lc['id']}/recibo", json={}).status_code == 409  # um recibo ativo por recebimento
    assert c.post(f"{API}/lancamentos/{lc['id']}/estornar", json={"motivo": "Teste de estorno"}).status_code == 409
    cx = _ok(c.post(f"{API}/recibos/{r['id']}/cancelar", json={"motivo": "Emitido com o referente errado"}))
    assert cx["situacao"] == "cancelado"
    db.expire_all()
    assert db.get(Minuta, uuid.UUID(r["minuta_id"])).situacao == "arquivada"
    assert _ok(c.post(f"{API}/lancamentos/{lc['id']}/estornar", json={"motivo": "Teste de estorno"}))["situacao"] == "previsto"


# ================================================================ conciliação

OFX = """OFXHEADER:100
DATA:OFXSGML
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>{d1}120000[-3:BRT]<TRNAMT>2345.67<FITID>{u}A<MEMO>PIX RECEBIDO {nome}
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>{d2}<TRNAMT>-19.90<FITID>{u}B<MEMO>TARIFA PACOTE
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>{d2}<TRNAMT>-55.00<FITID>{u}C<MEMO>COMPRA SEM LANCAMENTO
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


def test_conciliacao_ofx_sugere_concilia_cria_ignora_e_nao_repete(db, admin):
    c, _ = admin
    cli = _cliente(c)
    conta = _conta(c)
    hoje = date.today()
    lc = _lancar(c, valor="2345.67", venc=hoje - timedelta(days=2), cliente_id=cli["id"], descricao="Parcela sintética")
    u = uuid.uuid4().hex[:8]
    ofx = OFX.format(d1=(hoje - timedelta(days=1)).strftime("%Y%m%d"), d2=hoje.strftime("%Y%m%d"), u=u, nome=cli["nome"].upper())
    e = _ok(c.post(f"{API}/contas/{conta['id']}/extrato", files={"arquivo": ("extrato.ofx", ofx.encode("cp1252"))}), 201)
    assert e["formato"] == "ofx" and e["linhas_novas"] == 3 and e["linhas_repetidas"] == 0
    assert c.post(f"{API}/contas/{conta['id']}/extrato", files={"arquivo": ("extrato.ofx", ofx.encode("cp1252"))}).status_code == 409
    # outro arquivo com uma linha repetida (mesmo FITID) e uma nova
    ofx2 = ofx.replace(f"{u}C<MEMO>COMPRA SEM LANCAMENTO", f"{u}D<MEMO>OUTRA COMPRA").replace("-55.00", "-12.00")
    e2 = _ok(c.post(f"{API}/contas/{conta['id']}/extrato", files={"arquivo": ("extrato2.ofx", ofx2.encode())}), 201)
    assert e2["linhas_novas"] == 1 and e2["linhas_repetidas"] == 2
    ex = _ok(c.get(f"{API}/contas/{conta['id']}/extrato"))
    linhas = {x["descricao"]: x for x in ex["linhas"]}
    credito = next(x for d, x in linhas.items() if d.startswith("PIX RECEBIDO"))
    sug = credito["sugestoes"][0]
    assert sug["lancamento"]["id"] == lc["id"] and "nome do cliente na descrição" in sug["motivos"]
    tarifa = linhas["TARIFA PACOTE"]
    assert tarifa["sentido"] == "saida" and tarifa["valor"] == "-19.90"
    # valor diferente ou sentido errado não concilia
    outro = _lancar(c, valor="2345.66", venc=hoje)
    assert c.post(f"{API}/extrato/{credito['id']}/conciliar", json={"lancamento_id": outro["id"]}).status_code == 422
    r = _ok(c.post(f"{API}/extrato/{credito['id']}/conciliar", json={"lancamento_id": lc["id"]}))
    assert r["situacao"] == "conciliada"
    l2 = _ok(c.get(f"{API}/lancamentos/{lc['id']}"))
    assert l2["situacao"] == "liquidado" and l2["liquidado_em"] == (hoje - timedelta(days=1)).isoformat() and l2["conta_id"] == conta["id"]
    assert l2["conciliacao"]["id"] == credito["id"]
    assert c.post(f"{API}/lancamentos/{lc['id']}/estornar", json={"motivo": "Teste de estorno"}).status_code == 409
    assert c.post(f"{API}/extrato/{credito['id']}/conciliar", json={"lancamento_id": lc["id"]}).status_code == 409
    # tarifa vira lançamento já conciliado; a compra é ignorada com motivo
    t = _ok(c.post(f"{API}/extrato/{tarifa['id']}/lancar", json={"categoria_id": _cat(c, "tarifas_bancarias"),
                                                                 "descricao": "Tarifa do pacote"}), 201)
    assert t["lancamento"]["tipo"] == "despesa" and t["lancamento"]["valor"] == "19.90" and t["lancamento"]["situacao"] == "liquidado"
    compra = linhas["COMPRA SEM LANCAMENTO"]
    assert c.post(f"{API}/extrato/{compra['id']}/ignorar", json={"motivo": "x"}).status_code == 422
    assert _ok(c.post(f"{API}/extrato/{compra['id']}/ignorar", json={"motivo": "Despesa pessoal"}))["situacao"] == "ignorada"
    assert _ok(c.post(f"{API}/extrato/{compra['id']}/desfazer"))["situacao"] == "pendente"
    # desfazer a conciliação libera o estorno
    _ok(c.post(f"{API}/extrato/{credito['id']}/desfazer"))
    assert _ok(c.post(f"{API}/lancamentos/{lc['id']}/estornar", json={"motivo": "Teste de estorno"}))["situacao"] == "previsto"
    res = _ok(c.get(f"{API}/contas/{conta['id']}/extrato", params={"situacao": "todas"}))["resumo"]
    assert res["pendentes"] == 3 and res["conciliadas"] == 1


def test_conciliacao_csv_com_credito_e_debito(db, admin):
    c, _ = admin
    conta = _conta(c)
    csv = ("Extrato da conta\nData;Histórico;Crédito;Débito\n01/11/2026;SALDO ANTERIOR;;\n"
           "03/11/2026;DEP DINHEIRO;1.234,50;\n04/11/2026;BOLETO ALUGUEL;;2.000,00\n04/11/2026;BOLETO ALUGUEL;;2.000,00\n")
    e = _ok(c.post(f"{API}/contas/{conta['id']}/extrato", files={"arquivo": ("extrato.csv", csv.encode("cp1252"))}), 201)
    assert e["formato"] == "csv" and e["linhas_novas"] == 3  # duas linhas iguais são dois lançamentos
    ls = _ok(c.get(f"{API}/contas/{conta['id']}/extrato"))["linhas"]
    assert sorted(x["valor"] for x in ls) == ["-2000.00", "-2000.00", "1234.50"]
    assert c.post(f"{API}/contas/{conta['id']}/extrato", files={"arquivo": ("ruim.csv", b"a;b\n1;2\n")}).status_code == 422


# ================================================================ lembretes e portal

def test_lembrete_so_aparece_no_portal_depois_de_autorizado(db, admin, operador):
    c, _ = admin
    o, _ = operador
    cli = _cliente(c)
    escondido = _lancar(c, valor="300.00", venc=date.today() - timedelta(days=10), cliente_id=cli["id"])
    assert o.post(f"{API}/lancamentos/{escondido['id']}/lembrete", json={}).status_code == 422  # não visível no portal
    lc = _lancar(c, valor="450.00", venc=date.today() - timedelta(days=10), cliente_id=cli["id"], portal_visivel=True,
                 descricao="Honorários sintéticos de outubro")
    cliente = db.get(Cliente, uuid.UUID(cli["id"]))
    no_portal = portal.financeiro_do_cliente(db, cliente)
    assert [x["descricao"] for x in no_portal["itens"]] == ["Honorários sintéticos de outubro"]
    assert no_portal["itens"][0]["situacao"] == "vencido" and no_portal["lembretes"] == [] and no_portal["em_aberto"] == "450.00"
    # operador prepara: vira pedido de aprovação; ele não decide
    le = _ok(o.post(f"{API}/lancamentos/{lc['id']}/lembrete", json={}), 201)
    assert le["situacao"] == "aguardando_aprovacao" and "R$ 450,00" in le["texto"]
    assert o.post(f"{API}/lancamentos/{lc['id']}/lembrete", json={}).status_code == 409
    ap = db.execute(select(Aprovacao).where(Aprovacao.entidade_id == le["id"])).scalar_one()
    assert ap.tipo == "lembrete_cobranca" and ap.permissao == "financeiro:cobrar"
    db.expire_all()
    assert portal.financeiro_do_cliente(db, cliente)["lembretes"] == []
    assert o.post(f"/api/v1/aprovacoes/{ap.id}/decidir", json={"decisao": "aprovar"}).status_code in (403, 409)
    _ok(c.post(f"/api/v1/aprovacoes/{ap.id}/decidir", json={"decisao": "aprovar"}))
    db.expire_all()
    pub = portal.financeiro_do_cliente(db, cliente)["lembretes"]
    assert len(pub) == 1 and "450,00" in pub[0]["texto"]
    # recebido, o lembrete continua no histórico mas o item aparece pago; cancelado some do portal
    conta = _conta(c)
    _liquidar(c, lc["id"], conta["id"])
    db.expire_all()
    assert portal.financeiro_do_cliente(db, cliente)["itens"][0]["situacao"] == "pago"
    # advogado prepara direto: já sai autorizado
    lc2 = _lancar(c, valor="99.00", venc=date.today(), cliente_id=cli["id"], portal_visivel=True)
    le2 = _ok(c.post(f"{API}/lancamentos/{lc2['id']}/lembrete", json={"texto": "Lembrete sintético escrito pelo advogado."}), 201)
    assert le2["situacao"] == "publicado"
    _ok(c.post(f"{API}/lancamentos/{lc2['id']}/cancelar", json={"motivo": "Valor perdoado"}))
    db.expire_all()
    assert db.get(LembreteCobranca, uuid.UUID(le2["id"])).situacao == "retirado"
    assert all(x["id"] != lc2["id"] for x in portal.financeiro_do_cliente(db, cliente)["itens"])


# ================================================================ relatórios e exportação

def test_resumo_fluxo_rentabilidade_e_exportacao(db, admin):
    c, _ = admin
    esc = obter_escritorio(db)
    hoje = date.today()
    cli = _cliente(c)
    proc = _processo(c, cli)
    antes = rel.resumo_anual(db, esc.id, hoje.year)["meses"][hoje.month - 1]
    conta = _conta(c, saldo="500.00", data=hoje - timedelta(days=60))
    r1 = _lancar(c, valor="2000.00", venc=hoje, cliente_id=cli["id"], processo_id=proc["id"])
    _liquidar(c, r1["id"], conta["id"])
    d1 = _lancar(c, tipo="despesa", cat="pericias", valor="300.00", venc=hoje, processo_id=proc["id"])
    _liquidar(c, d1["id"], conta["id"])
    d2 = _lancar(c, tipo="despesa", cat="aluguel", valor="1000.00", venc=hoje)  # operacional: não entra no processo
    _liquidar(c, d2["id"], conta["id"])
    futuro = _lancar(c, valor="700.00", venc=hoje + timedelta(days=10), cliente_id=cli["id"], processo_id=proc["id"])
    db.expire_all()
    depois = rel.resumo_anual(db, esc.id, hoje.year)["meses"][hoje.month - 1]
    dif = lambda k: Decimal(depois[k]) - Decimal(antes[k])  # noqa: E731
    assert dif("receitas_recebidas") == Decimal("2000.00") and dif("despesas_pagas") == Decimal("1300.00")
    assert dif("resultado_caixa") == Decimal("700.00")
    fluxo = _ok(c.get(f"{API}/relatorios/fluxo", params={"de": hoje.isoformat(), "ate": (hoje + timedelta(days=20)).isoformat(),
                                                          "agrupar": "dia"}))
    assert len(fluxo["linhas"]) == 21
    dia_fut = next(x for x in fluxo["linhas"] if x["inicio"] == (hoje + timedelta(days=10)).isoformat())
    assert Decimal(dia_fut["entradas_previstas"]) >= Decimal("700.00")
    assert c.get(f"{API}/relatorios/fluxo", params={"de": "2027-01-10", "ate": "2027-01-01"}).status_code == 422
    rent = _ok(c.get(f"{API}/relatorios/rentabilidade", params={"de": (hoje - timedelta(days=1)).isoformat(), "ate": hoje.isoformat()}))
    item = next(x for x in rent["itens"] if x["id"] == proc["id"])
    assert item["receitas"] == "2000.00" and item["despesas"] == "300.00" and item["resultado"] == "1700.00"
    assert item["margem_percentual"] == "85.0" and Decimal(rent["totais"]["custos_operacionais"]) >= Decimal("1000.00")
    contas = {x["id"]: x for x in _geral(c)["contas"]}
    assert contas[conta["id"]]["saldo_atual"] == "1200.00"  # 500 + 2000 − 300 − 1000
    # processo mostra o financeiro dele
    pr = _ok(c.get(f"/api/v1/processos/{proc['id']}"))
    assert pr["financeiro"]["totais"] == {"recebido": "2000.00", "a_receber": "700.00", "despesas_pagas": "300.00",
                                          "despesas_a_pagar": "0.00", "resultado": "1700.00"} and pr["modulos_futuros"] == []
    # exportação: BOM, ponto e vírgula, vírgula decimal e fórmula neutralizada
    _lancar(c, valor="10.00", venc=hoje, cliente_id=cli["id"], descricao="=HYPERLINK(\"http://exemplo.invalid\")")
    r = c.get(f"{API}/exportar/lancamentos.csv", params={"cliente_id": cli["id"]})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    texto = r.content.decode("utf-8")
    assert texto.startswith("﻿Tipo;Situação;") and "2000,00" in texto and "'=HYPERLINK" in texto
    assert db.execute(select(Auditoria).where(Auditoria.operacao == "financeiro.exportar")).first()
    rs = c.get(f"{API}/exportar/resumo-{hoje.year}.csv")
    assert rs.status_code == 200 and f"Total {hoje.year}" in rs.content.decode("utf-8")
    # painel
    ind = {i["codigo"]: i for i in _ok(c.get("/api/v1/painel"))["indicadores"]}
    assert ind["honorarios_receber"]["disponivel"] and ind["honorarios_receber"]["formato"] == "moeda"
    assert ind["honorarios_receber"]["valor"] >= 700 and "custos_ia_mes" in ind
    assert futuro["situacao"] == "previsto"


# ================================================================ automação e funções virtuais

def test_automacao_de_honorario_pendente_e_ferramenta_do_assistente(db, admin):
    c, _ = admin
    esc = obter_escritorio(db)
    cli = _cliente(c)
    lc = _lancar(c, valor="321.00", venc=date.today() - timedelta(days=5), cliente_id=cli["id"], descricao="Parcela atrasada sintética")
    from datetime import datetime, timezone
    agora = datetime.now(timezone.utc)
    eventos = list(automacoes.GATILHOS["honorario_pendente"].varrer(db, esc.id, agora - timedelta(days=1), agora,
                                                                     {"dias": 3, "repetir_dias": 7}))
    ev = next(e for e in eventos if e["id"] == lc["id"])
    assert ev["valor"] == "R$ 321,00" and ev["dias_atraso"] == 5 and ev["cliente"] == cli["nome"]
    assert not [e for e in automacoes.GATILHOS["honorario_pendente"].varrer(db, esc.id, agora, agora, {"dias": 6, "repetir_dias": 7})
                if e["id"] == lc["id"]]
    a = _ok(c.post("/api/v1/automacoes", json={"nome": "Avisar honorário atrasado", "gatilho": "honorario_pendente",
                                               "acoes": [{"tipo": "criar_pendencia", "titulo": "Conferir {descricao} de {cliente}"}]}), 201)
    t = _ok(c.post(f"/api/v1/automacoes/{a['id']}/testar"))
    assert t["teste"]["eventos"] >= 1
    from app.servicos.ia import ferramentas
    ctx = ferramentas.Contexto(db, esc.id, frozenset({"financeiro:ler"}), None, uuid.UUID(cli["id"]), None)
    r = ferramentas.executar(ctx, "honorarios_a_receber", {})
    assert r["total"] == 1 and r["soma"] == "R$ 321,00" and r["itens"][0]["vencido"]


def test_funcoes_financeiras_por_regras_e_lembrete_pela_central(db, admin):
    c, _ = admin
    cli = _cliente(c)
    proc = _processo(c, cli)
    ct = _ok(c.post(f"{API}/contratos", json={"cliente_id": cli["id"], "processo_id": proc["id"], "descricao": "Êxito sintético",
                                              "modalidade": "exito", "percentual_exito": "30", "portal_visivel": True}), 201)
    db.get(Processo, uuid.UUID(proc["id"])).status = "encerrado"
    db.commit()
    lc = _lancar(c, valor="640.00", venc=date.today() - timedelta(days=4), cliente_id=cli["id"], portal_visivel=True)
    for codigo in ("gestor_financeiro", "controlador_honorarios", "conciliador", "analista_rentabilidade"):
        _ok(c.put(f"/api/v1/ia/funcoes/{codigo}", json={"ativa": True}))
        ex = _ok(c.post(f"/api/v1/ia/funcoes/{codigo}/executar", json={"entrada": {}}), 201)
        assert ex["estado"] == "concluida", ex
        assert not ex.get("simulado") and (ex.get("custo") in (None, "0", "0.000000", 0))
        if codigo == "controlador_honorarios":
            assert any(x["contrato"] == ct["numero"] for x in ex["saida"]["exito_a_conferir"])
            assert any(x["cliente"] == cli["nome"] for x in ex["saida"]["atrasos_por_cliente"])
        if codigo == "gestor_financeiro":
            assert any("Receitas vencidas" in a for a in ex["saida"]["alertas"])
    _ok(c.put("/api/v1/ia/funcoes/gestor_cobrancas", json={"ativa": True, "nivel": 3}))
    ex = _ok(c.post("/api/v1/ia/funcoes/gestor_cobrancas/executar", json={"entrada": {"lancamento_id": lc["id"]}}), 201)
    assert ex["estado"] == "aguardando_aprovacao", ex
    assert db.execute(select(LembreteCobranca).where(LembreteCobranca.lancamento_id == uuid.UUID(lc["id"]))).scalar() is None
    ap = db.get(Aprovacao, uuid.UUID(ex["aprovacao_id"]))
    assert ap.tipo == "ia_lembrete_cobranca" and ap.permissao == "financeiro:cobrar" and ap.solicitada_por is None
    _ok(c.post(f"/api/v1/aprovacoes/{ap.id}/decidir", json={"decisao": "aprovar"}))
    db.expire_all()
    le = db.execute(select(LembreteCobranca).where(LembreteCobranca.lancamento_id == uuid.UUID(lc["id"]))).scalar_one()
    assert le.situacao == "publicado" and le.origem == "funcao" and "R$ 640,00" in le.texto
    # nível 2: só sugere, sem pedido de aprovação
    lc2 = _lancar(c, valor="10.00", venc=date.today() - timedelta(days=1), cliente_id=cli["id"], portal_visivel=True)
    _ok(c.put("/api/v1/ia/funcoes/gestor_cobrancas", json={"ativa": True, "nivel": 2}))
    ex2 = _ok(c.post("/api/v1/ia/funcoes/gestor_cobrancas/executar", json={"entrada": {"lancamento_id": lc2["id"]}}), 201)
    assert ex2["estado"] == "concluida" and ex2["aprovacao_id"] is None and "nível" in ex2["saida"]["aviso"]
    assert db.execute(select(Lancamento).where(Lancamento.id == uuid.UUID(lc2["id"]))).scalar_one().situacao == "previsto"
