"""Documentos: acervo (upload, OCR, busca, versões), modelos, minutas (editor, aprovação, exportação) e assinatura."""
import json
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Contexto, exigir
from app.core.banco import obter_sessao
from app.modelos import (
    CATEGORIAS_DOCUMENTO, Assinatura, Cliente, ComentarioMinuta, Minuta, ModeloDocumento, Processo, Usuario, VersaoDocumento,
    VersaoMinuta,
)
from app.servicos import armazenamento, assinaturas, auditoria, catalogo, documentos as docs, producao
from app.servicos.conectores import documenso
from app.servicos.semente import obter_escritorio

rotas = APIRouter(tags=["documentos"])
publicas = APIRouter(tags=["publico"])
SEGURO = {"Content-Security-Policy": "sandbox", "X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"}


def _erro(e: Exception):
    raise HTTPException(getattr(e, "status", 409), str(e))


def _nomes(ctx: Contexto) -> dict:
    return {u.id: u.nome for u in ctx.db.execute(select(Usuario).where(Usuario.escritorio_id == ctx.usuario.escritorio_id)).scalars()}


def _doc(ctx: Contexto, did: uuid.UUID):
    try:
        return docs.obter(ctx.db, ctx.usuario.escritorio_id, did, ctx.permissoes)
    except docs.ErroDocumento as e:
        _erro(e)


def _vinculos_json(ctx: Contexto, cliente_id, processo_id) -> dict:
    cli = ctx.db.get(Cliente, cliente_id) if cliente_id else None
    proc = ctx.db.get(Processo, processo_id) if processo_id else None
    return {"cliente_nome": cli.nome if cli else None, "processo_numero": proc.numero if proc else None}


# ================================================================ acervo

@rotas.get("/documentos")
def listar(q: str | None = Query(None, max_length=200), categoria: str | None = Query(None, max_length=40),
           cliente_id: uuid.UUID | None = None, processo_id: uuid.UUID | None = None,
           situacao: Literal["ativo", "arquivado", "quarentena", "todos"] = "ativo", pagina: int = Query(1, ge=1, le=1000),
           ctx: Contexto = Depends(exigir("documentos:ler"))):
    r = docs.buscar(ctx.db, ctx.usuario.escritorio_id, ctx.permissoes, q=q, categoria=categoria, cliente_id=cliente_id,
                    processo_id=processo_id, situacao=None if situacao == "todos" else situacao, pagina=pagina)
    return {**r, "categorias": docs.ROTULOS_CATEGORIA}


@rotas.post("/documentos", status_code=201)
async def enviar(arquivo: UploadFile = File(...), titulo: str | None = Form(None, max_length=300),
                 categoria: str | None = Form(None, max_length=40), cliente_id: uuid.UUID | None = Form(None),
                 processo_id: uuid.UUID | None = Form(None), atendimento_id: uuid.UUID | None = Form(None),
                 sigiloso: bool = Form(False), ctx: Contexto = Depends(exigir("documentos:gerenciar"))):
    if sigiloso and "documentos:sigilosos" not in ctx.permissoes:
        raise HTTPException(403, "Só quem acessa documentos sigilosos pode marcar um envio como sigiloso")
    dados = await arquivo.read(200 * 1024 * 1024 + 1)
    try:
        doc, dup = docs.enviar(ctx.db, ctx.ator, ctx.usuario.escritorio_id, nome=arquivo.filename or "arquivo", dados=dados,
                               usuario=ctx.usuario, titulo=(titulo or "").strip() or None, categoria=categoria or None,
                               cliente_id=cliente_id, processo_id=processo_id, atendimento_id=atendimento_id, sigiloso=sigiloso)
    except docs.ErroDocumento as e:
        _erro(e)
    ctx.db.commit()
    return {**docs.como_json(doc), "duplicado": dup}


@rotas.get("/documentos/categorias")
def categorias(ctx: Contexto = Depends(exigir("documentos:ler"))):
    return docs.ROTULOS_CATEGORIA


