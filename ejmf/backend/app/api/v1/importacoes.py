"""Importação em massa: envio, mapeamento/validação, execução, conferência, relatório e reversão."""
import csv
import io
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.api.deps import Contexto, exigir
from app.modelos import Importacao, ImportacaoLinha, SITUACOES_LINHA
from app.servicos import importacao as svc
from app.servicos.leitura_arquivos import LIMITE_BYTES, ArquivoInvalido

rotas = APIRouter(tags=["importação"])


def _imp(ctx: Contexto, imp_id: uuid.UUID) -> Importacao:
    imp = ctx.db.get(Importacao, imp_id)
    if imp is None or imp.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Importação não encontrada")
    return imp


@rotas.get("/importacoes/campos")
def campos(ctx: Contexto = Depends(exigir("importacoes:executar"))):
    return [{"campo": c, "rotulo": r, "obrigatorio": o} for c, (r, o, _s) in svc.CAMPOS.items()]


@rotas.get("/importacoes")
def listar(ctx: Contexto = Depends(exigir("importacoes:executar"))):
    imps = ctx.db.execute(select(Importacao).where(Importacao.escritorio_id == ctx.usuario.escritorio_id)
                          .order_by(Importacao.criado_em.desc()).limit(100)).scalars().all()
    return [svc.como_json(i) for i in imps]


@rotas.post("/importacoes", status_code=201)
async def enviar(arquivo: UploadFile = File(...), ctx: Contexto = Depends(exigir("importacoes:executar"))):
    conteudo = await arquivo.read(LIMITE_BYTES + 1)
    try:
        imp = svc.analisar(ctx.db, ctx.ator, ctx.usuario.escritorio_id, ctx.usuario.id,
                           arquivo.filename or "arquivo", conteudo)
    except ArquivoInvalido as e:
        raise HTTPException(422, f"Arquivo inválido: {e}")
    ctx.db.commit()
    amostra = ctx.db.execute(select(ImportacaoLinha).where(ImportacaoLinha.importacao_id == imp.id)
                             .order_by(ImportacaoLinha.linha).limit(10)).scalars().all()
    return {**svc.como_json(imp), "amostra": [svc.linha_json(ln) for ln in amostra]}


@rotas.get("/importacoes/conferencia")
def fila_conferencia(pagina: int = Query(1, ge=1), ctx: Contexto = Depends(exigir("importacoes:conferir"))):
    base = select(ImportacaoLinha, Importacao).join(Importacao).where(
        Importacao.escritorio_id == ctx.usuario.escritorio_id, ImportacaoLinha.situacao == "conferencia",
        Importacao.status.in_(("validado", "processando", "concluido")))
    total = ctx.db.execute(select(func.count()).select_from(base.subquery())).scalar()
    linhas = ctx.db.execute(base.order_by(Importacao.criado_em, ImportacaoLinha.linha)
                            .offset((pagina - 1) * 50).limit(50)).all()
    return {"total": total, "itens": [{**svc.linha_json(ln), "importacao": {"id": str(i.id), "arquivo_nome": i.arquivo_nome,
                                                                          "status": i.status}} for ln, i in linhas]}


@rotas.get("/importacoes/{imp_id}")
def ver(imp_id: uuid.UUID, ctx: Contexto = Depends(exigir("importacoes:executar"))):
    imp = _imp(ctx, imp_id)
    return {**svc.como_json(imp), "totais": svc.totais(ctx.db, imp) | {k: v for k, v in (imp.totais or {}).items()
                                                                       if k in ("aviso", "reversao")}}


@rotas.get("/importacoes/{imp_id}/linhas")
def linhas(imp_id: uuid.UUID, situacao: str | None = None, so_com_mensagens: bool = False,
           pagina: int = Query(1, ge=1), por_pagina: int = Query(50, ge=1, le=500),
           ctx: Contexto = Depends(exigir("importacoes:executar"))):
    imp = _imp(ctx, imp_id)
    cond = [ImportacaoLinha.importacao_id == imp.id]
    if situacao:
        if situacao not in SITUACOES_LINHA:
            raise HTTPException(422, "Situação inválida")
        cond.append(ImportacaoLinha.situacao == situacao)
    if so_com_mensagens:
        cond.append(func.jsonb_array_length(ImportacaoLinha.mensagens) > 0)
    total = ctx.db.execute(select(func.count()).select_from(ImportacaoLinha).where(*cond)).scalar()
    lns = ctx.db.execute(select(ImportacaoLinha).where(*cond).order_by(ImportacaoLinha.linha)
                         .offset((pagina - 1) * por_pagina).limit(por_pagina)).scalars().all()
    return {"total": total, "itens": [svc.linha_json(ln) for ln in lns]}


