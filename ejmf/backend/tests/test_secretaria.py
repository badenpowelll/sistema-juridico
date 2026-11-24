"""Agenda e secretaria contra PostgreSQL real: compromissos, conflitos, sobrecarga, Google Calendar (OAuth e
sincronização contra o servidor simulado da API), prioridades, aprovações, relatórios e notificações."""
import json
import random
import uuid
from datetime import date, datetime, time, timedelta, timezone
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.modelos import (
    Aprovacao, Compromisso, CredencialIntegracao, Integracao, Notificacao, Pendencia, Prazo, Processo, Relatorio, Tarefa,
)
from app.servicos import agenda, agenda_google, prazos as svc_prazos, prioridades, relatorios, sincronizacao
from app.servicos.conectores import google_simulado
from app.servicos.conectores.base import CredencialRecusada
from app.servicos.semente import obter_escritorio
from tests import sinteticos as s
from tests.conftest import SENHA, criar

FZ = ZoneInfo("America/Fortaleza")


def _dia_livre() -> date:
    """Dia útil distante e aleatório para o teste não colidir com outros na mesma base."""
    d = date(2031, 1, 1) + timedelta(days=random.randint(0, 3000))
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _h(d: date, hh: int, mm: int = 0) -> str:
    return datetime.combine(d, time(hh, mm), FZ).isoformat()


def _processo(c):
    r = c.post("/api/v1/processos", json={"numero": s.numero(), "classe": "Procedimento Comum Cível"})
    assert r.status_code == 201, r.text
    return r.json()


def _comp(c, d, hi, hf, tipo="reuniao", **kw):
    r = c.post("/api/v1/agenda", json={"tipo": tipo, "titulo": kw.pop("titulo", f"{tipo} sintética"), "inicio": _h(d, *hi),
                                       "fim": _h(d, *hf), **kw})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
def simulados(monkeypatch):
    from app.core.config import obter_config
    monkeypatch.setenv("EJMF_CONECTORES_SIMULADOS", "true")
    obter_config.cache_clear()
    yield
    monkeypatch.delenv("EJMF_CONECTORES_SIMULADOS")
    obter_config.cache_clear()


def _desligar_google(db):
    esc = obter_escritorio(db).id
    for c in db.execute(select(CredencialIntegracao).where(CredencialIntegracao.escritorio_id == esc)).scalars():
        c.dados_cifrados, c.estado, c.escopos = None, {}, []
    agenda_google.limpar_vinculos(db, esc)
    for codigo, estado in (("google_calendar", "aguardando_credenciais"), ("google_calendar_simulado", "ambiente_testes")):
        i = db.execute(select(Integracao).where(Integracao.escritorio_id == esc, Integracao.codigo == codigo)).scalar_one()
        i.estado, i.falhas_consecutivas, i.circuito_aberto_ate, i.ultimo_erro, i.ultimo_sucesso_em = estado, 0, None, None, None
    db.commit()


# ------------------------------------------------------------------ agenda

