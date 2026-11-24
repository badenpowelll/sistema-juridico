"""Controladoria contra PostgreSQL real: conectores (HTTP simulado no transporte), captura, conferência,
prazos com dupla conferência, alertas, calendário, fila, circuito e central de contingência."""
import io
import json
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from app.modelos import AlertaPrazo, ExecucaoIntegracao, Integracao, Movimentacao, Prazo, Publicacao, RegraPrazo, Tarefa
from app.servicos import fila, prazos as svc_prazos, sincronizacao
from app.servicos.conectores.base import CredencialAusente, CredencialRecusada, FonteIndisponivel, LimiteTaxa
from app.servicos.conectores.datajud import ConectorDataJud, alias
from app.servicos.conectores.djen import ConectorDJEN, normalizar_item
from app.servicos.semente import obter_escritorio
from tests import sinteticos as s
from tests.conftest import SENHA, criar


# ------------------------------------------------------------------ auxiliares
def _comunicacao(i: int, numero: str, dia: str, texto: str = "Intimem-se as partes para, no prazo de 15 (quinze) dias, "
                 "manifestarem-se sobre o laudo.", tipo="Intimação") -> dict:
    """Item no formato da API do DJEN (campos observados em respostas reais; conteúdo 100% fictício)."""
    return {"id": i, "hash": f"H{i:010d}", "status": "P", "data_disponibilizacao": dia, "siglaTribunal": "TJRN",
            "nomeOrgao": "1ª Vara Cível Fictícia", "tipoComunicacao": tipo, "tipoDocumento": "DESPACHO",
            "nomeClasse": "PROCEDIMENTO COMUM CÍVEL", "numero_processo": numero.replace("-", "").replace(".", ""),
            "numeroprocessocommascara": numero, "texto": texto, "link": "https://exemplo.invalido/doc",
            "destinatarios": [{"nome": "PARTE FICTÍCIA", "polo": "A"}],
            "destinatarioadvogados": [{"advogado": {"nome": "ADVOGADO FICTÍCIO", "numero_oab": "12114", "uf_oab": "RN"}}]}


def _transporte_djen(itens: list[dict], chamadas: list | None = None, status: int = 200):
    def handler(req: httpx.Request) -> httpx.Response:
        if chamadas is not None:
            chamadas.append(dict(req.url.params))
        if status != 200:
            return httpx.Response(status, headers={"retry-after": "30"}, text="bloqueado")
        pagina, por = int(req.url.params["pagina"]), int(req.url.params["itensPorPagina"])
        fatia = itens[(pagina - 1) * por: pagina * por]
        return httpx.Response(200, json={"status": "success", "message": "", "count": len(itens), "items": fatia})
    return httpx.MockTransport(handler)


@pytest.fixture
def djen_falso():
    estado = {"itens": [], "status": 200, "chamadas": []}
    sincronizacao.FABRICAS["djen"] = lambda db, esc: ConectorDJEN(
        "https://djen.exemplo.invalido/api/v1", transporte=_transporte_djen(estado["itens"], estado["chamadas"], estado["status"]),
        limitador=None)
    yield estado
    sincronizacao.FABRICAS.pop("djen", None)


def _reset_integracao(db, codigo):
    esc = obter_escritorio(db)
    i = db.execute(select(Integracao).where(Integracao.escritorio_id == esc.id, Integracao.codigo == codigo)).scalar_one()
    i.falhas_consecutivas, i.circuito_aberto_ate, i.ultimo_erro, i.ultimo_sucesso_em = 0, None, None, None
    db.commit()
    return i


def _processo(c, **kw):
    r = c.post("/api/v1/processos", json={"numero": s.numero(), "classe": "Procedimento Comum Cível", **kw})
    assert r.status_code == 201, r.text
    return r.json()


def _homologar_regras(c):
    for r in c.get("/api/v1/prazos/regras").json():
        if r["situacao"] == "nao_homologada":
            assert c.post(f"/api/v1/prazos/regras/{r['id']}/homologar").status_code == 200


def _outro_admin(db, app_cliente):
    u = criar(db)
    c2 = app_cliente()
    assert c2.post("/api/v1/auth/login", json={"email": u.email, "senha": SENHA}).status_code == 200
    return c2, u


