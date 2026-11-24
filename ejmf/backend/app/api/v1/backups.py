"""Cópias de segurança (Fase 11): estado, histórico e pedidos. Não há download nem restauração pela API (ADR-0015)."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.api.deps import Contexto, exigir
from app.modelos import CopiaSeguranca
from app.servicos import auditoria, copias, fila

rotas = APIRouter(tags=["cópias de segurança"])


@rotas.get("/backups")
def listar(limite: int = Query(30, ge=1, le=200), ctx: Contexto = Depends(exigir("backups:ler"))):
    esc = ctx.usuario.escritorio_id
    lista = ctx.db.execute(select(CopiaSeguranca).where(CopiaSeguranca.escritorio_id == esc)
                           .order_by(CopiaSeguranca.iniciada_em.desc()).limit(limite)).scalars().all()
    return {**copias.estado(ctx.db, esc), "copias": [copias.como_json(c) for c in lista],
            "pode_executar": "backups:executar" in ctx.permissoes}


@rotas.post("/backups", status_code=202)
def pedir(ctx: Contexto = Depends(exigir("backups:executar"))):
    esc = ctx.usuario.escritorio_id
    if not copias.configurada():
        raise HTTPException(409, "Cópias de segurança aguardando configuração da chave (EJMF_BACKUP_CHAVE)")
    agora = datetime.now(timezone.utc)
    t = fila.enfileirar(ctx.db, esc, "backup.executar", f"backup:pessoa:{agora:%Y%m%d%H%M}",
                        {"origem": "pessoa", "usuario_id": str(ctx.usuario.id)}, max_tentativas=1, criada_por=str(ctx.usuario.id))
    auditoria.registrar(ctx.db, ctx.ator, "backup.pedido", entidade="tarefa", entidade_id=str(t.id))
    ctx.db.commit()
    return {"tarefa": str(t.id), "mensagem": "Cópia pedida. Ela roda em segundo plano e aparece aqui ao terminar."}


@rotas.post("/backups/{cid}/testar", status_code=202)
def testar(cid: uuid.UUID, ctx: Contexto = Depends(exigir("backups:executar"))):
    esc = ctx.usuario.escritorio_id
    c = ctx.db.get(CopiaSeguranca, cid)
    if c is None or c.escritorio_id != esc:
        raise HTTPException(404, "Cópia não encontrada")
    if c.situacao != "concluida":
        raise HTTPException(409, "Só uma cópia concluída pode ser testada")
    agora = datetime.now(timezone.utc)
    t = fila.enfileirar(ctx.db, esc, "backup.testar", f"backup:teste:pessoa:{cid}:{agora:%Y%m%d%H%M}", {"copia_id": str(cid)},
                        max_tentativas=1, criada_por=str(ctx.usuario.id))
    auditoria.registrar(ctx.db, ctx.ator, "backup.teste_pedido", entidade="copia_seguranca", entidade_id=str(cid))
    ctx.db.commit()
    return {"tarefa": str(t.id), "mensagem": "Teste de restauração pedido. O resultado aparece aqui ao terminar."}
