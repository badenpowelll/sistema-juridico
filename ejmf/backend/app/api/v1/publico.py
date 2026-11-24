"""Rotas sem sessão da equipe: link de cadastro (token), portal do cliente (sessão própria) e webhook do WhatsApp.

Cada grupo tem a própria forma de autenticação e nenhum deles aceita a sessão da equipe nem dá acesso ao painel.
"""
import json
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import ip_do_cliente
from app.core.banco import obter_sessao
from app.core.config import obter_config
from app.modelos import Atendimento
from app.servicos import atendimentos as svc, conversas, portal
from app.servicos.autenticacao import LimitadorTaxa
from app.servicos.conectores import whatsapp
from app.servicos.semente import obter_escritorio

rotas = APIRouter(tags=["público"])
COOKIE_PORTAL = "ejmf_portal"
limitador_publico = LimitadorTaxa()


def _limitar(request: Request, grupo: str, limite: int = 60) -> str | None:
    ip = ip_do_cliente(request)
    if not limitador_publico.permitir(f"{grupo}:{ip}", limite):
        raise HTTPException(429, "Muitas requisições. Aguarde um minuto.")
    return ip


def _erro(e: Exception):
    raise HTTPException(getattr(e, "status", 400), str(e))


# ================================================================ link de cadastro

def _estado_link(db: Session, link) -> dict:
    at = db.get(Atendimento, link.atendimento_id)
    cad = svc.cadastro_de(db, at)
    cont = svc.conteudo(cad)
    docs = svc.documentos_de(db, at)
    nome_esc = obter_escritorio(db).nome
    return {
        "escritorio": nome_esc, "protocolo": at.protocolo, "finalidade": link.finalidade, "expira_em": link.expira_em,
        "formulario": link.formulario, "dados": cont["dados"], "relato": cont["relato"], "cronologia": cont["cronologia"],
        "entrevista": cont["entrevista"], "passo": cad.passo if cad else 0,
        "confirmado_em": cad.confirmado_em if cad else None,
        "pendencias": svc.pendencias_cadastro(link, cont, docs),
        "documentos": [{"id": str(d.id), "nome": d.nome_original, "previsto": d.documento_previsto, "situacao": d.situacao,
                        "motivo": d.motivo, "enviado_em": d.criado_em} for d in docs],
        "aviso": ("Este link é pessoal. Seus dados ficam protegidos e só a equipe do escritório tem acesso. "
                  "Preencher este cadastro não cria vínculo de contratação; o advogado analisa e retorna."),
    }


@rotas.get("/publico/cadastro/{token}")
def abrir_cadastro(token: str, request: Request, db: Session = Depends(obter_sessao)):
    ip = _limitar(request, "cadastro")
    try:
        link = svc.link_pelo_token(db, token)
    except svc.ErroAtendimento as e:
        _erro(e)
    svc.registrar_uso(db, link, ip, "abrir")
    estado = _estado_link(db, link)
    db.commit()
    return estado


class SalvarCadastro(BaseModel):
    dados: dict[str, str | int | float | None] = Field(default_factory=dict, max_length=80)
    relato: str | None = Field(default=None, max_length=20000)
    cronologia: list[dict] | None = Field(default=None, max_length=60)
    entrevista: dict[str, str] | None = Field(default=None, max_length=40)
    passo: int | None = Field(default=None, ge=0, le=20)


@rotas.put("/publico/cadastro/{token}")
def salvar_cadastro(token: str, corpo: SalvarCadastro, request: Request, db: Session = Depends(obter_sessao)):
    ip = _limitar(request, "cadastro")
    try:
        link = svc.link_pelo_token(db, token, para_escrita=True)
        _, erros = svc.salvar(db, link, corpo.dados, relato=corpo.relato, cronologia=corpo.cronologia,
                              entrevista=corpo.entrevista, passo=corpo.passo)
    except svc.ErroAtendimento as e:
        _erro(e)
    link.ultimo_uso_em, link.ultimo_ip = svc.agora(), ip
    estado = _estado_link(db, link)
    db.commit()
    return {**estado, "erros": erros}


@rotas.post("/publico/cadastro/{token}/confirmar")
def confirmar_cadastro(token: str, request: Request, db: Session = Depends(obter_sessao)):
    ip = _limitar(request, "cadastro")
    try:
        link = svc.link_pelo_token(db, token, para_escrita=True)
        svc.confirmar(db, link, ip)
    except svc.ErroAtendimento as e:
        db.rollback()
        _erro(e)
    estado = _estado_link(db, link)
    db.commit()
    return estado


@rotas.post("/publico/cadastro/{token}/documentos", status_code=201)
async def enviar_documento_link(token: str, request: Request, arquivo: UploadFile = File(...),
                                previsto: str | None = Form(None), db: Session = Depends(obter_sessao)):
    ip = _limitar(request, "cadastro-arquivo", 30)
    dados = await arquivo.read(100 * 1024 * 1024 + 1)
    try:
        link = svc.link_pelo_token(db, token, para_escrita=True)
        at = db.get(Atendimento, link.atendimento_id)
        doc, dup = svc.receber_arquivo(db, at, nome=arquivo.filename or "arquivo", dados=dados, origem="link",
                                       previsto=previsto, ip=ip)
    except svc.ErroAtendimento as e:
        db.rollback()
        _erro(e)
    svc.registrar_uso(db, link, ip, "enviar_documento")
    db.commit()
    return {"id": str(doc.id), "nome": doc.nome_original, "previsto": doc.documento_previsto, "duplicado": dup}


# ================================================================ portal do cliente

