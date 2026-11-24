"""Sincronização bidirecional controlada entre a agenda do EJMF e o Google Calendar.

Ida (EJMF → Google): compromissos marcados para sincronizar e prazos homologados. Cada evento leva
`extendedProperties.private.ejmf_id`; só eventos com essa marca são alterados ou excluídos pelo EJMF.
Volta (Google → EJMF), incremental por syncToken:
- evento de outro sistema → entra como "externo" (só leitura; ocupa o horário). Nunca é excluído do Google.
- evento do EJMF alterado no Google → compromisso comum é atualizado (com histórico); audiência vira pedido na
  central de aprovações (não muda sozinha).
- evento do EJMF excluído no Google → o compromisso NÃO é cancelado: fica marcado "removido no Google" e gera
  pendência. Prazo homologado excluído no Google é recriado.
"""
from __future__ import annotations

import json
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import obter_config
from app.core.seguranca import cifrar, decifrar
from app.modelos import Aprovacao, Compromisso, CredencialIntegracao, Integracao, Prazo, Processo
from app.servicos import auditoria, prazos as svc_prazos
from app.servicos.agenda import fuso, inicio_do_dia
from app.servicos.conectores.base import CredencialAusente
from app.servicos.conectores.google_agenda import ESCOPOS, ConectorGoogleAgenda, OAuthGoogle, SyncTokenExpirado, pkce
from app.servicos.conectores.google_simulado import novo_estado, transporte as transporte_simulado

CODIGOS = ("google_calendar", "google_calendar_simulado")
MARCA = "ejmf_id"
JANELA_COMPLETA_DIAS = 30
# Permite trocar o transporte HTTP nos testes
TRANSPORTES: dict[str, object] = {}


def oauth() -> OAuthGoogle:
    cfg = obter_config()
    return OAuthGoogle(cfg.google_client_id, cfg.google_client_secret, cfg.google_redirect_uri,
                       transporte=TRANSPORTES.get("oauth"), timeout=cfg.conectores_timeout_segundos)


def credencial(db: Session, esc_id: uuid.UUID, codigo: str, *, travar: bool = False) -> CredencialIntegracao:
    q = select(CredencialIntegracao).where(CredencialIntegracao.escritorio_id == esc_id, CredencialIntegracao.codigo == codigo)
    c = db.execute(q.with_for_update() if travar else q).scalar()
    if c is None:
        c = CredencialIntegracao(escritorio_id=esc_id, codigo=codigo, estado={})
        db.add(c)
        db.flush()
    return c


def _tokens(c: CredencialIntegracao) -> dict | None:
    if not c.dados_cifrados:
        return None
    t = decifrar(c.dados_cifrados)
    return json.loads(t) if t else None


def situacao(db: Session, esc_id: uuid.UUID) -> dict:
    cfg = obter_config()
    c = db.execute(select(CredencialIntegracao).where(CredencialIntegracao.escritorio_id == esc_id,
                                                      CredencialIntegracao.codigo == "google_calendar")).scalar()
    sim = db.execute(select(CredencialIntegracao).where(CredencialIntegracao.escritorio_id == esc_id,
                                                        CredencialIntegracao.codigo == "google_calendar_simulado")).scalar()
    return {"oauth_configurado": oauth().configurado, "conectado": bool(c and c.dados_cifrados),
            "conectado_em": c.conectada_em if c else None, "escopos": c.escopos if c else [],
            "calendario_id": svc_prazos.config(db, esc_id, "agenda.google_calendario_id", "primary"),
            "simulado_disponivel": cfg.conectores_simulados, "simulado_ativo": bool(sim and sim.estado.get("ativo")),
            "ultima_sync": (c.estado or {}).get("ultima_sync") if c else None}


# ------------------------------------------------------------------ OAuth

def iniciar_conexao(db: Session, esc_id: uuid.UUID, usuario_id: uuid.UUID) -> str:
    o = oauth()
    estado, (verificador, desafio) = secrets.token_urlsafe(32), pkce()
    c = credencial(db, esc_id, "google_calendar", travar=True)
    c.estado = {**(c.estado or {}), "oauth": {"state": estado, "verificador": cifrar(verificador),
                                              "usuario": str(usuario_id),
                                              "expira": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()}}
    return o.url_autorizacao(estado, desafio)