# ------------------------------------------------------------------ conectores
def test_djen_normaliza_pagina_e_trata_erros():
    itens = [_comunicacao(i, s.numero(), "2026-03-02") for i in range(1, 151)]
    chamadas = []
    con = ConectorDJEN("https://djen.exemplo.invalido/api/v1", transporte=_transporte_djen(itens, chamadas), limitador=None)
    res = con.sincronizar(date(2026, 3, 1), date(2026, 3, 2), oabs=[("12.114", "RN"), ("12114", "RN")])
    assert len(res.itens) == 150  # duas grafias da OAB, sem duplicar
    assert chamadas[0]["numeroOab"] == "12114" and chamadas[0]["ufOab"] == "RN" and chamadas[1]["pagina"] == "2"
    n = res.itens[0]
    assert n["advogados"][0]["numero_oab"] == "12114" and n["disponibilizado_em"] == date(2026, 3, 2)
    assert n["original"]["hash"] == "H0000000001" and len(n["numero_processo"]) == 20
    with pytest.raises(LimiteTaxa) as e:
        ConectorDJEN("https://x.invalido", transporte=_transporte_djen([], status=429), limitador=None).sincronizar(
            date(2026, 3, 1), date(2026, 3, 1), oabs=[("1", "RN")])
    assert e.value.espera_segundos == 30
    with pytest.raises(FonteIndisponivel, match="403"):
        ConectorDJEN("https://x.invalido", transporte=_transporte_djen([], status=403), limitador=None).sincronizar(
            date(2026, 3, 1), date(2026, 3, 1), oabs=[("1", "RN")])
    # formato alternativo de data e advogado não aninhado
    alt = normalizar_item({"id": 7, "datadisponibilizacao": "05/03/2026", "texto": "x",
                           "destinatarioadvogados": [{"nome": "A", "numero_oab": "1", "uf_oab": "RN"}]})
    assert alt["disponibilizado_em"] == date(2026, 3, 5) and alt["advogados"][0]["uf_oab"] == "RN"


def test_datajud_lote_por_tribunal_e_credencial():
    assert alias("TJRN") == "api_publica_tjrn" and alias("TRE-RN") == "api_publica_tre-rn" and alias("STF") is None
    vistos = []

    def handler(req):
        vistos.append((req.url.path, req.headers.get("authorization"), json.loads(req.content)))
        n = json.loads(req.content)["query"]["terms"]["numeroProcesso"][0]
        mov = lambda c, d: {"codigo": c, "nome": f"Movimento {c}", "dataHora": d}  # noqa: E731
        return httpx.Response(200, json={"hits": {"hits": [
            {"_source": {"numeroProcesso": n, "grau": "G1", "classe": {"nome": "Procedimento Comum"},
                         "movimentos": [mov(26, "2026-01-10T10:00:00.000Z")]}},
            {"_source": {"numeroProcesso": n, "grau": "G2", "movimentos": [mov(51, "2026-02-01T09:00:00.000Z")]}}]}})
    con = ConectorDataJud("https://datajud.exemplo.invalido", "chave-ficticia", transporte=httpx.MockTransport(handler), limitador=None)
    res = con.sincronizar(date(2026, 1, 1), date(2026, 2, 1), processos={"TJRN": ["0" * 20], "STF": ["1" * 20]})
    assert vistos[0][0] == "/api_publica_tjrn/_search" and vistos[0][1] == "APIKey chave-ficticia"
    assert len(res.itens) == 1 and len(res.itens[0]["movimentos"]) == 2 and res.observacoes  # STF sem índice
    with pytest.raises(CredencialAusente):
        ConectorDataJud("https://x.invalido", None).sincronizar(date(2026, 1, 1), date(2026, 1, 1), processos={"TJRN": ["0" * 20]})
    with pytest.raises(CredencialRecusada):
        ConectorDataJud("https://x.invalido", "k", transporte=httpx.MockTransport(lambda r: httpx.Response(401)),
                        limitador=None).sincronizar(date(2026, 1, 1), date(2026, 1, 1), processos={"TJRN": ["0" * 20]})


