"""Conhecimento: biblioteca versionada, jurisprudência verificada, pesquisa com escopo e memória permanente."""
import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import Contexto, exigir
from app.modelos import TIPOS_BIBLIOTECA, FonteConhecimento, Usuario
from app.servicos import biblioteca as bib
from app.servicos import conhecimento, jurisprudencia as jur, memoria as mem, vetores

rotas = APIRouter(tags=["conhecimento"])


def _erro(e: Exception):
    raise HTTPException(getattr(e, "status", 409), str(e))


def _nomes(ctx: Contexto) -> dict:
    return dict(ctx.db.execute(select(Usuario.id, Usuario.nome).where(Usuario.escritorio_id == ctx.usuario.escritorio_id)).all())


# ================================================================ pesquisa

@rotas.get("/conhecimento/pesquisa")
def pesquisa(q: str = Query(..., min_length=2, max_length=300), cliente_id: uuid.UUID | None = None,
             processo_id: uuid.UUID | None = None,
             origem: list[Literal["biblioteca", "jurisprudencia", "documento", "memoria"]] | None = Query(None),
             limite: int = Query(20, ge=1, le=50), ctx: Contexto = Depends(exigir("conhecimento:ler"))):
    try:
        return conhecimento.pesquisar(ctx.db, ctx.usuario.escritorio_id, ctx.permissoes, q, cliente_id=cliente_id,
                                      processo_id=processo_id, origens=origem, limite=limite)
    except conhecimento.ErroConhecimento as e:
        _erro(e)


@rotas.get("/conhecimento/resumo")
def resumo(ctx: Contexto = Depends(exigir("conhecimento:ler"))):
    esc = ctx.usuario.escritorio_id
    itens = bib.listar(ctx.db, esc, ctx.usuario, alerta=False)
    fontes = ctx.db.execute(select(FonteConhecimento).where(FonteConhecimento.escritorio_id == esc)
                            .order_by(FonteConhecimento.tipo, FonteConhecimento.nome)).scalars().all()
    return {"biblioteca": len(itens), "com_alerta": sum(1 for i in itens if i["alertas"]),
            "metodo": vetores.DESCRICAO, "vetorizador": vetores.NOME,
            "fontes": [{"codigo": f.codigo, "nome": f.nome, "tipo": f.tipo, "dominios": f.dominios, "oficial": f.oficial,
                        "ativa": f.ativa} for f in fontes]}


# ================================================================ biblioteca

class NovoItem(BaseModel):
    tipo: str = Field(max_length=30)
    titulo: str = Field(min_length=3, max_length=400)
    identificador: str | None = Field(None, max_length=200)
    esfera: Literal["federal", "estadual", "municipal", "interna"] | None = None
    orgao: str | None = Field(None, max_length=200)
    ementa: str | None = Field(None, max_length=5000)
    departamento_id: uuid.UUID | None = None
    url_origem: str | None = Field(None, max_length=1000)
    licenca: Literal["publico", "licenciado", "interno", "referencia"] | None = None
    monitorar: bool = False
    assuntos: list[str] = Field(default_factory=list, max_length=30)
    texto: str | None = Field(None, max_length=3_000_000)


class AlterarItem(BaseModel):
    tipo: str | None = Field(None, max_length=30)
    titulo: str | None = Field(None, min_length=3, max_length=400)
    identificador: str | None = Field(None, max_length=200)
    esfera: Literal["federal", "estadual", "municipal", "interna"] | None = None
    orgao: str | None = Field(None, max_length=200)
    ementa: str | None = Field(None, max_length=5000)
    departamento_id: uuid.UUID | None = None
    url_origem: str | None = Field(None, max_length=1000)
    licenca: Literal["publico", "licenciado", "interno", "referencia"] | None = None
    monitorar: bool | None = None
    assuntos: list[str] | None = Field(None, max_length=30)


def _item(ctx: Contexto, iid: uuid.UUID):
    try:
        return bib.obter(ctx.db, ctx.usuario.escritorio_id, iid)
    except bib.ErroBiblioteca as e:
        _erro(e)


