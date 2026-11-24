"""Processos, clientes, tribunais, pesquisa global e operações em lote."""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import Contexto, contexto, exigir
from app.modelos import Cliente, Departamento, Parte, Processo, Tribunal
from app.servicos import auditoria, clientes as svc_clientes, processos as svc_processos
from app.servicos.identificadores import DocumentoInvalido, NumeroInvalido, normalizar_documento, normalizar_texto

rotas = APIRouter(tags=["gestão processual"])

Status = Literal["ativo", "suspenso", "arquivado", "encerrado"]
Polo = Literal["ativo", "passivo", "terceiro", "outro"]


def _deps(db: Session, esc_id: uuid.UUID) -> dict:
    return {d.id: d for d in db.execute(select(Departamento).where(Departamento.escritorio_id == esc_id)).scalars()}


def _processo(ctx: Contexto, processo_id: uuid.UUID) -> Processo:
    p = ctx.db.get(Processo, processo_id)
    if p is None or p.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Processo não encontrado")
    return p


def _cliente(ctx: Contexto, cliente_id: uuid.UUID) -> Cliente:
    c = ctx.db.get(Cliente, cliente_id)
    if c is None or c.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Cliente não encontrado")
    return c


def _departamento_valido(ctx: Contexto, dep_id: uuid.UUID | None) -> None:
    if dep_id is None:
        return
    d = ctx.db.get(Departamento, dep_id)
    if d is None or d.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(400, "Departamento inexistente")


# ---------------------------------------------------------------- tribunais
@rotas.get("/tribunais")
def listar_tribunais(ctx: Contexto = Depends(exigir("processos:ler"))):
    ts = ctx.db.execute(select(Tribunal).order_by(Tribunal.prioritario.desc(), Tribunal.segmento, Tribunal.codigo)).scalars()
    return [{"codigo": t.codigo, "sigla": t.sigla, "nome": t.nome, "uf": t.uf, "prioritario": t.prioritario} for t in ts]


# ---------------------------------------------------------------- processos
class EntradaParte(BaseModel):
    nome: str = Field(min_length=2, max_length=300)
    polo: Polo = "ativo"
    papel: str | None = Field(default=None, max_length=80)
    cliente_id: uuid.UUID | None = None


class EntradaProcesso(BaseModel):
    numero: str = Field(min_length=20, max_length=30)
    classe: str | None = Field(default=None, max_length=200)
    assuntos: list[str] = Field(default_factory=list, max_length=30)
    unidade: str | None = Field(default=None, max_length=300)
    status: Status = "ativo"
    departamento_id: uuid.UUID | None = None
    valor_causa: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=2)
    data_distribuicao: date | None = None
    observacoes: str | None = Field(default=None, max_length=5000)
    partes: list[EntradaParte] = Field(default_factory=list, max_length=50)


class AlteracaoProcesso(BaseModel):
    classe: str | None = Field(default=None, max_length=200)
    assuntos: list[str] | None = Field(default=None, max_length=30)
    unidade: str | None = Field(default=None, max_length=300)
    status: Status | None = None
    departamento_id: uuid.UUID | None = None
    valor_causa: Decimal | None = Field(default=None, ge=0, max_digits=16, decimal_places=2)
    data_distribuicao: date | None = None
    observacoes: str | None = Field(default=None, max_length=5000)


@rotas.get("/processos")
def listar_processos(
    q: str | None = Query(None, max_length=200), status: Status | None = None, tribunal: str | None = None,
    departamento_id: uuid.UUID | None = None, cliente_id: uuid.UUID | None = None,
    importacao_id: uuid.UUID | None = None,
    ordem: Literal["atualizado", "numero", "movimentacao"] = "atualizado",
    pagina: int = Query(1, ge=1, le=100000), por_pagina: int = Query(25, ge=1, le=200),
    ctx: Contexto = Depends(exigir("processos:ler")),
):
    cond = svc_processos.filtrar(ctx.usuario.escritorio_id, q=q, status=status, tribunal=tribunal,
                                 departamento_id=departamento_id, cliente_id=cliente_id, importacao_id=importacao_id)
    total = ctx.db.execute(select(func.count()).select_from(Processo).where(cond)).scalar()
    ordenacao = {"atualizado": (Processo.atualizado_em.desc(), Processo.id),
                 "numero": (Processo.numero,),
                 "movimentacao": (Processo.ultima_movimentacao_em.desc().nulls_last(), Processo.id)}[ordem]
    ps = ctx.db.execute(select(Processo).where(cond).order_by(*ordenacao)
                        .offset((pagina - 1) * por_pagina).limit(por_pagina)).scalars().all()
    tribs = svc_processos.tribunais_por_codigo(ctx.db)
    deps = _deps(ctx.db, ctx.usuario.escritorio_id)
    return {"total": total, "pagina": pagina, "por_pagina": por_pagina,
            "itens": [svc_processos.como_json(p, tribs, deps) for p in ps]}


