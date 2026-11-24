"""Aparelhos do usuário (Fase 10): notificações no celular por Web Push. Cada pessoa só vê e mexe nos próprios aparelhos."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import Contexto, contexto
from app.modelos import AssinaturaPush
from app.servicos import auditoria, push

rotas = APIRouter(tags=["aparelhos"])


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _erro(e: push.ErroPush):
    raise HTTPException(e.status, str(e))


@rotas.get("/aparelhos/push")
def estado(ctx: Contexto = Depends(contexto)):
    meus = ctx.db.execute(select(AssinaturaPush).where(AssinaturaPush.usuario_id == ctx.usuario.id, AssinaturaPush.revogada_em.is_(None))
                          .order_by(AssinaturaPush.criado_em.desc())).scalars().all()
    return {**push.estado(), "aparelhos": [push.como_json(a, ctx.sessao.id) for a in meus]}


class Chaves(_M):
    p256dh: str = Field(min_length=80, max_length=200, pattern=r"^[A-Za-z0-9_-]+=*$")
    auth: str = Field(min_length=16, max_length=100, pattern=r"^[A-Za-z0-9_-]+=*$")


class NovaAssinatura(_M):
    endpoint: str = Field(min_length=20, max_length=1000)
    keys: Chaves
    dispositivo: str | None = Field(None, max_length=120)
    so_urgentes: bool = False


@rotas.post("/aparelhos/push", status_code=201)
def assinar(dados: NovaAssinatura, ctx: Contexto = Depends(contexto)):
    try:
        a = push.assinar(ctx.db, ctx.ator, ctx.usuario, ctx.sessao, dados.endpoint, dados.keys.p256dh, dados.keys.auth,
                         dados.dispositivo, dados.so_urgentes)
    except push.ErroPush as e:
        _erro(e)
    ctx.db.commit()
    return push.como_json(a, ctx.sessao.id)


def _minha(ctx: Contexto, aid: uuid.UUID) -> AssinaturaPush:
    a = ctx.db.get(AssinaturaPush, aid)
    if a is None or a.usuario_id != ctx.usuario.id or a.revogada_em is not None:
        raise HTTPException(404, "Aparelho não encontrado")
    return a


class Preferencia(_M):
    so_urgentes: bool


@rotas.patch("/aparelhos/push/{aid}")
def alterar(aid: uuid.UUID, dados: Preferencia, ctx: Contexto = Depends(contexto)):
    a = _minha(ctx, aid)
    a.so_urgentes = dados.so_urgentes
    auditoria.registrar(ctx.db, ctx.ator, "push.preferencia", entidade="assinatura_push", entidade_id=a.id,
                        alteracoes={"so_urgentes": dados.so_urgentes})
    ctx.db.commit()
    return push.como_json(a, ctx.sessao.id)


@rotas.delete("/aparelhos/push/{aid}")
def encerrar(aid: uuid.UUID, ctx: Contexto = Depends(contexto)):
    a = _minha(ctx, aid)
    push.revogar(ctx.db, a, "Encerrada pelo usuário")
    auditoria.registrar(ctx.db, ctx.ator, "push.encerrar", entidade="assinatura_push", entidade_id=a.id)
    ctx.db.commit()
    return {"ok": True}


@rotas.post("/aparelhos/push/{aid}/teste")
def testar(aid: uuid.UUID, ctx: Contexto = Depends(contexto)):
    a = _minha(ctx, aid)
    if not push.disponivel():
        raise HTTPException(409, "Notificações no celular ainda não configuradas neste servidor")
    try:
        st = push.enviar(ctx.db, a, "info")
    except push.ErroConector as e:
        ctx.db.commit()
        raise HTTPException(502, str(e))
    ctx.db.commit()
    return {"enviado": st in (200, 201, 202), "status": st}
