"""Construtor de automações (seção 30). Avaliado contra o n8n no ADR-0012: ficou interno.

Uma automação = gatilho (lista fechada) + condições (E) + ações (lista fechada) + janela de horário.
- Os gatilhos são varreduras idempotentes: cada ocorrência tem uma chave e nunca é tratada duas vezes.
- Antes de ativar, a versão atual tem de passar pelo teste (roda sobre os dados de agora, sem efeito nenhum).
- Editar cria nova versão e devolve ao rascunho. Três falhas seguidas pausam a automação e avisam.
- Ações possíveis: notificar, criar pendência e pedir uma função virtual (que segue o próprio nível de autonomia).
  Não existe ação de enviar mensagem, e-mail, assinar, protocolar ou pagar.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modelos import (
    Assinatura, Automacao, Cliente, Compromisso, DocumentoRecebido, ExecucaoAutomacao, Minuta, Pendencia, Prazo, Processo, Publicacao,
    Usuario,
)
from app.servicos import agenda, auditoria, catalogo as cat_geral, contingencia, notificacoes
from app.servicos.ia import catalogo as cat_ia

LIMITE_EVENTOS = 50
OLHAR_PARA_TRAS_TESTE = timedelta(days=7)
SITUACOES = {"rascunho": "Rascunho", "testada": "Testada", "ativa": "Ativa", "pausada": "Pausada", "desativada": "Desativada"}


class ErroAutomacao(ValueError):
    def __init__(self, msg: str, status: int = 422):
        super().__init__(msg)
        self.status = status


@dataclass
class Gatilho:
    nome: str
    descricao: str
    campos: tuple[str, ...]
    parametros: dict[str, tuple[int, int, int]] = field(default_factory=dict)  # nome: (padrão, mínimo, máximo)
    varrer: Callable | None = None
    indisponivel: str | None = None


def _local(dt) -> str | None:
    return dt.astimezone(agenda.fuso()).strftime("%d/%m/%Y %H:%M") if dt else None


def _cliente_novo(db, esc, desde, agora, p):
    for c in db.execute(select(Cliente).where(Cliente.escritorio_id == esc, Cliente.criado_em > desde)
                        .order_by(Cliente.criado_em).limit(LIMITE_EVENTOS)).scalars():
        yield {"chave": f"cliente:{c.id}", "id": str(c.id), "nome": c.nome, "tipo": c.tipo, "origem": c.origem,
               "link": f"/painel/clientes/{c.id}"}


def _documento_recebido(db, esc, desde, agora, p):
    for d in db.execute(select(DocumentoRecebido).where(DocumentoRecebido.escritorio_id == esc, DocumentoRecebido.criado_em > desde)
                        .order_by(DocumentoRecebido.criado_em).limit(LIMITE_EVENTOS)).scalars():
        yield {"chave": f"docrecebido:{d.id}", "id": str(d.id), "arquivo": d.nome_original, "origem": d.origem,
               "documento_previsto": d.documento_previsto or "", "simulado": d.simulado,
               "link": f"/painel/atendimentos/{d.atendimento_id}" if d.atendimento_id else "/painel/atendimentos"}


def _publicacao(db, esc, desde, agora, p):
    for x in db.execute(select(Publicacao).where(Publicacao.escritorio_id == esc, Publicacao.capturado_em > desde,
                                                 Publicacao.situacao != "duplicada")
                        .order_by(Publicacao.capturado_em).limit(LIMITE_EVENTOS)).scalars():
        yield {"chave": f"publicacao:{x.id}", "id": str(x.id), "processo": x.numero_formatado or "", "tribunal": x.tribunal_sigla or "",
               "tipo": x.tipo_documento or x.tipo, "simulado": x.simulado, "texto": x.texto[:2000],
               "link": f"/painel/publicacoes/{x.id}"}


def _janela(agora, horas: int) -> str:
    return str(int(agora.timestamp() // (horas * 3600)))


def _assinatura(db, esc, desde, agora, p):
    corte = agora - timedelta(days=p["dias"])
    for a, m in db.execute(select(Assinatura, Minuta).join(Minuta, Minuta.id == Assinatura.minuta_id).where(
            Assinatura.escritorio_id == esc, Assinatura.situacao.in_(("enviada", "parcial")), Assinatura.enviada_em < corte)
            .limit(LIMITE_EVENTOS)).all():
        yield {"chave": f"assinatura:{a.id}:{_janela(agora, p['repetir_horas'])}", "id": str(a.id), "documento": m.titulo,
               "situacao": a.situacao, "dias": (agora - a.enviada_em).days, "link": f"/painel/minutas/{m.id}"}


def _compromisso(db, esc, desde, agora, p):
    for c in db.execute(select(Compromisso).where(
            Compromisso.escritorio_id == esc, Compromisso.situacao == "agendado", Compromisso.tipo != "pessoal",
            Compromisso.inicio > agora, Compromisso.inicio <= agora + timedelta(hours=p["horas"]))
            .order_by(Compromisso.inicio).limit(LIMITE_EVENTOS)).scalars():
        yield {"chave": f"compromisso:{c.id}:{c.inicio.isoformat()}", "id": str(c.id), "tipo": agenda.TIPOS.get(c.tipo, c.tipo),
               "titulo": c.titulo, "inicio": _local(c.inicio), "simulado": c.simulado,
               "link": f"/painel/agenda?compromisso={c.id}"}


def _sem_atualizacao(db, esc, desde, agora, p):
    corte = agora - timedelta(days=p["dias"])
    for x in db.execute(select(Processo).where(
            Processo.escritorio_id == esc, Processo.status == "ativo",
            ((Processo.ultima_movimentacao_em < corte) | (Processo.ultima_movimentacao_em.is_(None) & (Processo.criado_em < corte))))
            .order_by(Processo.ultima_movimentacao_em.asc().nulls_first()).limit(LIMITE_EVENTOS)).scalars():
        ref = x.ultima_movimentacao_em or x.criado_em
        yield {"chave": f"processo:{x.id}:{_janela(agora, p['repetir_dias'] * 24)}", "id": str(x.id),
               "processo": x.numero_formatado, "dias_sem_movimentacao": (agora - ref).days, "link": f"/painel/processos/{x.id}"}


def _prazo_sem_homologacao(db, esc, desde, agora, p):
    from app.servicos import prazos as svc_prazos
    hoje = svc_prazos.hoje_local()
    for pz, proc in db.execute(select(Prazo, Processo).join(Processo, Processo.id == Prazo.processo_id).where(
            Prazo.escritorio_id == esc, Prazo.situacao.in_(("sugerido", "aguardando_conferencia", "alterado")),
            Prazo.vencimento >= hoje, Prazo.vencimento <= hoje + timedelta(days=p["dias"]))
            .order_by(Prazo.vencimento).limit(LIMITE_EVENTOS)).all():
        yield {"chave": f"prazo:{pz.id}:{pz.vencimento}", "id": str(pz.id), "descricao": pz.descricao,
               "processo": proc.numero_formatado, "vencimento": pz.vencimento.strftime("%d/%m/%Y"), "situacao": pz.situacao,
               "link": f"/painel/prazos/{pz.id}"}


def _integracao(db, esc, desde, agora, p):
    dia = agora.astimezone(agenda.fuso()).date().isoformat()
    for f in contingencia.central(db, esc)["fontes"]:
        if f["comprometido"]:
            yield {"chave": f"fonte:{f['codigo']}:{dia}", "id": f["codigo"], "fonte": f["nome"],
                   "motivos": "; ".join(f["motivos"]), "link": "/painel/contingencia"}


GATILHOS: dict[str, Gatilho] = {
    "cliente_novo": Gatilho("Novo cliente", "Cliente cadastrado", ("nome", "tipo", "origem"), varrer=_cliente_novo),
    "documento_recebido": Gatilho("Documento recebido", "Arquivo enviado pelo link de cadastro, portal ou WhatsApp",
                                  ("arquivo", "origem", "documento_previsto"), varrer=_documento_recebido),
    "publicacao_capturada": Gatilho("Publicação capturada", "Nova publicação do DJEN ou cadastrada",
                                    ("processo", "tribunal", "tipo", "texto"), varrer=_publicacao),
    "assinatura_pendente": Gatilho("Contrato aguardando assinatura", "Envelope enviado e não concluído há N dias",
                                   ("documento", "situacao", "dias"), {"dias": (3, 1, 60), "repetir_horas": (24, 6, 720)},
                                   varrer=_assinatura),
    "compromisso_proximo": Gatilho("Compromisso próximo", "Compromisso ou audiência começando nas próximas N horas",
                                   ("tipo", "titulo", "inicio"), {"horas": (24, 1, 168)}, varrer=_compromisso),
    "processo_sem_atualizacao": Gatilho("Processo sem atualização", "Processo ativo sem movimentação há N dias",
                                        ("processo", "dias_sem_movimentacao"), {"dias": (90, 7, 3650), "repetir_dias": (30, 1, 365)},
                                        varrer=_sem_atualizacao),
    "prazo_sem_homologacao": Gatilho("Prazo sem homologação", "Prazo vencendo em N dias e ainda não homologado",
                                     ("descricao", "processo", "vencimento", "situacao"), {"dias": (5, 0, 60)},
                                     varrer=_prazo_sem_homologacao),
    "integracao_falhou": Gatilho("Falha de integração", "Fonte comprometida na central de contingência (uma vez por dia)",
                                 ("fonte", "motivos"), varrer=_integracao),
    "honorario_pendente": Gatilho("Honorário pendente", "Parcela vencida", ("cliente", "valor"),
                                  indisponivel="Depende do módulo financeiro (Fase 9)"),
    "backup_nao_realizado": Gatilho("Backup não realizado", "Backup do dia não concluído", ("data",),
                                    indisponivel="Depende do backup externo (Fase 11)"),
}

OPERADORES = {"igual": lambda a, b: str(a).lower() == str(b).lower(), "diferente": lambda a, b: str(a).lower() != str(b).lower(),
              "contem": lambda a, b: str(b).lower() in str(a).lower(), "nao_contem": lambda a, b: str(b).lower() not in str(a).lower(),
              "maior": lambda a, b: _num(a) > _num(b), "menor": lambda a, b: _num(a) < _num(b)}

# Funções que uma automação pode pedir, por gatilho, e como montar a entrada a partir do evento
FUNCOES_POR_GATILHO: dict[str, dict[str, Callable[[dict], dict]]] = {
    "publicacao_capturada": {"organizador_audiencias": lambda ev: {"entrada": {"publicacao_id": ev["id"]}}},
    "processo_sem_atualizacao": {"classificador_processual": lambda ev: {"entrada": {}, "processo_id": uuid.UUID(ev["id"])}},
    "integracao_falhou": {"monitor_integracoes": lambda ev: {"entrada": {}}},
}
ACOES = {"notificar": "Notificar quem tem uma permissão", "criar_pendencia": "Criar pendência na central de prioridades",
         "executar_funcao": "Pedir uma função virtual (segue o nível de autonomia dela)"}


def _num(v) -> float:
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return float("nan")


def _render(modelo: str, ev: dict, campos: tuple[str, ...]) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(ev.get(m.group(1), "")) if m.group(1) in campos else "", modelo or "")[:500]


# ---------------------------------------------------------------- validação

def validar(dados: dict) -> dict:
    g = GATILHOS.get(dados.get("gatilho"))
    if g is None:
        raise ErroAutomacao("Gatilho inválido")
    if g.indisponivel:
        raise ErroAutomacao(f"Gatilho indisponível: {g.indisponivel}")
    params = {}
    for nome, (padrao, mn, mx) in g.parametros.items():
        v = (dados.get("parametros") or {}).get(nome, padrao)
        try:
            v = int(v)
        except (TypeError, ValueError):
            raise ErroAutomacao(f"Parâmetro {nome} inválido") from None
        if not mn <= v <= mx:
            raise ErroAutomacao(f"Parâmetro {nome} deve ficar entre {mn} e {mx}")
        params[nome] = v
    conds = []
    for c in dados.get("condicoes") or []:
        if c.get("campo") not in g.campos or c.get("operador") not in OPERADORES:
            raise ErroAutomacao("Condição inválida: escolha um campo do gatilho e um operador da lista")
        conds.append({"campo": c["campo"], "operador": c["operador"], "valor": str(c.get("valor", ""))[:200]})
    if len(conds) > 10:
        raise ErroAutomacao("No máximo 10 condições")
    acoes = []
    for a in dados.get("acoes") or []:
        tipo = a.get("tipo")
        if tipo == "notificar":
            perm = a.get("permissao")
            if perm not in cat_geral.PERMISSOES:
                raise ErroAutomacao("Escolha a permissão de quem será notificado")
            if not str(a.get("titulo") or "").strip():
                raise ErroAutomacao("A notificação precisa de título")
            acoes.append({"tipo": tipo, "permissao": perm, "titulo": str(a["titulo"])[:200], "texto": str(a.get("texto") or "")[:500],
                          "nivel": "alerta" if a.get("nivel") == "alerta" else "info"})
        elif tipo == "criar_pendencia":
            if not str(a.get("titulo") or "").strip():
                raise ErroAutomacao("A pendência precisa de título")
            acoes.append({"tipo": tipo, "titulo": str(a["titulo"])[:200], "descricao": str(a.get("descricao") or "")[:500]})
        elif tipo == "executar_funcao":
            permitidas = FUNCOES_POR_GATILHO.get(dados["gatilho"], {})
            if a.get("funcao") not in permitidas:
                raise ErroAutomacao("Esta função não pode ser pedida por este gatilho")
            acoes.append({"tipo": tipo, "funcao": a["funcao"]})
        else:
            raise ErroAutomacao("Ação fora da lista permitida")
    if not acoes:
        raise ErroAutomacao("Inclua ao menos uma ação")
    if len(acoes) > 5:
        raise ErroAutomacao("No máximo 5 ações")
    h = dados.get("horario") or {}
    horario = {"dias_uteis": bool(h.get("dias_uteis")), "inicio": h.get("inicio") or None, "fim": h.get("fim") or None}
    for k in ("inicio", "fim"):
        if horario[k] and not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", horario[k]):
            raise ErroAutomacao("Horário no formato HH:MM")
    nome = str(dados.get("nome") or "").strip()
    if len(nome) < 3:
        raise ErroAutomacao("Dê um nome à automação")
    return {"nome": nome[:200], "descricao": (str(dados.get("descricao") or "").strip() or None), "gatilho": dados["gatilho"],
            "parametros": params, "condicoes": conds, "acoes": acoes, "horario": horario}


# ---------------------------------------------------------------- ciclo de vida

def criar(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, usuario: Usuario, dados: dict) -> Automacao:
    v = validar(dados)
    a = Automacao(escritorio_id=esc_id, criado_por=usuario.id, **v)
    db.add(a)
    db.flush()
    auditoria.registrar(db, ator, "automacao.criar", entidade="automacao", entidade_id=a.id, alteracoes=v)
    return a


def alterar(db: Session, ator: auditoria.Ator, a: Automacao, dados: dict) -> Automacao:
    if a.situacao == "desativada":
        raise ErroAutomacao("Automação desativada não é editada: crie outra", 409)
    v = validar({**dados, "gatilho": dados.get("gatilho", a.gatilho)})
    for k, x in v.items():
        setattr(a, k, x)
    a.versao += 1
    a.situacao = "rascunho"
    auditoria.registrar(db, ator, "automacao.alterar", entidade="automacao", entidade_id=a.id,
                        alteracoes={**v, "versao": a.versao, "observacao": "nova versão volta ao rascunho e precisa de teste"})
    return a


def _na_janela(a: Automacao, agora: datetime) -> bool:
    h = a.horario or {}
    local = agora.astimezone(agenda.fuso())
    if h.get("dias_uteis") and local.weekday() >= 5:
        return False
    hm = local.strftime("%H:%M")
    if h.get("inicio") and hm < h["inicio"]:
        return False
    if h.get("fim") and hm > h["fim"]:
        return False
    return True


def _eventos(db: Session, a: Automacao, desde: datetime, agora: datetime) -> list[dict]:
    g = GATILHOS[a.gatilho]
    params = {k: (a.parametros or {}).get(k, padrao) for k, (padrao, _, _) in g.parametros.items()}
    return list(g.varrer(db, a.escritorio_id, desde, agora, params))[:LIMITE_EVENTOS]


def _condicoes_ok(a: Automacao, ev: dict) -> bool:
    return all(OPERADORES[c["operador"]](ev.get(c["campo"], ""), c["valor"]) for c in a.condicoes or [])


def _previstas(a: Automacao, ev: dict) -> list[dict]:
    campos = GATILHOS[a.gatilho].campos
    out = []
    for ac in a.acoes or []:
        if ac["tipo"] == "notificar":
            out.append({"tipo": "notificar", "permissao": ac["permissao"], "titulo": _render(ac["titulo"], ev, campos),
                        "texto": _render(ac["texto"], ev, campos)})
        elif ac["tipo"] == "criar_pendencia":
            out.append({"tipo": "criar_pendencia", "titulo": _render(ac["titulo"], ev, campos),
                        "descricao": _render(ac["descricao"], ev, campos)})
        else:
            f = cat_ia.POR_CODIGO[ac["funcao"]]
            out.append({"tipo": "executar_funcao", "funcao": f.codigo, "funcao_nome": f.nome})
    return out


def _publico(ev: dict) -> dict:
    return {k: v for k, v in ev.items() if k != "texto"}


def testar(db: Session, ator: auditoria.Ator, a: Automacao, agora: datetime | None = None) -> dict:
    """Roda sobre os dados atuais (últimos 7 dias para gatilhos de novidade) sem efeito nenhum."""
    agora = agora or datetime.now(timezone.utc)
    if a.situacao == "desativada":
        raise ErroAutomacao("Automação desativada", 409)
    eventos = _eventos(db, a, agora - OLHAR_PARA_TRAS_TESTE, agora)
    casos = []
    for ev in eventos:
        ok = _condicoes_ok(a, ev)
        casos.append({"evento": _publico(ev), "condicoes": ok, "acoes": _previstas(a, ev) if ok else []})
    resultado = {"eventos": len(eventos), "disparariam": sum(1 for c in casos if c["condicoes"]), "casos": casos[:20],
                 "na_janela_agora": _na_janela(a, agora)}
    db.add(ExecucaoAutomacao(escritorio_id=a.escritorio_id, automacao_id=a.id, versao=a.versao, modo="teste",
                             chave=f"teste:{uuid.uuid4().hex}", evento={"eventos": len(eventos)}, resultado=casos[:20],
                             situacao="concluida"))
    a.testada_versao, a.testada_em = a.versao, agora
    if a.situacao == "rascunho":
        a.situacao = "testada"
    auditoria.registrar(db, ator, "automacao.testar", entidade="automacao", entidade_id=a.id,
                        alteracoes={"versao": a.versao, "eventos": len(eventos), "disparariam": resultado["disparariam"]})
    return resultado


def mudar_situacao(db: Session, ator: auditoria.Ator, a: Automacao, usuario: Usuario, acao: str, motivo: str | None = None) -> Automacao:
    agora = datetime.now(timezone.utc)
    if acao == "ativar":
        if a.situacao not in ("testada", "pausada"):
            raise ErroAutomacao("Teste a automação antes de ativar", 409)
        if a.testada_versao != a.versao:
            raise ErroAutomacao("A versão atual ainda não foi testada", 409)
        a.situacao, a.ativada_por, a.ativada_em, a.falhas_seguidas = "ativa", usuario.id, agora, 0
        a.ultima_varredura = agora  # só age sobre o que acontecer daqui em diante (e estados atuais)
    elif acao == "pausar":
        if a.situacao != "ativa":
            raise ErroAutomacao("Só uma automação ativa pode ser pausada", 409)
        a.situacao = "pausada"
    elif acao == "desativar":
        if len((motivo or "").strip()) < 3:
            raise ErroAutomacao("Explique o motivo")
        a.situacao = "desativada"
    else:
        raise ErroAutomacao("Ação inválida")
    auditoria.registrar(db, ator, f"automacao.{acao}", entidade="automacao", entidade_id=a.id,
                        alteracoes={"versao": a.versao, "motivo": motivo})
    return a


# ---------------------------------------------------------------- execução real (worker)

def _agir(db: Session, a: Automacao, ev: dict, ator: auditoria.Ator) -> tuple[list[dict], str]:
    from app.servicos.ia import orquestrador
    feitos, situacao = [], "concluida"
    for ac in _previstas(a, ev):
        if ac["tipo"] == "notificar":
            n = notificacoes.notificar(db, a.escritorio_id, ac["permissao"], ac["titulo"] or a.nome, texto=ac["texto"] or None,
                                       link=ev.get("link"), chave=f"automacao:{a.id}:{ev['chave']}")
            feitos.append({**ac, "destinatarios": n})
        elif ac["tipo"] == "criar_pendencia":
            r = db.execute(insert(Pendencia).values(
                escritorio_id=a.escritorio_id, chave=f"automacao:{a.id}:{ev['chave']}"[:200], origem="manual", tipo="automacao",
                titulo=ac["titulo"] or a.nome, descricao=ac["descricao"] or f"Criada pela automação “{a.nome}”.",
                link=ev.get("link"), situacao="aberta").on_conflict_do_nothing())
            feitos.append({**ac, "criada": bool(r.rowcount)})
        else:
            montar = FUNCOES_POR_GATILHO[a.gatilho][ac["funcao"]](ev)
            try:
                ex = orquestrador.solicitar(db, ator, a.escritorio_id, ac["funcao"], montar.get("entrada", {}), origem="automacao",
                                            chave=f"automacao:{a.id}:{ev['chave']}"[:200], processo_id=montar.get("processo_id"))
                feitos.append({**ac, "execucao_id": str(ex.id)})
            except orquestrador.ErroOrquestrador as e:
                feitos.append({**ac, "erro": str(e)})
                situacao = "falhou"
    return feitos, situacao


def varrer(db: Session, a: Automacao, agora: datetime | None = None) -> dict:
    agora = agora or datetime.now(timezone.utc)
    if a.situacao != "ativa" or not _na_janela(a, agora):
        return {"ignorada": True}
    ator = auditoria.Ator("sistema", None, f"Automação: {a.nome}", a.escritorio_id)
    desde = a.ultima_varredura or a.ativada_em or agora
    n = falhas = 0
    for ev in _eventos(db, a, desde, agora):
        ja = db.execute(select(ExecucaoAutomacao.id).where(ExecucaoAutomacao.automacao_id == a.id, ExecucaoAutomacao.modo == "real",
                                                           ExecucaoAutomacao.chave == ev["chave"][:200])).scalar()
        if ja:
            continue
        if not _condicoes_ok(a, ev):
            continue
        sp = db.begin_nested()
        try:
            feitos, situacao = _agir(db, a, ev, ator)
            sp.commit()
            erro = None
        except Exception as e:  # noqa: BLE001 — falha de uma ocorrência fica registrada e não derruba as outras
            sp.rollback()
            feitos, situacao, erro = [], "falhou", str(e)[:1000]
        db.add(ExecucaoAutomacao(escritorio_id=a.escritorio_id, automacao_id=a.id, versao=a.versao, modo="real",
                                 chave=ev["chave"][:200], evento=_publico(ev), resultado=feitos, situacao=situacao, erro=erro))
        db.flush()
        n += 1
        falhas += situacao == "falhou"
    a.ultima_varredura = agora
    a.falhas_seguidas = a.falhas_seguidas + falhas if falhas else 0
    if a.falhas_seguidas >= 3:
        a.situacao = "pausada"
        notificacoes.notificar(db, a.escritorio_id, "automacoes:gerenciar", f"Automação pausada: {a.nome}",
                               texto="Três falhas seguidas. Veja o histórico de execuções.", link=f"/painel/automacoes/{a.id}",
                               chave=f"automacao-pausada:{a.id}:{a.versao}", nivel="alerta")
        auditoria.registrar(db, ator, "automacao.pausar_por_falhas", entidade="automacao", entidade_id=a.id,
                            alteracoes={"falhas_seguidas": a.falhas_seguidas})
    return {"ocorrencias": n, "falhas": falhas}


def varrer_todas(db: Session, esc_id: uuid.UUID, agora: datetime | None = None) -> int:
    total = 0
    for a in db.execute(select(Automacao).where(Automacao.escritorio_id == esc_id, Automacao.situacao == "ativa")).scalars():
        total += varrer(db, a, agora).get("ocorrencias", 0)
    return total


def como_json(a: Automacao) -> dict:
    g = GATILHOS.get(a.gatilho)
    return {"id": str(a.id), "nome": a.nome, "descricao": a.descricao, "gatilho": a.gatilho, "gatilho_nome": g.nome if g else a.gatilho,
            "parametros": a.parametros, "condicoes": a.condicoes, "acoes": a.acoes, "horario": a.horario, "situacao": a.situacao,
            "situacao_rotulo": SITUACOES.get(a.situacao, a.situacao), "versao": a.versao, "testada_versao": a.testada_versao,
            "testada_em": a.testada_em, "pode_ativar": a.situacao in ("testada", "pausada") and a.testada_versao == a.versao,
            "ativada_em": a.ativada_em, "ultima_varredura": a.ultima_varredura, "falhas_seguidas": a.falhas_seguidas,
            "criado_em": a.criado_em}


def execucao_json(e: ExecucaoAutomacao) -> dict:
    return {"id": str(e.id), "versao": e.versao, "modo": e.modo, "evento": e.evento, "resultado": e.resultado,
            "situacao": e.situacao, "erro": e.erro, "criado_em": e.criado_em}


def catalogo_json() -> dict:
    return {"gatilhos": [{"codigo": k, "nome": g.nome, "descricao": g.descricao, "campos": list(g.campos),
                          "parametros": {n: {"padrao": p[0], "minimo": p[1], "maximo": p[2]} for n, p in g.parametros.items()},
                          "indisponivel": g.indisponivel,
                          "funcoes": [{"codigo": c, "nome": cat_ia.POR_CODIGO[c].nome} for c in FUNCOES_POR_GATILHO.get(k, {})]}
                         for k, g in GATILHOS.items()],
            "operadores": {"igual": "é igual a", "diferente": "é diferente de", "contem": "contém", "nao_contem": "não contém",
                           "maior": "é maior que", "menor": "é menor que"},
            "acoes": ACOES}
