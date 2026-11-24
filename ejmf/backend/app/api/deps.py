"""Dependências das rotas: sessão do banco, usuário autenticado, permissões e ator de auditoria."""
import ipaddress
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.banco import obter_sessao
from app.core.config import obter_config
from app.core.logs import trace_id_atual
from app.modelos import Sessao, Usuario
from app.servicos import auditoria
from app.servicos.autenticacao import eh_admin, permissoes_do_usuario, sessao_pelo_token


def ip_do_cliente(request: Request) -> str | None:
    """IP da conexão (o proxy reverso deve repassar o IP real; ver DEPLOYMENT.md). Valores inválidos viram None."""
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


@dataclass
class Contexto:
    db: Session
    usuario: Usuario
    sessao: Sessao
    permissoes: set[str]
    ator: auditoria.Ator


def _contexto(request: Request, db: Session, permitir_mfa_pendente: bool) -> Contexto:
    cfg = obter_config()
    achado = sessao_pelo_token(db, request.cookies.get(cfg.nome_cookie))
    if achado is None:
        raise HTTPException(401, "Sessão ausente ou expirada")
    s, u = achado
    if s.mfa_pendente and not permitir_mfa_pendente:
        raise HTTPException(401, "Verificação em duas etapas pendente")
    ator = auditoria.Ator("usuario", str(u.id), u.nome, u.escritorio_id, ip_do_cliente(request), trace_id_atual.get())
    return Contexto(db, u, s, permissoes_do_usuario(u), ator)


def contexto(request: Request, db: Session = Depends(obter_sessao)) -> Contexto:
    ctx = _contexto(request, db, permitir_mfa_pendente=False)
    cfg = obter_config()
    caminho = request.url.path
    if cfg.mfa_exigido_admin and eh_admin(ctx.usuario) and not ctx.usuario.mfa_ativo \
            and not caminho.startswith("/api/v1/auth/"):
        raise HTTPException(403, "Configure a verificação em duas etapas para continuar")
    return ctx


def contexto_mfa_pendente(request: Request, db: Session = Depends(obter_sessao)) -> Contexto:
    return _contexto(request, db, permitir_mfa_pendente=True)


def exigir(*codigos: str):
    def _dep(ctx: Contexto = Depends(contexto)) -> Contexto:
        faltando = [c for c in codigos if c not in ctx.permissoes]
        if faltando:
            auditoria.registrar(ctx.db, ctx.ator, "acesso.negado", entidade="permissao",
                                entidade_id=",".join(faltando), resultado="negado")
            ctx.db.commit()
            raise HTTPException(403, "Permissão insuficiente")
        return ctx
    return _dep
