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
    falhas_consecutivas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    circuito_aberto_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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
        Index("uq_movimentacoes_chave_externa", "processo_id", "chave_externa", unique=True,
              postgresql_where=text("chave_externa IS NOT NULL")),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    processo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("processos.id", ondelete="CASCADE"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    ocorrido_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    codigo_tpu: Mapped[int | None] = mapped_column(Integer)
    origem: Mapped[str] = mapped_column(String(40), nullable=False, server_default=text("'manual'"))
    chave_externa: Mapped[str | None] = mapped_column(String(120))  # deduplicação de fontes externas (DataJud)
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


# ============================================================ Fase 3 — controladoria

class DiaCalendario(Base):
    """Feriados, suspensões e possíveis suspensões. Abrangência: nacional | segmento:J | tribunal:J.TR | uf:XX."""
    __tablename__ = "calendario"
    __table_args__ = (
        CheckConstraint("tipo in ('feriado','suspensao','possivel_suspensao')"),
        UniqueConstraint("escritorio_id", "data", "abrangencia", "nome"),
        Index("ix_calendario_data", "escritorio_id", "data"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    abrangencia: Mapped[str] = mapped_column(String(30), nullable=False)
    fundamento: Mapped[str] = mapped_column(String(300), nullable=False)
    confirmado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    confirmado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    confirmado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    origem: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'semente'"))
    criado_em: Mapped[datetime] = _criado()


class RegraPrazo(Base):
    """Regra de contagem versionada. Só regra homologada permite homologar prazo."""
    __tablename__ = "regras_prazo"
    __table_args__ = (
        UniqueConstraint("escritorio_id", "codigo", "versao"),
        CheckConstraint("contagem in ('uteis','corridos')"),
        CheckConstraint("termo_inicial in ('disponibilizacao_djen','intimacao')"),
        CheckConstraint("situacao in ('nao_homologada','homologada','substituida')"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    codigo: Mapped[str] = mapped_column(String(60), nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    fundamento: Mapped[str] = mapped_column(Text, nullable=False)
    contagem: Mapped[str] = mapped_column(String(10), nullable=False)
    termo_inicial: Mapped[str] = mapped_column(String(30), nullable=False)
    suspensao_recesso: Mapped[bool] = mapped_column(Boolean, nullable=False)
    segmentos: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))  # sugestão automática
    observacao: Mapped[str | None] = mapped_column(Text)
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'nao_homologada'"))
    homologada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    homologada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = _criado()


SITUACOES_PUBLICACAO = ("nao_conferida", "conferida", "descartada", "duplicada")


class Publicacao(Base):
    """Publicação/intimação capturada. O original fica preservado; as quatro datas ficam separadas."""
    __tablename__ = "publicacoes"
    __table_args__ = (
        CheckConstraint("situacao in ('nao_conferida','conferida','descartada','duplicada')"),
        Index("uq_publicacoes_fonte_externo", "escritorio_id", "fonte", "id_externo", unique=True,
              postgresql_where=text("id_externo IS NOT NULL")),
        Index("ix_publicacoes_conteudo", "escritorio_id", "numero_processo", "disponibilizado_em", "texto_hash"),
        Index("ix_publicacoes_fila", "escritorio_id", "situacao", text("disponibilizado_em DESC")),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    fonte: Mapped[str] = mapped_column(String(40), nullable=False)  # djen | djen_simulado | manual | arquivo
    simulado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    id_externo: Mapped[str | None] = mapped_column(String(80))
    hash_certidao: Mapped[str | None] = mapped_column(String(80))
    tipo: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'publicacao'"))
    tipo_original: Mapped[str | None] = mapped_column(String(80))
    numero_processo: Mapped[str | None] = mapped_column(String(20), index=True)
    numero_formatado: Mapped[str | None] = mapped_column(String(25))
    processo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("processos.id", ondelete="SET NULL"), index=True)
    tribunal_sigla: Mapped[str | None] = mapped_column(String(20))
    orgao: Mapped[str | None] = mapped_column(String(300))
    classe: Mapped[str | None] = mapped_column(String(200))
    tipo_documento: Mapped[str | None] = mapped_column(String(120))
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    texto_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    destinatarios: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    advogados: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    link: Mapped[str | None] = mapped_column(Text)
    original: Mapped[Any] = mapped_column(JSONB, nullable=False)
    disponibilizado_em: Mapped[date | None] = mapped_column(Date)
    publicado_em: Mapped[date | None] = mapped_column(Date)  # calculada: 1º dia útil após a disponibilização
    ciencia_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # só por ato explícito
    ciencia_registrada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    capturado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    classificacao: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    pendencias: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'nao_conferida'"))
    duplicada_de_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("publicacoes.id", ondelete="SET NULL"))
    conferida_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    conferida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observacao: Mapped[str | None] = mapped_column(Text)
    execucao_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("execucoes_integracao.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = _criado()


class LeituraPublicacao(Base):
    """Histórico interno de leitura (quem abriu e quando). Não é ciência oficial."""
    __tablename__ = "publicacao_leituras"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    publicacao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("publicacoes.id", ondelete="CASCADE"), nullable=False, index=True)
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    lida_em: Mapped[datetime] = _criado()


SITUACOES_PRAZO = ("sugerido", "aguardando_conferencia", "homologado", "alterado", "concluido", "vencido",
                   "informacao_insuficiente")


class Prazo(Base):
    __tablename__ = "prazos"
    __table_args__ = (
        CheckConstraint("situacao in ('sugerido','aguardando_conferencia','homologado','alterado','concluido',"
                        "'vencido','informacao_insuficiente')"),
        Index("ix_prazos_agenda", "escritorio_id", "situacao", "vencimento"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    processo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("processos.id", ondelete="CASCADE"), nullable=False, index=True)
    publicacao_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("publicacoes.id", ondelete="SET NULL"), index=True)
    regra_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("regras_prazo.id"))
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    dias: Mapped[int | None] = mapped_column(Integer)
    dobro: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    dobro_motivo: Mapped[str | None] = mapped_column(String(300))
    data_base: Mapped[date | None] = mapped_column(Date)
    inicio_contagem: Mapped[date | None] = mapped_column(Date)
    vencimento: Mapped[date | None] = mapped_column(Date)
    vencimento_alternativo: Mapped[date | None] = mapped_column(Date)
    calculo: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    situacao: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'sugerido'"))
    origem: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'manual'"))
    simulado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    conferido_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    conferido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    homologado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    homologado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    concluido_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    conclusao: Mapped[str | None] = mapped_column(Text)
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    google_event_id: Mapped[str | None] = mapped_column(String(1024))  # evento do prazo homologado na agenda Google
    google_vencimento: Mapped[date | None] = mapped_column(Date)  # vencimento que está no Google
    criado_em: Mapped[datetime] = _criado()
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AlertaPrazo(Base):
    """Alerta gerado N dias antes do vencimento. Idempotente por (prazo, dias, vencimento)."""
    __tablename__ = "alertas_prazo"
    __table_args__ = (UniqueConstraint("prazo_id", "dias_antes", "vencimento"),)
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False, index=True)
    prazo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("prazos.id", ondelete="CASCADE"), nullable=False, index=True)
    dias_antes: Mapped[int] = mapped_column(Integer, nullable=False)
    vencimento: Mapped[date] = mapped_column(Date, nullable=False)
    confirmado_prazo: Mapped[bool] = mapped_column(Boolean, nullable=False)  # prazo estava homologado?
    canais: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[\"painel\"]'::jsonb"))
    gerado_em: Mapped[datetime] = _criado()
    ciente_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    ciente_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ExecucaoIntegracao(Base):
    """Cada sincronização com uma fonte externa (inclusive as que falharam ou foram puladas)."""
    __tablename__ = "execucoes_integracao"
    __table_args__ = (
        CheckConstraint("resultado in ('executando','sucesso','parcial','falha','ignorada')"),
        Index("ix_execucoes_integracao", "escritorio_id", "integracao", text("iniciada_em DESC")),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    integracao: Mapped[str] = mapped_column(String(60), nullable=False)
    simulado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    iniciada_em: Mapped[datetime] = _criado()
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resultado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'executando'"))
    parametros: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    itens_recebidos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    itens_novos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    itens_duplicados: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    erro: Mapped[str | None] = mapped_column(Text)
    tarefa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("tarefas.id", ondelete="SET NULL"))