def concluir_conexao(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, usuario_id: uuid.UUID, estado: str, codigo: str) -> None:
    c = credencial(db, esc_id, "google_calendar", travar=True)
    pend = (c.estado or {}).get("oauth") or {}
    if not pend or not secrets.compare_digest(pend.get("state", ""), estado or "") or pend.get("usuario") != str(usuario_id):
        raise ValueError("Pedido de conexão inválido ou de outra pessoa. Comece de novo.")
    if datetime.fromisoformat(pend["expira"]) < datetime.now(timezone.utc):
        raise ValueError("Pedido de conexão expirou. Comece de novo.")
    t = oauth().trocar_codigo(codigo, decifrar(pend["verificador"]) or "")
    concedidos = set((t.get("scope") or "").split())
    if concedidos and not set(ESCOPOS) <= concedidos:
        raise ValueError("A conta Google não concedeu a permissão de agenda pedida.")
    sim = credencial(db, esc_id, "google_calendar_simulado", travar=True)
    if (sim.estado or {}).get("ativo"):
        sim.estado = {**sim.estado, "ativo": False}
    limpar_vinculos(db, esc_id)
    c.dados_cifrados = cifrar(json.dumps({k: t.get(k) for k in ("access_token", "refresh_token", "expira_em")}))
    c.escopos, c.conectada_por, c.conectada_em = sorted(concedidos or ESCOPOS), usuario_id, datetime.now(timezone.utc)
    c.estado = {k: v for k, v in (c.estado or {}).items() if k != "oauth"}
    integ = db.execute(select(Integracao).where(Integracao.escritorio_id == esc_id, Integracao.codigo == "google_calendar")).scalar_one()
    anterior = integ.estado
    if integ.estado in ("aguardando_credenciais", "nao_implementada"):
        integ.estado = "ambiente_testes"  # sobe para "validada" na primeira sincronização real bem-sucedida
    integ.ultimo_erro = None
    auditoria.registrar(db, ator, "integracao.conectar", entidade="integracao", entidade_id="google_calendar",
                        alteracoes={"escopos": c.escopos, "antes": anterior, "depois": integ.estado})


def desconectar(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID) -> None:
    """Revoga o token e apaga as credenciais. Não exclui nada no Google."""
    c = credencial(db, esc_id, "google_calendar", travar=True)
    t = _tokens(c)
    if t:
        oauth().revogar(t.get("refresh_token") or t.get("access_token") or "")
    c.dados_cifrados, c.escopos, c.estado = None, [], {}
    integ = db.execute(select(Integracao).where(Integracao.escritorio_id == esc_id, Integracao.codigo == "google_calendar")).scalar_one()
    integ.estado = "aguardando_credenciais"
    auditoria.registrar(db, ator, "integracao.desconectar", entidade="integracao", entidade_id="google_calendar")


def limpar_vinculos(db: Session, esc_id: uuid.UUID) -> None:
    """Ao trocar de agenda (simulada ↔ real), esquece os vínculos com a anterior: espelhos externos saem e os
    compromissos do EJMF voltam a ser enviados à nova agenda."""
    from sqlalchemy import delete, update
    db.execute(delete(Compromisso).where(Compromisso.escritorio_id == esc_id, Compromisso.tipo == "externo"))
    db.execute(update(Compromisso).where(Compromisso.escritorio_id == esc_id).values(
        google_event_id=None, google_etag=None, removido_no_google=False, sync_pendente=Compromisso.sincronizar_google))
    db.execute(update(Prazo).where(Prazo.escritorio_id == esc_id).values(google_event_id=None, google_vencimento=None))
    for codigo in CODIGOS:
        c = db.execute(select(CredencialIntegracao).where(CredencialIntegracao.escritorio_id == esc_id,
                                                          CredencialIntegracao.codigo == codigo)).scalar()
        if c and (c.estado or {}).get("sync_token"):
            c.estado = {k: v for k, v in c.estado.items() if k != "sync_token"}


def ativar_simulado(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, ativo: bool) -> None:
    if not obter_config().conectores_simulados:
        raise CredencialAusente("Adaptador simulado desligado (EJMF_CONECTORES_SIMULADOS=false)")
    real = credencial(db, esc_id, "google_calendar")
    if ativo and real.dados_cifrados:
        raise ValueError("A conta Google real está conectada: desconecte antes de usar a agenda simulada.")
    limpar_vinculos(db, esc_id)
    c = credencial(db, esc_id, "google_calendar_simulado", travar=True)
    est = dict(c.estado or {})
    est["ativo"] = ativo
    est.setdefault("servidor", novo_estado())
    c.estado = est
    auditoria.registrar(db, ator, "integracao.simulado", entidade="integracao", entidade_id="google_calendar_simulado",
                        alteracoes={"ativo": ativo})


