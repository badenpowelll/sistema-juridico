import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import Contexto, contexto, contexto_mfa_pendente, ip_do_cliente
from app.core import seguranca
from app.core.banco import obter_sessao
from app.core.config import obter_config
from app.core.logs import trace_id_atual
from app.modelos import Sessao
from app.servicos import auditoria, push
from app.servicos.autenticacao import (
    ErroAutenticacao, agora, confirmar_mfa, eh_admin, login, revogar_sessoes,
)

rotas = APIRouter(prefix="/auth", tags=["autenticação"])


class EntradaLogin(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1, max_length=200)


class EntradaCodigo(BaseModel):
    codigo: str = Field(min_length=6, max_length=8)


class EntradaSenha(BaseModel):
    senha_atual: str
    senha_nova: str = Field(min_length=seguranca.SENHA_MINIMA, max_length=200)


def _definir_cookie(resp: Response, token: str) -> None:
    cfg = obter_config()
    resp.set_cookie(cfg.nome_cookie, token, httponly=True, secure=cfg.cookie_seguro, samesite="lax",
                    max_age=cfg.sessao_absoluta_horas * 3600, path="/")


def _eu(ctx: Contexto) -> dict:
    u = ctx.usuario
    cfg = obter_config()
    return {
        "id": str(u.id), "nome": u.nome, "email": u.email,
        "perfis": [p.codigo for p in u.perfis], "permissoes": sorted(ctx.permissoes),
        "mfa_ativo": u.mfa_ativo, "mfa_pendente": ctx.sessao.mfa_pendente,
        "mfa_obrigatorio": cfg.mfa_obrigatorio_admin and eh_admin(u),
    }


@rotas.post("/login")
def entrar(dados: EntradaLogin, request: Request, response: Response, db: Session = Depends(obter_sessao)):
    try:
        r = login(db, dados.email, dados.senha, ip_do_cliente(request), request.headers.get("user-agent"),
                  trace_id_atual.get())
    except ErroAutenticacao as e:
        raise HTTPException(e.status, e.mensagem)
    _definir_cookie(response, r.token)
    return {"mfa_necessario": r.mfa_necessario, "nome": r.usuario.nome}


@rotas.post("/mfa/verificar")
def verificar_mfa(dados: EntradaCodigo, ctx: Contexto = Depends(contexto_mfa_pendente)):
    try:
        confirmar_mfa(ctx.db, ctx.sessao, ctx.usuario, dados.codigo, ctx.ator)
    except ErroAutenticacao as e:
        raise HTTPException(e.status, e.mensagem)
    return {"ok": True}


@rotas.get("/eu")
def eu(ctx: Contexto = Depends(contexto_mfa_pendente)):
    return _eu(ctx)


@rotas.post("/sair")
def sair(response: Response, ctx: Contexto = Depends(contexto_mfa_pendente)):
    ctx.sessao.revogada_em = agora()
    push.revogar_das_sessoes(ctx.db, Sessao.id == ctx.sessao.id)
    auditoria.registrar(ctx.db, ctx.ator, "auth.sair", entidade="sessao", entidade_id=ctx.sessao.id)
    ctx.db.commit()
    response.delete_cookie(obter_config().nome_cookie, path="/")
    return {"ok": True}


@rotas.post("/mfa/configurar")
def configurar_mfa(ctx: Contexto = Depends(contexto)):
    if ctx.usuario.mfa_ativo:
        raise HTTPException(409, "A verificação em duas etapas já está ativa")
    segredo = seguranca.novo_segredo_totp()
    ctx.usuario.mfa_segredo_cifrado = seguranca.cifrar(segredo)
    auditoria.registrar(ctx.db, ctx.ator, "auth.mfa_configurar", entidade="usuario", entidade_id=ctx.usuario.id)
    ctx.db.commit()
    return {"segredo": segredo, "uri": seguranca.uri_totp(segredo, ctx.usuario.email)}


@rotas.post("/mfa/ativar")
def ativar_mfa(dados: EntradaCodigo, ctx: Contexto = Depends(contexto)):
    segredo = seguranca.decifrar(ctx.usuario.mfa_segredo_cifrado or "")
    if not segredo:
        raise HTTPException(400, "Configure a verificação em duas etapas primeiro")
    if not seguranca.verificar_totp(segredo, dados.codigo):
        raise HTTPException(400, "Código inválido")
    ctx.usuario.mfa_ativo = True
    revogar_sessoes(ctx.db, ctx.usuario.id, exceto=ctx.sessao.id)
    auditoria.registrar(ctx.db, ctx.ator, "auth.mfa_ativar", entidade="usuario", entidade_id=ctx.usuario.id)
    ctx.db.commit()
    return {"ok": True}


@rotas.post("/senha")
def trocar_senha(dados: EntradaSenha, ctx: Contexto = Depends(contexto)):
    if not seguranca.verificar_senha(ctx.usuario.senha_hash, dados.senha_atual):
        raise HTTPException(400, "Senha atual incorreta")
    ctx.usuario.senha_hash = seguranca.gerar_hash_senha(dados.senha_nova)
    n = revogar_sessoes(ctx.db, ctx.usuario.id, exceto=ctx.sessao.id)
    auditoria.registrar(ctx.db, ctx.ator, "auth.trocar_senha", entidade="usuario", entidade_id=ctx.usuario.id,
                        alteracoes={"sessoes_revogadas": n})
    ctx.db.commit()
    return {"ok": True, "sessoes_revogadas": n}


@rotas.get("/sessoes")
def minhas_sessoes(ctx: Contexto = Depends(contexto)):
    linhas = ctx.db.execute(
        select(Sessao).where(Sessao.usuario_id == ctx.usuario.id, Sessao.revogada_em.is_(None),
                             Sessao.expira_em > agora()).order_by(Sessao.ultimo_uso_em.desc())
    ).scalars().all()
    return [{"id": str(s.id), "criado_em": s.criado_em, "ultimo_uso_em": s.ultimo_uso_em,
             "ip": str(s.ip) if s.ip else None, "agente": s.agente, "atual": s.id == ctx.sessao.id} for s in linhas]


@rotas.delete("/sessoes/{sessao_id}")
def revogar(sessao_id: uuid.UUID, ctx: Contexto = Depends(contexto)):
    s = ctx.db.get(Sessao, sessao_id)
    if s is None or s.usuario_id != ctx.usuario.id:
        raise HTTPException(404, "Sessão não encontrada")
    s.revogada_em = agora()
    push.revogar_das_sessoes(ctx.db, Sessao.id == s.id)
    auditoria.registrar(ctx.db, ctx.ator, "auth.revogar_sessao", entidade="sessao", entidade_id=s.id)
    ctx.db.commit()
    return {"ok": True}


@rotas.post("/sessoes/revogar-outras")
def revogar_outras(ctx: Contexto = Depends(contexto)):
    n = revogar_sessoes(ctx.db, ctx.usuario.id, exceto=ctx.sessao.id)
    auditoria.registrar(ctx.db, ctx.ator, "auth.revogar_outras", entidade="usuario", entidade_id=ctx.usuario.id,
                        alteracoes={"sessoes_revogadas": n})
    ctx.db.commit()
    return {"sessoes_revogadas": n}