@rotas.post("/processos", status_code=201)
def novo_processo(dados: EntradaProcesso, ctx: Contexto = Depends(exigir("processos:gerenciar"))):
    _departamento_valido(ctx, dados.departamento_id)
    for pt in dados.partes:
        if pt.cliente_id:
            _cliente(ctx, pt.cliente_id)
    try:
        p = svc_processos.criar(ctx.db, ctx.ator, ctx.usuario.escritorio_id, numero=dados.numero, classe=dados.classe,
                                assuntos=dados.assuntos, unidade=dados.unidade, status=dados.status,
                                departamento_id=dados.departamento_id, valor_causa=dados.valor_causa,
                                data_distribuicao=dados.data_distribuicao, observacoes=dados.observacoes,
                                partes=[pt.model_dump() for pt in dados.partes])
    except NumeroInvalido as e:
        raise HTTPException(422, f"Número processual inválido: {e}")
    except svc_processos.ProcessoDuplicado as e:
        raise HTTPException(409, {"mensagem": str(e), "processo_id": str(e.existente.id)})
    except ValueError as e:
        raise HTTPException(422, str(e))
    ctx.db.commit()
    return svc_processos.como_json(p, svc_processos.tribunais_por_codigo(ctx.db), _deps(ctx.db, p.escritorio_id), completo=True)


@rotas.get("/processos/{processo_id}")
def prontuario(processo_id: uuid.UUID, ctx: Contexto = Depends(exigir("processos:ler"))):
    p = _processo(ctx, processo_id)
    dados = svc_processos.como_json(p, svc_processos.tribunais_por_codigo(ctx.db), _deps(ctx.db, p.escritorio_id), completo=True)
    dados["linha_do_tempo"] = svc_processos.linha_do_tempo(ctx.db, p, limite=50)
    # módulos ainda não implementados aparecem como tal, nunca como "zero"
    dados["modulos_futuros"] = [
        {"rotulo": "Publicações e intimações", "fase": 3}, {"rotulo": "Prazos homologados", "fase": 3},
        {"rotulo": "Audiências e compromissos", "fase": 4}, {"rotulo": "Documentos", "fase": 6},
        {"rotulo": "Financeiro", "fase": 9},
    ]
    return dados


@rotas.get("/processos/{processo_id}/linha-do-tempo")
def linha_do_tempo(processo_id: uuid.UUID, antes_de: datetime | None = None, limite: int = Query(50, ge=1, le=200),
                   ctx: Contexto = Depends(exigir("processos:ler"))):
    return svc_processos.linha_do_tempo(ctx.db, _processo(ctx, processo_id), limite=limite, antes_de=antes_de)


@rotas.patch("/processos/{processo_id}")
def alterar_processo(processo_id: uuid.UUID, dados: AlteracaoProcesso, ctx: Contexto = Depends(exigir("processos:gerenciar"))):
    p = _processo(ctx, processo_id)
    mudancas = dados.model_dump(exclude_unset=True)
    _departamento_valido(ctx, mudancas.get("departamento_id"))
    if "status" in mudancas and mudancas["status"] is None:
        raise HTTPException(422, "Situação não pode ficar vazia")
    try:
        svc_processos.alterar(ctx.db, ctx.ator, p, mudancas)
    except ValueError as e:
        raise HTTPException(422, str(e))
    ctx.db.commit()
    return svc_processos.como_json(p, svc_processos.tribunais_por_codigo(ctx.db), _deps(ctx.db, p.escritorio_id), completo=True)


@rotas.post("/processos/{processo_id}/partes", status_code=201)
def adicionar_parte(processo_id: uuid.UUID, dados: EntradaParte, ctx: Contexto = Depends(exigir("processos:gerenciar"))):
    p = _processo(ctx, processo_id)
    if dados.cliente_id:
        c = _cliente(ctx, dados.cliente_id)
        if any(pt.cliente_id == c.id for pt in p.partes):
            raise HTTPException(409, "Este cliente já está vinculado ao processo")
    parte = svc_processos.adicionar_parte(ctx.db, ctx.ator, p, dados.model_dump())
    ctx.db.commit()
    return {"id": str(parte.id)}


@rotas.delete("/processos/{processo_id}/partes/{parte_id}", status_code=204)
def remover_parte(processo_id: uuid.UUID, parte_id: uuid.UUID, ctx: Contexto = Depends(exigir("processos:gerenciar"))):
    try:
        svc_processos.remover_parte(ctx.db, ctx.ator, _processo(ctx, processo_id), parte_id)
    except LookupError as e:
        raise HTTPException(404, str(e))
    ctx.db.commit()