def test_compromissos_conflito_sobrecarga_disponibilidade_e_validacoes(db, admin):
    c, u = admin
    d = _dia_livre()
    proc = _processo(c)
    a = _comp(c, d, (9, 0), (10, 0), titulo="Reunião com cliente sintético")
    b = _comp(c, d, (9, 30), (11, 0), tipo="audiencia", titulo="Audiência de instrução sintética", processo_id=proc["id"])
    assert [x["id"] for x in b["conflitos"]] == [a["id"]]  # aviso no ato de marcar
    # audiência sem processo e evento externo criado à mão são recusados; fim antes do início também
    r = c.post("/api/v1/agenda", json={"tipo": "audiencia", "titulo": "Sem processo", "inicio": _h(d, 14), "fim": _h(d, 15)})
    assert r.status_code == 422 and "processo" in r.json()["detail"]
    assert c.post("/api/v1/agenda", json={"tipo": "externo", "titulo": "x" * 5, "inicio": _h(d, 14), "fim": _h(d, 15)}).status_code == 422
    assert c.post("/api/v1/agenda", json={"tipo": "reuniao", "titulo": "Invertida", "inicio": _h(d, 15), "fim": _h(d, 14)}).status_code == 422
    # dia inteiro vira 00:00–23:59:59 e não conflita
    lemb = _comp(c, d, (10, 0), (10, 0), tipo="lembrete", titulo="Lembrete do dia", dia_inteiro=True)
    assert lemb["dia_inteiro"] and lemb["inicio"].startswith(f"{d.isoformat()}T03:00")  # 00:00 em Fortaleza
    # sobrecarga: mais de 8 h no dia
    _comp(c, d, (11, 0), (18, 30), tipo="trabalho_concentrado", titulo="Trabalho concentrado sintético")
    v = c.get(f"/api/v1/agenda?inicio={d}&fim={d}").json()
    assert {(x["a"], x["b"]) for x in v["conflitos"]} >= {(a["id"], b["id"])} or {(x["b"], x["a"]) for x in v["conflitos"]} >= {(a["id"], b["id"])}
    sob = [x for x in v["sobrecarga"] if x["pessoa"] == str(u.id)]
    assert sob and sob[0]["horas"] == 10.0 and "limite 8 h" in sob[0]["motivos"][0]
    # disponibilidade no expediente 08–18 (Fortaleza): só 08:00–09:00 sobra com 60 min (11:00–12:00 UTC)
    livres = c.get(f"/api/v1/agenda/disponibilidade?dia={d}&pessoa={u.id}&duracao=60").json()
    assert [(x["inicio"][11:16], x["fim"][11:16]) for x in livres] == [("11:00", "12:00")]
    # reagendar registra histórico com de/para
    r = c.patch(f"/api/v1/agenda/{a['id']}", json={"inicio": _h(d, 8), "fim": _h(d, 8, 50)})
    assert r.status_code == 200 and r.json()["conflitos"] == []
    hist = c.get(f"/api/v1/agenda/{a['id']}").json()["historico"]
    assert [h["operacao"] for h in hist] == ["compromisso.criar", "compromisso.reagendar"]
    assert "inicio" in hist[1]["alteracoes"]
    # realizado: audiência exige resultado
    assert c.post(f"/api/v1/agenda/{b['id']}/concluir", json={}).status_code == 409
    assert c.post(f"/api/v1/agenda/{b['id']}/concluir", json={"resultado": "Instrução encerrada"}).json()["situacao"] == "realizado"


def test_compromisso_pessoal_fica_oculto_para_outras_pessoas(db, admin, operador):
    c, _ = admin
    op, _ = operador
    d = _dia_livre()
    p = _comp(c, d, (12, 0), (13, 0), tipo="pessoal", titulo="Consulta médica particular", local="Endereço particular")
    meu = c.get(f"/api/v1/agenda/{p['id']}").json()
    assert meu["titulo"] == "Consulta médica particular" and not meu["privado"]
    dele = op.get(f"/api/v1/agenda/{p['id']}").json()
    assert dele["titulo"] == "Compromisso pessoal" and dele["local"] is None and dele["privado"] and dele["historico"] == []
    assert op.patch(f"/api/v1/agenda/{p['id']}", json={"titulo": "Outro título"}).status_code == 403


