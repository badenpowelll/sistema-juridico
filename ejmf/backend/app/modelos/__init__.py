"""Modelos SQLAlchemy. Toda tabela de negócio tem escritorio_id (ADR-0006)."""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.banco import Base

ESTADOS_INTEGRACAO = (
    "implementada_validada", "ambiente_testes", "aguardando_credenciais",
    "aguardando_autorizacao", "indisponivel", "nao_implementada",
)


def _uuid() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))


def _criado() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Escritorio(Base):
    __tablename__ = "escritorios"
    id: Mapped[uuid.UUID] = _uuid()
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    sigla: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    criado_em: Mapped[datetime] = _criado()


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (UniqueConstraint("escritorio_id", "email"),)
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id", ondelete="RESTRICT"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    senha_hash: Mapped[str] = mapped_column(Text, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    mfa_segredo_cifrado: Mapped[str | None] = mapped_column(Text)
    mfa_ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    falhas_login: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    bloqueado_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_login_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = _criado()
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    perfis: Mapped[list["Perfil"]] = relationship(secondary="usuario_perfis", lazy="selectin")


class Perfil(Base):
    __tablename__ = "perfis"
    __table_args__ = (UniqueConstraint("escritorio_id", "codigo"),)
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    codigo: Mapped[str] = mapped_column(String(60), nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    permissoes: Mapped[list["Permissao"]] = relationship(secondary="perfil_permissoes", lazy="selectin")


class Permissao(Base):
    __tablename__ = "permissoes"
    id: Mapped[uuid.UUID] = _uuid()
    codigo: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)  # recurso:acao
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    nivel_autonomia: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    __table_args__ = (CheckConstraint("nivel_autonomia between 0 and 4"),)


class PerfilPermissao(Base):
    __tablename__ = "perfil_permissoes"
    perfil_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfis.id", ondelete="CASCADE"), primary_key=True)
    permissao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("permissoes.id", ondelete="CASCADE"), primary_key=True)


class UsuarioPerfil(Base):
    __tablename__ = "usuario_perfis"
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    perfil_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("perfis.id", ondelete="CASCADE"), primary_key=True)


class Sessao(Base):
    __tablename__ = "sessoes"
    id: Mapped[uuid.UUID] = _uuid()
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    mfa_pendente: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    criado_em: Mapped[datetime] = _criado()
    ultimo_uso_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revogada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(INET)
    agente: Mapped[str | None] = mapped_column(String(300))


class Departamento(Base):
    __tablename__ = "departamentos"
    __table_args__ = (UniqueConstraint("escritorio_id", "codigo"),)
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False, index=True)
    codigo: Mapped[str] = mapped_column(String(60), nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("100"))
    criado_em: Mapped[datetime] = _criado()


class Configuracao(Base):
    __tablename__ = "configuracoes"
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), primary_key=True)
    chave: Mapped[str] = mapped_column(String(120), primary_key=True)
    valor: Mapped[Any] = mapped_column(JSONB)
    sensivel: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Integracao(Base):
    __tablename__ = "integracoes"
    __table_args__ = (
        UniqueConstraint("escritorio_id", "codigo"),
        CheckConstraint("estado in ('" + "','".join(ESTADOS_INTEGRACAO) + "')", name="ck_integracoes_estado"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    codigo: Mapped[str] = mapped_column(String(60), nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    categoria: Mapped[str] = mapped_column(String(60), nullable=False)
    estado: Mapped[str] = mapped_column(String(40), nullable=False)
    simulado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    critica: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    observacao: Mapped[str | None] = mapped_column(Text)
    ultima_execucao_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_sucesso_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_erro: Mapped[str | None] = mapped_column(Text)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Auditoria(Base):
    __tablename__ = "auditoria"
    __table_args__ = (CheckConstraint("ator_tipo in ('usuario','agente','sistema','anonimo')"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    escritorio_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("escritorios.id"), index=True)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ator_tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    ator_id: Mapped[str | None] = mapped_column(String(80))
    ator_nome: Mapped[str | None] = mapped_column(String(200))
    operacao: Mapped[str] = mapped_column(String(80), nullable=False)
    entidade: Mapped[str | None] = mapped_column(String(80))
    entidade_id: Mapped[str | None] = mapped_column(String(80))
    origem: Mapped[str | None] = mapped_column(String(80))
    alteracoes: Mapped[Any] = mapped_column(JSONB)
    aprovacao_id: Mapped[str | None] = mapped_column(String(80))
    resultado: Mapped[str] = mapped_column(String(20), nullable=False)
    erro: Mapped[str | None] = mapped_column(Text)
    trace_id: Mapped[str | None] = mapped_column(String(64), index=True)
    ip: Mapped[str | None] = mapped_column(INET)
    hash_anterior: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
