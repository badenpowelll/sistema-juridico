"""Atendimento e CRM (lado da equipe): funil, links de cadastro, cadastro recebido, documentos, conversas e portal."""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select

from app.api.deps import Contexto, exigir
from app.modelos import (
    AcessoPortal, Atendimento, Auditoria, Cliente, Conversa, Departamento, DocumentoRecebido, LinkCadastro, Mensagem,
    Processo, SolicitacaoPortal, Usuario,
)
from app.servicos import atendimentos as svc, auditoria, conversas, portal

rotas = APIRouter(tags=["atendimento"])


def _nomes(ctx: Contexto) -> dict:
    return {u.id: u.nome for u in ctx.db.execute(select(Usuario).where(Usuario.escritorio_id == ctx.usuario.escritorio_id)).scalars()}


def _deps(ctx: Contexto) -> dict:
    return {d.id: d.nome for d in ctx.db.execute(select(Departamento).where(Departamento.escritorio_id == ctx.usuario.escritorio_id)).scalars()}


def _at(ctx: Contexto, aid: uuid.UUID) -> Atendimento:
    at = ctx.db.get(Atendimento, aid)
    if at is None or at.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Atendimento não encontrado")
    return at


def _erro(e: Exception):
    status = getattr(e, "status", 409)
    raise HTTPException(status, str(e))


# ================================================================ funil

@rotas.get("/atendimentos")
def listar(etapa: str | None = Query(None, max_length=40), q: str | None = Query(None, max_length=200), meus: bool = False,
           incluir_encerrados: bool = False, ctx: Contexto = Depends(exigir("atendimentos:ler"))):
    esc = ctx.usuario.escritorio_id
    contagem = dict(ctx.db.execute(select(Atendimento.etapa, func.count()).where(Atendimento.escritorio_id == esc)
                                   .group_by(Atendimento.etapa)).all())
    conds = [Atendimento.escritorio_id == esc]
    if etapa:
        conds.append(Atendimento.etapa == etapa)
    elif not incluir_encerrados:
        conds.append(Atendimento.etapa.not_in(("encerramento", "arquivamento")))
    if meus:
        conds.append(Atendimento.responsavel_id == ctx.usuario.id)
    if q:
        termo = f"%{q.strip()}%"
        conds.append(or_(Atendimento.contato_nome.ilike(termo), Atendimento.protocolo.ilike(termo),
                         Atendimento.contato_telefone.ilike(f"%{''.join(c for c in q if c.isdigit()) or q}%"),
                         Atendimento.assunto.ilike(termo)))
    itens = ctx.db.execute(select(Atendimento).where(*conds).order_by(Atendimento.atualizado_em.desc()).limit(300)).scalars().all()
    nomes, deps = _nomes(ctx), _deps(ctx)
    abertas = ctx.db.execute(select(func.count()).select_from(SolicitacaoPortal).where(
        SolicitacaoPortal.escritorio_id == esc, SolicitacaoPortal.situacao == "aberta")).scalar_one()
    return {"etapas": svc.ETAPAS, "contagem": contagem, "solicitacoes_portal_abertas": abertas,
            "itens": [svc.como_json(a, nomes, deps) for a in itens]}


class NovoAtendimento(BaseModel):
    contato_nome: str = Field(min_length=2, max_length=300)
    contato_telefone: str | None = Field(default=None, max_length=30)
    contato_email: EmailStr | None = None
    assunto: str | None = Field(default=None, max_length=500)
    departamento_id: uuid.UUID | None = None
    cliente_id: uuid.UUID | None = None
    canal: Literal["manual", "presencial", "telefone", "email", "site"] = "manual"
    responsavel_id: uuid.UUID | None = None


@rotas.post("/atendimentos", status_code=201)
def abrir(dados: NovoAtendimento, ctx: Contexto = Depends(exigir("atendimentos:gerenciar"))):
    try:
        at = svc.abrir(ctx.db, ctx.ator, ctx.usuario.escritorio_id, usuario=ctx.usuario, **dados.model_dump())
    except svc.ErroAtendimento as e:
        _erro(e)
    ctx.db.commit()
    return svc.como_json(at, _nomes(ctx), _deps(ctx))