ESTADOS_TAREFA = ("pendente", "executando", "concluida", "falhou", "cancelada")


class Tarefa(Base):
    """Fila de tarefas em segundo plano com idempotência (chave única), tentativas e espera exponencial."""
    __tablename__ = "tarefas"
    __table_args__ = (
        UniqueConstraint("escritorio_id", "chave"),
        CheckConstraint("estado in ('pendente','executando','concluida','falhou','cancelada')"),
        Index("ix_tarefas_fila", "estado", "agendada_para"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(60), nullable=False)
    chave: Mapped[str] = mapped_column(String(200), nullable=False)
    parametros: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pendente'"))
    tentativas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    max_tentativas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("5"))
    agendada_para: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    iniciada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    erro: Mapped[str | None] = mapped_column(Text)
    resultado: Mapped[Any | None] = mapped_column(JSONB)
    criada_por: Mapped[str | None] = mapped_column(String(120))
    criado_em: Mapped[datetime] = _criado()


# ================================================================ Fase 4 — agenda e secretaria

class Compromisso(Base):
    """Compromisso da agenda institucional. Eventos externos do Google entram como tipo 'externo' (só leitura)."""
    __tablename__ = "compromissos"
    __table_args__ = (
        CheckConstraint("tipo in ('audiencia','reuniao','atendimento','compromisso','lembrete','bloqueio',"
                        "'trabalho_concentrado','pessoal','externo')"),
        CheckConstraint("situacao in ('agendado','realizado','cancelado')"),
        CheckConstraint("fim >= inicio"),
        Index("ix_compromissos_periodo", "escritorio_id", "inicio", "fim"),
        Index("ix_compromissos_google", "escritorio_id", "google_event_id", unique=True,
              postgresql_where=text("google_event_id is not null")),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    titulo: Mapped[str] = mapped_column(String(300), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    local: Mapped[str | None] = mapped_column(String(300))
    link_virtual: Mapped[str | None] = mapped_column(String(500))
    modalidade: Mapped[str | None] = mapped_column(String(20))  # presencial | virtual | hibrida
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fim: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dia_inteiro: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    processo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("processos.id", ondelete="SET NULL"), index=True)
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clientes.id", ondelete="SET NULL"))
    responsavel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    participantes: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'agendado'"))
    resultado: Mapped[str | None] = mapped_column(Text)
    cancelado_motivo: Mapped[str | None] = mapped_column(Text)
    origem: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'manual'"))
    simulado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    sincronizar_google: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    sync_pendente: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    google_event_id: Mapped[str | None] = mapped_column(String(1024))
    google_etag: Mapped[str | None] = mapped_column(String(200))
    google_atualizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removido_no_google: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CredencialIntegracao(Base):
    """Tokens OAuth cifrados (Fernet) e estado de sincronização de uma integração. Nunca devolvidos pela API."""
    __tablename__ = "credenciais_integracao"
    __table_args__ = (UniqueConstraint("escritorio_id", "codigo"),)
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    codigo: Mapped[str] = mapped_column(String(50), nullable=False)
    dados_cifrados: Mapped[str | None] = mapped_column(Text)
    escopos: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    estado: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    conectada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    conectada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Pendencia(Base):
    """Item da central de prioridades. Os automáticos têm chave única e fecham quando a origem se resolve."""
    __tablename__ = "pendencias"
    __table_args__ = (
        CheckConstraint("situacao in ('aberta','aguardando_informacoes','aguardando_cliente','aguardando_terceiros',"
                        "'aguardando_aprovacao','automatizada','concluida','falha')"),
        Index("ix_pendencias_chave", "escritorio_id", "chave", unique=True, postgresql_where=text("chave is not null")),
        Index("ix_pendencias_fila", "escritorio_id", "situacao", "pontuacao"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    chave: Mapped[str | None] = mapped_column(String(200))
    origem: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'manual'"))  # sistema | manual
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    entidade: Mapped[str | None] = mapped_column(String(50))
    entidade_id: Mapped[str | None] = mapped_column(String(100))
    titulo: Mapped[str] = mapped_column(String(300), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(300))
    situacao: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'aberta'"))
    classe: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'normal'"))
    pontuacao: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    justificativa: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    critica: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    referencia_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # vencimento, início, captura…
    responsavel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    prazo_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    adiada_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observacao: Mapped[str | None] = mapped_column(Text)
    resolvida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolvida_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    resolucao: Mapped[str | None] = mapped_column(Text)
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Aprovacao(Base):
    """Pedido de aprovação humana (central única). Ações de agentes de IA também passarão por aqui (Fase 8)."""
    __tablename__ = "aprovacoes"
    __table_args__ = (
        CheckConstraint("situacao in ('pendente','aprovada','rejeitada','devolvida','cancelada')"),
        Index("ix_aprovacoes_pendentes", "escritorio_id", "situacao"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(50), nullable=False)
    entidade: Mapped[str | None] = mapped_column(String(50))
    entidade_id: Mapped[str | None] = mapped_column(String(100))
    titulo: Mapped[str] = mapped_column(String(300), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    dados: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    permissao: Mapped[str] = mapped_column(String(100), nullable=False)  # permissão exigida de quem decide
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pendente'"))
    solicitada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    solicitante_nome: Mapped[str | None] = mapped_column(String(200))
    solicitada_em: Mapped[datetime] = _criado()
    decidida_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    decidida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo: Mapped[str | None] = mapped_column(Text)


class Relatorio(Base):
    """Relatório diário (6h30) e de encerramento. Um por tipo e data (idempotente)."""
    __tablename__ = "relatorios"
    __table_args__ = (UniqueConstraint("escritorio_id", "tipo", "referencia"),
                      CheckConstraint("tipo in ('diario','encerramento')"))
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    referencia: Mapped[date] = mapped_column(Date, nullable=False)
    conteudo: Mapped[Any] = mapped_column(JSONB, nullable=False)
    entregas: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    gerado_em: Mapped[datetime] = _criado()


class Notificacao(Base):
    """Notificação no aplicativo, uma por usuário."""
    __tablename__ = "notificacoes"
    __table_args__ = (Index("ix_notificacoes_usuario", "usuario_id", "lida_em"),
                      Index("ix_notificacoes_chave", "usuario_id", "chave", unique=True, postgresql_where=text("chave is not null")))
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    chave: Mapped[str | None] = mapped_column(String(200))
    titulo: Mapped[str] = mapped_column(String(300), nullable=False)
    texto: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(300))
    nivel: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'info'"))
    criado_em: Mapped[datetime] = _criado()
    lida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