# ------------------------------------------------------------------ sincronização ponta a ponta
def test_sincronizacao_djen_captura_vincula_sugere_prazo_e_e_idempotente(db, admin, djen_falso):
    c, _ = admin
    _reset_integracao(db, "djen")
    p = _processo(c)
    hoje = svc_prazos.hoje_local()
    djen_falso["itens"] += [_comunicacao(9_100_001, p["numero"], (hoje - timedelta(days=1)).isoformat()),
                            _comunicacao(9_100_002, s.numero(), hoje.isoformat(), texto="Cite-se o réu.", tipo="Citação")]
    r = c.post("/api/v1/integracoes/djen/sincronizar")
    assert r.status_code == 200 and r.json()["tarefa"]["estado"] == "concluida", r.text
    res = r.json()["tarefa"]["resultado"]
    assert res["resultado"] == "sucesso" and res["novos"] == 2
    integ = db.execute(select(Integracao).where(Integracao.codigo == "djen")).scalar_one()
    db.refresh(integ)
    assert integ.estado == "implementada_validada" and integ.ultimo_sucesso_em is not None
    pubs = c.get("/api/v1/publicacoes", params={"fonte": "djen", "situacao": "nao_conferida"}).json()
    vinc = next(x for x in pubs["itens"] if x["processo_id"] == p["id"])
    assert vinc["prazo_dias_no_texto"] == 15 and vinc["publicado_em"] == svc_prazos.proximo_dia_util(
        db, obter_escritorio(db).id, "8.20", hoje - timedelta(days=1)).isoformat()
    solta = next(x for x in pubs["itens"] if x["processo_id"] is None and x["tipo"] == "citacao")
    assert any("não cadastrado" in m for m in solta["pendencias"]) and any("Prazo não identificado" in m for m in solta["pendencias"])
    detalhe = c.get(f"/api/v1/publicacoes/{vinc['id']}").json()
    assert detalhe["original"]["hash"] == "H0009100001" and detalhe["ciencia_em"] is None  # nada marca ciência sozinho
    assert detalhe["leituras"][0]["vezes"] == 1
    pz = detalhe["prazos"][0]
    assert pz["situacao"] == "sugerido" and pz["confirmado"] is False and pz["regra"]["codigo"] == "cpc_uteis_djen"
    assert pz["vencimento"] and any("não homologada" in a for a in pz["calculo"]["avisos"])
    # segunda execução: mesma janela, nada duplicado
    r2 = c.post("/api/v1/integracoes/djen/sincronizar").json()["tarefa"]["resultado"]
    assert r2["novos"] == 0
    ex = db.execute(select(ExecucaoIntegracao).where(ExecucaoIntegracao.integracao == "djen")
                    .order_by(ExecucaoIntegracao.iniciada_em.desc()).limit(1)).scalar_one()
    assert ex.itens_duplicados == 2


def test_falhas_abrem_circuito_e_central_mostra_monitoramento_comprometido(db, admin, djen_falso):
    c, _ = admin
    _reset_integracao(db, "djen")
    djen_falso["status"] = 403
    esc = obter_escritorio(db).id
    for _ in range(3):
        with pytest.raises(FonteIndisponivel):
            sincronizacao.sincronizar(db, esc, "djen")
    integ = db.execute(select(Integracao).where(Integracao.codigo == "djen")).scalar_one()
    db.refresh(integ)
    assert integ.falhas_consecutivas == 3 and integ.circuito_aberto_ate and integ.estado == "indisponivel"
    ignorada = sincronizacao.sincronizar(db, esc, "djen")  # circuito aberto: nem chama a fonte
    assert ignorada.resultado == "ignorada" and len(djen_falso["chamadas"]) == 3
    cent = c.get("/api/v1/contingencia").json()
    f = next(x for x in cent["fontes"] if x["codigo"] == "djen")
    assert cent["monitoramento_comprometido"] and f["comprometido"] and "403" in f["ultimo_erro"]
    assert "numeroOab=12114" in f["procedimento"]["link_consulta"] and "ausência de acontecimentos" in cent["aviso"].lower()
    painel = c.get("/api/v1/painel").json()
    assert any(i["id"] == "integracao-falha-djen" for i in painel["atencao_agora"])
    # fonte volta: circuito fecha e estado é restaurado
    djen_falso["status"] = 200
    integ.circuito_aberto_ate = None
    db.commit()
    ok = sincronizacao.sincronizar(db, esc, "djen")
    db.refresh(integ)
    assert ok.resultado == "sucesso" and integ.falhas_consecutivas == 0 and integ.estado == "implementada_validada"


