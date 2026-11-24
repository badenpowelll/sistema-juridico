"""Auditoria encadeada (ADR-0005). Grava na mesma transação da operação auditada."""
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modelos import Auditoria

HASH_INICIAL = "0" * 64
_CHAVES_SECRETAS = ("senha", "token", "segredo", "secret", "password", "chave", "api_key", "apikey")
_CHAVES_PARCIAIS = ("cpf", "cnpj", "rg", "documento")
_LOCK_AUDITORIA = 74201  # pg_advisory_xact_lock: serializa a cadeia


@dataclass
class Ator:
    tipo: str = "sistema"  # usuario | agente | sistema | anonimo
    id: str | None = None
    nome: str | None = None
    escritorio_id: uuid.UUID | None = None
    ip: str | None = None
    trace_id: str | None = None


def mascarar(valor: Any, chave: str = "") -> Any:
    c = chave.lower()
    if isinstance(valor, dict):
        return {k: mascarar(v, k) for k, v in valor.items()}
    if isinstance(valor, list):
        return [mascarar(v, chave) for v in valor]
    if valor is None or valor == "":
        return valor
    if any(s in c for s in _CHAVES_SECRETAS):
        return "***"
    if any(c == s or c.endswith("_" + s) for s in _CHAVES_PARCIAIS):
        dig = "".join(ch for ch in str(valor) if ch.isdigit())
        return ("*" * max(len(dig) - 2, 0)) + dig[-2:] if dig else "***"
    return valor


def _canonico(dados: dict[str, Any]) -> str:
    return json.dumps(dados, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _conteudo(r: Auditoria) -> dict[str, Any]:
    return {
        "escritorio_id": str(r.escritorio_id) if r.escritorio_id else None,
        "ocorrido_em": r.ocorrido_em.astimezone(timezone.utc).isoformat(),
        "ator_tipo": r.ator_tipo, "ator_id": r.ator_id, "ator_nome": r.ator_nome,
        "operacao": r.operacao, "entidade": r.entidade, "entidade_id": r.entidade_id,
        "origem": r.origem, "alteracoes": r.alteracoes, "aprovacao_id": r.aprovacao_id,
        "resultado": r.resultado, "erro": r.erro, "trace_id": r.trace_id,
        "ip": str(r.ip) if r.ip else None,
    }


def calcular_hash(hash_anterior: str, r: Auditoria) -> str:
    return hashlib.sha256((hash_anterior + _canonico(_conteudo(r))).encode()).hexdigest()


def registrar(
    sessao: Session, ator: Ator, operacao: str, *, entidade: str | None = None,
    entidade_id: Any = None, alteracoes: Any = None, resultado: str = "sucesso",
    erro: str | None = None, origem: str | None = "api", aprovacao_id: str | None = None,
) -> Auditoria:
    sessao.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _LOCK_AUDITORIA})
    anterior = sessao.execute(select(Auditoria.hash).order_by(Auditoria.id.desc()).limit(1)).scalar()
    r = Auditoria(
        escritorio_id=ator.escritorio_id, ocorrido_em=datetime.now(timezone.utc),
        ator_tipo=ator.tipo, ator_id=ator.id, ator_nome=ator.nome, operacao=operacao,
        entidade=entidade, entidade_id=str(entidade_id) if entidade_id is not None else None,
        origem=origem, alteracoes=mascarar(alteracoes) if alteracoes is not None else None,
        aprovacao_id=aprovacao_id, resultado=resultado, erro=erro, trace_id=ator.trace_id, ip=ator.ip,
        hash_anterior=anterior or HASH_INICIAL,
    )
    # normaliza o JSON como o banco devolverá, para o hash ser reprodutível
    r.alteracoes = json.loads(_canonico({"v": r.alteracoes}))["v"]
    r.hash = calcular_hash(r.hash_anterior, r)
    sessao.add(r)
    sessao.flush()
    return r


def verificar_cadeia(sessao: Session, lote: int = 5000) -> dict[str, Any]:
    anterior = HASH_INICIAL
    total = 0
    ultimo_id = 0
    while True:
        linhas = sessao.execute(
            select(Auditoria).where(Auditoria.id > ultimo_id).order_by(Auditoria.id).limit(lote)
        ).scalars().all()
        if not linhas:
            break
        for r in linhas:
            if r.hash_anterior != anterior or calcular_hash(anterior, r) != r.hash:
                return {"integra": False, "registros_verificados": total, "primeiro_registro_invalido": r.id}
            anterior = r.hash
            total += 1
            ultimo_id = r.id
        sessao.expunge_all()
    return {"integra": True, "registros_verificados": total, "ultimo_hash": anterior}
