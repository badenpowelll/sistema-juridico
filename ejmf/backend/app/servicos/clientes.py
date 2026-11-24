"""Clientes PF/PJ. CPF/CNPJ fica cifrado; a busca exata e a deduplicação usam um HMAC do documento."""
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.seguranca import cifrar, decifrar, hash_token
from app.modelos import Cliente, Parte, Processo
from app.servicos import auditoria
from app.servicos.identificadores import (
    DocumentoInvalido, formatar_documento, mascarar_documento, normalizar_documento, normalizar_texto,
)


class ClienteDuplicado(ValueError):
    def __init__(self, existente: Cliente):
        super().__init__("Já existe cliente com este CPF/CNPJ")
        self.existente = existente


def hash_documento(doc: str) -> str:
    return hash_token("documento:" + doc)


def por_documento(db: Session, escritorio_id: uuid.UUID, documento: str) -> Cliente | None:
    norm = normalizar_documento(documento)
    if norm is None:
        return None
    return db.execute(select(Cliente).where(Cliente.escritorio_id == escritorio_id,
                                            Cliente.documento_hash == hash_documento(norm[1]))).scalar()


def por_nome(db: Session, escritorio_id: uuid.UUID, nome: str, limite: int = 5) -> list[Cliente]:
    return list(db.execute(select(Cliente).where(Cliente.escritorio_id == escritorio_id,
                                                 Cliente.nome_normalizado == normalizar_texto(nome))
                           .limit(limite)).scalars())


def criar(db: Session, ator: auditoria.Ator, escritorio_id: uuid.UUID, *, nome: str, tipo: str | None = None,
          documento: str | None = None, email: str | None = None, telefone: str | None = None,
          contatos: list | None = None, observacoes: str | None = None, origem: str = "manual",
          importacao_id: uuid.UUID | None = None, auditar: bool = True) -> Cliente:
    nome = " ".join((nome or "").split())
    if len(nome) < 2:
        raise ValueError("Nome do cliente é obrigatório")
    norm = normalizar_documento(documento, tipo)  # levanta DocumentoInvalido
    if norm:
        tipo = norm[0]
        existente = db.execute(select(Cliente).where(Cliente.escritorio_id == escritorio_id,
                                                     Cliente.documento_hash == hash_documento(norm[1]))).scalar()
        if existente:
            raise ClienteDuplicado(existente)
    if tipo not in ("PF", "PJ"):
        raise ValueError("Informe o tipo (PF ou PJ) ou um CPF/CNPJ válido")
    c = novo_objeto(escritorio_id, nome=nome, tipo=tipo, documento=norm[1] if norm else None, email=email,
                    telefone=telefone, contatos=contatos, observacoes=observacoes, origem=origem,
                    importacao_id=importacao_id)
    db.add(c)
    db.flush()
    if auditar:
        auditoria.registrar(db, ator, "cliente.criar", entidade="cliente", entidade_id=c.id, origem=origem,
                            alteracoes={"nome": nome, "tipo": tipo, "documento": norm[1] if norm else None})
    return c


def novo_objeto(escritorio_id: uuid.UUID, *, nome: str, tipo: str, documento: str | None = None,
                email: str | None = None, telefone: str | None = None, contatos: list | None = None,
                observacoes: str | None = None, origem: str = "manual", importacao_id: uuid.UUID | None = None) -> Cliente:
    """Monta o cliente (documento já validado e limpo) sem consultar o banco; o id é gerado aqui."""
    nome = " ".join((nome or "").split())
    return Cliente(
        id=uuid.uuid4(), escritorio_id=escritorio_id, tipo=tipo, nome=nome, nome_normalizado=normalizar_texto(nome),
        documento_cifrado=cifrar(documento) if documento else None,
        documento_hash=hash_documento(documento) if documento else None,
        documento_mascarado=mascarar_documento(tipo, documento) if documento else None,
        email=(email or None), telefone=(telefone or None), contatos=contatos or [],
        observacoes=observacoes or None, origem=origem, importacao_id=importacao_id,
    )


def documento_completo(c: Cliente) -> str | None:
    if not c.documento_cifrado:
        return None
    doc = decifrar(c.documento_cifrado)
    return formatar_documento(c.tipo, doc) if doc else None


def como_json(c: Cliente, *, processos: int | None = None) -> dict[str, Any]:
    return {
        "id": str(c.id), "tipo": c.tipo, "nome": c.nome, "documento": c.documento_mascarado,
        "email": c.email, "telefone": c.telefone, "contatos": c.contatos, "observacoes": c.observacoes,
        "origem": c.origem, "importacao_id": str(c.importacao_id) if c.importacao_id else None,
        "criado_em": c.criado_em, "atualizado_em": c.atualizado_em,
        **({"processos": processos} if processos is not None else {}),
    }


def processos_do_cliente(db: Session, cliente_id: uuid.UUID) -> list[Processo]:
    ids = select(Parte.processo_id).where(Parte.cliente_id == cliente_id)
    return list(db.execute(select(Processo).where(Processo.id.in_(ids)).order_by(Processo.atualizado_em.desc())).scalars())


def contar_processos(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not ids:
        return {}
    linhas = db.execute(select(Parte.cliente_id, func.count(func.distinct(Parte.processo_id)))
                        .where(Parte.cliente_id.in_(ids)).group_by(Parte.cliente_id)).all()
    return {cid: n for cid, n in linhas}


__all__ = ["ClienteDuplicado", "DocumentoInvalido", "criar", "por_documento", "por_nome", "como_json",
           "documento_completo", "hash_documento", "processos_do_cliente", "contar_processos"]