class EntradaMovimentacao(BaseModel):
    tipo: Literal["anotacao", "movimentacao"] = "anotacao"
    descricao: str = Field(min_length=2, max_length=10000)
    ocorrido_em: datetime | None = None


@rotas.post("/processos/{processo_id}/movimentacoes", status_code=201)
def nova_movimentacao(processo_id: uuid.UUID, dados: EntradaMovimentacao, ctx: Contexto = Depends(exigir("processos:gerenciar"))):
    p = _processo(ctx, processo_id)
    if dados.ocorrido_em and dados.ocorrido_em.tzinfo is None:
        raise HTTPException(422, "Informe a data com fuso horário")
    m = svc_processos.registrar_movimentacao(ctx.db, ctx.ator, p, descricao=dados.descricao, tipo=dados.tipo,
                                             ocorrido_em=dados.ocorrido_em, autor_id=ctx.usuario.id)
    ctx.db.commit()
    return {"id": str(m.id)}


class OperacaoLote(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=1000)
    acao: Literal["status", "departamento"]
    valor: str | None = None


@rotas.post("/processos/lote")
def operacao_em_lote(dados: OperacaoLote, ctx: Contexto = Depends(exigir("processos:gerenciar", "processos:lote"))):
    """Altera situação ou departamento de vários processos. Valida tudo antes; grava tudo ou nada."""
    esc = ctx.usuario.escritorio_id
    if dados.acao == "status":
        if dados.valor not in ("ativo", "suspenso", "arquivado", "encerrado"):
            raise HTTPException(422, "Situação inválida")
        mudanca = {"status": dados.valor}
    else:
        dep = uuid.UUID(dados.valor) if dados.valor else None
        _departamento_valido(ctx, dep)
        mudanca = {"departamento_id": dep}
    ids = list(set(dados.ids))
    ps = ctx.db.execute(select(Processo).where(Processo.id.in_(ids), Processo.escritorio_id == esc)
                        .with_for_update()).scalars().all()
    if len(ps) != len(ids):
        raise HTTPException(404, f"{len(ids) - len(ps)} processo(s) não encontrado(s); nada foi alterado")
    alterados = sum(1 for p in ps if svc_processos.alterar(ctx.db, ctx.ator, p, mudanca, operacao="processo.lote"))
    auditoria.registrar(ctx.db, ctx.ator, "processo.lote.resumo", entidade="processo", entidade_id=None,
                        alteracoes={"acao": dados.acao, "valor": dados.valor, "selecionados": len(ids), "alterados": alterados})
    ctx.db.commit()
    return {"selecionados": len(ids), "alterados": alterados}


# ---------------------------------------------------------------- clientes
class EntradaCliente(BaseModel):
    tipo: Literal["PF", "PJ"] | None = None
    nome: str = Field(min_length=2, max_length=300)
    documento: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    telefone: str | None = Field(default=None, max_length=30)
    observacoes: str | None = Field(default=None, max_length=5000)


class AlteracaoCliente(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=300)
    email: EmailStr | None = None
    telefone: str | None = Field(default=None, max_length=30)
    observacoes: str | None = Field(default=None, max_length=5000)


@rotas.get("/clientes")
def listar_clientes(q: str | None = Query(None, max_length=200), tipo: Literal["PF", "PJ"] | None = None,
                    pagina: int = Query(1, ge=1), por_pagina: int = Query(25, ge=1, le=200),
                    ctx: Contexto = Depends(exigir("clientes:ler"))):
    cond = [Cliente.escritorio_id == ctx.usuario.escritorio_id]
    if tipo:
        cond.append(Cliente.tipo == tipo)
    if q:
        cond.append(_condicao_cliente(q))
    total = ctx.db.execute(select(func.count()).select_from(Cliente).where(*cond)).scalar()
    cs = ctx.db.execute(select(Cliente).where(*cond).order_by(Cliente.nome_normalizado, Cliente.id)
                        .offset((pagina - 1) * por_pagina).limit(por_pagina)).scalars().all()
    contagem = svc_clientes.contar_processos(ctx.db, [c.id for c in cs])
    return {"total": total, "pagina": pagina, "por_pagina": por_pagina,
            "itens": [svc_clientes.como_json(c, processos=contagem.get(c.id, 0)) for c in cs]}


def _condicao_cliente(q: str):
    try:
        norm = normalizar_documento(q)
    except DocumentoInvalido:
        norm = None
    if norm:  # busca exata por CPF/CNPJ sem expor o documento (compara o HMAC)
        return Cliente.documento_hash == svc_clientes.hash_documento(norm[1])
    return Cliente.nome_normalizado.contains(normalizar_texto(q))