class Mapeamento(BaseModel):
    mapeamento: dict[str, str | None]


@rotas.post("/importacoes/{imp_id}/validar")
def validar(imp_id: uuid.UUID, dados: Mapeamento, ctx: Contexto = Depends(exigir("importacoes:executar"))):
    imp = _imp(ctx, imp_id)
    try:
        totais = svc.validar(ctx.db, ctx.ator, imp, {k: v for k, v in dados.mapeamento.items()})
    except ValueError as e:
        raise HTTPException(422, str(e))
    ctx.db.commit()
    return {**svc.como_json(imp), "totais": totais}


@rotas.post("/importacoes/{imp_id}/executar")
def executar(imp_id: uuid.UUID, prazo_segundos: float | None = Query(None, ge=1, le=120),
             ctx: Contexto = Depends(exigir("importacoes:executar"))):
    """Grava em lotes de 500. Com prazo_segundos, devolve o controle ao fim do lote em andamento
    (a interface chama de novo até concluir e mostra o progresso). Sem prazo, vai até o fim."""
    _imp(ctx, imp_id)
    try:
        return svc.executar(ctx.db, ctx.ator, imp_id, prazo_segundos=prazo_segundos)
    except ValueError as e:
        raise HTTPException(409, str(e))


@rotas.post("/importacoes/{imp_id}/cancelar")
def cancelar(imp_id: uuid.UUID, ctx: Contexto = Depends(exigir("importacoes:executar"))):
    imp = _imp(ctx, imp_id)
    if imp.status not in ("analisado", "validado"):
        raise HTTPException(409, "Só é possível cancelar antes da execução; depois, use a reversão")
    imp.status = "cancelado"
    svc.auditoria.registrar(ctx.db, ctx.ator, "importacao.cancelar", entidade="importacao", entidade_id=imp.id)
    ctx.db.commit()
    return svc.como_json(imp)


@rotas.post("/importacoes/{imp_id}/reverter")
def reverter(imp_id: uuid.UUID, ctx: Contexto = Depends(exigir("importacoes:reverter"))):
    imp = _imp(ctx, imp_id)
    try:
        r = svc.reverter(ctx.db, ctx.ator, imp)
    except ValueError as e:
        raise HTTPException(409, str(e))
    ctx.db.commit()
    return r


class Resolucao(BaseModel):
    acao: Literal["associar", "novo_cliente", "sem_cliente"]
    cliente_id: uuid.UUID | None = None


@rotas.post("/importacoes/linhas/{linha_id}/resolver")
def resolver(linha_id: int, dados: Resolucao, ctx: Contexto = Depends(exigir("importacoes:conferir"))):
    ln = ctx.db.get(ImportacaoLinha, linha_id)
    if ln is None or _imp(ctx, ln.importacao_id) is None:
        raise HTTPException(404, "Linha não encontrada")
    try:
        svc.resolver(ctx.db, ctx.ator, ln, dados.acao, dados.cliente_id, ctx.usuario.id)
    except ValueError as e:
        raise HTTPException(422, str(e))
    ctx.db.commit()
    return svc.linha_json(ln)


@rotas.get("/importacoes/{imp_id}/relatorio.csv")
def relatorio_csv(imp_id: uuid.UUID, ctx: Contexto = Depends(exigir("importacoes:executar"))):
    """Relatório de inconsistências (CPF/CNPJ mascarado). Abre direto no Excel (separador ;)."""
    imp = _imp(ctx, imp_id)
    saida = io.StringIO()
    w = csv.writer(saida, delimiter=";")
    w.writerow(["linha", "situacao", "numero", "nivel", "campo", "mensagem"])
    lns = ctx.db.execute(select(ImportacaoLinha).where(ImportacaoLinha.importacao_id == imp.id,
                                                       func.jsonb_array_length(ImportacaoLinha.mensagens) > 0)
                         .order_by(ImportacaoLinha.linha)).scalars()
    for ln in lns:
        num = (ln.normalizado or {}).get("numero_formatado") or ""
        for m in ln.mensagens:
            w.writerow([ln.linha, ln.situacao, num, m["nivel"], m["campo"], m["texto"]])
    nome = f"inconsistencias-{str(imp.id)[:8]}.csv"
    return Response(content="﻿" + saida.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})