@rotas.get("/atendimentos/{aid}")
def detalhe(aid: uuid.UUID, ctx: Contexto = Depends(exigir("atendimentos:ler"))):
    at = _at(ctx, aid)
    links = ctx.db.execute(select(LinkCadastro).where(LinkCadastro.atendimento_id == at.id)
                           .order_by(LinkCadastro.criado_em.desc())).scalars().all()
    resumo = svc.resumo(ctx.db, at)
    if resumo is not None:
        auditoria.registrar(ctx.db, ctx.ator, "atendimento.cadastro.ver", entidade="atendimento", entidade_id=at.id)
    hist = ctx.db.execute(select(Auditoria).where(Auditoria.entidade == "atendimento", Auditoria.entidade_id == str(at.id),
                                                  Auditoria.operacao != "atendimento.cadastro.ver")
                          .order_by(Auditoria.id.desc()).limit(100)).scalars().all()
    conv = ctx.db.execute(select(Conversa).where(Conversa.atendimento_id == at.id).limit(1)).scalar()
    cli = ctx.db.get(Cliente, at.cliente_id) if at.cliente_id else None
    proc = ctx.db.get(Processo, at.processo_id) if at.processo_id else None
    ctx.db.commit()
    return {**svc.como_json(at, _nomes(ctx), _deps(ctx)),
            "links": [svc.link_json(x) for x in links], "cadastro": resumo,
            "documentos": [svc.documento_json(d) for d in svc.documentos_de(ctx.db, at)],
            "cliente": {"id": str(cli.id), "nome": cli.nome, "documento": cli.documento_mascarado} if cli else None,
            "processo": {"id": str(proc.id), "numero": proc.numero_formatado} if proc else None,
            "conversa": conversas.conversa_json(conv) if conv else None,
            "historico": [{"operacao": h.operacao, "por": h.ator_nome, "quando": h.ocorrido_em, "alteracoes": h.alteracoes,
                           "origem": h.origem} for h in hist]}


class AlterarAtendimento(BaseModel):
    contato_nome: str | None = Field(default=None, min_length=2, max_length=300)
    contato_telefone: str | None = Field(default=None, max_length=30)
    contato_email: EmailStr | None = None
    assunto: str | None = Field(default=None, max_length=500)
    departamento_id: uuid.UUID | None = None
    responsavel_id: uuid.UUID | None = None
    observacoes: str | None = Field(default=None, max_length=10000)


@rotas.patch("/atendimentos/{aid}")
def alterar(aid: uuid.UUID, dados: AlterarAtendimento, ctx: Contexto = Depends(exigir("atendimentos:gerenciar"))):
    at = _at(ctx, aid)
    mud = dados.model_dump(exclude_unset=True)
    if "departamento_id" in mud and mud["departamento_id"]:
        d = ctx.db.get(Departamento, mud["departamento_id"])
        if d is None or d.escritorio_id != at.escritorio_id:
            raise HTTPException(404, "Departamento não encontrado")
    for k, v in mud.items():
        setattr(at, k, v)
    auditoria.registrar(ctx.db, ctx.ator, "atendimento.alterar", entidade="atendimento", entidade_id=at.id,
                        alteracoes={k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in mud.items() if k != "observacoes"}
                        | ({"observacoes": "(alteradas)"} if "observacoes" in mud else {}))
    ctx.db.commit()
    return svc.como_json(at, _nomes(ctx), _deps(ctx))


class MudarEtapa(BaseModel):
    etapa: str = Field(max_length=40)
    motivo: str | None = Field(default=None, max_length=2000)


@rotas.post("/atendimentos/{aid}/etapa")
def etapa(aid: uuid.UUID, dados: MudarEtapa, ctx: Contexto = Depends(exigir("atendimentos:gerenciar"))):
    at = _at(ctx, aid)
    try:
        svc.mover(ctx.db, ctx.ator, at, dados.etapa, ctx.usuario, ctx.permissoes, dados.motivo)
    except svc.ErroAtendimento as e:
        _erro(e)
    ctx.db.commit()
    return svc.como_json(at, _nomes(ctx), _deps(ctx))


class PedidoLink(BaseModel):
    finalidade: Literal["cadastro", "documentos"] = "cadastro"


@rotas.post("/atendimentos/{aid}/links", status_code=201)
def gerar_link(aid: uuid.UUID, dados: PedidoLink, ctx: Contexto = Depends(exigir("atendimentos:gerenciar"))):
    at = _at(ctx, aid)
    try:
        g = svc.gerar_link(ctx.db, ctx.ator, at, ctx.usuario, finalidade=dados.finalidade, canal="painel")
    except svc.ErroAtendimento as e:
        _erro(e)
    ctx.db.commit()
    # o endereço completo aparece só agora: o banco guarda apenas o hash do token
    return {**svc.link_json(g.link), "url": g.url}