def test_datajud_sem_chave_fica_aguardando_credenciais_e_com_chave_grava_movimentos(db, admin):
    c, _ = admin
    _reset_integracao(db, "datajud")
    esc = obter_escritorio(db).id
    with pytest.raises(CredencialAusente):
        sincronizacao.sincronizar(db, esc, "datajud")
    i = db.execute(select(Integracao).where(Integracao.codigo == "datajud")).scalar_one()
    db.refresh(i)
    assert i.estado == "aguardando_credenciais" and "DATAJUD_API_KEY" in i.ultimo_erro
    p = _processo(c)
    numero = p["numero"].replace("-", "").replace(".", "")

    def handler(req):
        termos = json.loads(req.content)["query"]["terms"]["numeroProcesso"]
        hits = [{"_source": {"numeroProcesso": numero, "movimentos": [
            {"codigo": 60, "nome": "Expedição de documento", "dataHora": "2026-05-04T12:00:00.000Z"}]}}] if numero in termos else []
        return httpx.Response(200, json={"hits": {"hits": hits}})
    sincronizacao.FABRICAS["datajud"] = lambda db_, e: ConectorDataJud("https://dj.invalido", "k",
                                                                       transporte=httpx.MockTransport(handler), limitador=None)
    try:
        i.circuito_aberto_ate = None
        db.commit()
        assert sincronizacao.sincronizar(db, esc, "datajud").itens_novos == 1
        assert sincronizacao.sincronizar(db, esc, "datajud").itens_novos == 0  # chave externa evita duplicar
    finally:
        sincronizacao.FABRICAS.pop("datajud")
    movs = db.execute(select(Movimentacao).where(Movimentacao.origem == "datajud",
                                                 Movimentacao.chave_externa.like("datajud:60:%"))).scalars().all()
    assert any(m.descricao == "Expedição de documento" for m in movs)
    tl = c.get(f"/api/v1/processos/{p['id']}").json()["linha_do_tempo"]
    assert any(e["origem"] == "datajud" for e in tl)


# ------------------------------------------------------------------ prazos
def test_dupla_conferencia_regra_homologada_alteracao_e_conclusao(db, admin, app_cliente):
    c, u = admin
    p = _processo(c)
    corpo = {"processo_id": p["id"], "descricao": "Réplica à contestação", "dias": 15, "data_base": "2026-03-02"}
    sim = c.post("/api/v1/prazos/simular", json={k: corpo[k] for k in ("processo_id", "dias", "data_base")}).json()
    assert sim["vencimento"] == "2026-03-24"
    pz = c.post("/api/v1/prazos", json=corpo).json()
    assert pz["situacao"] == "aguardando_conferencia" and pz["vencimento"] == "2026-03-24"
    assert pz["conferido_por"] == u.nome
    regra = db.get(RegraPrazo, pz["regra"]["id"])
    if regra.situacao == "homologada":  # outra execução já homologou: volta ao estado de partida deste teste
        regra.situacao = "nao_homologada"
        db.commit()
    c2, _ = _outro_admin(db, app_cliente)
    r = c2.post(f"/api/v1/prazos/{pz['id']}/homologar")
    assert r.status_code == 409 and "regra" in r.json()["detail"].lower()
    _homologar_regras(c)
    r = c.post(f"/api/v1/prazos/{pz['id']}/homologar")
    assert r.status_code == 409 and "Dupla conferência" in r.json()["detail"]
    r = c2.post(f"/api/v1/prazos/{pz['id']}/homologar")
    assert r.status_code == 200 and r.json()["situacao"] == "homologado" and r.json()["confirmado"]
    # mudar um prazo homologado exige nova homologação
    alt = c.patch(f"/api/v1/prazos/{pz['id']}", json={"dias": 5}).json()
    assert alt["situacao"] == "alterado" and alt["vencimento"] == "2026-03-10" and alt["homologado_por"] is None
    assert c2.post(f"/api/v1/prazos/{pz['id']}/homologar").json()["situacao"] == "homologado"
    assert c.post(f"/api/v1/prazos/{pz['id']}/concluir", json={"conclusao": "xx"}).status_code == 422
    fim = c.post(f"/api/v1/prazos/{pz['id']}/concluir", json={"conclusao": "Réplica protocolada em 09/03/2026"}).json()
    assert fim["situacao"] == "concluido"
    hist = [h["operacao"] for h in c.get(f"/api/v1/prazos/{pz['id']}").json()["historico"]]
    assert hist == ["prazo.criar", "prazo.homologar", "prazo.alterar", "prazo.homologar", "prazo.concluir"]
    assert c.patch(f"/api/v1/prazos/{pz['id']}", json={"dias": 3}).status_code == 409
    assert c.post("/api/v1/prazos", json={**corpo, "dobro": True}).status_code == 422  # dobro exige fundamento