def test_operador_pede_cancelamento_de_audiencia_e_advogado_aprova(db, admin, operador):
    c, u = admin
    op, uo = operador
    d = _dia_livre()
    proc = _processo(c)
    aud = _comp(c, d, (14, 0), (15, 0), tipo="audiencia", titulo="Audiência de conciliação sintética", processo_id=proc["id"])
    r = op.post(f"/api/v1/agenda/{aud['id']}/cancelar", json={"motivo": "Juízo redesignou a pauta"})
    assert r.status_code == 200 and r.json()["pendente_aprovacao"]
    assert op.post(f"/api/v1/agenda/{aud['id']}/cancelar", json={"motivo": "De novo, sem querer"}).status_code == 409
    assert c.get(f"/api/v1/agenda/{aud['id']}").json()["situacao"] == "agendado"
    aid = r.json()["aprovacao_id"]
    # o advogado foi notificado; o operador vê o pedido mas não pode decidir
    assert any(n["link"] == "/painel/aprovacoes" for n in c.get("/api/v1/notificacoes?nao_lidas=true").json()["itens"])
    item = next(i for i in op.get("/api/v1/aprovacoes").json()["pendentes"] if i["id"] == aid)
    assert item["proprio"] and not item["pode_decidir"]
    assert op.post(f"/api/v1/aprovacoes/{aid}/decidir", json={"decisao": "aprovar"}).status_code == 409
    assert c.post(f"/api/v1/aprovacoes/{aid}/decidir", json={"decisao": "rejeitar"}).status_code == 409  # sem motivo
    assert c.post(f"/api/v1/aprovacoes/{aid}/decidir", json={"decisao": "aprovar"}).json()["situacao"] == "aprovada"
    v = c.get(f"/api/v1/agenda/{aud['id']}").json()
    assert v["situacao"] == "cancelado" and v["cancelado_motivo"] == "Juízo redesignou a pauta"
    assert any("aprovada" in n["titulo"] for n in op.get("/api/v1/notificacoes").json()["itens"])
    assert c.post(f"/api/v1/aprovacoes/{aid}/decidir", json={"decisao": "aprovar"}).status_code == 409  # já decidido
    # a central também lista as aprovações que já existiam: prazo aguardando homologação e regras
    tipos = {i["tipo"] for i in c.get("/api/v1/aprovacoes").json()["pendentes"]}
    assert "homologar_regra" in tipos or "homologar_prazo" in tipos or "confirmar_suspensao" in tipos


# ------------------------------------------------------------------ Google Calendar (servidor simulado)

