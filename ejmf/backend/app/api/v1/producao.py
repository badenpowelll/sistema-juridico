"""Prontidão para produção (Fase 12): só leitura, calculada na hora."""
from fastapi import APIRouter, Depends

from app.api.deps import Contexto, exigir
from app.servicos import prontidao

rotas = APIRouter(tags=["produção"])


@rotas.get("/producao/prontidao")
def ver(ctx: Contexto = Depends(exigir("producao:ler"))):
    return prontidao.verificar(ctx.db, ctx.usuario.escritorio_id)
