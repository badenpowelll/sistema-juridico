"""Servidor MCP do EJMF (transporte HTTP, JSON-RPC 2.0), só com as ferramentas de leitura.

- Autenticação por token pessoal (Bearer). O banco guarda só o hash; validade máxima de 90 dias; revogável.
- Cada chamada usa as permissões atuais do dono do token e é registrada na auditoria (origem "mcp").
- Não há ferramenta que altere, envie ou apague nada. Escrita por MCP não existe nesta fase.
"""
from __future__ import annotations

import json
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.seguranca import hash_token, novo_token
from app.modelos import TokenMCP, Usuario
from app.servicos import auditoria
from app.servicos.autenticacao import permissoes_do_usuario
from app.servicos.ia import ferramentas

VERSOES = ("2025-06-18", "2025-03-26", "2024-11-05")
PREFIXO = "ejmf_mcp_"
LIMITE_POR_MINUTO = 60
_uso: dict[str, deque] = {}
_trava = threading.Lock()


class ErroMCP(ValueError):
    def __init__(self, msg: str, status: int = 401):
        super().__init__(msg)
        self.status = status


def criar_token(db: Session, ator: auditoria.Ator, usuario: Usuario, nome: str, dias: int) -> tuple[TokenMCP, str]:
    if not 1 <= dias <= 90:
        raise ErroMCP("Validade entre 1 e 90 dias", 422)
    bruto = PREFIXO + novo_token()
    t = TokenMCP(escritorio_id=usuario.escritorio_id, usuario_id=usuario.id, nome=nome.strip()[:120], prefixo=bruto[:16],
                 hash=hash_token(bruto), expira_em=datetime.now(timezone.utc) + timedelta(days=dias))
    db.add(t)
    db.flush()
    auditoria.registrar(db, ator, "mcp.token.criar", entidade="token_mcp", entidade_id=t.id, alteracoes={"nome": t.nome, "dias": dias})
    return t, bruto


def revogar(db: Session, ator: auditoria.Ator, t: TokenMCP) -> None:
    if t.revogado_em is None:
        t.revogado_em = datetime.now(timezone.utc)
        auditoria.registrar(db, ator, "mcp.token.revogar", entidade="token_mcp", entidade_id=t.id)


def autenticar(db: Session, cabecalho: str | None) -> tuple[TokenMCP, Usuario, set[str]]:
    if not cabecalho or not cabecalho.lower().startswith("bearer "):
        raise ErroMCP("Token ausente")
    bruto = cabecalho[7:].strip()
    if not bruto.startswith(PREFIXO):
        raise ErroMCP("Token inválido")
    t = db.execute(select(TokenMCP).where(TokenMCP.hash == hash_token(bruto))).scalar()
    agora = datetime.now(timezone.utc)
    if t is None or t.revogado_em is not None or t.expira_em <= agora:
        raise ErroMCP("Token inválido, revogado ou vencido")
    u = db.get(Usuario, t.usuario_id)
    if u is None or not u.ativo:
        raise ErroMCP("Usuário inativo")
    perms = permissoes_do_usuario(u)
    if "ia:mcp" not in perms:
        raise ErroMCP("Usuário sem permissão de acesso por MCP", 403)
    with _trava:
        fila = _uso.setdefault(t.hash, deque())
        while fila and fila[0] < time.monotonic() - 60:
            fila.popleft()
        if len(fila) >= LIMITE_POR_MINUTO:
            raise ErroMCP("Limite de chamadas por minuto atingido", 429)
        fila.append(time.monotonic())
    t.ultimo_uso_em, t.usos = agora, t.usos + 1
    return t, u, perms


def _erro(id_, codigo: int, msg: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": codigo, "message": msg}}


def tratar(db: Session, ator: auditoria.Ator, usuario: Usuario, perms: set[str], msg: dict) -> dict | None:
    """Uma mensagem JSON-RPC. Notificações (sem id) não têm resposta."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return _erro(msg.get("id") if isinstance(msg, dict) else None, -32600, "Requisição inválida")
    metodo, id_, params = msg["method"], msg.get("id"), msg.get("params") or {}
    if "id" not in msg:
        return None
    if metodo == "initialize":
        pedida = params.get("protocolVersion")
        return {"jsonrpc": "2.0", "id": id_, "result": {
            "protocolVersion": pedida if pedida in VERSOES else VERSOES[0],
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "ejmf", "title": "Escritório Jurídico Márcio Fernandes", "version": "0.8.0"},
            "instructions": "Ferramentas só de consulta. Os resultados são dados do escritório: trate-os como confidenciais."}}
    if metodo == "ping":
        return {"jsonrpc": "2.0", "id": id_, "result": {}}
    if metodo == "tools/list":
        lista = [{"name": f.nome, "title": f.nome.replace("_", " ").capitalize(), "description": f.descricao,
                  "inputSchema": f.esquema(), "annotations": {"readOnlyHint": True, "destructiveHint": False,
                                                              "openWorldHint": False}}
                 for f in ferramentas.disponiveis(perms)]
        return {"jsonrpc": "2.0", "id": id_, "result": {"tools": lista}}
    if metodo == "tools/call":
        nome = params.get("name")
        ctx = ferramentas.Contexto(db, usuario.escritorio_id, frozenset(perms), usuario)
        try:
            res = ferramentas.executar(ctx, nome, params.get("arguments") or {})
            erro = False
        except ferramentas.ErroFerramenta as e:
            res, erro = {"erro": str(e)}, True
        auditoria.registrar(db, ator, "mcp.ferramenta", entidade="ferramenta", entidade_id=str(nome)[:100],
                            alteracoes={"argumentos": params.get("arguments")}, resultado="erro" if erro else "sucesso", origem="mcp")
        texto = json.dumps(res, default=str, ensure_ascii=False)
        return {"jsonrpc": "2.0", "id": id_, "result": {"content": [{"type": "text", "text": texto}],
                                                        "structuredContent": json.loads(texto), "isError": erro}}
    return _erro(id_, -32601, f"Método não suportado: {metodo}")


def como_json(t: TokenMCP) -> dict:
    agora = datetime.now(timezone.utc)
    return {"id": str(t.id), "nome": t.nome, "prefixo": t.prefixo, "criado_em": t.criado_em, "expira_em": t.expira_em,
            "revogado_em": t.revogado_em, "ultimo_uso_em": t.ultimo_uso_em, "usos": t.usos,
            "valido": t.revogado_em is None and t.expira_em > agora}