def conector(db: Session, esc_id: uuid.UUID, codigo: str) -> tuple[ConectorGoogleAgenda, CredencialIntegracao]:
    cfg = obter_config()
    cal = svc_prazos.config(db, esc_id, "agenda.google_calendario_id", "primary")
    c = credencial(db, esc_id, codigo, travar=True)
    if codigo == "google_calendar_simulado":
        if not cfg.conectores_simulados or not (c.estado or {}).get("ativo"):
            raise CredencialAusente("Adaptador simulado do Google desligado")
        con = ConectorGoogleAgenda("simulado", cal, base_url=cfg.google_api_url, limitador=None,
                                   transporte=transporte_simulado(c.estado["servidor"]))
        con.simulado, con.codigo = True, codigo
        return con, c
    t = _tokens(c)
    if not t:
        raise CredencialAusente("Conta Google não conectada. Conecte em Agenda > Google Calendar.")
    if not t.get("access_token") or datetime.fromisoformat(t["expira_em"]) <= datetime.now(timezone.utc):
        if not t.get("refresh_token"):
            raise CredencialAusente("Token do Google expirado e sem renovação. Conecte a conta de novo.")
        t = oauth().renovar(t["refresh_token"])
        c.dados_cifrados = cifrar(json.dumps({k: t.get(k) for k in ("access_token", "refresh_token", "expira_em")}))
    return ConectorGoogleAgenda(t["access_token"], cal, base_url=cfg.google_api_url,
                                transporte=TRANSPORTES.get("api"), timeout=cfg.conectores_timeout_segundos), c


# ------------------------------------------------------------------ conversão

def _quando(v: dict | None) -> tuple[datetime | None, bool]:
    if not v:
        return None, False
    if v.get("dateTime"):
        return datetime.fromisoformat(v["dateTime"].replace("Z", "+00:00")), False
    if v.get("date"):
        return inicio_do_dia(date.fromisoformat(v["date"])), True
    return None, False


def evento_de_compromisso(c: Compromisso, processo: Processo | None) -> dict:
    tz = str(fuso())
    desc = [c.descricao or ""]
    if processo:
        desc.append(f"Processo {processo.numero_formatado}")
    desc.append("Criado pelo Escritório Jurídico Márcio Fernandes (EJMF). Altere de preferência pelo EJMF.")
    ev = {"summary": ("[Audiência] " if c.tipo == "audiencia" else "") + c.titulo,
          "description": "\n\n".join(x for x in desc if x), "location": c.local or c.link_virtual or None,
          "extendedProperties": {"private": {MARCA: str(c.id), "ejmf_tipo": c.tipo}},
          "visibility": "private" if c.tipo == "pessoal" else "default",
          "transparency": "opaque", "status": "confirmed"}
    if c.dia_inteiro:
        ini, fim = c.inicio.astimezone(fuso()).date(), c.fim.astimezone(fuso()).date()
        ev["start"], ev["end"] = {"date": ini.isoformat()}, {"date": (fim + timedelta(days=1)).isoformat()}
    else:
        ev["start"] = {"dateTime": c.inicio.astimezone(fuso()).isoformat(), "timeZone": tz}
        ev["end"] = {"dateTime": c.fim.astimezone(fuso()).isoformat(), "timeZone": tz}
    return ev


def evento_de_prazo(pz: Prazo, processo: Processo | None) -> dict:
    return {"summary": f"Prazo: {pz.descricao}",
            "description": "\n\n".join(x for x in [
                f"Processo {processo.numero_formatado}" if processo else "",
                f"Vencimento homologado no EJMF ({(pz.calculo or {}).get('regra', {}).get('nome', '')}).",
                "Gerado pelo EJMF; a data correta é sempre a do EJMF."] if x),
            "start": {"date": pz.vencimento.isoformat()}, "end": {"date": (pz.vencimento + timedelta(days=1)).isoformat()},
            "extendedProperties": {"private": {MARCA: f"prazo:{pz.id}", "ejmf_tipo": "prazo"}},
            "transparency": "transparent", "status": "confirmed"}


# ------------------------------------------------------------------ sincronização

