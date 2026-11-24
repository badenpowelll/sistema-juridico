from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.api.deps import Contexto, exigir
from app.modelos import Auditoria
from app.servicos import auditoria, painel

rotas = APIRouter(tags=["painel e auditoria"])


@rotas.get("/painel")
def obter_painel(ctx: Contexto = Depends(exigir("painel:ler"))):
    return painel.resumo(ctx.db, ctx.usuario)


@rotas.get("/auditoria")
def listar_auditoria(
    ctx: Contexto = Depends(exigir("auditoria:ler")),
    entidade: str | None = None, entidade_id: str | None = None, operacao: str | None = None,
    ator_id: str | None = None, desde: datetime | None = None, antes_de_id: int | None = None,
    limite: int = Query(50, ge=1, le=500),
):
    q = select(Auditoria).where((Auditoria.escritorio_id == ctx.usuario.escritorio_id) | Auditoria.escritorio_id.is_(None))
    if entidade:
        q = q.where(Auditoria.entidade == entidade)
    if entidade_id:
        q = q.where(Auditoria.entidade_id == entidade_id)
    if operacao:
        q = q.where(Auditoria.operacao.like(operacao.replace("*", "%")))
    if ator_id:
        q = q.where(Auditoria.ator_id == ator_id)
    if desde:
        q = q.where(Auditoria.ocorrido_em >= desde)
    if antes_de_id:
        q = q.where(Auditoria.id < antes_de_id)
    linhas = ctx.db.execute(q.order_by(Auditoria.id.desc()).limit(limite)).scalars().all()
    return [{"id": r.id, "ocorrido_em": r.ocorrido_em, "ator_tipo": r.ator_tipo, "ator_nome": r.ator_nome,
             "operacao": r.operacao, "entidade": r.entidade, "entidade_id": r.entidade_id, "resultado": r.resultado,
             "erro": r.erro, "alteracoes": r.alteracoes, "trace_id": r.trace_id, "hash": r.hash} for r in linhas]


@rotas.get("/auditoria/verificar")
def verificar(ctx: Contexto = Depends(exigir("auditoria:ler"))):
    return auditoria.verificar_cadeia(ctx.db)