def test_regra_penal_por_classe_e_informacao_insuficiente(admin):
    c, _ = admin
    p = _processo(c, classe="Ação Penal - Procedimento Ordinário")
    pz = c.post("/api/v1/prazos", json={"processo_id": p["id"], "descricao": "Resposta à acusação", "dias": 10,
                                        "data_base": "2026-03-02"}).json()
    assert pz["regra"]["codigo"] == "cpp_corridos_djen" and pz["vencimento"] == "2026-03-13"
    sem = c.post("/api/v1/prazos", json={"processo_id": p["id"], "descricao": "Prazo a definir"}).json()
    assert sem["situacao"] == "informacao_insuficiente" and sem["vencimento"] is None
    assert c.post(f"/api/v1/prazos/{sem['id']}/conferir").status_code == 409


def test_confirmar_carnaval_recalcula_e_derruba_homologacao(db, admin, app_cliente):
    c, _ = admin
    _homologar_regras(c)
    p = _processo(c)
    pz = c.post("/api/v1/prazos", json={"processo_id": p["id"], "descricao": "Manifestação", "dias": 15,
                                        "data_base": "2026-02-12"}).json()
    assert pz["vencimento"] == "2026-03-06" and pz["vencimento_alternativo"] == "2026-03-10"
    c2, _ = _outro_admin(db, app_cliente)
    assert c2.post(f"/api/v1/prazos/{pz['id']}/homologar").json()["situacao"] == "homologado"
    dias = c.get("/api/v1/calendario", params={"ano": 2026}).json()
    carnaval = [d for d in dias if d["nome"].startswith("Carnaval") and d["abrangencia"] == "nacional"]
    for d in carnaval:
        r = c.post(f"/api/v1/calendario/{d['id']}/confirmar")
        assert r.status_code == 200
    novo = c.get(f"/api/v1/prazos/{pz['id']}").json()
    assert novo["vencimento"] == "2026-03-10" and novo["situacao"] == "alterado"
    assert c.post(f"/api/v1/calendario/{carnaval[0]['id']}/confirmar").status_code == 409
    feriado = next(d for d in dias if d["nome"] == "Tiradentes")
    assert c.delete(f"/api/v1/calendario/{feriado['id']}").status_code == 409
    # desfaz a confirmação para não afetar outros testes
    from app.modelos import DiaCalendario
    for d in carnaval:
        db.get(DiaCalendario, d["id"]).confirmado = False
    db.commit()


def test_alertas_por_limiar_com_recuperacao_e_vencidos(db, admin):
    c, _ = admin
    p = _processo(c)
    hoje = svc_prazos.hoje_local()
    pz = c.post("/api/v1/prazos", json={"processo_id": p["id"], "descricao": "Contrarrazões", "dias": 1,
                                        "data_base": hoje.isoformat()}).json()
    esc = obter_escritorio(db).id
    obj = db.get(Prazo, pz["id"])
    obj.vencimento = hoje + timedelta(days=4)  # faltam 4 dias: limiar corrente é 5
    db.commit()
    assert svc_prazos.gerar_alertas(db, esc, hoje) >= 1
    assert svc_prazos.gerar_alertas(db, esc, hoje) == 0  # idempotente
    db.commit()
    alertas = db.execute(select(AlertaPrazo).where(AlertaPrazo.prazo_id == obj.id)).scalars().all()
    assert [a.dias_antes for a in alertas] == [5] and alertas[0].confirmado_prazo is False
    lista = c.get("/api/v1/alertas").json()
    a = next(x for x in lista if x["prazo_id"] == pz["id"])
    assert c.post(f"/api/v1/alertas/{a['id']}/ciente").json()["ciente_em"]
    obj.vencimento = hoje - timedelta(days=1)
    db.commit()
    assert svc_prazos.marcar_vencidos(db, esc, hoje) >= 1
    db.commit()
    db.refresh(obj)
    assert obj.situacao == "vencido"
    assert any(i["id"] == "prazos-vencidos" for i in c.get("/api/v1/painel").json()["atencao_agora"])