def test_google_simulado_sincroniza_ida_e_volta_sem_duplicar_nem_apagar_externos(db, admin, simulados):
    c, u = admin
    esc = obter_escritorio(db).id
    _desligar_google(db)
    try:
        assert c.post("/api/v1/agenda/google/simulado", json={"ativo": True}).json()["simulado_ativo"]
        d = _dia_livre()
        proc = _processo(c)
        reu = _comp(c, d, (9, 0), (10, 0), titulo="Reunião que vai ao Google")
        aud = _comp(c, d, (14, 0), (15, 0), tipo="audiencia", titulo="Audiência que vai ao Google", processo_id=proc["id"])
        local = _comp(c, d, (16, 0), (17, 0), titulo="Só no EJMF", sincronizar_google=False)
        r = c.post("/api/v1/integracoes/google_calendar_simulado/sincronizar").json()["tarefa"]
        assert r["estado"] == "concluida", r
        cred = db.execute(select(CredencialIntegracao).where(CredencialIntegracao.codigo == "google_calendar_simulado")).scalar_one()
        db.refresh(cred)
        servidor = cred.estado["servidor"]
        meus = {e["extendedProperties"]["private"]["ejmf_id"]: e for e in servidor["eventos"].values() if e.get("extendedProperties")}
        assert reu["id"] in meus and aud["id"] in meus and local["id"] not in meus
        assert meus[aud["id"]]["summary"].startswith("[Audiência]")
        externos = db.execute(select(Compromisso).where(Compromisso.escritorio_id == esc, Compromisso.tipo == "externo")).scalars().all()
        assert len(externos) == 2 and all(x.simulado and x.titulo.startswith("[SIMULADO") for x in externos)
        # segunda sincronização: nada duplicado
        assert c.post("/api/v1/integracoes/google_calendar_simulado/sincronizar").json()["tarefa"]["estado"] == "concluida"
        db.expire_all()
        assert len(db.execute(select(Compromisso).where(Compromisso.tipo == "externo", Compromisso.escritorio_id == esc)).scalars().all()) == 2
        cred = db.get(CredencialIntegracao, cred.id)
        marcas = [e["extendedProperties"]["private"]["ejmf_id"] for e in cred.estado["servidor"]["eventos"].values()
                  if e.get("extendedProperties")]
        assert marcas.count(reu["id"]) == 1 and marcas.count(aud["id"]) == 1 and len(marcas) == len(meus)

        # mudanças feitas "no app do Google"
        srv = cred.estado["servidor"]
        ext_id = externos[0].google_event_id
        google_simulado.editar(srv, ext_id, summary="Reunião externa remarcada")
        google_simulado.editar(srv, meus[reu["id"]]["id"], start={"dateTime": _h(d, 10)}, end={"dateTime": _h(d, 11)})
        google_simulado.editar(srv, meus[aud["id"]]["id"], start={"dateTime": _h(d, 16)}, end={"dateTime": _h(d, 17)})
        cred.estado = json.loads(json.dumps({**cred.estado, "servidor": srv}))
        flag_modified(cred, "estado")
        db.commit()
        c.post("/api/v1/integracoes/google_calendar_simulado/sincronizar")
        db.expire_all()
        assert db.get(Compromisso, externos[0].id).titulo == "Reunião externa remarcada"
        r_reu = c.get(f"/api/v1/agenda/{reu['id']}").json()
        assert r_reu["inicio"].startswith(f"{d}T13:00")  # 10:00 em Fortaleza, aplicado com histórico de origem google
        assert r_reu["historico"][-1]["operacao"] == "compromisso.reagendar" and r_reu["historico"][-1]["origem"] == "google"
        r_aud = c.get(f"/api/v1/agenda/{aud['id']}").json()
        assert r_aud["inicio"].startswith(f"{d}T17:00")  # 14:00 local: audiência NÃO muda sozinha
        ap = db.execute(select(Aprovacao).where(Aprovacao.entidade_id == aud["id"], Aprovacao.tipo == "reagendamento_google")).scalar_one()
        # rejeitar devolve o horário do EJMF ao Google
        assert c.post(f"/api/v1/aprovacoes/{ap.id}/decidir", json={"decisao": "rejeitar", "motivo": "Data não confirmada pelo juízo"}).status_code == 200
        c.post("/api/v1/integracoes/google_calendar_simulado/sincronizar")
        db.expire_all()
        cred = db.get(CredencialIntegracao, cred.id)
        ev_aud = cred.estado["servidor"]["eventos"][meus[aud["id"]]["id"]]
        assert ev_aud["start"]["dateTime"].startswith(f"{d}T14:00")

        # reunião excluída no Google: o EJMF não cancela, marca e cria pendência
        srv = cred.estado["servidor"]
        google_simulado.editar(srv, meus[reu["id"]]["id"], status="cancelled")
        cred.estado = json.loads(json.dumps({**cred.estado, "servidor": srv}))
        flag_modified(cred, "estado")
        db.commit()
        c.post("/api/v1/integracoes/google_calendar_simulado/sincronizar")
        r_reu = c.get(f"/api/v1/agenda/{reu['id']}").json()
        assert r_reu["situacao"] == "agendado" and r_reu["removido_no_google"]
        prioridades.atualizar(db, esc)
        db.commit()
        if d - date.today() <= timedelta(days=30):
            assert db.execute(select(Pendencia).where(Pendencia.chave == f"removido_google:{reu['id']}")).scalar()

        # cancelar no EJMF exclui do Google só o evento do EJMF; externos nunca são excluídos
        assert c.post(f"/api/v1/agenda/{aud['id']}/cancelar", json={"motivo": "Audiência retirada de pauta"}).status_code == 200
        c.post("/api/v1/integracoes/google_calendar_simulado/sincronizar")
        db.expire_all()
        cred = db.get(CredencialIntegracao, cred.id)
        assert cred.estado["servidor"]["eventos"][meus[aud["id"]]["id"]]["status"] == "cancelled"
        assert all(e.get("status") != "cancelled" for k, e in cred.estado["servidor"]["eventos"].items() if k.startswith("ext"))

        # token de sincronização expirado (410): leitura completa sem duplicar
        cred.estado = {**cred.estado, "servidor": {**cred.estado["servidor"], "expirar_token": True}}
        flag_modified(cred, "estado")
        db.commit()
        assert c.post("/api/v1/integracoes/google_calendar_simulado/sincronizar").json()["tarefa"]["estado"] == "concluida"
        db.expire_all()
        assert len(db.execute(select(Compromisso).where(Compromisso.tipo == "externo", Compromisso.escritorio_id == esc,
                                                        Compromisso.situacao == "agendado")).scalars().all()) == 2
        i = db.execute(select(Integracao).where(Integracao.codigo == "google_calendar_simulado")).scalar_one()
        assert i.estado == "ambiente_testes"  # simulado nunca vira "validada"
    finally:
        _desligar_google(db)