@rotas.get("/biblioteca")
def biblioteca(q: str | None = Query(None, max_length=200), tipo: str | None = Query(None, max_length=30),
               departamento_id: uuid.UUID | None = None, colecao_id: uuid.UUID | None = None, alerta: bool = False,
               favoritos: bool = False, incluir_arquivados: bool = False, ctx: Contexto = Depends(exigir("conhecimento:ler"))):
    return {"itens": bib.listar(ctx.db, ctx.usuario.escritorio_id, ctx.usuario, q=q, tipo=tipo, departamento_id=departamento_id,
                                colecao_id=colecao_id, alerta=alerta, favoritos_=favoritos, incluir_arquivados=incluir_arquivados),
            "tipos": bib.ROTULOS_TIPO, "licencas": bib.ROTULOS_LICENCA, "vigencias": bib.ROTULOS_VIGENCIA,
            "colecoes": bib.colecoes(ctx.db, ctx.usuario.escritorio_id),
            "pode_gerenciar": "biblioteca:gerenciar" in ctx.permissoes, "pode_conferir": "biblioteca:conferir" in ctx.permissoes}


@rotas.post("/biblioteca", status_code=201)
def criar_item(dados: NovoItem, ctx: Contexto = Depends(exigir("biblioteca:gerenciar"))):
    if dados.tipo not in TIPOS_BIBLIOTECA:
        raise HTTPException(422, "Tipo inválido")
    d = dados.model_dump(exclude={"texto"})
    if d.get("licenca") is None:
        d.pop("licenca")
    try:
        i = bib.criar(ctx.db, ctx.ator, ctx.usuario.escritorio_id, ctx.usuario, d, dados.texto)
    except bib.ErroBiblioteca as e:
        _erro(e)
    ctx.db.commit()
    return bib.detalhe(ctx.db, i, ctx.usuario)


@rotas.get("/biblioteca/lexml")
def lexml(q: str = Query(..., min_length=2, max_length=200), ctx: Contexto = Depends(exigir("biblioteca:gerenciar"))):
    return bib.pesquisar_lexml(q, 15)


class ImportarLexml(BaseModel):
    urn: str = Field(max_length=300)
    titulo: str | None = Field(None, max_length=400)
    tipo_documento: str | None = Field(None, max_length=100)
    autoridade: str | None = Field(None, max_length=200)
    ementa: str | None = Field(None, max_length=5000)
    assunto: str | None = Field(None, max_length=1000)


@rotas.post("/biblioteca/lexml", status_code=201)
def importar_lexml(dados: ImportarLexml, ctx: Contexto = Depends(exigir("biblioteca:gerenciar"))):
    try:
        i = bib.importar_lexml(ctx.db, ctx.ator, ctx.usuario.escritorio_id, ctx.usuario, dados.model_dump())
    except bib.ErroBiblioteca as e:
        _erro(e)
    ctx.db.commit()
    return bib.detalhe(ctx.db, i, ctx.usuario)


@rotas.get("/biblioteca/{iid}")
def item(iid: uuid.UUID, ctx: Contexto = Depends(exigir("conhecimento:ler"))):
    i = _item(ctx, iid)
    return {**bib.detalhe(ctx.db, i, ctx.usuario), "pode_gerenciar": "biblioteca:gerenciar" in ctx.permissoes,
            "pode_conferir": "biblioteca:conferir" in ctx.permissoes}


@rotas.patch("/biblioteca/{iid}")
def alterar_item(iid: uuid.UUID, dados: AlterarItem, ctx: Contexto = Depends(exigir("biblioteca:gerenciar"))):
    i = _item(ctx, iid)
    mud = dados.model_dump(exclude_unset=True)
    if mud.get("tipo") is not None and mud["tipo"] not in TIPOS_BIBLIOTECA:
        raise HTTPException(422, "Tipo inválido")
    try:
        bib.alterar(ctx.db, ctx.ator, i, {k: v for k, v in mud.items() if v is not None or k in ("departamento_id", "url_origem")})
    except bib.ErroBiblioteca as e:
        _erro(e)
    ctx.db.commit()
    return bib.detalhe(ctx.db, i, ctx.usuario)


class TextoNovo(BaseModel):
    texto: str = Field(min_length=10, max_length=3_000_000)


@rotas.post("/biblioteca/{iid}/versoes", status_code=201)
def nova_versao(iid: uuid.UUID, dados: TextoNovo, ctx: Contexto = Depends(exigir("biblioteca:gerenciar"))):
    i = _item(ctx, iid)
    try:
        v = bib.nova_versao_manual(ctx.db, ctx.ator, i, ctx.usuario, dados.texto)
    except bib.ErroBiblioteca as e:
        _erro(e)
    ctx.db.commit()
    return {"numero": v.numero}