@rotas.get("/documentos/{did}")
def detalhe(did: uuid.UUID, ctx: Contexto = Depends(exigir("documentos:ler"))):
    d = _doc(ctx, did)
    texto = docs.texto_atual(ctx.db, d)
    return {**docs.como_json(d), **_vinculos_json(ctx, d.cliente_id, d.processo_id),
            "versoes": [docs.versao_json(v) for v in docs.versoes(ctx.db, d)],
            "texto": texto.texto[:200_000] if texto and texto.texto else None,
            "texto_cortado": bool(texto and texto.texto and len(texto.texto) > 200_000),
            "pode_gerenciar": "documentos:gerenciar" in ctx.permissoes,
            "pode_arquivar": "documentos:arquivar" in ctx.permissoes,
            "pode_liberar": "documentos:sigilosos" in ctx.permissoes}


class AlterarDocumento(BaseModel):
    titulo: str | None = Field(default=None, min_length=2, max_length=300)
    categoria: str | None = Field(default=None, max_length=40)
    cliente_id: uuid.UUID | None = None
    processo_id: uuid.UUID | None = None
    sigiloso: bool | None = None


@rotas.patch("/documentos/{did}")
def alterar(did: uuid.UUID, dados: AlterarDocumento, ctx: Contexto = Depends(exigir("documentos:gerenciar"))):
    d = _doc(ctx, did)
    mud = dados.model_dump(exclude_unset=True)
    if "sigiloso" in mud and "documentos:sigilosos" not in ctx.permissoes:
        raise HTTPException(403, "Sem permissão para alterar o sigilo")
    if mud.get("categoria") is not None and mud["categoria"] not in CATEGORIAS_DOCUMENTO:
        raise HTTPException(422, "Categoria inválida")
    try:
        docs.alterar(ctx.db, ctx.ator, d, {k: v for k, v in mud.items() if v is not None or k.endswith("_id")})
    except docs.ErroDocumento as e:
        _erro(e)
    ctx.db.commit()
    return docs.como_json(d)


@rotas.post("/documentos/{did}/versoes", status_code=201)
async def nova_versao(did: uuid.UUID, arquivo: UploadFile = File(...), ctx: Contexto = Depends(exigir("documentos:gerenciar"))):
    d = _doc(ctx, did)
    dados = await arquivo.read(200 * 1024 * 1024 + 1)
    try:
        v = docs.nova_versao(ctx.db, ctx.ator, d, nome=arquivo.filename or "arquivo", dados=dados, usuario=ctx.usuario)
    except docs.ErroDocumento as e:
        _erro(e)
    ctx.db.commit()
    return docs.versao_json(v)


@rotas.get("/documentos/{did}/versoes/{numero}/arquivo")
def baixar(did: uuid.UUID, numero: int, ctx: Contexto = Depends(exigir("documentos:ler"))):
    d = _doc(ctx, did)
    if d.situacao == "quarentena" and "documentos:sigilosos" not in ctx.permissoes:
        raise HTTPException(403, "Arquivo em quarentena: só pode ser baixado por quem libera a quarentena")
    v = ctx.db.execute(select(VersaoDocumento).where(VersaoDocumento.documento_id == d.id, VersaoDocumento.numero == numero)).scalar()
    if v is None:
        raise HTTPException(404, "Versão não encontrada")
    auditoria.registrar(ctx.db, ctx.ator, "documento.baixar", entidade="documento", entidade_id=d.id,
                             alteracoes={"versao": numero})
    ctx.db.commit()
    if v.caminho is None:  # versão de texto extraído
        nome = f"{(v.nome_arquivo or d.titulo)[:80]}-texto.txt"
        return Response((v.texto or "").encode(), media_type="text/plain; charset=utf-8",
                        headers={**SEGURO, "Content-Disposition": f"attachment; filename*=UTF-8''{_cod(nome)}"})
    try:
        caminho = armazenamento.caminho(v.caminho)
    except ValueError:
        raise HTTPException(400, "Caminho inválido")
    # sempre como anexo e sob sandbox: o navegador não executa conteúdo enviado por terceiros
    return FileResponse(caminho, media_type=v.tipo_mime or "application/octet-stream", filename=v.nome_arquivo or "arquivo",
                        headers=SEGURO)


def _cod(nome: str) -> str:
    from urllib.parse import quote
    return quote(nome, safe="")


