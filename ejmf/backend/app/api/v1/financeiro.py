"""Financeiro: contratos de honorários, lançamentos, contas, conciliação, recibos, lembretes e relatórios.

Registro e controle: nenhuma rota movimenta dinheiro, emite cobrança ou fala com banco (ADR-0013).
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.api.deps import Contexto, exigir
from app.modelos import (
    CategoriaFinanceira, ContaFinanceira, ContratoHonorarios, ExtratoImportado, Lancamento, LembreteCobranca, LinhaExtrato, Recibo,
)
from app.servicos import auditoria, conciliacao as conc, financeiro as fin, financeiro_relatorios as rel

rotas = APIRouter(tags=["financeiro"])
Dinheiro = Decimal


def _erro(e: Exception):
    raise HTTPException(getattr(e, "status", 409), str(e))


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _esc(ctx: Contexto) -> uuid.UUID:
    return ctx.usuario.escritorio_id


def _permissoes(ctx: Contexto) -> dict:
    p = ctx.permissoes
    return {k: f"financeiro:{k}" in p for k in ("gerenciar", "liquidar", "conciliar", "recibos", "cobrar", "exportar")}


# ================================================================ visão geral

@rotas.get("/financeiro")
def visao_geral(ano: int | None = Query(None, ge=2000, le=2100), ctx: Contexto = Depends(exigir("financeiro:ler"))):
    esc = _esc(ctx)
    ano = ano or fin.hoje().year
    cats = ctx.db.execute(select(CategoriaFinanceira).where(CategoriaFinanceira.escritorio_id == esc)
                          .order_by(CategoriaFinanceira.tipo.desc(), CategoriaFinanceira.nome)).scalars().all()
    contas = ctx.db.execute(select(ContaFinanceira).where(ContaFinanceira.escritorio_id == esc).order_by(ContaFinanceira.nome)).scalars().all()
    h = fin.hoje()
    proximos = fin.listar(ctx.db, esc, situacao="aberto", de=h, ate=h + timedelta(days=30), por_pagina=10)
    return {"resumo": rel.resumo_anual(ctx.db, esc, ano), "categorias": [fin.categoria_json(c) for c in cats],
            "contas": [fin.conta_json(ctx.db, c) for c in contas], "proximos": proximos["itens"],
            "vencidos": fin.listar(ctx.db, esc, situacao="vencido", tipo="receita", por_pagina=10),
            "formas": fin.FORMAS, "modalidades": fin.MODALIDADES, "tipos_conta": fin.TIPOS_CONTA, "pode": _permissoes(ctx),
            "aviso": "O EJMF registra e controla: não acessa banco, não emite cobrança e não movimenta dinheiro."}


# ================================================================ contas e categorias

class NovaConta(_M):
    nome: str = Field(min_length=2, max_length=120)
    tipo: Literal["corrente", "caixa", "aplicacao", "outra"] = "corrente"
    saldo_inicial: Dinheiro = Field(Decimal(0), max_digits=14, decimal_places=2)
    data_saldo_inicial: date | None = None


@rotas.post("/financeiro/contas", status_code=201)
def criar_conta(dados: NovaConta, ctx: Contexto = Depends(exigir("financeiro:gerenciar"))):
    try:
        c = fin.criar_conta(ctx.db, ctx.ator, _esc(ctx), dados.model_dump())
    except fin.ErroFinanceiro as e:
        _erro(e)
    ctx.db.commit()
    return fin.conta_json(ctx.db, c)


class AlterarConta(_M):
    nome: str | None = Field(None, min_length=2, max_length=120)
    ativa: bool | None = None
    saldo_inicial: Dinheiro | None = Field(None, max_digits=14, decimal_places=2)
    data_saldo_inicial: date | None = None


@rotas.patch("/financeiro/contas/{cid}")
def alterar_conta(cid: uuid.UUID, dados: AlterarConta, ctx: Contexto = Depends(exigir("financeiro:gerenciar"))):
    try:
        c = fin._obter(ctx.db, ContaFinanceira, cid, _esc(ctx), "Conta")
        if (dados.saldo_inicial is not None or dados.data_saldo_inicial is not None) and "financeiro:liquidar" not in ctx.permissoes:
            raise HTTPException(403, "Só quem registra recebimentos pode mudar o saldo inicial")
        fin.alterar_conta(ctx.db, ctx.ator, c, dados.model_dump(exclude_unset=True))
    except fin.ErroFinanceiro as e:
        _erro(e)
    ctx.db.commit()
    return fin.conta_json(ctx.db, c)


class NovaCategoria(_M):
    nome: str = Field(min_length=3, max_length=120)
    tipo: Literal["receita", "despesa"]
    operacional: bool = False


@rotas.post("/financeiro/categorias", status_code=201)
def criar_categoria(dados: NovaCategoria, ctx: Contexto = Depends(exigir("financeiro:gerenciar"))):
    try:
        c = fin.criar_categoria(ctx.db, ctx.ator, _esc(ctx), dados.nome, dados.tipo, dados.operacional)
    except fin.ErroFinanceiro as e:
        _erro(e)
    ctx.db.commit()
    return fin.categoria_json(c)


# ================================================================ lançamentos

Situacao = Literal["previsto", "faturado", "liquidado", "cancelado", "aberto", "vencido"]


@rotas.get("/financeiro/lancamentos")
def lancamentos(tipo: Literal["receita", "despesa"] | None = None, situacao: Situacao | None = None,
                cliente_id: uuid.UUID | None = None, processo_id: uuid.UUID | None = None, contrato_id: uuid.UUID | None = None,
                categoria_id: uuid.UUID | None = None, conta_id: uuid.UUID | None = None, de: date | None = None,
                ate: date | None = None, q: str | None = Query(None, max_length=100), pagina: int = Query(1, ge=1),
                por_pagina: int = Query(50, ge=1, le=200), ctx: Contexto = Depends(exigir("financeiro:ler"))):
    r = fin.listar(ctx.db, _esc(ctx), tipo=tipo, situacao=situacao, cliente_id=cliente_id, processo_id=processo_id,
                   contrato_id=contrato_id, categoria_id=categoria_id, conta_id=conta_id, de=de, ate=ate, q=q, pagina=pagina,
                   por_pagina=por_pagina)
    return {**r, "pode": _permissoes(ctx)}


class NovoLancamento(_M):
    tipo: Literal["receita", "despesa"]
    categoria_id: uuid.UUID
    descricao: str = Field(min_length=3, max_length=300)
    valor: Dinheiro = Field(gt=0, max_digits=14, decimal_places=2)
    vencimento: date
    competencia: date | None = None
    cliente_id: uuid.UUID | None = None
    processo_id: uuid.UUID | None = None
    contrato_id: uuid.UUID | None = None
    departamento_id: uuid.UUID | None = None
    reembolsavel: bool = False
    portal_visivel: bool = False
    observacao: str | None = Field(None, max_length=2000)


def _lanc(ctx: Contexto, lid: uuid.UUID) -> Lancamento:
    try:
        return fin.obter_lancamento(ctx.db, _esc(ctx), lid)
    except fin.ErroFinanceiro as e:
        _erro(e)


def _lanc_json(ctx: Contexto, lc: Lancamento) -> dict:
    d = fin.como_json(lc, fin.nomes(ctx.db, lc.escritorio_id, [lc]))
    d["recibos"] = [fin.recibo_json(ctx.db, r) for r in ctx.db.execute(select(Recibo).where(Recibo.lancamento_id == lc.id)
                                                                         .order_by(Recibo.emitido_em)).scalars()]
    d["lembretes"] = [fin.lembrete_json(x) for x in ctx.db.execute(select(LembreteCobranca).where(
        LembreteCobranca.lancamento_id == lc.id).order_by(LembreteCobranca.criado_em)).scalars()]
    ln = ctx.db.execute(select(LinhaExtrato).where(LinhaExtrato.lancamento_id == lc.id, LinhaExtrato.situacao == "conciliada")).scalar()
    d["conciliacao"] = conc.linha_json(ln) if ln else None
    d["pode"] = _permissoes(ctx)
    return d


@rotas.post("/financeiro/lancamentos", status_code=201)
def criar_lancamento(dados: NovoLancamento, ctx: Contexto = Depends(exigir("financeiro:gerenciar"))):
    try:
        lc = fin.criar_lancamento(ctx.db, ctx.ator, _esc(ctx), ctx.usuario, dados.model_dump())
    except fin.ErroFinanceiro as e:
        _erro(e)
    ctx.db.commit()
    return _lanc_json(ctx, lc)


@rotas.get("/financeiro/lancamentos/{lid}")
def lancamento(lid: uuid.UUID, ctx: Contexto = Depends(exigir("financeiro:ler"))):
    return _lanc_json(ctx, _lanc(ctx, lid))


class AlterarLancamento(_M):
    categoria_id: uuid.UUID | None = None
    descricao: str | None = Field(None, min_length=3, max_length=300)
    valor: Dinheiro | None = Field(None, gt=0, max_digits=14, decimal_places=2)
    vencimento: date | None = None
    competencia: date | None = None
    cliente_id: uuid.UUID | None = None
    processo_id: uuid.UUID | None = None
    departamento_id: uuid.UUID | None = None
    reembolsavel: bool | None = None
    portal_visivel: bool | None = None
    observacao: str | None = Field(None, max_length=2000)


@rotas.patch("/financeiro/lancamentos/{lid}")
def alterar_lancamento(lid: uuid.UUID, dados: AlterarLancamento, ctx: Contexto = Depends(exigir("financeiro:gerenciar"))):
    lc = _lanc(ctx, lid)
    try:
        fin.alterar_lancamento(ctx.db, ctx.ator, lc, dados.model_dump(exclude_unset=True))
    except fin.ErroFinanceiro as e:
        _erro(e)
    ctx.db.commit()
    return _lanc_json(ctx, lc)


class Faturar(_M):
    data: date | None = None


@rotas.post("/financeiro/lancamentos/{lid}/faturar")
def faturar(lid: uuid.UUID, dados: Faturar, ctx: Contexto = Depends(exigir("financeiro:liquidar"))):
    lc = _lanc(ctx, lid)
    try:
        fin.faturar(ctx.db, ctx.ator, lc, dados.data)
    except fin.ErroFinanceiro as e:
        _erro(e)
    ctx.db.commit()
    return _lanc_json(ctx, lc)


class Liquidar(_M):
    data: date
    conta_id: uuid.UUID
    forma: Literal["pix", "transferencia", "boleto", "dinheiro", "cartao", "cheque", "deposito_judicial", "outra"] | None = None
    valor: Dinheiro | None = Field(None, gt=0, max_digits=14, decimal_places=2)
    observacao: str | None = Field(None, max_length=1000)


@rotas.post("/financeiro/lancamentos/{lid}/liquidar")
def liquidar(lid: uuid.UUID, dados: Liquidar, ctx: Contexto = Depends(exigir("financeiro:liquidar"))):
    lc = _lanc(ctx, lid)
    try:
        _, saldo = fin.liquidar(ctx.db, ctx.ator, lc, ctx.usuario, **dados.model_dump())
    except fin.ErroFinanceiro as e:
        _erro(e)
    ctx.db.commit()
    return {**_lanc_json(ctx, lc), "saldo_id": str(saldo.id) if saldo else None}


class Motivo(_M):
    motivo: str = Field(min_length=5, max_length=1000)


@rotas.post("/financeiro/lancamentos/{lid}/estornar")
def estornar(lid: uuid.UUID, dados: Motivo, ctx: Contexto = Depends(exigir("financeiro:liquidar"))):
    lc = _lanc(ctx, lid)
    try:
        fin.estornar(ctx.db, ctx.ator, lc, dados.motivo)
    except fin.ErroFinanceiro as e:
        _erro(e)
    ctx.db.commit()
    return _lanc_json(ctx, lc)


@rotas.post("/financeiro/lancamentos/{lid}/cancelar")
def cancelar(lid: uuid.UUID, dados: Motivo, ctx: Contexto = Depends(exigir("financeiro:gerenciar"))):
    lc = _lanc(ctx, lid)
    if lc.situacao == "faturado" and "financeiro:liquidar" not in ctx.permissoes:
        raise HTTPException(403, "Lançamento já faturado: só quem registra recebimentos pode cancelar")
    try:
        fin.cancelar(ctx.db, ctx.ator, lc, dados.motivo)
    except fin.ErroFinanceiro as e:
        _erro(e)
    ctx.db.commit()
    return _lanc_json(ctx, lc)


class NovoRecibo(_M):
    referente: str | None = Field(None, min_length=3, max_length=500)


@rotas.post("/financeiro/lancamentos/{lid}/recibo", status_code=201)
def emitir_recibo(lid: uuid.UUID, dados: NovoRecibo, ctx: Contexto = Depends(exigir("financeiro:recibos"))):
    lc = _lanc(ctx, lid)
    try:
        r, aviso = fin.emitir_recibo(ctx.db, ctx.ator, lc, ctx.usuario, dados.referente)
    except fin.ErroFinanceiro as e:
        _erro(e)
    except Exception as e:  # erros do módulo de documentos (modelo, vínculos)
        if hasattr(e, "status"):
            _erro(e)
        raise
    ctx.db.commit()
    return {**fin.recibo_json(ctx.db, r), "aviso": aviso}


@rotas.post("/financeiro/recibos/{rid}/cancelar")
def cancelar_recibo(rid: uuid.UUID, dados: Motivo, ctx: Contexto = Depends(exigir("financeiro:recibos"))):
    try:
        r = fin._obter(ctx.db, Recibo, rid, _esc(ctx), "Recibo")
        fin.cancelar_recibo(ctx.db, ctx.ator, r, dados.motivo)
    except fin.ErroFinanceiro as e:
        _erro(e)
    ctx.db.commit()
    return fin.recibo_json(ctx.db, r)


@rotas.get("/financeiro/recibos")
def recibos(ctx: Contexto = Depends(exigir("financeiro:ler"))):
    rs = ctx.db.execute(select(Recibo).where(Recibo.escritorio_id == _esc(ctx)).order_by(Recibo.emitido_em.desc()).limit(200)).scalars()
    return {"itens": [fin.recibo_json(ctx.db, r) for r in rs]}


class NovoLembrete(_M):
    texto: str | None = Field(None, min_length=10, max_length=2000)


@rotas.post("/financeiro/lancamentos/{lid}/lembrete", status_code=201)
def preparar_lembrete(lid: uuid.UUID, dados: NovoLembrete, ctx: Contexto = Depends(exigir("financeiro:gerenciar"))):
    lc = _lanc(ctx, lid)
    try:
        le = fin.preparar_lembrete(ctx.db, ctx.ator, lc, ctx.usuario, ctx.permissoes, dados.texto)
    except fin.ErroFinanceiro as e:
        _erro(e)
    except Exception as e:
        if e.__class__.__name__ == "ErroAprovacao":
            raise HTTPException(409, str(e))
        raise
    ctx.db.commit()
    return fin.lembrete_json(le)


@rotas.get("/financeiro/lancamentos/{lid}/lembrete/texto")
def texto_lembrete(lid: uuid.UUID, ctx: Contexto = Depends(exigir("financeiro:ler"))):
    lc = _lanc(ctx, lid)
    return {"texto": fin.texto_lembrete(ctx.db, lc) if lc.cliente_id else None}


@rotas.post("/financeiro/lembretes/{leid}/retirar")
def retirar_lembrete(leid: uuid.UUID, ctx: Contexto = Depends(exigir("financeiro:cobrar"))):
    try:
        le = fin._obter(ctx.db, LembreteCobranca, leid, _esc(ctx), "Lembrete")
        fin.retirar_lembrete(ctx.db, ctx.ator, le)
    except fin.ErroFinanceiro as e:
        _erro(e)
    ctx.db.commit()
    return fin.lembrete_json(le)


# ================================================================ contratos de honorários

class NovoContrato(_M):
    cliente_id: uuid.UUID
    processo_id: uuid.UUID | None = None
    departamento_id: uuid.UUID | None = None
    minuta_id: uuid.UUID | None = None
    descricao: str = Field(min_length=3, max_length=500)
    modalidade: Literal["fixo", "parcelado", "mensal", "exito", "misto"]
    valor_fixo: Dinheiro | None = Field(None, gt=0, max_digits=14, decimal_places=2)
    parcelas: int | None = Field(None, ge=1, le=fin.MAX_PARCELAS)
    primeiro_vencimento: date | None = None
    percentual_exito: Decimal | None = Field(None, gt=0, le=100, max_digits=5, decimal_places=2)
    data_contrato: date | None = None
    portal_visivel: bool = False


@rotas.get("/financeiro/contratos")
def contratos(situacao: Literal["vigente", "encerrado", "cancelado"] | None = None, cliente_id: uuid.UUID | None = None,
              processo_id: uuid.UUID | None = None, ctx: Contexto = Depends(exigir("financeiro:ler"))):
    cond = [ContratoHonorarios.escritorio_id == _esc(ctx)]
    if situacao:
        cond.append(ContratoHonorarios.situacao == situacao)
    if cliente_id:
        cond.append(ContratoHonorarios.cliente_id == cliente_id)
    if processo_id:
        cond.append(ContratoHonorarios.processo_id == processo_id)
    cs = ctx.db.execute(select(ContratoHonorarios).where(*cond).order_by(ContratoHonorarios.criado_em.desc()).limit(300)).scalars()
    return {"itens": [fin.contrato_json(ctx.db, c) for c in cs], "modalidades": fin.MODALIDADES, "pode": _permissoes(ctx)}


@rotas.post("/financeiro/contratos", status_code=201)
def criar_contrato(dados: NovoContrato, ctx: Contexto = Depends(exigir("financeiro:gerenciar"))):
    try:
        c = fin.criar_contrato(ctx.db, ctx.ator, _esc(ctx), ctx.usuario, dados.model_dump())
    except fin.ErroFinanceiro as e:
        _erro(e)
    ctx.db.commit()
    return fin.contrato_json(ctx.db, c, completo=True)


def _contrato(ctx: Contexto, cid: uuid.UUID) -> ContratoHonorarios:
    try:
        return fin.obter_contrato(ctx.db, _esc(ctx), cid)
    except fin.ErroFinanceiro as e:
        _erro(e)


@rotas.get("/financeiro/contratos/{cid}")
def contrato(cid: uuid.UUID, ctx: Contexto = Depends(exigir("financeiro:ler"))):
    return {**fin.contrato_json(ctx.db, _contrato(ctx, cid), completo=True), "pode": _permissoes(ctx)}


class Exito(_M):
    base: Dinheiro = Field(gt=0, max_digits=14, decimal_places=2)
    vencimento: date
    descricao: str | None = Field(None, min_length=3, max_length=300)


@rotas.post("/financeiro/contratos/{cid}/exito", status_code=201)
def exito(cid: uuid.UUID, dados: Exito, ctx: Contexto = Depends(exigir("financeiro:gerenciar"))):
    c = _contrato(ctx, cid)
    try:
        lc = fin.registrar_exito(ctx.db, ctx.ator, c, ctx.usuario, **dados.model_dump())
    except fin.ErroFinanceiro as e:
        _erro(e)
    ctx.db.commit()
    return _lanc_json(ctx, lc)


class Encerrar(_M):
    situacao: Literal["encerrado", "cancelado"]
    motivo: str = Field(min_length=5, max_length=1000)


@rotas.post("/financeiro/contratos/{cid}/encerrar")
def encerrar(cid: uuid.UUID, dados: Encerrar, ctx: Contexto = Depends(exigir("financeiro:liquidar"))):
    c = _contrato(ctx, cid)
    try:
        r = fin.encerrar_contrato(ctx.db, ctx.ator, c, dados.situacao, dados.motivo)
    except fin.ErroFinanceiro as e:
        _erro(e)
    ctx.db.commit()
    return {**fin.contrato_json(ctx.db, c, completo=True), **r}


# ================================================================ conciliação

@rotas.get("/financeiro/contas/{cid}/extrato")
def extrato(cid: uuid.UUID, situacao: Literal["pendente", "conciliada", "ignorada", "todas"] = "pendente",
            ctx: Contexto = Depends(exigir("financeiro:ler"))):
    try:
        c = fin._obter(ctx.db, ContaFinanceira, cid, _esc(ctx), "Conta")
    except fin.ErroFinanceiro as e:
        _erro(e)
    cond = [LinhaExtrato.conta_id == c.id] + ([LinhaExtrato.situacao == situacao] if situacao != "todas" else [])
    linhas = ctx.db.execute(select(LinhaExtrato).where(*cond).order_by(LinhaExtrato.data, LinhaExtrato.descricao).limit(500)).scalars().all()
    pode = "financeiro:conciliar" in ctx.permissoes
    exts = ctx.db.execute(select(ExtratoImportado).where(ExtratoImportado.conta_id == c.id)
                          .order_by(ExtratoImportado.criado_em.desc()).limit(20)).scalars()
    return {"conta": fin.conta_json(ctx.db, c), "resumo": conc.resumo_conta(ctx.db, c),
            "linhas": [{**conc.linha_json(x), "sugestoes": conc.sugestoes(ctx.db, x) if pode and x.situacao == "pendente" else []}
                       for x in linhas],
            "extratos": [conc.extrato_json(e) for e in exts], "pode": _permissoes(ctx)}


@rotas.post("/financeiro/contas/{cid}/extrato", status_code=201)
async def importar_extrato(cid: uuid.UUID, arquivo: UploadFile = File(...), ctx: Contexto = Depends(exigir("financeiro:conciliar"))):
    dados = await arquivo.read(conc.LIMITE_BYTES + 1)
    try:
        c = fin._obter(ctx.db, ContaFinanceira, cid, _esc(ctx), "Conta")
        e = conc.importar(ctx.db, ctx.ator, c, ctx.usuario, arquivo.filename or "extrato", dados)
    except fin.ErroFinanceiro as x:
        _erro(x)
    ctx.db.commit()
    return conc.extrato_json(e)


def _linha(ctx: Contexto, lid: uuid.UUID) -> LinhaExtrato:
    try:
        return conc.obter_linha(ctx.db, _esc(ctx), lid)
    except fin.ErroFinanceiro as e:
        _erro(e)


class Conciliar(_M):
    lancamento_id: uuid.UUID


@rotas.post("/financeiro/extrato/{lid}/conciliar")
def conciliar(lid: uuid.UUID, dados: Conciliar, ctx: Contexto = Depends(exigir("financeiro:conciliar"))):
    ln = _linha(ctx, lid)
    try:
        lc = fin.obter_lancamento(ctx.db, _esc(ctx), dados.lancamento_id)
        conc.conciliar(ctx.db, ctx.ator, ln, lc, ctx.usuario)
    except fin.ErroFinanceiro as e:
        _erro(e)
    ctx.db.commit()
    return conc.linha_json(ln)


class CriarDaLinha(_M):
    categoria_id: uuid.UUID
    descricao: str = Field(min_length=3, max_length=300)
    cliente_id: uuid.UUID | None = None
    processo_id: uuid.UUID | None = None


@rotas.post("/financeiro/extrato/{lid}/lancar", status_code=201)
def lancar_da_linha(lid: uuid.UUID, dados: CriarDaLinha, ctx: Contexto = Depends(exigir("financeiro:conciliar", "financeiro:gerenciar"))):
    ln = _linha(ctx, lid)
    try:
        lc = conc.criar_e_conciliar(ctx.db, ctx.ator, ln, ctx.usuario, dados.model_dump())
    except fin.ErroFinanceiro as e:
        _erro(e)
    ctx.db.commit()
    return {"linha": conc.linha_json(ln), "lancamento": _lanc_json(ctx, lc)}


class Ignorar(_M):
    motivo: str = Field(min_length=3, max_length=500)


@rotas.post("/financeiro/extrato/{lid}/ignorar")
def ignorar(lid: uuid.UUID, dados: Ignorar, ctx: Contexto = Depends(exigir("financeiro:conciliar"))):
    ln = _linha(ctx, lid)
    try:
        conc.ignorar(ctx.db, ctx.ator, ln, ctx.usuario, dados.motivo)
    except fin.ErroFinanceiro as e:
        _erro(e)
    ctx.db.commit()
    return conc.linha_json(ln)


@rotas.post("/financeiro/extrato/{lid}/desfazer")
def desfazer(lid: uuid.UUID, ctx: Contexto = Depends(exigir("financeiro:conciliar"))):
    ln = _linha(ctx, lid)
    try:
        conc.desfazer(ctx.db, ctx.ator, ln)
    except fin.ErroFinanceiro as e:
        _erro(e)
    ctx.db.commit()
    return conc.linha_json(ln)


# ================================================================ relatórios e exportação

@rotas.get("/financeiro/relatorios/fluxo")
def fluxo(de: date, ate: date, agrupar: Literal["dia", "semana", "mes"] = "mes", ctx: Contexto = Depends(exigir("financeiro:ler"))):
    try:
        return rel.fluxo_caixa(ctx.db, _esc(ctx), de, ate, agrupar)
    except fin.ErroFinanceiro as e:
        _erro(e)


@rotas.get("/financeiro/relatorios/rentabilidade")
def rentabilidade(de: date, ate: date, por: Literal["processo", "cliente", "departamento"] = "processo",
                  ctx: Contexto = Depends(exigir("financeiro:ler"))):
    try:
        return rel.rentabilidade(ctx.db, _esc(ctx), de, ate, por)
    except fin.ErroFinanceiro as e:
        _erro(e)


def _arquivo(dados: bytes, nome: str) -> Response:
    return Response(dados, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"', "Cache-Control": "no-store",
                             "X-Content-Type-Options": "nosniff"})


@rotas.get("/financeiro/exportar/lancamentos.csv")
def exportar_lancamentos(tipo: Literal["receita", "despesa"] | None = None, situacao: Situacao | None = None,
                         cliente_id: uuid.UUID | None = None, processo_id: uuid.UUID | None = None, de: date | None = None,
                         ate: date | None = None, ctx: Contexto = Depends(exigir("financeiro:exportar"))):
    dados, n = rel.csv_lancamentos(ctx.db, _esc(ctx), tipo=tipo, situacao=situacao, cliente_id=cliente_id, processo_id=processo_id,
                                   de=de, ate=ate)
    auditoria.registrar(ctx.db, ctx.ator, "financeiro.exportar", entidade="lancamentos",
                        alteracoes={"linhas": n, "filtros": {"tipo": tipo, "situacao": situacao, "de": str(de) if de else None,
                                                             "ate": str(ate) if ate else None}})
    ctx.db.commit()
    return _arquivo(dados, f"lancamentos-{fin.hoje().isoformat()}.csv")


@rotas.get("/financeiro/exportar/resumo-{ano}.csv")
def exportar_resumo(ano: int, ctx: Contexto = Depends(exigir("financeiro:exportar"))):
    if not 2000 <= ano <= 2100:
        raise HTTPException(422, "Ano inválido")
    dados = rel.csv_resumo(rel.resumo_anual(ctx.db, _esc(ctx), ano))
    auditoria.registrar(ctx.db, ctx.ator, "financeiro.exportar", entidade="resumo", alteracoes={"ano": ano})
    ctx.db.commit()
    return _arquivo(dados, f"resumo-financeiro-{ano}.csv")