@rotas.post("/atendimentos/{aid}/links/{lid}/revogar")
def revogar_link(aid: uuid.UUID, lid: uuid.UUID, ctx: Contexto = Depends(exigir("atendimentos:gerenciar"))):
    at = _at(ctx, aid)
    link = ctx.db.get(LinkCadastro, lid)
    if link is None or link.atendimento_id != at.id:
        raise HTTPException(404, "Link não encontrado")
    svc.revogar_link(ctx.db, ctx.ator, link, ctx.usuario)
    ctx.db.commit()
    return svc.link_json(link)


@rotas.post("/atendimentos/{aid}/cliente")
def criar_cliente(aid: uuid.UUID, ctx: Contexto = Depends(exigir("atendimentos:gerenciar", "clientes:gerenciar"))):
    at = _at(ctx, aid)
    try:
        c, novo = svc.criar_cliente(ctx.db, ctx.ator, at)
    except svc.ErroAtendimento as e:
        _erro(e)
    except ValueError as e:
        raise HTTPException(422, str(e))
    ctx.db.commit()
    return {"cliente_id": str(c.id), "novo": novo, "nome": c.nome}


class VincularProcesso(BaseModel):
    processo_id: uuid.UUID


@rotas.post("/atendimentos/{aid}/processo")
def vincular_processo(aid: uuid.UUID, dados: VincularProcesso, ctx: Contexto = Depends(exigir("atendimentos:gerenciar"))):
    at = _at(ctx, aid)
    p = ctx.db.get(Processo, dados.processo_id)
    if p is None:
        raise HTTPException(404, "Processo não encontrado")
    try:
        svc.vincular_processo(ctx.db, ctx.ator, at, p)
    except svc.ErroAtendimento as e:
        _erro(e)
    ctx.db.commit()
    return svc.como_json(at, _nomes(ctx), _deps(ctx))


@rotas.post("/atendimentos/{aid}/documentos", status_code=201)
async def enviar_documento(aid: uuid.UUID, arquivo: UploadFile = File(...), previsto: str | None = Form(None),
                           ctx: Contexto = Depends(exigir("atendimentos:gerenciar"))):
    at = _at(ctx, aid)
    dados = await arquivo.read(100 * 1024 * 1024 + 1)
    try:
        doc, dup = svc.receber_arquivo(ctx.db, at, nome=arquivo.filename or "arquivo", dados=dados, origem="painel",
                                       previsto=previsto, usuario=ctx.usuario, ator=ctx.ator)
    except svc.ErroAtendimento as e:
        _erro(e)
    ctx.db.commit()
    return {**svc.documento_json(doc), "duplicado": dup}


def _doc(ctx: Contexto, did: uuid.UUID) -> DocumentoRecebido:
    d = ctx.db.get(DocumentoRecebido, did)
    if d is None or d.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Documento não encontrado")
    return d


@rotas.get("/documentos-recebidos/{did}/arquivo")
def baixar(did: uuid.UUID, ctx: Contexto = Depends(exigir("atendimentos:ler"))):
    d = _doc(ctx, did)
    caminho = svc.caminho_arquivo(d)
    if not caminho.exists():
        raise HTTPException(410, "Arquivo não está mais no armazenamento")
    auditoria.registrar(ctx.db, ctx.ator, "documento_recebido.baixar", entidade="atendimento",
                        entidade_id=d.atendimento_id or d.cliente_id, alteracoes={"documento_id": str(d.id)})
    ctx.db.commit()
    # sempre como anexo: o navegador não executa nem exibe o conteúdo enviado por terceiros
    return FileResponse(caminho, media_type=d.tipo_mime, filename=d.nome_original,
                        headers={"Content-Security-Policy": "sandbox", "X-Content-Type-Options": "nosniff"})


class ConferirDocumento(BaseModel):
    aceitar: bool
    motivo: str | None = Field(default=None, max_length=2000)


@rotas.post("/documentos-recebidos/{did}/conferir")
def conferir_documento(did: uuid.UUID, dados: ConferirDocumento, ctx: Contexto = Depends(exigir("atendimentos:gerenciar"))):
    d = _doc(ctx, did)
    try:
        svc.conferir_documento(ctx.db, ctx.ator, d, ctx.usuario, dados.aceitar, dados.motivo)
    except svc.ErroAtendimento as e:
        _erro(e)
    ctx.db.commit()
    return svc.documento_json(d)


@rotas.get("/formularios")
def formularios(ctx: Contexto = Depends(exigir("atendimentos:ler"))):
    esc = ctx.usuario.escritorio_id
    deps = ctx.db.execute(select(Departamento).where(Departamento.escritorio_id == esc, Departamento.ativo.is_(True))
                          .order_by(Departamento.ordem)).scalars().all()
    return [{"departamento_id": str(d.id), "departamento": d.nome, **svc.formulario(ctx.db, esc, d.codigo)} for d in deps]