@rotas.post("/clientes", status_code=201)
def novo_cliente(dados: EntradaCliente, ctx: Contexto = Depends(exigir("clientes:gerenciar"))):
    try:
        c = svc_clientes.criar(ctx.db, ctx.ator, ctx.usuario.escritorio_id, nome=dados.nome, tipo=dados.tipo,
                               documento=dados.documento, email=dados.email, telefone=dados.telefone,
                               observacoes=dados.observacoes)
    except svc_clientes.ClienteDuplicado as e:
        raise HTTPException(409, {"mensagem": str(e), "cliente_id": str(e.existente.id)})
    except (DocumentoInvalido, ValueError) as e:
        raise HTTPException(422, str(e))
    ctx.db.commit()
    return svc_clientes.como_json(c, processos=0)


@rotas.get("/clientes/{cliente_id}")
def ver_cliente(cliente_id: uuid.UUID, ctx: Contexto = Depends(exigir("clientes:ler"))):
    c = _cliente(ctx, cliente_id)
    procs = svc_clientes.processos_do_cliente(ctx.db, c.id)
    tribs = svc_processos.tribunais_por_codigo(ctx.db)
    deps = _deps(ctx.db, c.escritorio_id)
    return {**svc_clientes.como_json(c, processos=len(procs)),
            "pode_ver_documento": "clientes:ver_documento" in ctx.permissoes,
            "lista_processos": [svc_processos.como_json(p, tribs, deps) for p in procs[:200]]}


@rotas.get("/clientes/{cliente_id}/documento")
def ver_documento(cliente_id: uuid.UUID, ctx: Contexto = Depends(exigir("clientes:ver_documento"))):
    c = _cliente(ctx, cliente_id)
    auditoria.registrar(ctx.db, ctx.ator, "cliente.documento.ver", entidade="cliente", entidade_id=c.id)
    ctx.db.commit()
    return {"documento": svc_clientes.documento_completo(c)}


@rotas.patch("/clientes/{cliente_id}")
def alterar_cliente(cliente_id: uuid.UUID, dados: AlteracaoCliente, ctx: Contexto = Depends(exigir("clientes:gerenciar"))):
    c = _cliente(ctx, cliente_id)
    mudancas = dados.model_dump(exclude_unset=True)
    if "nome" in mudancas and not mudancas["nome"]:
        raise HTTPException(422, "Nome não pode ficar vazio")
    antes = {k: getattr(c, k) for k in mudancas}
    for k, v in mudancas.items():
        setattr(c, k, " ".join(v.split()) if k == "nome" else v)
    if "nome" in mudancas:
        c.nome_normalizado = normalizar_texto(c.nome)
        for pt in ctx.db.execute(select(Parte).where(Parte.cliente_id == c.id)).scalars():
            pt.nome = c.nome
            svc_processos.atualizar_texto_busca(pt.processo)
    ctx.db.flush()
    auditoria.registrar(ctx.db, ctx.ator, "cliente.alterar", entidade="cliente", entidade_id=c.id,
                        alteracoes={"antes": antes, "depois": mudancas})
    ctx.db.commit()
    return svc_clientes.como_json(c)


# ---------------------------------------------------------------- pesquisa global
@rotas.get("/pesquisa")
def pesquisa_global(q: str = Query(min_length=2, max_length=200), ctx: Contexto = Depends(contexto)):
    """Procura em processos e clientes conforme as permissões do usuário. Cada resultado mostra a origem."""
    resultados: list[dict] = []
    if "processos:ler" in ctx.permissoes:
        ps = ctx.db.execute(select(Processo).where(svc_processos.filtrar(ctx.usuario.escritorio_id, q=q))
                            .order_by(Processo.atualizado_em.desc()).limit(10)).scalars().all()
        tribs = svc_processos.tribunais_por_codigo(ctx.db)
        for p in ps:
            t = tribs.get(p.tribunal_codigo)
            clientes_txt = ", ".join(pt.nome for pt in p.partes if pt.cliente_id)[:120]
            resultados.append({"tipo": "processo", "id": str(p.id), "titulo": p.numero_formatado,
                               "detalhe": " · ".join(filter(None, [t.sigla if t else None, p.classe, clientes_txt])),
                               "origem": "Processos", "link": f"/painel/processos/{p.id}"})
    if "clientes:ler" in ctx.permissoes:
        cs = ctx.db.execute(select(Cliente).where(Cliente.escritorio_id == ctx.usuario.escritorio_id,
                                                  _condicao_cliente(q))
                            .order_by(Cliente.nome_normalizado).limit(10)).scalars().all()
        for c in cs:
            resultados.append({"tipo": "cliente", "id": str(c.id), "titulo": c.nome,
                               "detalhe": " · ".join(filter(None, [c.tipo, c.documento_mascarado])),
                               "origem": "Clientes", "link": f"/painel/clientes/{c.id}"})
    return {"q": q, "resultados": resultados,
            "escopo": [r for r, perm in (("processos", "processos:ler"), ("clientes", "clientes:ler")) if perm in ctx.permissoes]}