@rotas.get("/documentos/{did}/comparar")
def comparar(did: uuid.UUID, a: int = Query(..., ge=1), b: int = Query(..., ge=1), ctx: Contexto = Depends(exigir("documentos:ler"))):
    d = _doc(ctx, did)
    try:
        return docs.comparar(ctx.db, d, a, b)
    except docs.ErroDocumento as e:
        _erro(e)


class Motivo(BaseModel):
    motivo: str | None = Field(default=None, max_length=2000)


@rotas.post("/documentos/{did}/arquivar")
def arquivar(did: uuid.UUID, dados: Motivo, ctx: Contexto = Depends(exigir("documentos:arquivar"))):
    d = _doc(ctx, did)
    try:
        docs.arquivar(ctx.db, ctx.ator, d, True, dados.motivo)
    except docs.ErroDocumento as e:
        _erro(e)
    ctx.db.commit()
    return docs.como_json(d)


@rotas.post("/documentos/{did}/desarquivar")
def desarquivar(did: uuid.UUID, ctx: Contexto = Depends(exigir("documentos:arquivar"))):
    d = _doc(ctx, did)
    try:
        docs.arquivar(ctx.db, ctx.ator, d, False, None)
    except docs.ErroDocumento as e:
        _erro(e)
    ctx.db.commit()
    return docs.como_json(d)


@rotas.post("/documentos/{did}/liberar")
def liberar(did: uuid.UUID, dados: Motivo, ctx: Contexto = Depends(exigir("documentos:sigilosos"))):
    d = _doc(ctx, did)
    try:
        docs.liberar_quarentena(ctx.db, ctx.ator, d, dados.motivo or "")
    except docs.ErroDocumento as e:
        _erro(e)
    ctx.db.commit()
    return docs.como_json(d)


@rotas.post("/documentos/{did}/processar")
def processar(did: uuid.UUID, ctx: Contexto = Depends(exigir("documentos:gerenciar"))):
    """Roda agora a extração de texto/OCR pendente deste documento (sem esperar o worker)."""
    d = _doc(ctx, did)
    if d.situacao == "quarentena":
        raise HTTPException(409, "Arquivo em quarentena não é processado")
    docs.processar_pendentes(ctx.db, d)
    ctx.db.commit()
    return detalhe(did, ctx)


# ================================================================ modelos

def _modelo(ctx: Contexto, mid: uuid.UUID) -> ModeloDocumento:
    m = ctx.db.get(ModeloDocumento, mid)
    if m is None or m.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Modelo não encontrado")
    return m


@rotas.get("/modelos")
def modelos(incluir_arquivados: bool = False, ctx: Contexto = Depends(exigir("modelos:ler"))):
    return {"itens": producao.listar_modelos(ctx.db, ctx.usuario.escritorio_id, ctx.usuario, incluir_arquivados),
            "categorias": producao.CATEGORIAS_MODELO, "aviso_inicial": catalogo.AVISO_MODELO_INICIAL}


@rotas.get("/modelos/campos")
def campos_disponiveis(ctx: Contexto = Depends(exigir("modelos:ler"))):
    return {"campos": [{"campo": k, "rotulo": v} for k, v in producao.CAMPOS.items()],
            "manual": "Use {{manual.nome_do_campo}} para dados que a pessoa preenche na minuta (ex.: {{manual.valor}})."}


@rotas.get("/modelos/{mid}")
def modelo(mid: uuid.UUID, ctx: Contexto = Depends(exigir("modelos:ler"))):
    m = _modelo(ctx, mid)
    versoes = ctx.db.execute(select(ModeloDocumento).where(ModeloDocumento.escritorio_id == m.escritorio_id,
                                                           ModeloDocumento.codigo == m.codigo)
                             .order_by(ModeloDocumento.versao.desc())).scalars().all()
    nomes = _nomes(ctx)
    return {**producao.modelo_json(m, completo=True), "homologado_por": nomes.get(m.homologado_por),
            "versoes": [producao.modelo_json(v) for v in versoes],
            "pode_editar": "modelos:gerenciar" in ctx.permissoes, "pode_homologar": "modelos:homologar" in ctx.permissoes}


