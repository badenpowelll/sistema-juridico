"""Modelos SQLAlchemy. Toda tabela de negócio tem escritorio_id (ADR-0006)."""
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Computed, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB, TSVECTOR, UUID
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
    __table_args__ = (
        CheckConstraint("ator_tipo in ('usuario','agente','sistema','anonimo')"),
        Index("ix_auditoria_entidade", "entidade", "entidade_id"),
        Index("ix_auditoria_ocorrido_em", "ocorrido_em"),
    )
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


# ====================================================================== Fase 2 — gestão processual
STATUS_PROCESSO = ("ativo", "suspenso", "arquivado", "encerrado")
POLOS = ("ativo", "passivo", "terceiro", "outro")


class Tribunal(Base):
    """Referência nacional (não depende do escritório): código J.TR do número único."""
    __tablename__ = "tribunais"
    codigo: Mapped[str] = mapped_column(String(5), primary_key=True)  # ex.: 8.20
    segmento: Mapped[str] = mapped_column(String(1), nullable=False)
    sigla: Mapped[str] = mapped_column(String(20), nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    uf: Mapped[str | None] = mapped_column(String(2))
    prioritario: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))


class Cliente(Base):
    __tablename__ = "clientes"
    __table_args__ = (
        CheckConstraint("tipo in ('PF','PJ')"),
        UniqueConstraint("escritorio_id", "documento_hash"),
        Index("ix_clientes_nome_trgm", "nome_normalizado", postgresql_using="gin", postgresql_ops={"nome_normalizado": "gin_trgm_ops"}),
        Index("ix_clientes_nome_norm", "escritorio_id", "nome_normalizado"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(2), nullable=False)
    nome: Mapped[str] = mapped_column(String(300), nullable=False)
    nome_normalizado: Mapped[str] = mapped_column(String(300), nullable=False)
    # CPF/CNPJ: cifrado (Fernet) + HMAC para busca exata e deduplicação; nunca em claro no banco
    documento_cifrado: Mapped[str | None] = mapped_column(Text)
    documento_hash: Mapped[str | None] = mapped_column(String(64))
    documento_mascarado: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(254))
    telefone: Mapped[str | None] = mapped_column(String(30))
    contatos: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    observacoes: Mapped[str | None] = mapped_column(Text)
    origem: Mapped[str] = mapped_column(String(40), nullable=False, server_default=text("'manual'"))
    importacao_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("importacoes.id", ondelete="SET NULL"), index=True)
    criado_em: Mapped[datetime] = _criado()
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Processo(Base):
    __tablename__ = "processos"
    __table_args__ = (
        UniqueConstraint("escritorio_id", "numero"),
        CheckConstraint("status in ('ativo','suspenso','arquivado','encerrado')"),
        CheckConstraint("numero ~ '^[0-9]{20}$'", name="ck_processos_numero_20_digitos"),
        Index("ix_processos_busca", "busca", postgresql_using="gin"),
        Index("ix_processos_texto_trgm", "texto_busca", postgresql_using="gin", postgresql_ops={"texto_busca": "gin_trgm_ops"}),
        Index("ix_processos_numero_trgm", "numero", postgresql_using="gin", postgresql_ops={"numero": "gin_trgm_ops"}),
        Index("ix_processos_listagem", "escritorio_id", text("atualizado_em DESC"), "id"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False, index=True)
    numero: Mapped[str] = mapped_column(String(20), nullable=False)  # só dígitos
    numero_formatado: Mapped[str] = mapped_column(String(25), nullable=False)
    tribunal_codigo: Mapped[str | None] = mapped_column(ForeignKey("tribunais.codigo"), index=True)
    departamento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departamentos.id"), index=True)
    classe: Mapped[str | None] = mapped_column(String(200))
    assuntos: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    unidade: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'ativo'"), index=True)
    valor_causa: Mapped[Any | None] = mapped_column(Numeric(16, 2))
    data_distribuicao: Mapped[date | None] = mapped_column(Date)
    observacoes: Mapped[str | None] = mapped_column(Text)
    origem: Mapped[str] = mapped_column(String(40), nullable=False, server_default=text("'manual'"))
    importacao_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("importacoes.id", ondelete="SET NULL"), index=True)
    texto_busca: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    busca: Mapped[Any] = mapped_column(TSVECTOR, Computed("to_tsvector('simple'::regconfig, texto_busca)", persisted=True))
    ultima_movimentacao_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = _criado()
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    partes: Mapped[list["Parte"]] = relationship(back_populates="processo", cascade="all, delete-orphan",
                                                 order_by="Parte.criado_em", lazy="selectin")