# ------------------------------------------------------------------ publicações
def test_cadastro_manual_duplicidade_vinculo_descarte_e_ciencia(db, admin, operador):
    c, _ = admin
    o, _ = operador
    p = _processo(c)
    corpo = {"texto": "Fica a parte intimada para, em 5 (cinco) dias, juntar documentos.", "disponibilizado_em": "2026-03-02",
             "numero_processo": p["numero"]}
    a = o.post("/api/v1/publicacoes", json=corpo)
    assert a.status_code == 201 and a.json()["processo_id"] == p["id"] and a.json()["contagem"]["prazos_sugeridos"] == 1
    b = o.post("/api/v1/publicacoes", json=corpo).json()
    assert b["situacao"] == "duplicada" and b["duplicada_de_id"] == a.json()["id"]
    assert o.post("/api/v1/publicacoes", json={**corpo, "numero_processo": "123"}).status_code == 422
    sem = o.post("/api/v1/publicacoes", json={"texto": "Publicação sem número informado.", "disponibilizado_em": "2026-03-03"}).json()
    assert o.post(f"/api/v1/publicacoes/{sem['id']}/conferir", json={}).status_code == 409  # precisa vincular
    assert o.post(f"/api/v1/publicacoes/{sem['id']}/descartar", json={"motivo": "x"}).status_code == 422
    v = o.post(f"/api/v1/publicacoes/{sem['id']}/vincular", json={"processo_id": p["id"]}).json()
    assert v["processo_id"] == p["id"]
    assert o.post(f"/api/v1/publicacoes/{sem['id']}/conferir", json={"observacao": "lida"}).json()["situacao"] == "conferida"
    assert o.post(f"/api/v1/publicacoes/{b['id']}/descartar", json={"motivo": "Repetida no diário"}).json()["situacao"] == "descartada"
    # ciência oficial: só quem tem a permissão, com confirmação explícita
    pid = a.json()["id"]
    assert o.post(f"/api/v1/publicacoes/{pid}/ciencia", json={"ciencia_em": "2026-03-03T10:00:00-03:00", "confirmo": True}).status_code == 403
    assert c.post(f"/api/v1/publicacoes/{pid}/ciencia", json={"ciencia_em": "2026-03-03T10:00:00-03:00", "confirmo": False}).status_code == 422
    r = c.post(f"/api/v1/publicacoes/{pid}/ciencia", json={"ciencia_em": "2026-03-03T10:00:00-03:00", "confirmo": True})
    assert r.status_code == 200
    assert datetime.fromisoformat(r.json()["ciencia_em"]) == datetime(2026, 3, 3, 13, 0, tzinfo=timezone.utc)
    # operador não homologa prazo nem regra
    pz = c.get(f"/api/v1/publicacoes/{pid}").json()["prazos"][0]
    assert o.post(f"/api/v1/prazos/{pz['id']}/conferir").status_code == 200
    assert o.post(f"/api/v1/prazos/{pz['id']}/homologar").status_code == 403
    regra = c.get("/api/v1/prazos/regras").json()[0]
    assert o.post(f"/api/v1/prazos/regras/{regra['id']}/homologar").status_code == 403


def test_importar_arquivo_do_djen(db, admin):
    c, _ = admin
    p = _processo(c)
    conteudo = json.dumps({"count": 2, "items": [_comunicacao(9_200_001, p["numero"], "2026-03-04"),
                                                 _comunicacao(9_200_002, s.numero(), "2026-03-04")]}).encode()
    r = c.post("/api/v1/publicacoes/importar", files={"arquivo": ("djen.json", io.BytesIO(conteudo), "application/json")})
    assert r.status_code == 200 and r.json()["novos"] == 2 and r.json()["vinculados"] == 1, r.text
    r2 = c.post("/api/v1/publicacoes/importar", files={"arquivo": ("djen.json", io.BytesIO(conteudo), "application/json")})
    assert r2.json()["ja_capturados"] == 2
    ruim = c.post("/api/v1/publicacoes/importar", files={"arquivo": ("x.json", io.BytesIO(b'{"a": 1}'), "application/json")})
    assert ruim.status_code == 422