# ================================================================ conversas (WhatsApp e simulador)

def _conv(ctx: Contexto, cid: uuid.UUID) -> Conversa:
    c = ctx.db.get(Conversa, cid)
    if c is None or c.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Conversa não encontrada")
    return c


@rotas.get("/conversas")
def listar_conversas(estado: Literal["recepcionista", "humano", "encerrada"] | None = None,
                     ctx: Contexto = Depends(exigir("conversas:ler"))):
    from app.servicos.conectores import whatsapp
    esc = ctx.usuario.escritorio_id
    return {"itens": conversas.listar(ctx.db, esc, estado), "simulador": conversas.simulador_disponivel(),
            "whatsapp_configurado": whatsapp.configurado(), "aguardando_equipe": conversas.nao_lidas(ctx.db, esc)}


@rotas.get("/conversas/{cid}")
def ver_conversa(cid: uuid.UUID, ctx: Contexto = Depends(exigir("conversas:ler"))):
    c = _conv(ctx, cid)
    msgs = ctx.db.execute(select(Mensagem).where(Mensagem.conversa_id == c.id).order_by(Mensagem.criado_em)).scalars().all()
    c.nao_lidas = 0
    ctx.db.commit()
    nomes = _nomes(ctx)
    return {**conversas.conversa_json(c), "mensagens": [conversas.mensagem_json(m, nomes) for m in msgs]}


class Responder(BaseModel):
    texto: str = Field(min_length=1, max_length=4000)


@rotas.post("/conversas/{cid}/mensagens", status_code=201)
def responder(cid: uuid.UUID, dados: Responder, ctx: Contexto = Depends(exigir("conversas:responder"))):
    c = _conv(ctx, cid)
    if c.estado != "humano":
        conversas.assumir(ctx.db, ctx.ator, c, ctx.usuario)  # quem responde assume a conversa
    try:
        m = conversas.enviar(ctx.db, c, dados.texto, autor="equipe", usuario=ctx.usuario)
    except conversas.ErroConversa as e:
        _erro(e)
    auditoria.registrar(ctx.db, ctx.ator, "conversa.responder", entidade="conversa", entidade_id=c.id,
                        alteracoes={"mensagem_id": str(m.id)})
    ctx.db.commit()
    return conversas.mensagem_json(m, _nomes(ctx))


@rotas.post("/conversas/{cid}/{acao}")
def acao_conversa(cid: uuid.UUID, acao: Literal["assumir", "devolver", "encerrar"],
                  ctx: Contexto = Depends(exigir("conversas:responder"))):
    c = _conv(ctx, cid)
    {"assumir": lambda: conversas.assumir(ctx.db, ctx.ator, c, ctx.usuario),
     "devolver": lambda: conversas.devolver(ctx.db, ctx.ator, c),
     "encerrar": lambda: conversas.encerrar(ctx.db, ctx.ator, c)}[acao]()
    ctx.db.commit()
    return conversas.conversa_json(c)


class MensagemSimulada(BaseModel):
    contato: str = Field(min_length=8, max_length=20, pattern=r"^\d+$")
    nome: str | None = Field(default=None, max_length=100)
    texto: str = Field(min_length=1, max_length=2000)


@rotas.post("/simulador/whatsapp", status_code=201)
def simular_whatsapp(dados: MensagemSimulada, ctx: Contexto = Depends(exigir("conversas:responder"))):
    """Simula a mensagem de um contato (dados fictícios). Só existe com EJMF_CONECTORES_SIMULADOS=true."""
    if not conversas.simulador_disponivel():
        raise HTTPException(404, "Simulador desligado")
    conv, entrada, respostas = conversas.receber(ctx.db, ctx.usuario.escritorio_id, "whatsapp_simulado",
                                                 contato_id=dados.contato, nome=dados.nome, texto=dados.texto,
                                                 id_externo=f"sim-{uuid.uuid4().hex}")
    ctx.db.commit()
    return {"conversa": conversas.conversa_json(conv), "respostas": [conversas.mensagem_json(m) for m in respostas]}


# ================================================================ portal (lado da equipe)

def _cliente(ctx: Contexto, cid: uuid.UUID) -> Cliente:
    c = ctx.db.get(Cliente, cid)
    if c is None or c.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Cliente não encontrado")
    return c


