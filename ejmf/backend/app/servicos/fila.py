"""Fila de tarefas no PostgreSQL: idempotência por chave, tentativas com espera exponencial e retomada.

Sem broker externo: o worker pega tarefas com `FOR UPDATE SKIP LOCKED` (vários workers não pegam a mesma).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.modelos import Tarefa

ESPERA_BASE_S = 60
ESPERA_MAX_S = 3600
TRAVADA_APOS = timedelta(minutes=30)

EXECUTORES: dict[str, Callable[[Session, Tarefa], dict | None]] = {}


def executor(tipo: str):
    def registrar(fn):
        EXECUTORES[tipo] = fn
        return fn
    return registrar


def enfileirar(db: Session, esc_id: uuid.UUID, tipo: str, chave: str, parametros: dict | None = None, *,
               quando: datetime | None = None, max_tentativas: int = 5, criada_por: str | None = None) -> Tarefa:
    """Cria a tarefa se a chave ainda não existe; senão devolve a existente (idempotente)."""
    db.execute(insert(Tarefa).values(
        escritorio_id=esc_id, tipo=tipo, chave=chave, parametros=parametros or {}, max_tentativas=max_tentativas,
        agendada_para=quando or datetime.now(timezone.utc), criada_por=criada_por,
    ).on_conflict_do_nothing(index_elements=["escritorio_id", "chave"]))
    return db.execute(select(Tarefa).where(Tarefa.escritorio_id == esc_id, Tarefa.chave == chave)).scalar_one()


def espera(tentativas: int) -> timedelta:
    return timedelta(seconds=min(ESPERA_BASE_S * 2 ** max(tentativas - 1, 0), ESPERA_MAX_S))


def pegar(db: Session, agora: datetime | None = None, *, tarefa_id: uuid.UUID | None = None) -> Tarefa | None:
    agora = agora or datetime.now(timezone.utc)
    q = select(Tarefa).where(Tarefa.estado == "pendente", Tarefa.agendada_para <= agora)
    if tarefa_id:
        q = select(Tarefa).where(Tarefa.id == tarefa_id, Tarefa.estado == "pendente")
    t = db.execute(q.order_by(Tarefa.agendada_para).limit(1).with_for_update(skip_locked=True)).scalar()
    if t:
        t.estado, t.tentativas, t.iniciada_em, t.erro = "executando", t.tentativas + 1, agora, None
        db.flush()
    return t


def executar(db: Session, t: Tarefa) -> Tarefa:
    """Roda a tarefa já marcada como executando. Commita o resultado; em erro, reagenda ou marca como falhou."""
    from app.servicos.conectores.base import ErroConector, LimiteTaxa
    fn = EXECUTORES.get(t.tipo)
    db.commit()  # grava "executando" e a tentativa antes de rodar
    agora = datetime.now(timezone.utc)
    try:
        if fn is None:
            raise RuntimeError(f"tipo de tarefa desconhecido: {t.tipo}")
        t.resultado = fn(db, t)
        t.estado, t.concluida_em = "concluida", datetime.now(timezone.utc)
        db.commit()
    except Exception as e:  # noqa: BLE001 — qualquer falha vira registro, nunca some
        db.rollback()
        t = db.get(Tarefa, t.id)
        t.erro = str(e)[:2000]
        permanente = isinstance(e, ErroConector) and not e.transitorio
        if permanente or t.tentativas >= t.max_tentativas:
            t.estado, t.concluida_em = "falhou", agora
        else:
            t.estado = "pendente"
            atraso = timedelta(seconds=e.espera_segundos) if isinstance(e, LimiteTaxa) else espera(t.tentativas)
            t.agendada_para = agora + atraso
        db.commit()
    return t


def recuperar_travadas(db: Session, agora: datetime | None = None) -> int:
    """Tarefas 'executando' há muito tempo (worker caiu) voltam para a fila."""
    agora = agora or datetime.now(timezone.utc)
    r = db.execute(update(Tarefa).where(Tarefa.estado == "executando", Tarefa.iniciada_em < agora - TRAVADA_APOS)
                   .values(estado="pendente", agendada_para=agora, erro="retomada: execução anterior interrompida"))
    return r.rowcount or 0


def processar(db: Session, limite: int = 20) -> int:
    n = 0
    while n < limite:
        t = pegar(db)
        if t is None:
            break
        executar(db, t)
        n += 1
    return n


def como_json(t: Tarefa) -> dict:
    return {"id": str(t.id), "tipo": t.tipo, "chave": t.chave, "estado": t.estado, "tentativas": t.tentativas,
            "max_tentativas": t.max_tentativas, "agendada_para": t.agendada_para, "iniciada_em": t.iniciada_em,
            "concluida_em": t.concluida_em, "erro": t.erro, "resultado": t.resultado, "criado_em": t.criado_em}