def sessao_cliente(request: Request, db: Session = Depends(obter_sessao)) -> portal.SessaoCliente:
    sc = portal.sessao_pelo_token(db, request.cookies.get(COOKIE_PORTAL), ip_do_cliente(request))
    if sc is None:
        raise HTTPException(401, "Entre no portal para continuar")
    return sc


class EntradaPortal(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1, max_length=200)


@rotas.post("/portal/entrar")
def entrar_portal(dados: EntradaPortal, request: Request, response: Response, db: Session = Depends(obter_sessao)):
    try:
        token = portal.entrar(db, dados.email, dados.senha, ip_do_cliente(request))
    except portal.ErroPortal as e:
        _erro(e)
    response.set_cookie(COOKIE_PORTAL, token, httponly=True, secure=obter_config().cookie_seguro, samesite="strict",
                        max_age=int(portal.ABSOLUTA.total_seconds()), path="/")
    return {"ok": True}


@rotas.post("/portal/sair")
def sair_portal(response: Response, sc: portal.SessaoCliente = Depends(sessao_cliente), db: Session = Depends(obter_sessao)):
    portal.sair(db, sc)
    response.delete_cookie(COOKIE_PORTAL, path="/")
    return {"ok": True}


class Ativacao(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    senha: str = Field(min_length=1, max_length=200)


@rotas.post("/portal/ativar")
def ativar_portal(dados: Ativacao, request: Request, db: Session = Depends(obter_sessao)):
    ip = _limitar(request, "portal-ativar", 20)
    try:
        ac = portal.ativar(db, dados.token, dados.senha, ip)
    except portal.ErroPortal as e:
        _erro(e)
    db.commit()
    return {"ok": True, "email": ac.email}


@rotas.get("/portal/eu")
def portal_inicio(sc: portal.SessaoCliente = Depends(sessao_cliente), db: Session = Depends(obter_sessao)):
    return portal.inicio(db, sc)


@rotas.get("/portal/processos/{pid}")
def portal_processo(pid: uuid.UUID, sc: portal.SessaoCliente = Depends(sessao_cliente), db: Session = Depends(obter_sessao)):
    try:
        p = portal.processo_visivel(db, sc.cliente, pid)
    except portal.ErroPortal as e:
        _erro(e)
    return {**portal._proc_json(db, p, completo=True), "ultima_sincronizacao": portal.ultima_sincronizacao(db, sc.cliente.escritorio_id)}


class NovaSolicitacao(BaseModel):
    tipo: Literal["mensagem", "atendimento", "atualizar_dados"]
    assunto: str = Field(min_length=3, max_length=300)
    texto: str = Field(min_length=3, max_length=5000)


@rotas.post("/portal/solicitacoes", status_code=201)
def portal_solicitar(dados: NovaSolicitacao, sc: portal.SessaoCliente = Depends(sessao_cliente),
                     db: Session = Depends(obter_sessao)):
    try:
        s = portal.solicitar(db, sc, dados.tipo, dados.assunto, dados.texto)
    except portal.ErroPortal as e:
        _erro(e)
    db.commit()
    return portal.solicitacao_json(s)


@rotas.post("/portal/documentos", status_code=201)
async def portal_documento(request: Request, arquivo: UploadFile = File(...), previsto: str | None = Form(None),
                           atendimento_id: uuid.UUID | None = Form(None),
                           sc: portal.SessaoCliente = Depends(sessao_cliente), db: Session = Depends(obter_sessao)):
    ip = _limitar(request, "portal-arquivo", 30)
    dados = await arquivo.read(100 * 1024 * 1024 + 1)
    try:
        at = portal.atendimento_para_documento(db, sc.cliente, atendimento_id)
        doc, dup = svc.receber_arquivo(db, at, nome=arquivo.filename or "arquivo", dados=dados, origem="portal",
                                       previsto=previsto, ip=ip, cliente_id=sc.cliente.id, ator=sc.ator)
    except (svc.ErroAtendimento, portal.ErroPortal) as e:
        db.rollback()
        _erro(e)
    db.commit()
    return {"id": str(doc.id), "nome": doc.nome_original, "duplicado": dup}


# ================================================================ webhook do WhatsApp (Meta)

@rotas.get("/publico/whatsapp/webhook", response_class=PlainTextResponse)
def verificar_webhook(modo: str | None = Query(None, alias="hub.mode"), token: str | None = Query(None, alias="hub.verify_token"),
                      desafio: str | None = Query(None, alias="hub.challenge")):
    resposta = whatsapp.verificar_inscricao(modo, token, desafio)
    if resposta is None:
        raise HTTPException(403, "Verificação recusada")
    return resposta


@rotas.post("/publico/whatsapp/webhook")
async def receber_webhook(request: Request, db: Session = Depends(obter_sessao)):
    corpo = await request.body()
    if len(corpo) > 1024 * 1024:
        raise HTTPException(413, "Corpo grande demais")
    if not whatsapp.configurado() or not whatsapp.verificar_assinatura(corpo, request.headers.get("x-hub-signature-256")):
        raise HTTPException(403, "Assinatura inválida")
    try:
        dados = json.loads(corpo)
    except ValueError:
        raise HTTPException(400, "JSON inválido")
    esc = obter_escritorio(db)
    conversas.webhook_recebido(db, esc.id)
    msgs, sts = whatsapp.interpretar_webhook(dados)
    for m in msgs:
        conversas.receber(db, esc.id, "whatsapp", contato_id=m.de, nome=m.nome, texto=m.texto, id_externo=m.id_externo,
                          tipo="texto" if m.tipo in ("text", "interactive", "button") else m.tipo, original=m.original)
    conversas.atualizar_status(db, esc.id, sts)
    db.commit()
    return {"ok": True}