@rotas.get("/clientes/{cid}/portal")
def portal_do_cliente(cid: uuid.UUID, ctx: Contexto = Depends(exigir("clientes:ler"))):
    c = _cliente(ctx, cid)
    ac = ctx.db.execute(select(AcessoPortal).where(AcessoPortal.cliente_id == c.id)).scalar()
    sols = ctx.db.execute(select(SolicitacaoPortal).where(SolicitacaoPortal.cliente_id == c.id)
                          .order_by(SolicitacaoPortal.criado_em.desc()).limit(50)).scalars().all()
    ats = ctx.db.execute(select(Atendimento).where(Atendimento.cliente_id == c.id).order_by(Atendimento.criado_em.desc())).scalars().all()
    return {"acesso": portal.acesso_json(ac), "solicitacoes": [portal.solicitacao_json(s) for s in sols],
            "processos_visiveis": [{"id": str(p.id), "numero": p.numero_formatado} for p in portal.processos_visiveis(ctx.db, c)],
            "atendimentos": [svc.como_json(a) for a in ats],
            "documentos": [svc.documento_json(d) for d in ctx.db.execute(
                select(DocumentoRecebido).where(DocumentoRecebido.cliente_id == c.id, DocumentoRecebido.atendimento_id.is_(None))
                .order_by(DocumentoRecebido.criado_em.desc())).scalars()]}


class Convite(BaseModel):
    email: EmailStr | None = None


@rotas.post("/clientes/{cid}/portal/convite", status_code=201)
def convidar(cid: uuid.UUID, dados: Convite, ctx: Contexto = Depends(exigir("portal:gerenciar"))):
    c = _cliente(ctx, cid)
    try:
        ac, token = portal.convidar(ctx.db, ctx.ator, c, dados.email, ctx.usuario)
    except portal.ErroPortal as e:
        _erro(e)
    ctx.db.commit()
    return {**portal.acesso_json(ac), "url": portal.url_convite(token)}


@rotas.post("/clientes/{cid}/portal/revogar")
def revogar_portal(cid: uuid.UUID, ctx: Contexto = Depends(exigir("portal:gerenciar"))):
    c = _cliente(ctx, cid)
    ac = ctx.db.execute(select(AcessoPortal).where(AcessoPortal.cliente_id == c.id)).scalar()
    if ac is None:
        raise HTTPException(404, "O cliente não tem acesso ao portal")
    portal.revogar(ctx.db, ctx.ator, ac)
    ctx.db.commit()
    return portal.acesso_json(ac)


class Resposta(BaseModel):
    resposta: str = Field(min_length=2, max_length=5000)
    encerrar: bool = False


@rotas.post("/solicitacoes-portal/{sid}/responder")
def responder_solicitacao(sid: uuid.UUID, dados: Resposta, ctx: Contexto = Depends(exigir("atendimentos:gerenciar"))):
    s = ctx.db.get(SolicitacaoPortal, sid)
    if s is None or s.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Pedido não encontrado")
    try:
        portal.responder(ctx.db, ctx.ator, s, ctx.usuario, dados.resposta, dados.encerrar)
    except portal.ErroPortal as e:
        _erro(e)
    ctx.db.commit()
    return portal.solicitacao_json(s)


@rotas.get("/solicitacoes-portal")
def listar_solicitacoes(situacao: Literal["aberta", "respondida", "encerrada"] | None = "aberta",
                        ctx: Contexto = Depends(exigir("atendimentos:ler"))):
    q = select(SolicitacaoPortal, Cliente.nome).join(Cliente, Cliente.id == SolicitacaoPortal.cliente_id) \
        .where(SolicitacaoPortal.escritorio_id == ctx.usuario.escritorio_id)
    if situacao:
        q = q.where(SolicitacaoPortal.situacao == situacao)
    return [{**portal.solicitacao_json(s), "cliente_id": str(s.cliente_id), "cliente": nome}
            for s, nome in ctx.db.execute(q.order_by(SolicitacaoPortal.criado_em.desc()).limit(200)).all()]


class Visibilidade(BaseModel):
    visivel: bool


@rotas.post("/processos/{pid}/portal")
def visibilidade_portal(pid: uuid.UUID, dados: Visibilidade, ctx: Contexto = Depends(exigir("portal:gerenciar"))):
    p = ctx.db.get(Processo, pid)
    if p is None or p.escritorio_id != ctx.usuario.escritorio_id:
        raise HTTPException(404, "Processo não encontrado")
    p.portal_visivel = dados.visivel
    auditoria.registrar(ctx.db, ctx.ator, "processo.portal_visivel", entidade="processo", entidade_id=p.id,
                        alteracoes={"visivel": dados.visivel})
    ctx.db.commit()
    return {"id": str(p.id), "portal_visivel": p.portal_visivel}