def test_google_real_oauth_pkce_tokens_cifrados_renovacao_e_falha_de_credencial(db, admin, operador, monkeypatch):
    from app.core.config import obter_config
    c, u = admin
    op, _ = operador
    esc = obter_escritorio(db).id
    _desligar_google(db)
    assert c.post("/api/v1/agenda/google/conectar").status_code == 409  # sem client id/secret: aguardando credenciais
    monkeypatch.setenv("EJMF_GOOGLE_CLIENT_ID", "cliente-sintetico.apps.googleusercontent.com")
    monkeypatch.setenv("EJMF_GOOGLE_CLIENT_SECRET", "segredo-sintetico")
    monkeypatch.setenv("EJMF_GOOGLE_REDIRECT_URI", "https://ejmf.exemplo.invalido/api/v1/agenda/google/retorno")
    obter_config.cache_clear()
    pedidos_token: list[dict] = []
    revogados: list[str] = []
    seq = {"n": 0}

    def oauth_h(req: httpx.Request) -> httpx.Response:
        dados = dict(x.split("=", 1) for x in req.content.decode().split("&"))
        if req.url.path.endswith("/revoke"):
            revogados.append(dados["token"])
            return httpx.Response(200)
        pedidos_token.append(dados)
        seq["n"] += 1
        corpo = {"access_token": f"acesso-sintetico-{seq['n']}", "expires_in": 3600,
                 "scope": "https://www.googleapis.com/auth/calendar.events.owned", "token_type": "Bearer"}
        if dados["grant_type"] == "authorization_code":
            corpo["refresh_token"] = "renovacao-sintetica"
        return httpx.Response(200, json=corpo)

    servidor = google_simulado.novo_estado(semear=False)
    cabecalhos: list[str] = []
    base_transporte = google_simulado.transporte(servidor)

    def api_h(req: httpx.Request) -> httpx.Response:
        cabecalhos.append(req.headers.get("authorization", ""))
        if servidor.get("recusar"):
            return httpx.Response(401, json={"error": {"code": 401}})
        return base_transporte.handle_request(req)

    agenda_google.TRANSPORTES.update(oauth=httpx.MockTransport(oauth_h), api=httpx.MockTransport(api_h))
    try:
        assert op.post("/api/v1/agenda/google/conectar").status_code == 403  # operador não conecta contas
        url = c.post("/api/v1/agenda/google/conectar").json()["url"]
        q = parse_qs(urlparse(url).query)
        assert q["scope"] == ["https://www.googleapis.com/auth/calendar.events.owned"]
        assert q["code_challenge_method"] == ["S256"] and q["access_type"] == ["offline"] and len(q["state"][0]) > 20
        # retorno com state errado é recusado; outra pessoa também não pode concluir
        r = c.get("/api/v1/agenda/google/retorno?state=errado&code=abc", follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].endswith("google=erro")
        r = c.get(f"/api/v1/agenda/google/retorno?state={q['state'][0]}&code=codigo-sintetico", follow_redirects=False)
        assert r.headers["location"].endswith("google=conectado"), r.headers["location"]
        assert pedidos_token[-1]["grant_type"] == "authorization_code" and len(pedidos_token[-1]["code_verifier"]) >= 43
        cred = db.execute(select(CredencialIntegracao).where(CredencialIntegracao.escritorio_id == esc,
                                                             CredencialIntegracao.codigo == "google_calendar")).scalar_one()
        assert cred.dados_cifrados and "acesso-sintetico" not in cred.dados_cifrados and "renovacao" not in cred.dados_cifrados
        st = c.get("/api/v1/agenda/google/situacao").json()
        assert st["conectado"] and "acesso-sintetico" not in json.dumps(st)
        i = db.execute(select(Integracao).where(Integracao.codigo == "google_calendar")).scalar_one()
        assert i.estado == "ambiente_testes"
        # prazo homologado vai para o Google como evento de dia inteiro
        proc = _processo(c)
        pz = Prazo(escritorio_id=esc, processo_id=uuid.UUID(proc["id"]), descricao="Contestação sintética", situacao="homologado",
                   vencimento=svc_prazos.hoje_local() + timedelta(days=10), calculo={"regra": {"nome": "CPC"}})
        db.add(pz)
        db.commit()
        r = c.post("/api/v1/integracoes/google_calendar/sincronizar").json()["tarefa"]
        assert r["estado"] == "concluida", r
        assert cabecalhos and all(h == "Bearer acesso-sintetico-1" for h in cabecalhos)
        db.expire_all()
        pz = db.get(Prazo, pz.id)
        ev = servidor["eventos"][pz.google_event_id]
        assert ev["start"] == {"date": pz.vencimento.isoformat()} and ev["summary"] == "Prazo: Contestação sintética"
        i = db.execute(select(Integracao).where(Integracao.codigo == "google_calendar")).scalar_one()
        assert i.estado == "implementada_validada"  # primeira sincronização real bem-sucedida
        # prazo devolvido para conferência sai da agenda Google
        pz.situacao = "alterado"
        db.commit()
        c.post("/api/v1/integracoes/google_calendar/sincronizar")
        db.expire_all()
        assert db.get(Prazo, pz.id).google_event_id is None and servidor["eventos"][ev["id"]]["status"] == "cancelled"
        # token vencido: renova com o refresh token
        t = json.loads(__import__("app.core.seguranca", fromlist=["decifrar"]).decifrar(cred.dados_cifrados))
        t["expira_em"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        cred = db.get(CredencialIntegracao, cred.id)
        cred.dados_cifrados = __import__("app.core.seguranca", fromlist=["cifrar"]).cifrar(json.dumps(t))
        db.commit()
        c.post("/api/v1/integracoes/google_calendar/sincronizar")
        assert pedidos_token[-1]["grant_type"] == "refresh_token" and cabecalhos[-1] == "Bearer acesso-sintetico-2"
        # acesso revogado no Google: falha permanente e integração volta a "aguardando credenciais"
        servidor["recusar"] = True
        r = c.post("/api/v1/integracoes/google_calendar/sincronizar").json()["tarefa"]
        assert r["estado"] == "falhou" and "401" in r["erro"]
        db.expire_all()
        assert db.execute(select(Integracao).where(Integracao.codigo == "google_calendar")).scalar_one().estado == "aguardando_credenciais"
        # desconectar revoga e apaga os tokens
        assert not c.post("/api/v1/agenda/google/desconectar").json()["conectado"]
        assert revogados == ["renovacao-sintetica"]
    finally:
        agenda_google.TRANSPORTES.clear()
        _desligar_google(db)


# ------------------------------------------------------------------ prioridades

def test_central_de_prioridades_classes_criterios_e_acoes(db, admin, operador):
    c, u = admin
    op, uo = operador
    esc = obter_escritorio(db).id
    hoje = svc_prazos.hoje_local()
    cal = svc_prazos.calendario_para(db, esc, None, hoje, hoje + timedelta(days=30))
    proc = _processo(c)
    pid = uuid.UUID(proc["id"])
    amanha = cal.proximo_util(hoje)
    longe = hoje + timedelta(days=40)
    urg = Prazo(escritorio_id=esc, processo_id=pid, descricao="Recurso sintético", situacao="homologado", vencimento=amanha, calculo={})
    nao_conf = Prazo(escritorio_id=esc, processo_id=pid, descricao="Réplica sintética", situacao="aguardando_conferencia",
                     vencimento=longe, calculo={})
    db.add_all([urg, nao_conf])
    db.commit()
    lista = c.get("/api/v1/prioridades").json()
    por_chave = {i["link"]: i for i in lista["itens"]}
    i_urg = por_chave[f"/painel/prazos/{urg.id}"]
    assert i_urg["classe"] == "atencao_imediata" and i_urg["critica"]
    assert "vence em 1 dia(s) útil(eis)" in i_urg["justificativa"][0] and "critério" in i_urg["justificativa"][0]
    i_nc = por_chave[f"/painel/prazos/{nao_conf.id}"]
    assert i_nc["classe"] == "normal" and any("não confirmado" in j for j in i_nc["justificativa"])
    assert lista["itens"][0]["critica"]  # críticos no topo
    # item crítico não pode ser adiado, nem concluído à mão; ao mudar de situação continua em atenção imediata
    r = c.post(f"/api/v1/prioridades/{i_urg['id']}/acao", json={"acao": "reagendar", "quando": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()})
    assert r.status_code == 409 and "crítico" in r.json()["detail"]
    assert c.post(f"/api/v1/prioridades/{i_urg['id']}/acao", json={"acao": "concluir"}).status_code == 409
    r = c.post(f"/api/v1/prioridades/{i_urg['id']}/acao", json={"acao": "aguardar_terceiros", "texto": "Aguardando guia do correspondente"})
    assert r.json()["situacao"] == "aguardando_terceiros" and r.json()["classe"] == "atencao_imediata"
    # item não crítico pode ser adiado e some da lista até a data
    r = c.post(f"/api/v1/prioridades/{i_nc['id']}/acao", json={"acao": "reagendar", "quando": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()})
    assert r.status_code == 200
    assert f"/painel/prazos/{nao_conf.id}" not in {i["link"] for i in c.get("/api/v1/prioridades").json()["itens"]}
    # resolver na origem fecha o item automático
    urg = db.get(Prazo, urg.id)
    urg.situacao, urg.conclusao = "concluido", "Protocolado (sintético)"
    db.commit()
    concl = c.get("/api/v1/prioridades?classe=concluida").json()["itens"]
    assert any(i["id"] == i_urg["id"] and i["resolucao"] == "Resolvida na origem" for i in concl)
    # manual: criar, delegar (notifica), pedir informações, concluir; função virtual ainda não existe
    venc = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
    m = c.post("/api/v1/prioridades", json={"titulo": "Ligar para o cartório sintético", "prazo_em": venc}).json()
    assert m["classe"] == "alta" and "data-limite em" in m["justificativa"][0]
    assert c.post(f"/api/v1/prioridades/{m['id']}/acao", json={"acao": "delegar_funcao_virtual"}).status_code == 409
    r = c.post(f"/api/v1/prioridades/{m['id']}/acao", json={"acao": "delegar", "responsavel_id": str(uo.id), "texto": "Por favor"})
    assert r.json()["responsavel"] == uo.nome
    assert any("encaminhada" in n["titulo"] for n in op.get("/api/v1/notificacoes").json()["itens"])
    assert op.post(f"/api/v1/prioridades/{m['id']}/acao", json={"acao": "solicitar_informacoes"}).status_code == 409  # sem texto
    r = op.post(f"/api/v1/prioridades/{m['id']}/acao", json={"acao": "solicitar_informacoes", "texto": "Qual o número do protocolo?"})
    assert r.json()["classe"] == "aguardando_informacoes"
    assert op.get("/api/v1/prioridades?meus=true").json()["itens"][0]["id"] == m["id"]
    r = op.post(f"/api/v1/prioridades/{m['id']}/acao", json={"acao": "concluir", "texto": "Feito"})
    assert r.json()["classe"] == "concluida"


# ------------------------------------------------------------------ relatórios

def test_relatorio_diario_e_de_encerramento_idempotentes_com_entregas(db, admin):
    c, u = admin
    esc = obter_escritorio(db).id
    d = _dia_livre()
    proc = _processo(c)
    pid = uuid.UUID(proc["id"])
    db.add_all([Prazo(escritorio_id=esc, processo_id=pid, descricao="Manifestação sintética", situacao="homologado", vencimento=d, calculo={}),
                Prazo(escritorio_id=esc, processo_id=pid, descricao="Embargos sintéticos", situacao="sugerido", vencimento=d, calculo={})])
    db.commit()
    _comp(c, d, (10, 0), (11, 0), tipo="audiencia", titulo="Audiência do relatório", processo_id=proc["id"])
    _comp(c, d, (15, 0), (16, 0), tipo="atendimento", titulo="Atendimento do relatório")
    agora = datetime.combine(d, time(6, 31), FZ)
    r = relatorios.gerar(db, esc, "diario", d, agora=agora)
    db.commit()
    sec = r.conteudo["secoes"]
    assert {p["descricao"] for p in sec["prazos_hoje"]} >= {"Manifestação sintética", "Embargos sintéticos"}
    assert [a["titulo"] for a in sec["audiencias"]] == ["Audiência do relatório"]
    assert [a["titulo"] for a in sec["reunioes"]] == ["Atendimento do relatório"]
    assert any("sem homologação" in a for a in r.conteudo["avisos"]) and "sem homologação" in r.conteudo["resumo"]
    assert {m["fase"] for m in sec["modulos_futuros"]} == {5, 6, 9}  # ainda não acompanhados: fase, não zero
    canais = {e["canal"]: e for e in r.entregas}
    assert canais["painel"]["situacao"] == "entregue" and canais["notificacao"]["destinatarios"] >= 1
    assert canais["email"]["situacao"] == "aguardando_credenciais" and canais["whatsapp"]["situacao"] == "aguardando_credenciais"
    assert relatorios.gerar(db, esc, "diario", d, agora=agora).id == r.id  # idempotente
    notifs = c.get("/api/v1/notificacoes").json()["itens"]
    assert sum(1 for n in notifs if n["link"] == f"/painel/relatorios/{r.id}") == 1
    e = relatorios.gerar(db, esc, "encerramento", d, agora=datetime.combine(d, time(18, 5), FZ))
    db.commit()
    assert len(e.conteudo["secoes"]["prazos_hoje_sem_cumprimento"]) >= 2 and e.conteudo["resumo"].startswith("ATENÇÃO")
    assert [a["titulo"] for a in e.conteudo["secoes"]["audiencias_sem_resultado"]] == ["Audiência do relatório"]
    lido = c.get(f"/api/v1/relatorios/{r.id}").json()
    assert lido["conteudo"]["secoes"]["audiencias"][0]["titulo"] == "Audiência do relatório"
    # marcar notificações como lidas (só as próprias)
    nid = notifs[0]["id"]
    assert c.post(f"/api/v1/notificacoes/{nid}/lida").json()["lida_em"]
    c.post("/api/v1/notificacoes/lidas")
    assert c.get("/api/v1/notificacoes").json()["nao_lidas"] == 0


def test_agendador_dos_relatorios_respeita_horario_e_nao_repete(db, operador):
    esc = obter_escritorio(db).id
    dia = date(2032, 3, 2)
    antes = relatorios.agendar(db, esc, datetime.combine(dia, time(6, 10), FZ))
    assert not any(k.startswith("relatorio:") for k in antes)
    depois = relatorios.agendar(db, esc, datetime.combine(dia, time(6, 35), FZ))
    de_novo = relatorios.agendar(db, esc, datetime.combine(dia, time(7, 0), FZ))
    noite = relatorios.agendar(db, esc, datetime.combine(dia, time(18, 1), FZ))
    db.commit()
    assert f"relatorio:diario:{dia}" in depois and f"relatorio:diario:{dia}" in de_novo
    assert f"relatorio:encerramento:{dia}" in noite and f"relatorio:encerramento:{dia}" not in de_novo
    ts = db.execute(select(Tarefa).where(Tarefa.chave.like(f"relatorio:%:{dia}"))).scalars().all()
    assert sorted(t.chave for t in ts) == [f"relatorio:diario:{dia}", f"relatorio:encerramento:{dia}"]
    from app.servicos import fila
    t = fila.executar(db, fila.pegar(db, tarefa_id=ts[0].id))
    assert t.estado == "concluida" and db.execute(select(Relatorio).where(Relatorio.referencia == dia)).scalar()
    for x in db.execute(select(Tarefa).where(Tarefa.chave.like("%2032-03-02%"))).scalars():
        x.estado = "cancelada"
    db.commit()
    # operador lê e gera relatório, mas não conecta Google
    op, _ = operador
    assert op.post("/api/v1/relatorios/gerar", json={"tipo": "diario"}).status_code == 201
    assert op.get("/api/v1/relatorios").status_code == 200