# ------------------------------------------------------------------ fila e worker
def test_fila_idempotente_espera_exponencial_e_retomada(db):
    esc = obter_escritorio(db).id
    chamadas = {"n": 0}

    @fila.executor("teste.falha")
    def _falha(db_, t):
        chamadas["n"] += 1
        raise RuntimeError("falha simulada")

    @fila.executor("teste.taxa")
    def _taxa(db_, t):
        raise LimiteTaxa("limite", 120)

    t1 = fila.enfileirar(db, esc, "teste.falha", "teste:falha:1", max_tentativas=2)
    t2 = fila.enfileirar(db, esc, "teste.falha", "teste:falha:1")
    assert t1.id == t2.id
    db.commit()
    t = fila.executar(db, fila.pegar(db, tarefa_id=t1.id))
    assert t.estado == "pendente" and t.tentativas == 1 and "falha simulada" in t.erro
    assert t.agendada_para > datetime.now(timezone.utc) + timedelta(seconds=50)
    t.agendada_para = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    t = fila.executar(db, fila.pegar(db, tarefa_id=t1.id))
    assert t.estado == "falhou" and chamadas["n"] == 2
    tx = fila.enfileirar(db, esc, "teste.taxa", "teste:taxa:1")
    db.commit()
    tx = fila.executar(db, fila.pegar(db, tarefa_id=tx.id))
    assert tx.estado == "pendente" and tx.agendada_para > datetime.now(timezone.utc) + timedelta(seconds=110)
    # tarefa "executando" de um worker que caiu volta para a fila
    trav = fila.enfileirar(db, esc, "teste.falha", "teste:travada:1")
    trav.estado, trav.iniciada_em = "executando", datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    assert fila.recuperar_travadas(db) >= 1
    db.commit()
    db.refresh(trav)
    assert trav.estado == "pendente"
    trav.estado = "cancelada"
    tx.estado = "cancelada"
    db.commit()


def test_agendador_cria_chaves_do_horario_uma_vez(db):
    from zoneinfo import ZoneInfo
    esc = obter_escritorio(db).id
    quando = datetime(2030, 5, 6, 13, 5, tzinfo=ZoneInfo("America/Fortaleza"))
    a = sincronizacao.agendar(db, esc, quando)
    b = sincronizacao.agendar(db, esc, quando.replace(minute=40))
    db.commit()
    assert a == b and "sincronizar:djen:2030-05-06:12" in a and "prazos.rotina:2030-05-06:13" in a
    n = db.execute(select(Tarefa).where(Tarefa.chave.like("%2030-05-06%"))).scalars().all()
    assert len(n) == len(a)
    for t in n:
        t.estado = "cancelada"
    db.commit()


def test_simulado_desligado_por_padrao_e_marcado_quando_ligado(db, monkeypatch):
    from app.core.config import obter_config
    esc = obter_escritorio(db).id
    _reset_integracao(db, "djen_simulado")
    with pytest.raises(CredencialAusente):
        sincronizacao.sincronizar(db, esc, "djen_simulado")
    monkeypatch.setenv("EJMF_CONECTORES_SIMULADOS", "true")
    obter_config.cache_clear()
    try:
        _reset_integracao(db, "djen_simulado")
        hoje = svc_prazos.hoje_local()
        ex = sincronizacao.sincronizar(db, esc, "djen_simulado", desde=hoje - timedelta(days=6), ate=hoje)
        assert ex.resultado == "sucesso" and ex.simulado and ex.itens_novos >= 1
        pubs = db.execute(select(Publicacao).where(Publicacao.execucao_id == ex.id)).scalars().all()
        assert pubs and all(p.simulado and p.fonte == "djen_simulado" and p.texto.startswith("[SIMULADO") for p in pubs)
        i = db.execute(select(Integracao).where(Integracao.codigo == "djen_simulado")).scalar_one()
        db.refresh(i)
        assert i.simulado and i.estado == "ambiente_testes"  # simulado nunca vira "validada"
        prazos_sim = db.execute(select(Prazo).where(Prazo.publicacao_id.in_([p.id for p in pubs]))).scalars().all()
        assert all(z.simulado for z in prazos_sim)
    finally:
        monkeypatch.delenv("EJMF_CONECTORES_SIMULADOS")
        obter_config.cache_clear()


def test_painel_indicadores_reais_da_controladoria(admin):
    c, _ = admin
    ind = {i["codigo"]: i for i in c.get("/api/v1/painel").json()["indicadores"]}
    for cod in ("publicacoes_pendentes", "prazos_hoje", "prazos_futuros", "intimacoes_24h"):
        assert ind[cod]["disponivel"] is True and isinstance(ind[cod]["valor"], int)