def sincronizar(db: Session, esc_id: uuid.UUID, con: ConectorGoogleAgenda, cred: CredencialIntegracao, ator: auditoria.Ator) -> dict:
    cont = {"recebidos": 0, "externos_novos": 0, "externos_atualizados": 0, "alterados_no_google": 0,
            "removidos_no_google": 0, "aprovacoes": 0, "enviados": 0, "atualizados": 0, "excluidos": 0, "observacoes": []}
    estado = dict(cred.estado or {})
    token = estado.get("sync_token")
    try:
        itens, proximo = con.listar_mudancas(token, datetime.now(timezone.utc) - timedelta(days=JANELA_COMPLETA_DIAS))
    except SyncTokenExpirado:
        cont["observacoes"].append("token de sincronização expirado: leitura completa refeita")
        itens, proximo = con.listar_mudancas(None, datetime.now(timezone.utc) - timedelta(days=JANELA_COMPLETA_DIAS))
    cont["recebidos"] = len(itens)
    for ev in itens:
        _receber(db, esc_id, ev, con.simulado, ator, cont)
    db.flush()
    _enviar(db, esc_id, con, cont)
    estado["sync_token"] = proximo or token
    estado["ultima_sync"] = datetime.now(timezone.utc).isoformat()
    cred.estado = estado
    flag_modified(cred, "estado")  # o servidor simulado é alterado no lugar; força a gravação do JSONB
    return cont


def _receber(db: Session, esc_id: uuid.UUID, ev: dict, simulado: bool, ator: auditoria.Ator, cont: dict) -> None:
    marca = ((ev.get("extendedProperties") or {}).get("private") or {}).get(MARCA)
    cancelado = ev.get("status") == "cancelled"
    if marca and marca.startswith("prazo:"):
        pz = db.get(Prazo, uuid.UUID(marca.split(":", 1)[1])) if _uuid_ok(marca.split(":", 1)[1]) else None
        if pz and pz.escritorio_id == esc_id and cancelado and pz.google_event_id == ev["id"]:
            pz.google_event_id, pz.google_vencimento = None, None  # será recriado se ainda estiver homologado
        return
    if marca:
        c = db.get(Compromisso, uuid.UUID(marca)) if _uuid_ok(marca) else None
        if c is None or c.escritorio_id != esc_id:
            return
        if c.google_etag == ev.get("etag"):
            return  # eco do que o próprio EJMF enviou
        c.google_etag = ev.get("etag")
        if cancelado:
            if c.situacao == "agendado" and not c.removido_no_google:
                c.removido_no_google, c.google_event_id = True, None
                cont["removidos_no_google"] += 1
                auditoria.registrar(db, ator, "compromisso.removido_no_google", entidade="compromisso", entidade_id=c.id,
                                    origem="worker")
            return
        ini, dia_int = _quando(ev.get("start"))
        fim, _ = _quando(ev.get("end"))
        if dia_int and fim:
            fim -= timedelta(seconds=1)
        if ini is None or fim is None or (ini == c.inicio and fim == c.fim):
            return
        cont["alterados_no_google"] += 1
        if c.tipo == "audiencia":
            db.add(Aprovacao(escritorio_id=esc_id, tipo="reagendamento_google", entidade="compromisso", entidade_id=str(c.id),
                             titulo=f"Audiência reagendada no Google: {c.titulo}",
                             descricao="A audiência foi movida diretamente no Google Calendar. Ela só muda no EJMF se aprovada; "
                                       "se rejeitada, o EJMF devolve o horário original ao Google.",
                             dados={"de": {"inicio": c.inicio.isoformat(), "fim": c.fim.isoformat()},
                                    "para": {"inicio": ini.isoformat(), "fim": fim.isoformat()}},
                             permissao="agenda:cancelar_audiencia", solicitante_nome="Google Calendar"))
            cont["aprovacoes"] += 1
            return
        from app.servicos.agenda import alterar
        alterar(db, ator, c, {"inicio": ini, "fim": fim, "dia_inteiro": dia_int}, origem="google")
        c.sync_pendente = False
        return
    # evento externo
    c = db.execute(select(Compromisso).where(Compromisso.escritorio_id == esc_id,
                                             Compromisso.google_event_id == ev["id"])).scalar()
    if cancelado:
        if c and c.situacao != "cancelado":
            c.situacao, c.cancelado_motivo = "cancelado", "cancelado no Google"
            cont["externos_atualizados"] += 1
        return
    ini, dia_int = _quando(ev.get("start"))
    fim, _ = _quando(ev.get("end"))
    if ini is None or fim is None:
        return
    if dia_int:
        fim -= timedelta(seconds=1)
    privado = ev.get("visibility") in ("private", "confidential")
    titulo = "Ocupado (evento privado no Google)" if privado else (ev.get("summary") or "(sem título)")[:300]
    if c is None:
        c = Compromisso(escritorio_id=esc_id, tipo="externo", origem="google", google_event_id=ev["id"], simulado=simulado,
                        sincronizar_google=False, titulo=titulo, inicio=ini, fim=fim, dia_inteiro=dia_int, situacao="agendado")
        db.add(c)
        cont["externos_novos"] += 1
    else:
        cont["externos_atualizados"] += 1
        c.titulo, c.inicio, c.fim, c.dia_inteiro, c.situacao = titulo, ini, fim, dia_int, "agendado"
    c.local = None if privado else ev.get("location")
    c.descricao = None if privado else (ev.get("description") or None)
    c.google_etag, c.google_atualizado_em = ev.get("etag"), _quando({"dateTime": ev["updated"]})[0] if ev.get("updated") else None