class NovoModelo(BaseModel):
    codigo: str = Field(pattern=r"^[a-z][a-z0-9_]{2,59}$")
    titulo: str = Field(min_length=3, max_length=300)
    categoria: str = Field(max_length=40)
    conteudo: str = Field(min_length=1, max_length=500_000)
    cabecalho: str | None = Field(default=None, max_length=500)
    rodape: str | None = Field(default=None, max_length=500)
    descricao: str | None = Field(default=None, max_length=2000)
    departamento_id: uuid.UUID | None = None


@rotas.post("/modelos", status_code=201)
def criar_modelo(dados: NovoModelo, ctx: Contexto = Depends(exigir("modelos:gerenciar"))):
    try:
        m = producao.criar_modelo(ctx.db, ctx.ator, ctx.usuario.escritorio_id, ctx.usuario, **dados.model_dump())
    except producao.ErroProducao as e:
        _erro(e)
    ctx.db.commit()
    return producao.modelo_json(m, completo=True)


class EditarModelo(BaseModel):
    titulo: str | None = Field(default=None, min_length=3, max_length=300)
    categoria: str | None = Field(default=None, max_length=40)
    conteudo: str | None = Field(default=None, min_length=1, max_length=500_000)
    cabecalho: str | None = Field(default=None, max_length=500)
    rodape: str | None = Field(default=None, max_length=500)
    descricao: str | None = Field(default=None, max_length=2000)


@rotas.patch("/modelos/{mid}")
def editar_modelo(mid: uuid.UUID, dados: EditarModelo, ctx: Contexto = Depends(exigir("modelos:gerenciar"))):
    m = _modelo(ctx, mid)
    try:
        alvo = producao.editar_modelo(ctx.db, ctx.ator, m, ctx.usuario, dados.model_dump(exclude_unset=True))
    except producao.ErroProducao as e:
        _erro(e)
    ctx.db.commit()
    return producao.modelo_json(alvo, completo=True)


@rotas.post("/modelos/{mid}/homologar")
def homologar(mid: uuid.UUID, ctx: Contexto = Depends(exigir("modelos:homologar"))):
    m = _modelo(ctx, mid)
    try:
        producao.homologar_modelo(ctx.db, ctx.ator, m, ctx.usuario)
    except producao.ErroProducao as e:
        _erro(e)
    ctx.db.commit()
    return producao.modelo_json(m, completo=True)


@rotas.post("/modelos/{mid}/arquivar")
def arquivar_modelo(mid: uuid.UUID, ctx: Contexto = Depends(exigir("modelos:gerenciar"))):
    m = _modelo(ctx, mid)
    producao.arquivar_modelo(ctx.db, ctx.ator, m)
    ctx.db.commit()
    return {"ok": True}


class Favorito(BaseModel):
    favorito: bool


@rotas.post("/modelos/{mid}/favorito")
def favorito(mid: uuid.UUID, dados: Favorito, ctx: Contexto = Depends(exigir("modelos:ler"))):
    producao.favoritar(ctx.db, ctx.usuario, _modelo(ctx, mid), dados.favorito)
    ctx.db.commit()
    return {"ok": True}


# ================================================================ minutas

def _minuta(ctx: Contexto, mid: uuid.UUID) -> Minuta:
    m = ctx.db.get(Minuta, mid)
    if m is None or m.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Minuta não encontrada")
    return m


def _minuta_completa(ctx: Contexto, m: Minuta) -> dict:
    nomes = _nomes(ctx)
    comentarios = ctx.db.execute(select(ComentarioMinuta).where(ComentarioMinuta.minuta_id == m.id)
                                 .order_by(ComentarioMinuta.criado_em)).scalars().all()
    versoes = ctx.db.execute(select(VersaoMinuta).where(VersaoMinuta.minuta_id == m.id)
                             .order_by(VersaoMinuta.numero.desc())).scalars().all()
    p = ctx.permissoes
    return {**producao.minuta_json(m, nomes, completo=True), **_vinculos_json(ctx, m.cliente_id, m.processo_id),
            "comentarios": [{"id": str(c.id), "autor": nomes.get(c.autor_id), "texto": c.texto, "trecho": c.trecho,
                             "resolvido": c.resolvido_em is not None, "resolvido_por": nomes.get(c.resolvido_por),
                             "criado_em": c.criado_em} for c in comentarios],
            "versoes": [{"numero": v.numero, "motivo": v.motivo, "autor": nomes.get(v.autor_id), "criado_em": v.criado_em}
                        for v in versoes],
            "assinaturas": [assinaturas.como_json(a, nomes) for a in assinaturas.listar(ctx.db, m)],
            "assinatura": assinaturas.disponivel(), "pdf_disponivel": producao.conversao_pdf_disponivel(),
            "pode_editar": (m.situacao == "rascunho" and "minutas:editar" in p) or (m.situacao == "em_revisao" and "minutas:aprovar" in p),
            "pode_aprovar": "minutas:aprovar" in p, "pode_enviar_assinatura": "assinaturas:enviar" in p}