@rotas.get("/biblioteca/{iid}/versoes/{n}")
def texto_versao(iid: uuid.UUID, n: int, ctx: Contexto = Depends(exigir("conhecimento:ler"))):
    i = _item(ctx, iid)
    try:
        return {"numero": n, "texto": bib.texto_versao(ctx.db, i, n)}
    except bib.ErroBiblioteca as e:
        _erro(e)


@rotas.get("/biblioteca/{iid}/comparar")
def comparar(iid: uuid.UUID, a: int = Query(..., ge=1), b: int = Query(..., ge=1), ctx: Contexto = Depends(exigir("conhecimento:ler"))):
    i = _item(ctx, iid)
    try:
        return bib.comparar(ctx.db, i, a, b)
    except bib.ErroBiblioteca as e:
        _erro(e)


class ConferirVersao(BaseModel):
    aceitar: bool
    observacao: str | None = Field(None, max_length=1000)


@rotas.post("/biblioteca/{iid}/versoes/{n}/conferir")
def conferir_versao(iid: uuid.UUID, n: int, dados: ConferirVersao, ctx: Contexto = Depends(exigir("biblioteca:conferir"))):
    i = _item(ctx, iid)
    try:
        bib.conferir_versao(ctx.db, ctx.ator, i, ctx.usuario, n, dados.aceitar, dados.observacao)
    except bib.ErroBiblioteca as e:
        _erro(e)
    ctx.db.commit()
    return bib.detalhe(ctx.db, i, ctx.usuario)


class ConferirVigencia(BaseModel):
    vigencia: Literal["vigente", "revogado", "parcialmente_revogado", "nao_se_aplica"]
    desde: date | None = None
    ate: date | None = None
    observacao: str | None = Field(None, max_length=1000)


@rotas.post("/biblioteca/{iid}/vigencia")
def conferir_vigencia(iid: uuid.UUID, dados: ConferirVigencia, ctx: Contexto = Depends(exigir("biblioteca:conferir"))):
    i = _item(ctx, iid)
    try:
        bib.conferir_vigencia(ctx.db, ctx.ator, i, ctx.usuario, dados.vigencia, dados.desde, dados.ate, dados.observacao)
    except bib.ErroBiblioteca as e:
        _erro(e)
    ctx.db.commit()
    return bib.detalhe(ctx.db, i, ctx.usuario)


@rotas.post("/biblioteca/{iid}/verificar")
def verificar_item(iid: uuid.UUID, ctx: Contexto = Depends(exigir("biblioteca:gerenciar"))):
    i = _item(ctx, iid)
    try:
        r = bib.verificar_agora(ctx.db, ctx.ator, i)
    except bib.ErroBiblioteca as e:
        _erro(e)
    ctx.db.commit()
    return {"resultado": r, "item": bib.detalhe(ctx.db, i, ctx.usuario)}


class Motivo(BaseModel):
    motivo: str = Field(min_length=5, max_length=1000)


@rotas.post("/biblioteca/{iid}/arquivar")
def arquivar_item(iid: uuid.UUID, dados: Motivo, ctx: Contexto = Depends(exigir("biblioteca:gerenciar"))):
    i = _item(ctx, iid)
    try:
        bib.arquivar(ctx.db, ctx.ator, i, True, dados.motivo)
    except bib.ErroBiblioteca as e:
        _erro(e)
    ctx.db.commit()
    return bib.detalhe(ctx.db, i, ctx.usuario)


@rotas.post("/biblioteca/{iid}/desarquivar")
def desarquivar_item(iid: uuid.UUID, ctx: Contexto = Depends(exigir("biblioteca:gerenciar"))):
    i = _item(ctx, iid)
    try:
        bib.arquivar(ctx.db, ctx.ator, i, False, None)
    except bib.ErroBiblioteca as e:
        _erro(e)
    ctx.db.commit()
    return bib.detalhe(ctx.db, i, ctx.usuario)


class Favorito(BaseModel):
    tipo: Literal["biblioteca", "jurisprudencia"]
    ref_id: uuid.UUID
    favorito: bool = True


@rotas.post("/conhecimento/favoritos")
def favoritar(dados: Favorito, ctx: Contexto = Depends(exigir("conhecimento:ler"))):
    try:
        bib.favoritar(ctx.db, ctx.usuario, dados.tipo, dados.ref_id, dados.favorito)
    except bib.ErroBiblioteca as e:
        _erro(e)
    ctx.db.commit()
    return {"ok": True}


