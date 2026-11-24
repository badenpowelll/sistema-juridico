"""Agenda institucional: compromissos, audiências, conflitos, sobrecarga, disponibilidade e prazos na agenda.

Regras:
- Evento externo (vindo do Google) é só leitura no EJMF e nunca é excluído do Google.
- Cancelar audiência exige `agenda:cancelar_audiencia`; sem ela, o pedido vai para a central de aprovações.
- Compromisso pessoal aparece para os outros só como "Compromisso pessoal" (ocupa o horário, sem detalhes).
- Prazos entram na agenda como itens do dia do vencimento; os não homologados aparecem marcados "não confirmado".
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import obter_config
from app.modelos import Compromisso, Prazo, Processo, Usuario
from app.servicos import auditoria, prazos as svc_prazos

TIPOS = {
    "audiencia": "Audiência", "reuniao": "Reunião", "atendimento": "Atendimento", "compromisso": "Compromisso",
    "lembrete": "Lembrete", "bloqueio": "Bloqueio de agenda", "trabalho_concentrado": "Trabalho concentrado",
    "pessoal": "Compromisso pessoal", "externo": "Evento do Google",
}
SITUACOES = {"agendado": "Agendado", "realizado": "Realizado", "cancelado": "Cancelado"}
# tipos que ocupam a pessoa (entram em conflito e na carga do dia)
OCUPAM = {"audiencia", "reuniao", "atendimento", "compromisso", "bloqueio", "trabalho_concentrado", "pessoal", "externo"}
CARGA = {"audiencia", "reuniao", "atendimento", "compromisso", "trabalho_concentrado", "externo"}


class ErroAgenda(ValueError):
    pass


def fuso() -> ZoneInfo:
    return ZoneInfo(obter_config().fuso_horario)


def dia_local(d: datetime) -> date:
    return d.astimezone(fuso()).date()


def inicio_do_dia(d: date) -> datetime:
    return datetime.combine(d, time(0), fuso())


def _validar(dados: dict) -> None:
    if dados["fim"] < dados["inicio"]:
        raise ErroAgenda("O fim não pode ser antes do início")
    if dados["fim"] - dados["inicio"] > timedelta(days=31):
        raise ErroAgenda("Um compromisso não pode durar mais de 31 dias")
    if dados.get("tipo") == "externo":
        raise ErroAgenda("Eventos externos chegam só pela sincronização com o Google")
    if dados.get("tipo") == "audiencia" and not dados.get("processo_id"):
        raise ErroAgenda("Audiência precisa estar vinculada a um processo")


def _normalizar_dia_inteiro(dados: dict) -> None:
    if dados.get("dia_inteiro"):
        ini, fim = dia_local(dados["inicio"]), dia_local(dados["fim"])
        dados["inicio"], dados["fim"] = inicio_do_dia(ini), inicio_do_dia(fim) + timedelta(days=1) - timedelta(seconds=1)


CAMPOS = ("tipo", "titulo", "descricao", "local", "link_virtual", "modalidade", "inicio", "fim", "dia_inteiro",
          "processo_id", "cliente_id", "responsavel_id", "participantes", "sincronizar_google")


def criar(db: Session, ator: auditoria.Ator, esc_id: uuid.UUID, dados: dict, usuario: Usuario | None) -> Compromisso:
    _normalizar_dia_inteiro(dados)
    _validar(dados)
    c = Compromisso(escritorio_id=esc_id, criado_por=usuario.id if usuario else None, origem="manual",
                    **{k: dados.get(k) for k in CAMPOS if k in dados})
    c.participantes = [str(p) for p in (dados.get("participantes") or [])]
    c.responsavel_id = dados.get("responsavel_id") or (usuario.id if usuario else None)
    c.sync_pendente = c.sincronizar_google
    db.add(c)
    db.flush()
    auditoria.registrar(db, ator, "compromisso.criar", entidade="compromisso", entidade_id=c.id,
                        alteracoes={"tipo": c.tipo, "titulo": c.titulo if c.tipo != "pessoal" else "(pessoal)",
                                    "inicio": c.inicio, "fim": c.fim, "processo_id": c.processo_id})
    return c


def alterar(db: Session, ator: auditoria.Ator, c: Compromisso, dados: dict, *, origem: str = "api") -> Compromisso:
    if c.tipo == "externo":
        raise ErroAgenda("Evento externo: altere no Google")
    if c.situacao == "cancelado":
        raise ErroAgenda("Compromisso cancelado não pode ser alterado")
    novo = {k: getattr(c, k) for k in CAMPOS}
    novo.update({k: v for k, v in dados.items() if k in CAMPOS})
    if "dia_inteiro" in dados or "inicio" in dados or "fim" in dados:
        _normalizar_dia_inteiro(novo)
    _validar(novo)
    antes = {k: getattr(c, k) for k in CAMPOS}
    for k, v in novo.items():
        setattr(c, k, v)
    if "participantes" in dados:
        c.participantes = [str(p) for p in (dados.get("participantes") or [])]
    mudou = {k: {"de": antes[k], "para": getattr(c, k)} for k in CAMPOS if antes[k] != getattr(c, k)}
    if not mudou:
        return c
    reagendou = "inicio" in mudou or "fim" in mudou
    c.sync_pendente = c.sincronizar_google or bool(c.google_event_id)
    auditoria.registrar(db, ator, "compromisso.reagendar" if reagendou else "compromisso.alterar", entidade="compromisso",
                        entidade_id=c.id, alteracoes=mudou, origem=origem)
    return c


def cancelar(db: Session, ator: auditoria.Ator, c: Compromisso, motivo: str) -> Compromisso:
    if c.tipo == "externo":
        raise ErroAgenda("Evento externo: cancele no Google")
    if c.situacao != "agendado":
        raise ErroAgenda("Só compromisso agendado pode ser cancelado")
    if len((motivo or "").strip()) < 5:
        raise ErroAgenda("Informe o motivo do cancelamento")
    c.situacao, c.cancelado_motivo = "cancelado", motivo.strip()
    c.sync_pendente = bool(c.google_event_id)
    auditoria.registrar(db, ator, "compromisso.cancelar", entidade="compromisso", entidade_id=c.id,
                        alteracoes={"motivo": c.cancelado_motivo, "tipo": c.tipo})
    return c


def concluir(db: Session, ator: auditoria.Ator, c: Compromisso, resultado: str | None) -> Compromisso:
    if c.tipo == "externo":
        raise ErroAgenda("Evento externo não é concluído no EJMF")
    if c.situacao != "agendado":
        raise ErroAgenda("Só compromisso agendado pode ser marcado como realizado")
    if c.tipo == "audiencia" and len((resultado or "").strip()) < 3:
        raise ErroAgenda("Registre o resultado da audiência")
    c.situacao, c.resultado = "realizado", (resultado or "").strip() or None
    auditoria.registrar(db, ator, "compromisso.concluir", entidade="compromisso", entidade_id=c.id,
                        alteracoes={"resultado": c.resultado})
    return c


# ------------------------------------------------------------------ leitura

def no_periodo(db: Session, esc_id: uuid.UUID, ini: datetime, fim: datetime, *, incluir_cancelados: bool = False,
               processo_id: uuid.UUID | None = None) -> list[Compromisso]:
    conds = [Compromisso.escritorio_id == esc_id, Compromisso.inicio <= fim, Compromisso.fim >= ini]
    if not incluir_cancelados:
        conds.append(Compromisso.situacao != "cancelado")
    if processo_id:
        conds.append(Compromisso.processo_id == processo_id)
    return list(db.execute(select(Compromisso).where(*conds).order_by(Compromisso.inicio)).scalars())


def prazos_no_periodo(db: Session, esc_id: uuid.UUID, d_ini: date, d_fim: date) -> list[Prazo]:
    return list(db.execute(select(Prazo).where(
        Prazo.escritorio_id == esc_id, Prazo.vencimento >= d_ini, Prazo.vencimento <= d_fim,
        Prazo.situacao.not_in(("concluido",)))).scalars())


def _pessoas(c: Compromisso) -> set[str]:
    p = {str(x) for x in (c.participantes or [])}
    if c.responsavel_id:
        p.add(str(c.responsavel_id))
    return p or {"escritorio"}


@dataclass
class Conflito:
    a: Compromisso
    b: Compromisso
    pessoas: set[str]


def conflitos(itens: list[Compromisso]) -> list[Conflito]:
    """Sobreposição de horário entre compromissos que ocupam a mesma pessoa. Lembretes e dia inteiro não conflitam,
    exceto bloqueio de dia inteiro."""
    cand = [c for c in itens if c.situacao == "agendado" and c.tipo in OCUPAM and (not c.dia_inteiro or c.tipo == "bloqueio")]
    cand.sort(key=lambda c: c.inicio)
    out: list[Conflito] = []
    for i, a in enumerate(cand):
        for b in cand[i + 1:]:
            if b.inicio >= a.fim:
                break
            if a.tipo == "bloqueio" and b.tipo == "bloqueio":
                continue
            comuns = _pessoas(a) & _pessoas(b)
            if "escritorio" in _pessoas(a) or "escritorio" in _pessoas(b):
                comuns = comuns or (_pessoas(a) | _pessoas(b))
            if comuns:
                out.append(Conflito(a, b, comuns))
    return out


def sobrecarga(db: Session, esc_id: uuid.UUID, itens: list[Compromisso]) -> list[dict]:
    """Dias (e pessoas) acima do limite de horas ou de audiências configurado."""
    lim_h = float(svc_prazos.config(db, esc_id, "agenda.limite_horas_dia", 8))
    lim_a = int(svc_prazos.config(db, esc_id, "agenda.limite_audiencias_dia", 4))
    por: dict[tuple[date, str], dict] = {}
    for c in itens:
        if c.situacao == "cancelado" or c.tipo not in CARGA or c.dia_inteiro:
            continue
        for pessoa in _pessoas(c):
            k = (dia_local(c.inicio), pessoa)
            r = por.setdefault(k, {"dia": k[0], "pessoa": pessoa, "horas": 0.0, "audiencias": 0})
            r["horas"] += (c.fim - c.inicio).total_seconds() / 3600
            r["audiencias"] += c.tipo == "audiencia"
    out = []
    for r in por.values():
        motivos = []
        if r["horas"] > lim_h:
            motivos.append(f"{r['horas']:.1f} h de compromissos (limite {lim_h:g} h)")
        if r["audiencias"] > lim_a:
            motivos.append(f"{r['audiencias']} audiências (limite {lim_a})")
        if motivos:
            out.append({**r, "horas": round(r["horas"], 1), "motivos": motivos})
    return sorted(out, key=lambda r: r["dia"])


def _hhmm(v: str, padrao: time) -> time:
    try:
        h, m = str(v).split(":")
        return time(int(h), int(m))
    except (ValueError, AttributeError):
        return padrao


def disponibilidade(db: Session, esc_id: uuid.UUID, dia: date, pessoa: str | None, duracao_min: int = 60) -> list[dict]:
    """Janelas livres no expediente do dia para a pessoa (ou para o escritório)."""
    ini_exp = datetime.combine(dia, _hhmm(svc_prazos.config(db, esc_id, "agenda.expediente_inicio", "08:00"), time(8)), fuso())
    fim_exp = datetime.combine(dia, _hhmm(svc_prazos.config(db, esc_id, "agenda.expediente_fim", "18:00"), time(18)), fuso())
    if not svc_prazos.calendario_para(db, esc_id, None, dia, dia).util(dia):
        return []
    ocup = sorted((c.inicio, c.fim) for c in no_periodo(db, esc_id, ini_exp, fim_exp)
                  if c.tipo in OCUPAM and (pessoa is None or pessoa in _pessoas(c) or "escritorio" in _pessoas(c)))
    livres, cursor = [], ini_exp
    for a, b in ocup:
        if a > cursor and (a - cursor) >= timedelta(minutes=duracao_min):
            livres.append({"inicio": cursor, "fim": a})
        cursor = max(cursor, b)
    if fim_exp > cursor and (fim_exp - cursor) >= timedelta(minutes=duracao_min):
        livres.append({"inicio": cursor, "fim": fim_exp})
    return livres


def como_json(c: Compromisso, *, visualizador: uuid.UUID | None = None, processo: Processo | None = None,
              nomes: dict | None = None) -> dict:
    nomes = nomes or {}
    oculto = c.tipo == "pessoal" and visualizador not in (c.criado_por, c.responsavel_id)
    return {
        "id": str(c.id), "tipo": c.tipo, "tipo_rotulo": TIPOS[c.tipo],
        "titulo": "Compromisso pessoal" if oculto else c.titulo,
        "descricao": None if oculto else c.descricao, "local": None if oculto else c.local,
        "link_virtual": None if oculto else c.link_virtual, "modalidade": c.modalidade,
        "inicio": c.inicio.astimezone(timezone.utc), "fim": c.fim.astimezone(timezone.utc), "dia_inteiro": c.dia_inteiro,
        "processo_id": str(c.processo_id) if c.processo_id else None,
        "processo": {"numero": processo.numero_formatado} if processo and not oculto else None,
        "responsavel_id": str(c.responsavel_id) if c.responsavel_id else None, "responsavel": nomes.get(c.responsavel_id),
        "participantes": c.participantes, "situacao": c.situacao, "situacao_rotulo": SITUACOES[c.situacao],
        "resultado": c.resultado, "cancelado_motivo": c.cancelado_motivo, "origem": c.origem, "simulado": c.simulado,
        "privado": oculto, "somente_leitura": c.tipo == "externo",
        "sincronizar_google": c.sincronizar_google, "no_google": bool(c.google_event_id), "sync_pendente": c.sync_pendente,
        "removido_no_google": c.removido_no_google, "criado_em": c.criado_em,
    }


def prazo_na_agenda(pz: Prazo, processo: Processo | None) -> dict:
    return {"id": f"prazo:{pz.id}", "prazo_id": str(pz.id), "tipo": "prazo", "tipo_rotulo": "Prazo",
            "titulo": pz.descricao, "data": pz.vencimento, "confirmado": pz.situacao == "homologado",
            "situacao": pz.situacao, "processo_id": str(pz.processo_id),
            "processo": {"numero": processo.numero_formatado} if processo else None, "simulado": pz.simulado}