@rotas.get("/minutas")
def minutas(situacao: str | None = Query(None, max_length=20), cliente_id: uuid.UUID | None = None,
            processo_id: uuid.UUID | None = None, atendimento_id: uuid.UUID | None = None,
            q: str | None = Query(None, max_length=200), ctx: Contexto = Depends(exigir("minutas:ler"))):
    conds = [Minuta.escritorio_id == ctx.usuario.escritorio_id]
    if situacao:
        conds.append(Minuta.situacao == situacao)
    elif not q:
        conds.append(Minuta.situacao != "arquivada")
    for col, val in ((Minuta.cliente_id, cliente_id), (Minuta.processo_id, processo_id), (Minuta.atendimento_id, atendimento_id)):
        if val:
            conds.append(col == val)
    if q:
        conds.append(Minuta.titulo.ilike(f"%{q.strip()}%"))
    itens = ctx.db.execute(select(Minuta).where(*conds).order_by(Minuta.atualizado_em.desc()).limit(300)).scalars().all()
    nomes = _nomes(ctx)
    return {"itens": [producao.minuta_json(m, nomes) for m in itens]}


class GerarMinuta(BaseModel):
    modelo_id: uuid.UUID
    titulo: str | None = Field(default=None, max_length=300)
    cliente_id: uuid.UUID | None = None
    processo_id: uuid.UUID | None = None
    atendimento_id: uuid.UUID | None = None
    manuais: dict[str, str] = Field(default_factory=dict, max_length=50)


@rotas.post("/minutas", status_code=201)
def gerar(dados: GerarMinuta, ctx: Contexto = Depends(exigir("minutas:editar"))):
    modelo_ = _modelo(ctx, dados.modelo_id)
    try:
        m = producao.gerar(ctx.db, ctx.ator, ctx.usuario, modelo_, titulo=dados.titulo, cliente_id=dados.cliente_id,
                           processo_id=dados.processo_id, atendimento_id=dados.atendimento_id,
                           manuais={k: v[:2000] for k, v in dados.manuais.items()})
    except producao.ErroProducao as e:
        _erro(e)
    ctx.db.commit()
    return _minuta_completa(ctx, m)


@rotas.get("/minutas/{mid}")
def minuta(mid: uuid.UUID, ctx: Contexto = Depends(exigir("minutas:ler"))):
    return _minuta_completa(ctx, _minuta(ctx, mid))


class SalvarMinuta(BaseModel):
    conteudo: str | None = Field(default=None, max_length=2_000_000)
    titulo: str | None = Field(default=None, min_length=2, max_length=300)
    cabecalho: str | None = Field(default=None, max_length=500)
    rodape: str | None = Field(default=None, max_length=500)
    base: datetime | None = None
    criar_versao: bool = False


@rotas.put("/minutas/{mid}")
def salvar(mid: uuid.UUID, dados: SalvarMinuta, ctx: Contexto = Depends(exigir("minutas:ler"))):
    m = _minuta(ctx, mid)
    try:
        producao.salvar(ctx.db, ctx.ator, m, ctx.usuario, ctx.permissoes, conteudo=dados.conteudo, titulo=dados.titulo,
                        cabecalho=dados.cabecalho, rodape=dados.rodape, base=dados.base, criar_versao=dados.criar_versao)
    except producao.ErroProducao as e:
        _erro(e)
    ctx.db.commit()
    return {"atualizado_em": m.atualizado_em, "versao_atual": m.versao_atual, "pendentes": m.pendentes}


class Preencher(BaseModel):
    valores: dict[str, str] = Field(max_length=50)