class NovaColecao(BaseModel):
    nome: str = Field(min_length=3, max_length=200)
    descricao: str | None = Field(None, max_length=2000)
    departamento_id: uuid.UUID | None = None


@rotas.get("/conhecimento/colecoes")
def colecoes(ctx: Contexto = Depends(exigir("conhecimento:ler"))):
    return {"itens": bib.colecoes(ctx.db, ctx.usuario.escritorio_id)}


@rotas.post("/conhecimento/colecoes", status_code=201)
def criar_colecao(dados: NovaColecao, ctx: Contexto = Depends(exigir("biblioteca:gerenciar"))):
    try:
        c = bib.criar_colecao(ctx.db, ctx.ator, ctx.usuario.escritorio_id, ctx.usuario, dados.nome, dados.descricao,
                              dados.departamento_id)
    except bib.ErroBiblioteca as e:
        _erro(e)
    ctx.db.commit()
    return {"id": str(c.id), "nome": c.nome}


class ItemDaColecao(BaseModel):
    tipo: Literal["biblioteca", "jurisprudencia"]
    ref_id: uuid.UUID
    incluir: bool = True


@rotas.post("/conhecimento/colecoes/{cid}/itens")
def colecao_item(cid: uuid.UUID, dados: ItemDaColecao, ctx: Contexto = Depends(exigir("biblioteca:gerenciar"))):
    try:
        c = bib.obter_colecao(ctx.db, ctx.usuario.escritorio_id, cid)
        bib.colecao_item(ctx.db, ctx.ator, c, dados.tipo, dados.ref_id, dados.incluir)
    except bib.ErroBiblioteca as e:
        _erro(e)
    ctx.db.commit()
    return {"ok": True}


# ================================================================ jurisprudência

class NovoJulgado(BaseModel):
    tribunal: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9]+$")
    numero: str = Field(min_length=3, max_length=120)
    classe: str | None = Field(None, max_length=120)
    orgao_julgador: str | None = Field(None, max_length=200)
    relator: str | None = Field(None, max_length=200)
    data_julgamento: date | None = None
    data_publicacao: date | None = None
    ementa: str = Field(min_length=20, max_length=20000)
    url_original: str | None = Field(None, max_length=1000)
    assuntos: list[str] = Field(default_factory=list, max_length=30)


class AlterarJulgado(BaseModel):
    tribunal: str | None = Field(None, min_length=2, max_length=20, pattern=r"^[A-Za-z0-9]+$")
    numero: str | None = Field(None, min_length=3, max_length=120)
    classe: str | None = Field(None, max_length=120)
    orgao_julgador: str | None = Field(None, max_length=200)
    relator: str | None = Field(None, max_length=200)
    data_julgamento: date | None = None
    data_publicacao: date | None = None
    ementa: str | None = Field(None, min_length=20, max_length=20000)
    url_original: str | None = Field(None, max_length=1000)
    assuntos: list[str] | None = Field(None, max_length=30)


def _julgado(ctx: Contexto, jid: uuid.UUID):
    try:
        return jur.obter(ctx.db, ctx.usuario.escritorio_id, jid)
    except jur.ErroJurisprudencia as e:
        _erro(e)


def _julgado_json(ctx: Contexto, j) -> dict:
    return {**jur.como_json(j, _nomes(ctx)), "colecoes": bib.colecoes_do(ctx.db, "jurisprudencia", j.id),
            "favorito": j.id in bib.favoritos(ctx.db, ctx.usuario, "jurisprudencia"),
            "html_citacao": jur.html_citacao(j) if j.homologada_em else None}