class Parte(Base):
    __tablename__ = "processo_partes"
    __table_args__ = (CheckConstraint("polo in ('ativo','passivo','terceiro','outro')"),)
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    processo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("processos.id", ondelete="CASCADE"), nullable=False, index=True)
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clientes.id", ondelete="SET NULL"), index=True)
    nome: Mapped[str] = mapped_column(String(300), nullable=False)
    polo: Mapped[str] = mapped_column(String(10), nullable=False)
    papel: Mapped[str | None] = mapped_column(String(80))  # autor, réu, reclamante, reclamada…
    representado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    importacao_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("importacoes.id", ondelete="SET NULL"), index=True)
    criado_em: Mapped[datetime] = _criado()

    processo: Mapped[Processo] = relationship(back_populates="partes")


class Movimentacao(Base):
    """Linha do tempo do processo. Movimentação ≠ intimação formal (as intimações chegam na Fase 3)."""
    __tablename__ = "movimentacoes"
    __table_args__ = (
        CheckConstraint("tipo in ('movimentacao','anotacao','sistema')"),
        Index("ix_movimentacoes_processo_data", "processo_id", text("ocorrido_em DESC")),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    processo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("processos.id", ondelete="CASCADE"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    codigo_tpu: Mapped[int | None] = mapped_column(Integer)
    origem: Mapped[str] = mapped_column(String(40), nullable=False, server_default=text("'manual'"))
    autor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    importacao_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("importacoes.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = _criado()


class Importacao(Base):
    __tablename__ = "importacoes"
    __table_args__ = (CheckConstraint(
        "status in ('analisado','validado','processando','concluido','revertido','cancelado')"),)
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'processos'"))
    arquivo_nome: Mapped[str] = mapped_column(String(255), nullable=False)
    arquivo_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    formato: Mapped[str] = mapped_column(String(10), nullable=False)
    colunas: Mapped[Any] = mapped_column(JSONB, nullable=False)
    mapeamento: Mapped[Any | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'analisado'"))
    totais: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revertido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


SITUACOES_LINHA = ("pendente", "valida", "invalida", "duplicada_arquivo", "existente", "conferencia",
                   "importada", "ignorada", "revertida")


class ImportacaoLinha(Base):
    __tablename__ = "importacao_linhas"
    __table_args__ = (
        UniqueConstraint("importacao_id", "linha"),
        CheckConstraint("situacao in ('pendente','valida','invalida','duplicada_arquivo','existente',"
                        "'conferencia','importada','ignorada','revertida')"),
        Index("ix_importacao_linhas_lote_situacao", "importacao_id", "situacao", "linha"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    importacao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("importacoes.id", ondelete="CASCADE"), nullable=False)
    linha: Mapped[int] = mapped_column(Integer, nullable=False)  # número da linha no arquivo
    original: Mapped[Any] = mapped_column(JSONB, nullable=False)
    normalizado: Mapped[Any | None] = mapped_column(JSONB)
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pendente'"), index=True)
    mensagens: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    candidatos: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    processo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("processos.id", ondelete="SET NULL"))
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clientes.id", ondelete="SET NULL"))
    resolvido_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    resolvido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