@rotas.post("/minutas/{mid}/preencher")
def preencher(mid: uuid.UUID, dados: Preencher, ctx: Contexto = Depends(exigir("minutas:ler"))):
    m = _minuta(ctx, mid)
    try:
        producao.preencher(ctx.db, ctx.ator, m, ctx.usuario, ctx.permissoes, {k: v[:2000] for k, v in dados.valores.items()})
    except producao.ErroProducao as e:
        _erro(e)
    ctx.db.commit()
    return _minuta_completa(ctx, m)


class Comentario(BaseModel):
    texto: str = Field(min_length=2, max_length=4000)
    trecho: str | None = Field(default=None, max_length=500)


@rotas.post("/minutas/{mid}/comentarios", status_code=201)
def comentar(mid: uuid.UUID, dados: Comentario, ctx: Contexto = Depends(exigir("minutas:editar"))):
    m = _minuta(ctx, mid)
    try:
        producao.comentar(ctx.db, ctx.ator, m, ctx.usuario, dados.texto, dados.trecho)
    except producao.ErroProducao as e:
        _erro(e)
    ctx.db.commit()
    return _minuta_completa(ctx, m)


@rotas.post("/minutas/{mid}/comentarios/{cid}/resolver")
def resolver_comentario(mid: uuid.UUID, cid: uuid.UUID, ctx: Contexto = Depends(exigir("minutas:editar"))):
    m = _minuta(ctx, mid)
    c = ctx.db.get(ComentarioMinuta, cid)
    if c is None or c.minuta_id != m.id:
        raise HTTPException(404, "Comentário não encontrado")
    producao.resolver_comentario(ctx.db, ctx.ator, c, ctx.usuario)
    ctx.db.commit()
    return _minuta_completa(ctx, m)


@rotas.post("/minutas/{mid}/revisao")
def pedir_revisao(mid: uuid.UUID, ctx: Contexto = Depends(exigir("minutas:editar"))):
    m = _minuta(ctx, mid)
    try:
        producao.pedir_revisao(ctx.db, ctx.ator, m, ctx.usuario)
    except producao.ErroProducao as e:
        _erro(e)
    ctx.db.commit()
    return _minuta_completa(ctx, m)


@rotas.post("/minutas/{mid}/devolver")
def devolver(mid: uuid.UUID, dados: Motivo, ctx: Contexto = Depends(exigir("minutas:aprovar"))):
    m = _minuta(ctx, mid)
    try:
        producao.devolver(ctx.db, ctx.ator, m, ctx.usuario, dados.motivo or "")
    except producao.ErroProducao as e:
        _erro(e)
    ctx.db.commit()
    return _minuta_completa(ctx, m)


@rotas.post("/minutas/{mid}/aprovar")
def aprovar(mid: uuid.UUID, ctx: Contexto = Depends(exigir("minutas:aprovar"))):
    m = _minuta(ctx, mid)
    try:
        producao.aprovar(ctx.db, ctx.ator, m, ctx.usuario, ctx.permissoes)
    except (producao.ErroProducao, docs.ErroDocumento) as e:
        ctx.db.rollback()
        _erro(e)
    except Exception as e:  # erro de etapa do atendimento, por exemplo
        ctx.db.rollback()
        if hasattr(e, "status"):
            _erro(e)
        raise
    ctx.db.commit()
    return _minuta_completa(ctx, m)


@rotas.post("/minutas/{mid}/arquivar")
def arquivar_minuta(mid: uuid.UUID, dados: Motivo, ctx: Contexto = Depends(exigir("minutas:editar"))):
    m = _minuta(ctx, mid)
    try:
        producao.arquivar(ctx.db, ctx.ator, m, dados.motivo or "")
    except producao.ErroProducao as e:
        _erro(e)
    ctx.db.commit()
    return _minuta_completa(ctx, m)


@rotas.get("/minutas/{mid}/comparar")
def comparar_minuta(mid: uuid.UUID, a: int = Query(..., ge=1), b: int = Query(..., ge=1),
                    ctx: Contexto = Depends(exigir("minutas:ler"))):
    try:
        return producao.comparar_versoes(ctx.db, _minuta(ctx, mid), a, b)
    except producao.ErroProducao as e:
        _erro(e)