@rotas.get("/jurisprudencia")
def julgados(q: str | None = Query(None, max_length=200), tribunal: str | None = Query(None, max_length=20),
             verificacao: str | None = Query(None, max_length=30), homologadas: bool = False,
             incluir_descartadas: bool = False, favoritos: bool = False, colecao_id: uuid.UUID | None = None,
             ctx: Contexto = Depends(exigir("conhecimento:ler"))):
    itens = jur.listar(ctx.db, ctx.usuario.escritorio_id, ctx.usuario, q=q, tribunal=tribunal, verificacao=verificacao,
                       homologadas=homologadas, incluir_descartadas=incluir_descartadas, favoritos_=favoritos,
                       colecao_id=colecao_id)
    for x in itens:
        x["html_citacao"] = (f'<span data-jurisprudencia="{x["id"]}">({_esc(x["rotulo"])})</span>' if x["citavel"] else None)
    return {"itens": itens, "verificacoes": jur.ROTULOS_VERIFICACAO,
            "colecoes": bib.colecoes(ctx.db, ctx.usuario.escritorio_id),
            "fontes": [{"nome": f.nome, "dominios": f.dominios} for f in ctx.db.execute(
                select(FonteConhecimento).where(FonteConhecimento.escritorio_id == ctx.usuario.escritorio_id,
                                                FonteConhecimento.tipo == "jurisprudencia",
                                                FonteConhecimento.ativa.is_(True)).order_by(FonteConhecimento.nome)).scalars()],
            "pode_gerenciar": "jurisprudencia:gerenciar" in ctx.permissoes,
            "pode_homologar": "jurisprudencia:homologar" in ctx.permissoes}


def _esc(t: str) -> str:
    from html import escape
    return escape(t)


@rotas.post("/jurisprudencia", status_code=201)
def criar_julgado(dados: NovoJulgado, ctx: Contexto = Depends(exigir("jurisprudencia:gerenciar"))):
    try:
        j = jur.criar(ctx.db, ctx.ator, ctx.usuario.escritorio_id, ctx.usuario, dados.model_dump())
    except jur.ErroJurisprudencia as e:
        _erro(e)
    ctx.db.commit()
    return _julgado_json(ctx, j)


@rotas.get("/jurisprudencia/{jid}")
def julgado(jid: uuid.UUID, ctx: Contexto = Depends(exigir("conhecimento:ler"))):
    return _julgado_json(ctx, _julgado(ctx, jid))


@rotas.patch("/jurisprudencia/{jid}")
def alterar_julgado(jid: uuid.UUID, dados: AlterarJulgado, ctx: Contexto = Depends(exigir("jurisprudencia:gerenciar"))):
    j = _julgado(ctx, jid)
    mud = dados.model_dump(exclude_unset=True)
    for k in ("tribunal", "numero", "ementa"):
        if k in mud and mud[k] is None:
            raise HTTPException(422, f"O campo {k} não pode ficar vazio")
    try:
        jur.alterar(ctx.db, ctx.ator, j, mud)
    except jur.ErroJurisprudencia as e:
        _erro(e)
    ctx.db.commit()
    return _julgado_json(ctx, j)


@rotas.post("/jurisprudencia/{jid}/verificar")
def verificar_julgado(jid: uuid.UUID, ctx: Contexto = Depends(exigir("jurisprudencia:gerenciar"))):
    j = _julgado(ctx, jid)
    try:
        jur.verificar(ctx.db, ctx.ator, j)
    except jur.ErroJurisprudencia as e:
        _erro(e)
    ctx.db.commit()
    return _julgado_json(ctx, j)


@rotas.post("/jurisprudencia/{jid}/homologar")
def homologar_julgado(jid: uuid.UUID, ctx: Contexto = Depends(exigir("jurisprudencia:homologar"))):
    j = _julgado(ctx, jid)
    try:
        jur.homologar(ctx.db, ctx.ator, j, ctx.usuario)
    except jur.ErroJurisprudencia as e:
        _erro(e)
    ctx.db.commit()
    return _julgado_json(ctx, j)


@rotas.post("/jurisprudencia/{jid}/descartar")
def descartar_julgado(jid: uuid.UUID, dados: Motivo, ctx: Contexto = Depends(exigir("jurisprudencia:gerenciar"))):
    j = _julgado(ctx, jid)
    try:
        jur.descartar(ctx.db, ctx.ator, j, dados.motivo)
    except jur.ErroJurisprudencia as e:
        _erro(e)
    ctx.db.commit()
    return _julgado_json(ctx, j)


# ================================================================ memória

class NovaMemoria(BaseModel):
    tipo: Literal["decisao", "orientacao", "preferencia", "fato"]
    titulo: str = Field(min_length=3, max_length=300)
    texto: str = Field(min_length=5, max_length=20000)
    cliente_id: uuid.UUID | None = None
    processo_id: uuid.UUID | None = None
    departamento_id: uuid.UUID | None = None
    referencia: str | None = Field(None, max_length=500)
    origem: Literal["pessoa", "documento"] = "pessoa"