def _uuid_ok(v: str) -> bool:
    try:
        uuid.UUID(v)
        return True
    except ValueError:
        return False


def _enviar(db: Session, esc_id: uuid.UUID, con: ConectorGoogleAgenda, cont: dict) -> None:
    procs: dict = {}

    def proc(pid):
        if pid and pid not in procs:
            procs[pid] = db.get(Processo, pid)
        return procs.get(pid)

    pend = db.execute(select(Compromisso).where(Compromisso.escritorio_id == esc_id, Compromisso.sync_pendente.is_(True),
                                                Compromisso.tipo != "externo")
                      .limit(500)).scalars().all()
    for c in pend:
        if c.situacao == "cancelado" or not c.sincronizar_google:
            if c.google_event_id:
                con.remover(c.google_event_id)  # evento criado pelo EJMF
                c.google_event_id, c.google_etag = None, None
                cont["excluidos"] += 1
        elif c.google_event_id:
            r = con.atualizar(c.google_event_id, evento_de_compromisso(c, proc(c.processo_id)))
            c.google_etag = r.get("etag")
            cont["atualizados"] += 1
        elif not c.removido_no_google:
            r = con.inserir(evento_de_compromisso(c, proc(c.processo_id)))
            c.google_event_id, c.google_etag = r["id"], r.get("etag")
            cont["enviados"] += 1
        c.sync_pendente = False
    if not svc_prazos.config(db, esc_id, "agenda.sincronizar_prazos_homologados", True):
        return
    hoje = svc_prazos.hoje_local()
    homologados = db.execute(select(Prazo).where(Prazo.escritorio_id == esc_id, Prazo.situacao == "homologado",
                                                 Prazo.simulado.is_(False), Prazo.vencimento >= hoje - timedelta(days=1))).scalars()
    for pz in homologados:
        if pz.google_event_id and pz.google_vencimento == pz.vencimento:
            continue
        ev = evento_de_prazo(pz, proc(pz.processo_id))
        if pz.google_event_id:
            con.atualizar(pz.google_event_id, ev)
            cont["atualizados"] += 1
        else:
            pz.google_event_id = con.inserir(ev)["id"]
            cont["enviados"] += 1
        pz.google_vencimento = pz.vencimento
    # prazo que deixou de ser homologado (alterado, devolvido) sai do Google: data não confirmada não vai para a agenda
    for pz in db.execute(select(Prazo).where(Prazo.escritorio_id == esc_id, Prazo.google_event_id.is_not(None),
                                             Prazo.situacao.not_in(("homologado", "concluido")))).scalars():
        con.remover(pz.google_event_id)
        pz.google_event_id, pz.google_vencimento = None, None
        cont["excluidos"] += 1


def decidir_reagendamento(db: Session, ator: auditoria.Ator, ap: Aprovacao, aprovado: bool) -> None:
    c = db.get(Compromisso, uuid.UUID(ap.entidade_id))
    if c is None:
        return
    from app.servicos.agenda import alterar
    if aprovado:
        alterar(db, ator, c, {"inicio": datetime.fromisoformat(ap.dados["para"]["inicio"]),
                              "fim": datetime.fromisoformat(ap.dados["para"]["fim"])}, origem="google")
        c.sync_pendente = False
    else:
        c.sync_pendente = True  # devolve o horário do EJMF ao Google na próxima sincronização