@rotas.get("/minutas/{mid}/exportar")
def exportar(mid: uuid.UUID, formato: Literal["docx", "pdf"] = "docx", ctx: Contexto = Depends(exigir("minutas:ler"))):
    """Exporta. Antes da aprovação o arquivo sai marcado como RASCUNHO no cabeçalho."""
    m = _minuta(ctx, mid)
    dados = producao.exportar_docx(m)
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if formato == "pdf":
        try:
            dados, mime = producao.converter_pdf(dados), "application/pdf"
        except producao.ErroProducao as e:
            _erro(e)
    nome = f"{producao._nome_arquivo(m)}{'' if m.situacao == 'aprovada' else '-RASCUNHO'}.{formato}"
    auditoria.registrar(ctx.db, ctx.ator, "minuta.exportar", entidade="minuta", entidade_id=m.id,
                             alteracoes={"formato": formato, "situacao": m.situacao})
    ctx.db.commit()
    return Response(dados, media_type=mime, headers={**SEGURO, "Content-Disposition": f"attachment; filename*=UTF-8''{_cod(nome)}"})


# ================================================================ assinatura

class Participante(BaseModel):
    nome: str = Field(min_length=3, max_length=200)
    email: str = Field(min_length=5, max_length=254)
    papel: Literal["assinar", "aprovar", "receber_copia", "visualizar"] = "assinar"
    ordem: int | None = Field(default=None, ge=1, le=20)


class PrepararAssinatura(BaseModel):
    participantes: list[Participante] = Field(min_length=1, max_length=10)
    mensagem: str | None = Field(default=None, max_length=2000)


def _assinatura(ctx: Contexto, aid: uuid.UUID) -> Assinatura:
    a = ctx.db.get(Assinatura, aid)
    if a is None or a.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Pedido de assinatura não encontrado")
    return a


@rotas.post("/minutas/{mid}/assinaturas", status_code=201)
def preparar_assinatura(mid: uuid.UUID, dados: PrepararAssinatura, ctx: Contexto = Depends(exigir("minutas:editar"))):
    m = _minuta(ctx, mid)
    try:
        assinaturas.preparar(ctx.db, ctx.ator, m, ctx.usuario, [p.model_dump() for p in dados.participantes], dados.mensagem)
    except assinaturas.ErroAssinatura as e:
        _erro(e)
    ctx.db.commit()
    return _minuta_completa(ctx, m)


@rotas.post("/assinaturas/{aid}/enviar")
def enviar_assinatura(aid: uuid.UUID, ctx: Contexto = Depends(exigir("assinaturas:enviar"))):
    """Autorização profissional do envio. Quem assina é cada participante, no Documenso."""
    a = _assinatura(ctx, aid)
    try:
        assinaturas.enviar(ctx.db, ctx.ator, a, ctx.usuario)
    except assinaturas.ErroAssinatura as e:
        _erro(e)
    ctx.db.commit()
    return _minuta_completa(ctx, ctx.db.get(Minuta, a.minuta_id))


@rotas.post("/assinaturas/{aid}/cancelar")
def cancelar_assinatura(aid: uuid.UUID, ctx: Contexto = Depends(exigir("minutas:editar"))):
    a = _assinatura(ctx, aid)
    try:
        assinaturas.cancelar_preparo(ctx.db, ctx.ator, a)
    except assinaturas.ErroAssinatura as e:
        _erro(e)
    ctx.db.commit()
    return _minuta_completa(ctx, ctx.db.get(Minuta, a.minuta_id))


@publicas.post("/publico/documenso/webhook")
async def webhook_documenso(request: Request, db: Session = Depends(obter_sessao)):
    if not documenso.verificar_segredo(request.headers.get("x-documenso-secret")):
        raise HTTPException(403, "Segredo inválido")
    corpo = await request.body()
    if len(corpo) > 1024 * 1024:
        raise HTTPException(413, "Corpo grande demais")
    try:
        dados = json.loads(corpo)
    except ValueError:
        raise HTTPException(400, "JSON inválido")
    if not isinstance(dados, dict):
        raise HTTPException(400, "JSON inválido")
    a = assinaturas.receber_webhook(db, obter_escritorio(db).id, dados)
    db.commit()
    return {"ok": True, "aplicado": a is not None}