def _memoria(ctx: Contexto, mid: uuid.UUID):
    try:
        return mem.obter(ctx.db, ctx.usuario.escritorio_id, mid)
    except mem.ErroMemoria as e:
        _erro(e)


@rotas.get("/memorias")
def memorias(cliente_id: uuid.UUID | None = None, processo_id: uuid.UUID | None = None,
             situacao: Literal["a_confirmar", "confirmada", "substituida", "excluida"] | None = None,
             tipo: str | None = Query(None, max_length=20), q: str | None = Query(None, max_length=200),
             gerais: bool = False, ctx: Contexto = Depends(exigir("memoria:ler"))):
    nomes = _nomes(ctx)
    ms = mem.listar(ctx.db, ctx.usuario.escritorio_id, cliente_id=cliente_id, processo_id=processo_id, situacao=situacao,
                    tipo=tipo, q=q, so_gerais=gerais)
    return {"itens": [mem.como_json(m, nomes) for m in ms], "tipos": mem.ROTULOS_TIPO,
            "pode_gerenciar": "memoria:gerenciar" in ctx.permissoes, "pode_confirmar": "memoria:confirmar" in ctx.permissoes,
            "pode_excluir": "memoria:excluir" in ctx.permissoes}


@rotas.post("/memorias", status_code=201)
def registrar_memoria(dados: NovaMemoria, ctx: Contexto = Depends(exigir("memoria:gerenciar"))):
    d = dados.model_dump(exclude={"origem"})
    try:
        m = mem.registrar(ctx.db, ctx.ator, ctx.usuario.escritorio_id, ctx.usuario, d, origem=dados.origem)
    except mem.ErroMemoria as e:
        _erro(e)
    ctx.db.commit()
    return mem.como_json(m, _nomes(ctx))


class Confirmar(BaseModel):
    texto: str | None = Field(None, min_length=5, max_length=20000)


@rotas.post("/memorias/{mid}/confirmar")
def confirmar_memoria(mid: uuid.UUID, dados: Confirmar, ctx: Contexto = Depends(exigir("memoria:confirmar"))):
    m = _memoria(ctx, mid)
    try:
        mem.confirmar(ctx.db, ctx.ator, m, ctx.usuario, dados.texto)
    except mem.ErroMemoria as e:
        _erro(e)
    ctx.db.commit()
    return mem.como_json(m, _nomes(ctx))


class Corrigir(BaseModel):
    titulo: str | None = Field(None, min_length=3, max_length=300)
    texto: str = Field(min_length=5, max_length=20000)
    motivo: str = Field(min_length=5, max_length=1000)


@rotas.post("/memorias/{mid}/corrigir")
def corrigir_memoria(mid: uuid.UUID, dados: Corrigir, ctx: Contexto = Depends(exigir("memoria:gerenciar"))):
    m = _memoria(ctx, mid)
    try:
        nova = mem.corrigir(ctx.db, ctx.ator, m, ctx.usuario, dados.titulo, dados.texto, dados.motivo)
    except mem.ErroMemoria as e:
        _erro(e)
    ctx.db.commit()
    return mem.como_json(nova, _nomes(ctx))


@rotas.post("/memorias/{mid}/excluir")
def excluir_memoria(mid: uuid.UUID, dados: Motivo, ctx: Contexto = Depends(exigir("memoria:excluir"))):
    m = _memoria(ctx, mid)
    try:
        mem.excluir(ctx.db, ctx.ator, m, dados.motivo)
    except mem.ErroMemoria as e:
        _erro(e)
    ctx.db.commit()
    return mem.como_json(m, _nomes(ctx))


@rotas.get("/memorias/exportar")
def exportar_memorias(cliente_id: uuid.UUID | None = None, ctx: Contexto = Depends(exigir("memoria:ler"))):
    dados = mem.exportar(ctx.db, ctx.usuario.escritorio_id, cliente_id)
    from app.servicos import auditoria
    auditoria.registrar(ctx.db, ctx.ator, "memoria.exportar", entidade="cliente" if cliente_id else "escritorio",
                        entidade_id=str(cliente_id) if cliente_id else None, alteracoes={"quantidade": len(dados["memorias"])})
    ctx.db.commit()
    nome = f"memorias-{'cliente-' + str(cliente_id)[:8] if cliente_id else 'escritorio'}.json"
    return JSONResponse(jsonable_encoder(dados), headers={"Content-Disposition": f'attachment; filename="{nome}"', "Cache-Control": "no-store"})

