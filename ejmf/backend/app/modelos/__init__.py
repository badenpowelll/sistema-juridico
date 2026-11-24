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
        CheckConstraint("ator_tipo in ('usuario','agente','sistema','anonimo','cliente')", name="auditoria_ator_tipo_check"),
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
    # Portal do cliente (Fase 5): só aparece para o cliente o que for expressamente liberado
    portal_visivel: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
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


# ============================================================== Fase 5 — atendimento e CRM

ETAPAS_ATENDIMENTO = (
    "primeiro_contato", "atendimento_iniciado", "cadastro_enviado", "cadastro_preenchido", "documentos_pendentes",
    "documentos_recebidos", "conferencia_profissional", "contrato_preparado", "assinatura_pendente",
    "atendimento_ativo", "processo_vinculado", "acompanhamento", "encerramento", "arquivamento",
)


class Atendimento(Base):
    """Funil de atendimento (14 etapas). O contato pode ainda não ser cliente cadastrado."""
    __tablename__ = "atendimentos"
    __table_args__ = (
        CheckConstraint("etapa in (" + ",".join(f"'{e}'" for e in ETAPAS_ATENDIMENTO) + ")"),
        UniqueConstraint("escritorio_id", "protocolo"),
        Index("ix_atendimentos_funil", "escritorio_id", "etapa", "atualizado_em"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    protocolo: Mapped[str] = mapped_column(String(20), nullable=False)
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clientes.id", ondelete="SET NULL"), index=True)
    processo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("processos.id", ondelete="SET NULL"), index=True)
    departamento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departamentos.id"))
    contato_nome: Mapped[str] = mapped_column(String(300), nullable=False)
    contato_telefone: Mapped[str | None] = mapped_column(String(30))
    contato_email: Mapped[str | None] = mapped_column(String(254))
    assunto: Mapped[str | None] = mapped_column(String(500))
    canal: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'manual'"))
    etapa: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'primeiro_contato'"))
    etapa_em: Mapped[datetime] = _criado()
    responsavel_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    observacoes: Mapped[str | None] = mapped_column(Text)  # internas: nunca vão ao cliente
    motivo_encerramento: Mapped[str | None] = mapped_column(Text)
    conferido_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    conferido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    simulado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class LinkCadastro(Base):
    """Link seguro de cadastro: token aleatório guardado só pelo hash, com validade, revogação e registro de uso."""
    __tablename__ = "links_cadastro"
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    atendimento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("atendimentos.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    finalidade: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'cadastro'"))  # cadastro | documentos
    formulario: Mapped[Any] = mapped_column(JSONB, nullable=False)  # cópia do formulário no momento do envio
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revogado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revogado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    concluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    usos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    primeiro_uso_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_uso_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_ip: Mapped[str | None] = mapped_column(INET)
    enviado_por_canal: Mapped[str | None] = mapped_column(String(20))
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()


class CadastroAtendimento(Base):
    """Respostas do cliente. Conteúdo (dados pessoais, relato, cronologia, entrevista) cifrado em repouso."""
    __tablename__ = "cadastros_atendimento"
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    atendimento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("atendimentos.id", ondelete="CASCADE"), nullable=False, unique=True)
    conteudo_cifrado: Mapped[str] = mapped_column(Text, nullable=False)
    campos_preenchidos: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    passo: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    relato_hash: Mapped[str | None] = mapped_column(String(64))  # prova de que o relato original não mudou
    confirmado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmado_ip: Mapped[str | None] = mapped_column(INET)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class DocumentoRecebido(Base):
    """Arquivo enviado pelo cliente (link, portal ou WhatsApp). O original fica intacto; a gestão completa é da Fase 6."""
    __tablename__ = "documentos_recebidos"
    __table_args__ = (
        CheckConstraint("situacao in ('recebido','aceito','recusado')"),
        Index("ix_documentos_recebidos_hash", "atendimento_id", "sha256"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    atendimento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("atendimentos.id", ondelete="SET NULL"), index=True)
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clientes.id", ondelete="SET NULL"), index=True)
    documento_previsto: Mapped[str | None] = mapped_column(String(60))
    nome_original: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo_mime: Mapped[str] = mapped_column(String(100), nullable=False)
    tamanho: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    caminho: Mapped[str] = mapped_column(String(300), nullable=False)
    origem: Mapped[str] = mapped_column(String(20), nullable=False)  # link | portal | whatsapp | painel
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'recebido'"))
    motivo: Mapped[str | None] = mapped_column(Text)
    conferido_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    conferido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    enviado_por_usuario: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    ip: Mapped[str | None] = mapped_column(INET)
    simulado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    criado_em: Mapped[datetime] = _criado()


class AcessoPortal(Base):
    """Login do cliente no portal: credencial própria, separada dos usuários da equipe."""
    __tablename__ = "acessos_portal"
    __table_args__ = (UniqueConstraint("escritorio_id", "email"), UniqueConstraint("cliente_id"))
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    cliente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    senha_hash: Mapped[str | None] = mapped_column(String(300))
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    convite_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    convite_expira_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ativado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    falhas_login: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    bloqueado_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_login_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()


class SessaoPortal(Base):
    __tablename__ = "sessoes_portal"
    id: Mapped[uuid.UUID] = _uuid()
    acesso_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("acessos_portal.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    criado_em: Mapped[datetime] = _criado()
    ultimo_uso_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revogada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str | None] = mapped_column(INET)


class SolicitacaoPortal(Base):
    """Pedido ou mensagem do cliente pelo portal; respondido pela equipe."""
    __tablename__ = "solicitacoes_portal"
    __table_args__ = (CheckConstraint("situacao in ('aberta','respondida','encerrada')"),)
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    cliente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)  # mensagem | atendimento | atualizar_dados
    assunto: Mapped[str] = mapped_column(String(300), nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'aberta'"))
    resposta: Mapped[str | None] = mapped_column(Text)
    respondida_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    respondida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = _criado()


class Conversa(Base):
    """Conversa em um canal (WhatsApp ou simulado). A recepcionista virtual responde enquanto estiver com ela."""
    __tablename__ = "conversas"
    __table_args__ = (UniqueConstraint("escritorio_id", "canal", "contato_id"),
                      CheckConstraint("estado in ('recepcionista','humano','encerrada')"))
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    canal: Mapped[str] = mapped_column(String(30), nullable=False)  # whatsapp | whatsapp_simulado
    contato_id: Mapped[str] = mapped_column(String(64), nullable=False)  # wa_id (número) no canal
    contato_nome: Mapped[str | None] = mapped_column(String(300))
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clientes.id", ondelete="SET NULL"))
    atendimento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("atendimentos.id", ondelete="SET NULL"))
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'recepcionista'"))
    contexto: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    ultima_entrada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # abre a janela de 24 h
    ultima_mensagem_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    nao_lidas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    simulado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    criado_em: Mapped[datetime] = _criado()


class Mensagem(Base):
    __tablename__ = "mensagens"
    __table_args__ = (
        CheckConstraint("direcao in ('entrada','saida')"),
        Index("ix_mensagens_conversa", "conversa_id", "criado_em"),
        Index("uq_mensagens_externo", "escritorio_id", "id_externo", unique=True, postgresql_where=text("id_externo is not null")),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    conversa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversas.id", ondelete="CASCADE"), nullable=False)
    direcao: Mapped[str] = mapped_column(String(10), nullable=False)
    autor: Mapped[str] = mapped_column(String(20), nullable=False)  # contato | recepcionista | equipe
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'texto'"))
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    intencao: Mapped[str | None] = mapped_column(String(40))
    id_externo: Mapped[str | None] = mapped_column(String(200))
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'recebida'"))
    erro: Mapped[str | None] = mapped_column(Text)
    original: Mapped[Any | None] = mapped_column(JSONB)
    criado_em: Mapped[datetime] = _criado()


# ============================================================ Fase 6 — documentos, modelos, minutas e assinaturas

CATEGORIAS_DOCUMENTO = (
    "identidade", "cpf", "comprovante_residencia", "procuracao", "contrato", "declaracao", "peticao", "decisao",
    "sentenca", "laudo", "contracheque", "ctps", "rescisao", "extrato", "recibo", "comprovante", "correspondencia",
    "foto", "audio", "planilha", "outro",
)


class Documento(Base):
    """Documento do acervo. O arquivo original (versão 1) nunca muda; texto extraído e novas versões são registros próprios."""
    __tablename__ = "documentos"
    __table_args__ = (
        CheckConstraint("situacao in ('ativo','arquivado','quarentena')"),
        CheckConstraint("origem in ('upload','recebido','gerado','assinado')"),
        Index("ix_documentos_hash", "escritorio_id", "sha256"),
        Index("ix_documentos_cliente", "cliente_id"),
        Index("ix_documentos_processo", "processo_id"),
        Index("ix_documentos_titulo_trgm", "titulo", postgresql_using="gin", postgresql_ops={"titulo": "gin_trgm_ops"}),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    titulo: Mapped[str] = mapped_column(String(300), nullable=False)
    categoria: Mapped[str] = mapped_column(String(40), nullable=False, server_default=text("'outro'"))
    categoria_por: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'regra'"))  # regra | pessoa
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clientes.id", ondelete="SET NULL"))
    processo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("processos.id", ondelete="SET NULL"))
    atendimento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("atendimentos.id", ondelete="SET NULL"))
    origem: Mapped[str] = mapped_column(String(20), nullable=False)
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'ativo'"))
    motivo_situacao: Mapped[str | None] = mapped_column(Text)
    sigiloso: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)  # do original
    versao_atual: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    documento_recebido_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documentos_recebidos.id", ondelete="SET NULL"))
    minuta_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class VersaoDocumento(Base):
    """Uma versão do documento: o original, o texto extraído (OCR), uma nova versão enviada ou o PDF gerado/assinado."""
    __tablename__ = "versoes_documento"
    __table_args__ = (
        UniqueConstraint("documento_id", "numero"),
        CheckConstraint("tipo in ('original','texto_extraido','nova_versao','pdf_gerado','assinado')"),
        CheckConstraint("extracao in ('pendente','concluida','ilegivel','sem_texto','nao_aplicavel','falha','indisponivel')"),
        Index("ix_versoes_documento_busca", "busca", postgresql_using="gin"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    documento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documentos.id", ondelete="CASCADE"), nullable=False)
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    derivada_de: Mapped[int | None] = mapped_column(Integer)  # número da versão de onde o texto saiu
    nome_arquivo: Mapped[str | None] = mapped_column(String(255))
    tipo_mime: Mapped[str | None] = mapped_column(String(100))
    tamanho: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    caminho: Mapped[str | None] = mapped_column(String(300))
    paginas: Mapped[int | None] = mapped_column(Integer)
    texto: Mapped[str | None] = mapped_column(Text)
    extracao: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'nao_aplicavel'"))
    metodo: Mapped[str | None] = mapped_column(String(20))  # texto_nativo | ocr | docx | planilha | texto
    confianca: Mapped[float | None] = mapped_column(Numeric(5, 2))
    erro: Mapped[str | None] = mapped_column(Text)
    busca: Mapped[Any] = mapped_column(TSVECTOR, Computed("to_tsvector('portuguese'::regconfig, coalesce(texto, ''))", persisted=True))
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()


class ModeloDocumento(Base):
    """Modelo parametrizado. Só modelos homologados geram minutas; editar um homologado cria nova versão em rascunho."""
    __tablename__ = "modelos_documento"
    __table_args__ = (
        UniqueConstraint("escritorio_id", "codigo", "versao"),
        CheckConstraint("situacao in ('rascunho','homologado','substituido','arquivado')"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    codigo: Mapped[str] = mapped_column(String(60), nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    categoria: Mapped[str] = mapped_column(String(40), nullable=False)
    departamento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departamentos.id", ondelete="SET NULL"))
    descricao: Mapped[str | None] = mapped_column(Text)
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)  # HTML restrito com {{campos}}
    cabecalho: Mapped[str | None] = mapped_column(String(500))
    rodape: Mapped[str | None] = mapped_column(String(500))
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'rascunho'"))
    sugerido_pelo_sistema: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    homologado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    homologado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ModeloFavorito(Base):
    __tablename__ = "modelos_favoritos"
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    codigo: Mapped[str] = mapped_column(String(60), primary_key=True)
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)


class Minuta(Base):
    """Documento em produção a partir de um modelo homologado. É sempre rascunho até a aprovação profissional."""
    __tablename__ = "minutas"
    __table_args__ = (CheckConstraint("situacao in ('rascunho','em_revisao','aprovada','arquivada')"),)
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    titulo: Mapped[str] = mapped_column(String(300), nullable=False)
    modelo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("modelos_documento.id", ondelete="SET NULL"))
    modelo_codigo: Mapped[str | None] = mapped_column(String(60))
    modelo_versao: Mapped[int | None] = mapped_column(Integer)
    categoria: Mapped[str] = mapped_column(String(40), nullable=False)
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clientes.id", ondelete="SET NULL"), index=True)
    processo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("processos.id", ondelete="SET NULL"), index=True)
    atendimento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("atendimentos.id", ondelete="SET NULL"), index=True)
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    cabecalho: Mapped[str | None] = mapped_column(String(500))
    rodape: Mapped[str | None] = mapped_column(String(500))
    campos: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # campo -> {valor, fonte}
    pendentes: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'rascunho'"))
    versao_atual: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    revisao_pedida_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    revisao_pedida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    aprovada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    aprovada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    documento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documentos.id", ondelete="SET NULL"))
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    atualizado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class VersaoMinuta(Base):
    __tablename__ = "versoes_minuta"
    __table_args__ = (UniqueConstraint("minuta_id", "numero"),)
    id: Mapped[uuid.UUID] = _uuid()
    minuta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("minutas.id", ondelete="CASCADE"), nullable=False)
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    conteudo: Mapped[str] = mapped_column(Text, nullable=False)
    motivo: Mapped[str] = mapped_column(String(20), nullable=False)  # criacao | automatica | manual | aprovacao | devolucao
    autor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()


class ComentarioMinuta(Base):
    __tablename__ = "comentarios_minuta"
    id: Mapped[uuid.UUID] = _uuid()
    minuta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("minutas.id", ondelete="CASCADE"), nullable=False, index=True)
    autor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    trecho: Mapped[str | None] = mapped_column(String(500))
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    resolvido_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    resolvido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = _criado()


class Assinatura(Base):
    """Pedido de assinatura eletrônica num provedor externo. O EJMF nunca simula nem faz a assinatura."""
    __tablename__ = "assinaturas"
    __table_args__ = (
        CheckConstraint("situacao in ('preparada','enviando','enviada','parcial','concluida','recusada','cancelada','falha')"),
        Index("uq_assinaturas_externo", "provedor", "id_externo", unique=True, postgresql_where=text("id_externo is not null")),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    minuta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("minutas.id", ondelete="CASCADE"), nullable=False, index=True)
    documento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documentos.id", ondelete="SET NULL"))
    provedor: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'documenso'"))
    id_externo: Mapped[str | None] = mapped_column(String(200))
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'preparada'"))
    participantes: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    eventos: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    mensagem: Mapped[str | None] = mapped_column(Text)
    preparada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    autorizada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    enviada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    erro: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = _criado()
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


# ====================================================================== Fase 7 — conhecimento

from pgvector.sqlalchemy import Vector  # noqa: E402

DIMENSAO_VETOR = 384
TIPOS_BIBLIOTECA = ("constituicao", "lei", "lei_complementar", "codigo", "decreto", "medida_provisoria", "regulamento",
                    "sumula", "sumula_vinculante", "tema", "orientacao_jurisprudencial", "doutrina", "interno")


class FonteConhecimento(Base):
    """Origem autorizada de normas e julgados. Só domínios desta lista são consultados pelos verificadores."""
    __tablename__ = "fontes_conhecimento"
    __table_args__ = (UniqueConstraint("escritorio_id", "codigo"),)
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    codigo: Mapped[str] = mapped_column(String(40), nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)  # legislacao | jurisprudencia | interna
    dominios: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    oficial: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    observacao: Mapped[str | None] = mapped_column(Text)


class ItemBiblioteca(Base):
    """Norma, súmula, doutrina licenciada ou material interno, com vigência, origem e versões."""
    __tablename__ = "itens_biblioteca"
    __table_args__ = (
        CheckConstraint("vigencia in ('vigente','revogado','parcialmente_revogado','a_conferir','nao_se_aplica')"),
        CheckConstraint("situacao in ('ativo','alteracao_a_conferir','arquivado')"),
        CheckConstraint("licenca in ('publico','licenciado','interno','referencia')"),
        Index("ix_biblioteca_titulo_trgm", "titulo", postgresql_using="gin", postgresql_ops={"titulo": "gin_trgm_ops"}),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(30), nullable=False)
    titulo: Mapped[str] = mapped_column(String(400), nullable=False)
    identificador: Mapped[str | None] = mapped_column(String(200))  # ex.: Lei 13.467/2017; urn:lex:...
    esfera: Mapped[str | None] = mapped_column(String(20))  # federal | estadual | municipal | interna
    orgao: Mapped[str | None] = mapped_column(String(200))
    ementa: Mapped[str | None] = mapped_column(Text)
    departamento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departamentos.id", ondelete="SET NULL"))
    fonte_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fontes_conhecimento.id", ondelete="SET NULL"))
    url_origem: Mapped[str | None] = mapped_column(String(1000))
    licenca: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'publico'"))
    vigencia: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'a_conferir'"))
    vigencia_desde: Mapped[date | None] = mapped_column(Date)
    vigencia_ate: Mapped[date | None] = mapped_column(Date)
    vigencia_conferida_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    vigencia_conferida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    situacao: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'ativo'"))
    monitorar: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    versao_atual: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    coletado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # última versão conferida
    verificado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # última checagem da fonte
    erro_verificacao: Mapped[str | None] = mapped_column(Text)
    assuntos: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class VersaoItemBiblioteca(Base):
    """Texto de um item num momento. Alteração detectada na fonte vira versão nova, a conferir; a anterior é preservada."""
    __tablename__ = "versoes_item_biblioteca"
    __table_args__ = (
        UniqueConstraint("item_id", "numero"),
        CheckConstraint("motivo in ('cadastro','alteracao_detectada','manual','importacao')"),
        CheckConstraint("situacao in ('a_conferir','conferida','descartada')"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("itens_biblioteca.id", ondelete="CASCADE"), nullable=False, index=True)
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    url_coleta: Mapped[str | None] = mapped_column(String(1000))
    coletado_em: Mapped[datetime] = _criado()
    motivo: Mapped[str] = mapped_column(String(30), nullable=False)
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'a_conferir'"))
    conferida_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    conferida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    autor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))


class Colecao(Base):
    __tablename__ = "colecoes_conhecimento"
    __table_args__ = (UniqueConstraint("escritorio_id", "nome"),)
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    departamento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departamentos.id", ondelete="SET NULL"))
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()


class ItemColecao(Base):
    __tablename__ = "itens_colecao"
    colecao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("colecoes_conhecimento.id", ondelete="CASCADE"), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(20), primary_key=True)  # biblioteca | jurisprudencia
    ref_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    adicionado_em: Mapped[datetime] = _criado()


class FavoritoConhecimento(Base):
    __tablename__ = "favoritos_conhecimento"
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(20), primary_key=True)
    ref_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    criado_em: Mapped[datetime] = _criado()


class Jurisprudencia(Base):
    """Julgado com o status de verificação contra o original. Sem verificação e homologação, não entra em documento final."""
    __tablename__ = "jurisprudencias"
    __table_args__ = (
        CheckConstraint("verificacao in ('pendente','verificada','nao_localizada','fonte_indisponivel','divergente')"),
        CheckConstraint("situacao in ('ativa','descartada')"),
        Index("uq_jurisprudencia_numero", "escritorio_id", "tribunal", "numero_normalizado", unique=True,
              postgresql_where=text("situacao = 'ativa'")),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    tribunal: Mapped[str] = mapped_column(String(20), nullable=False)  # sigla: STF, STJ, TST, TRT21…
    numero: Mapped[str] = mapped_column(String(120), nullable=False)
    numero_normalizado: Mapped[str] = mapped_column(String(120), nullable=False)
    classe: Mapped[str | None] = mapped_column(String(120))
    orgao_julgador: Mapped[str | None] = mapped_column(String(200))
    relator: Mapped[str | None] = mapped_column(String(200))
    data_julgamento: Mapped[date | None] = mapped_column(Date)
    data_publicacao: Mapped[date | None] = mapped_column(Date)
    ementa: Mapped[str] = mapped_column(Text, nullable=False)
    url_original: Mapped[str | None] = mapped_column(String(1000))
    fonte_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fontes_conhecimento.id", ondelete="SET NULL"))
    origem: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'manual'"))  # manual | importacao | sugestao_ia
    assuntos: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    verificacao: Mapped[str] = mapped_column(String(30), nullable=False, server_default=text("'pendente'"))
    verificacao_detalhe: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    verificada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consultado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # data da consulta ao original
    sha256_original: Mapped[str | None] = mapped_column(String(64))
    homologada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    homologada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'ativa'"))
    motivo_descarte: Mapped[str | None] = mapped_column(Text)
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class TrechoConhecimento(Base):
    """Pedaço indexado para busca textual e por similaridade. O escopo (cliente, processo, sigilo) é filtrado antes da busca."""
    __tablename__ = "trechos_conhecimento"
    __table_args__ = (
        CheckConstraint("origem in ('biblioteca','jurisprudencia','documento','memoria')"),
        Index("ix_trechos_origem", "origem", "ref_id"),
        Index("ix_trechos_escopo", "escritorio_id", "cliente_id", "processo_id"),
        Index("ix_trechos_vetor", "vetor", postgresql_using="hnsw", postgresql_ops={"vetor": "vector_cosine_ops"}),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    origem: Mapped[str] = mapped_column(String(20), nullable=False)
    ref_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    versao: Mapped[int | None] = mapped_column(Integer)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    processo_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    sigiloso: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    vetorizador: Mapped[str] = mapped_column(String(40), nullable=False)
    vetor: Mapped[Any] = mapped_column(Vector(DIMENSAO_VETOR), nullable=False)
    busca: Mapped[Any] = mapped_column(TSVECTOR, Computed("to_tsvector('portuguese'::regconfig, texto)", persisted=True))
    criado_em: Mapped[datetime] = _criado()


Index("ix_trechos_busca", TrechoConhecimento.busca, postgresql_using="gin")


class Memoria(Base):
    """Memória do escritório: decisões, orientações e preferências. Sugestão de IA só vale depois de confirmada por pessoa."""
    __tablename__ = "memorias"
    __table_args__ = (
        CheckConstraint("tipo in ('decisao','orientacao','preferencia','fato')"),
        CheckConstraint("origem in ('pessoa','documento','sugestao_ia')"),
        CheckConstraint("situacao in ('a_confirmar','confirmada','substituida','excluida')"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    titulo: Mapped[str] = mapped_column(String(300), nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"))
    processo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("processos.id", ondelete="CASCADE"))
    departamento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departamentos.id", ondelete="SET NULL"))
    origem: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pessoa'"))
    referencia: Mapped[str | None] = mapped_column(String(500))  # documento, ata, mensagem de onde veio
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'confirmada'"))
    confirmada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    confirmada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    substituida_por: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    motivo_exclusao: Mapped[str | None] = mapped_column(Text)
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


# ================================================================ Fase 8 — IA, funções virtuais e automações

class ModeloIA(Base):
    """Modelo de IA cadastrado pelo escritório. Preço e aprovação para dados confidenciais são decisões do advogado."""
    __tablename__ = "ia_modelos"
    __table_args__ = (
        UniqueConstraint("escritorio_id", "provedor", "modelo"),
        CheckConstraint("provedor in ('anthropic','openai_compativel','simulado')"),
        CheckConstraint("not aprovado_confidencial or retencao_conferida is not null", name="ck_ia_modelos_retencao"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    provedor: Mapped[str] = mapped_column(String(30), nullable=False)
    modelo: Mapped[str] = mapped_column(String(120), nullable=False)
    rotulo: Mapped[str] = mapped_column(String(200), nullable=False)
    preco_entrada_milhao: Mapped[Any | None] = mapped_column(Numeric(12, 4))  # USD por milhão de tokens
    preco_saida_milhao: Mapped[Any | None] = mapped_column(Numeric(12, 4))
    preco_conferido_em: Mapped[date | None] = mapped_column(Date)
    preco_fonte: Mapped[str | None] = mapped_column(String(500))
    aprovado_confidencial: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    retencao_conferida: Mapped[str | None] = mapped_column(Text)  # o que o advogado conferiu sobre retenção de dados
    aprovado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    aprovado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    simulado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    criado_em: Mapped[datetime] = _criado()
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class FuncaoVirtual(Base):
    """Uma das 40 funções virtuais (AGENTS.md). Teto de nível e ferramentas vêm do código; aqui só se restringe."""
    __tablename__ = "ia_funcoes"
    __table_args__ = (
        UniqueConstraint("escritorio_id", "codigo"),
        UniqueConstraint("escritorio_id", "numero"),
        CheckConstraint("nivel between 0 and 4"),
        CheckConstraint("limite_iteracoes between 1 and 20"),
        CheckConstraint("limite_segundos between 5 and 900"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    codigo: Mapped[str] = mapped_column(String(60), nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    nivel: Mapped[int] = mapped_column(Integer, nullable=False)
    modelo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ia_modelos.id", ondelete="SET NULL"))
    modelo_reserva_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ia_modelos.id", ondelete="SET NULL"))
    limite_iteracoes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("5"))
    limite_segundos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("120"))
    orcamento_execucao: Mapped[Any] = mapped_column(Numeric(10, 4), nullable=False, server_default=text("0.50"))  # USD
    ferramentas_desligadas: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    atualizado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PromptIA(Base):
    """Versão de instrução de uma função. Nunca é alterada: editar cria nova versão."""
    __tablename__ = "ia_prompts"
    __table_args__ = (UniqueConstraint("escritorio_id", "funcao", "versao"),)
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    funcao: Mapped[str] = mapped_column(String(60), nullable=False)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    motivo: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()


ESTADOS_EXECUCAO_IA = ("pendente", "executando", "aguardando_aprovacao", "concluida", "falhou", "bloqueada", "cancelada",
                       "interrompida")


class ExecucaoIA(Base):
    """Execução de uma função virtual: estado persistente, custo, modelo e versão da instrução usados."""
    __tablename__ = "ia_execucoes"
    __table_args__ = (
        CheckConstraint("estado in (" + ",".join(f"'{e}'" for e in ESTADOS_EXECUCAO_IA) + ")"),
        CheckConstraint("origem in ('pessoa','assistente','agendador','automacao','mcp')"),
        Index("ix_ia_execucoes_chave", "escritorio_id", "chave", unique=True, postgresql_where=text("chave is not null")),
        Index("ix_ia_execucoes_periodo", "escritorio_id", "criado_em"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    funcao: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    origem: Mapped[str] = mapped_column(String(20), nullable=False)
    chave: Mapped[str | None] = mapped_column(String(200))
    estado: Mapped[str] = mapped_column(String(25), nullable=False, server_default=text("'pendente'"))
    prioridade: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("5"))
    entrada: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    saida: Mapped[Any | None] = mapped_column(JSONB)
    erro: Mapped[str | None] = mapped_column(Text)
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clientes.id", ondelete="SET NULL"))
    processo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("processos.id", ondelete="SET NULL"))
    departamento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departamentos.id", ondelete="SET NULL"))
    provedor: Mapped[str | None] = mapped_column(String(30))
    modelo: Mapped[str | None] = mapped_column(String(120))
    simulado: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    prompt_versao: Mapped[int | None] = mapped_column(Integer)
    prompt_sha256: Mapped[str | None] = mapped_column(String(64))
    tokens_entrada: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    tokens_saida: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    custo: Mapped[Any] = mapped_column(Numeric(12, 6), nullable=False, server_default=text("0"))  # USD
    iteracoes: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    tentativas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    aprovacao_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("aprovacoes.id", ondelete="SET NULL"))
    solicitada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    iniciada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = _criado()


class PassoExecucaoIA(Base):
    """Cada chamada ao modelo, ferramenta, validação ou pedido de aprovação dentro de uma execução."""
    __tablename__ = "ia_passos"
    __table_args__ = (CheckConstraint("tipo in ('modelo','ferramenta','validacao','aprovacao','regra','bloqueio')"),)
    id: Mapped[uuid.UUID] = _uuid()
    execucao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ia_execucoes.id", ondelete="CASCADE"), nullable=False, index=True)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    parametros: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    resultado: Mapped[Any | None] = mapped_column(JSONB)
    sucesso: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    tokens_entrada: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    tokens_saida: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    custo: Mapped[Any] = mapped_column(Numeric(12, 6), nullable=False, server_default=text("0"))
    duracao_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    criado_em: Mapped[datetime] = _criado()


class ComandoAssistente(Base):
    """Comando dado ao assistente pessoal. Consultas respondem na hora; o que altera dados espera confirmação."""
    __tablename__ = "assistente_comandos"
    __table_args__ = (
        CheckConstraint("tipo in ('consulta','comando','recusado','livre')"),
        CheckConstraint("situacao in ('respondido','aguardando_confirmacao','confirmado','cancelado','recusado','falhou')"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    canal: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'texto'"))
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    intencao: Mapped[str | None] = mapped_column(String(60))
    tipo: Mapped[str] = mapped_column(String(15), nullable=False)
    situacao: Mapped[str] = mapped_column(String(25), nullable=False)
    proposta: Mapped[Any | None] = mapped_column(JSONB)  # ação que espera confirmação
    resposta: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    execucao_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ia_execucoes.id", ondelete="SET NULL"))
    criado_em: Mapped[datetime] = _criado()
    decidido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Automacao(Base):
    """Automação: gatilho, condições e ações de uma lista fechada. Só é ativada depois de testada na versão atual."""
    __tablename__ = "automacoes"
    __table_args__ = (CheckConstraint("situacao in ('rascunho','testada','ativa','pausada','desativada')"),)
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(Text)
    gatilho: Mapped[str] = mapped_column(String(60), nullable=False)
    parametros: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    condicoes: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    acoes: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    horario: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))  # dias úteis, faixa de horas
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'rascunho'"))
    versao: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    testada_versao: Mapped[int | None] = mapped_column(Integer)
    testada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ativada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    ativada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultima_varredura: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    falhas_seguidas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ExecucaoAutomacao(Base):
    """Uma ocorrência do gatilho tratada (ou simulada no teste). A chave impede repetir a mesma ocorrência."""
    __tablename__ = "automacao_execucoes"
    __table_args__ = (
        CheckConstraint("modo in ('teste','real')"),
        CheckConstraint("situacao in ('concluida','ignorada','falhou','aguardando_aprovacao')"),
        Index("ix_automacao_exec_chave", "automacao_id", "chave", unique=True, postgresql_where=text("modo = 'real'")),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    automacao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("automacoes.id", ondelete="CASCADE"), nullable=False, index=True)
    versao: Mapped[int] = mapped_column(Integer, nullable=False)
    modo: Mapped[str] = mapped_column(String(10), nullable=False)
    chave: Mapped[str] = mapped_column(String(200), nullable=False)
    evento: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    resultado: Mapped[Any] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    situacao: Mapped[str] = mapped_column(String(25), nullable=False)
    erro: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = _criado()


class TokenMCP(Base):
    """Token pessoal para clientes MCP. Só o hash fica no banco; vale com as permissões atuais do dono, só leitura."""
    __tablename__ = "tokens_mcp"
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    prefixo: Mapped[str] = mapped_column(String(16), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revogado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultimo_uso_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    usos: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    criado_em: Mapped[datetime] = _criado()


# ================================================================ Fase 9 — financeiro
# Registro e controle. Nenhuma tabela guarda credencial bancária e nada aqui movimenta dinheiro: receber e pagar são
# fatos registrados por uma pessoa (ou conciliados a partir de um extrato importado), nunca ordens enviadas a um banco.

class ContaFinanceira(Base):
    """Conta onde o dinheiro entra e sai (conta corrente, caixa, aplicação). Só nome e saldo inicial; sem dados de acesso."""
    __tablename__ = "contas_financeiras"
    __table_args__ = (CheckConstraint("tipo in ('corrente','caixa','aplicacao','outra')"),
                      UniqueConstraint("escritorio_id", "nome"))
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo: Mapped[str] = mapped_column(String(15), nullable=False, server_default=text("'corrente'"))
    saldo_inicial: Mapped[Any] = mapped_column(Numeric(14, 2), nullable=False, server_default=text("0"))
    data_saldo_inicial: Mapped[date] = mapped_column(Date, nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    criado_em: Mapped[datetime] = _criado()


class CategoriaFinanceira(Base):
    __tablename__ = "categorias_financeiras"
    __table_args__ = (CheckConstraint("tipo in ('receita','despesa')"), UniqueConstraint("escritorio_id", "codigo"))
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    codigo: Mapped[str] = mapped_column(String(60), nullable=False)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    honorario: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    operacional: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))  # custo fixo do escritório
    ativa: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class ContratoHonorarios(Base):
    """Honorários combinados com o cliente. As parcelas viram lançamentos previstos; êxito entra quando registrado."""
    __tablename__ = "contratos_honorarios"
    __table_args__ = (
        CheckConstraint("modalidade in ('fixo','parcelado','mensal','exito','misto')"),
        CheckConstraint("situacao in ('vigente','encerrado','cancelado')"),
        CheckConstraint("percentual_exito is null or (percentual_exito > 0 and percentual_exito <= 100)"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    numero: Mapped[str] = mapped_column(String(20), nullable=False)  # AAAA/NNNN
    cliente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False, index=True)
    processo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("processos.id", ondelete="SET NULL"), index=True)
    departamento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departamentos.id", ondelete="SET NULL"))
    minuta_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("minutas.id", ondelete="SET NULL"))  # contrato assinado
    descricao: Mapped[str] = mapped_column(String(500), nullable=False)
    modalidade: Mapped[str] = mapped_column(String(10), nullable=False)
    valor_fixo: Mapped[Any | None] = mapped_column(Numeric(14, 2))
    parcelas: Mapped[int | None] = mapped_column(Integer)
    primeiro_vencimento: Mapped[date | None] = mapped_column(Date)
    percentual_exito: Mapped[Any | None] = mapped_column(Numeric(5, 2))
    data_contrato: Mapped[date] = mapped_column(Date, nullable=False)
    portal_visivel: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    situacao: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'vigente'"))
    motivo_situacao: Mapped[str | None] = mapped_column(Text)
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()


class Lancamento(Base):
    """Receita ou despesa. Situação: previsto → faturado (só receita) → liquidado (recebido/pago), ou cancelado.
    Valor sempre positivo; o tipo diz o sentido. Cancelar e estornar exigem motivo; nada é apagado."""
    __tablename__ = "lancamentos"
    __table_args__ = (
        CheckConstraint("tipo in ('receita','despesa')"),
        CheckConstraint("situacao in ('previsto','faturado','liquidado','cancelado')"),
        CheckConstraint("valor > 0"),
        CheckConstraint("forma is null or forma in ('pix','transferencia','boleto','dinheiro','cartao','cheque','deposito_judicial','outra')"),
        CheckConstraint("situacao <> 'liquidado' or liquidado_em is not null"),
        CheckConstraint("tipo = 'receita' or situacao <> 'faturado'"),
        Index("ix_lancamentos_abertos", "escritorio_id", "vencimento", postgresql_where=text("situacao in ('previsto','faturado')")),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(10), nullable=False)
    categoria_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categorias_financeiras.id"), nullable=False)
    descricao: Mapped[str] = mapped_column(String(300), nullable=False)
    valor: Mapped[Any] = mapped_column(Numeric(14, 2), nullable=False)
    vencimento: Mapped[date] = mapped_column(Date, nullable=False)
    competencia: Mapped[date] = mapped_column(Date, nullable=False)  # primeiro dia do mês de referência
    situacao: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'previsto'"), index=True)
    cliente_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("clientes.id", ondelete="RESTRICT"), index=True)
    processo_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("processos.id", ondelete="SET NULL"), index=True)
    contrato_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contratos_honorarios.id", ondelete="RESTRICT"), index=True)
    departamento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("departamentos.id", ondelete="SET NULL"))
    parcela: Mapped[int | None] = mapped_column(Integer)
    total_parcelas: Mapped[int | None] = mapped_column(Integer)
    origem_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # saldo desdobrado de outro lançamento
    reembolsavel: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))  # despesa a cobrar do cliente
    portal_visivel: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    faturado_em: Mapped[date | None] = mapped_column(Date)
    liquidado_em: Mapped[date | None] = mapped_column(Date)
    conta_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("contas_financeiras.id"))
    forma: Mapped[str | None] = mapped_column(String(20))
    observacao: Mapped[str | None] = mapped_column(Text)
    motivo_cancelamento: Mapped[str | None] = mapped_column(Text)
    liquidado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Recibo(Base):
    """Recibo numerado de um valor recebido. O texto sai do modelo homologado 'Recibo de honorários' (Fase 6)."""
    __tablename__ = "recibos"
    __table_args__ = (UniqueConstraint("escritorio_id", "numero"), CheckConstraint("situacao in ('emitido','cancelado')"),
                      Index("ix_recibo_lancamento_ativo", "lancamento_id", unique=True, postgresql_where=text("situacao = 'emitido'")))
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    numero: Mapped[str] = mapped_column(String(20), nullable=False)
    lancamento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lancamentos.id", ondelete="RESTRICT"), nullable=False, index=True)
    valor: Mapped[Any] = mapped_column(Numeric(14, 2), nullable=False)
    referente: Mapped[str] = mapped_column(String(500), nullable=False)
    minuta_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("minutas.id", ondelete="SET NULL"))
    situacao: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'emitido'"))
    motivo_cancelamento: Mapped[str | None] = mapped_column(Text)
    emitido_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    emitido_em: Mapped[datetime] = _criado()


class ExtratoImportado(Base):
    """Extrato bancário enviado pela equipe (OFX ou CSV). O EJMF não acessa banco nenhum."""
    __tablename__ = "extratos_importados"
    __table_args__ = (UniqueConstraint("conta_id", "sha256"),)
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    conta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contas_financeiras.id"), nullable=False, index=True)
    nome_arquivo: Mapped[str] = mapped_column(String(255), nullable=False)
    formato: Mapped[str] = mapped_column(String(5), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    linhas_novas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    linhas_repetidas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    importado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    criado_em: Mapped[datetime] = _criado()


class LinhaExtrato(Base):
    __tablename__ = "extrato_linhas"
    __table_args__ = (
        UniqueConstraint("conta_id", "chave"),
        CheckConstraint("situacao in ('pendente','conciliada','ignorada')"),
        CheckConstraint("valor <> 0"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    conta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("contas_financeiras.id"), nullable=False, index=True)
    extrato_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("extratos_importados.id", ondelete="CASCADE"), nullable=False)
    chave: Mapped[str] = mapped_column(String(120), nullable=False)  # FITID do OFX ou hash de data+valor+descrição+ordem
    data: Mapped[date] = mapped_column(Date, nullable=False)
    valor: Mapped[Any] = mapped_column(Numeric(14, 2), nullable=False)  # positivo entra, negativo sai
    descricao: Mapped[str] = mapped_column(String(300), nullable=False)
    situacao: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'pendente'"), index=True)
    lancamento_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lancamentos.id", ondelete="SET NULL"), index=True)
    motivo: Mapped[str | None] = mapped_column(Text)
    conciliada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    conciliada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LembreteCobranca(Base):
    """Lembrete de pagamento ao cliente. Só aparece no portal depois de autorizado; o EJMF não envia cobrança para fora."""
    __tablename__ = "lembretes_cobranca"
    __table_args__ = (CheckConstraint("situacao in ('aguardando_aprovacao','publicado','rejeitado','retirado')"),)
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    lancamento_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lancamentos.id", ondelete="CASCADE"), nullable=False, index=True)
    cliente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    situacao: Mapped[str] = mapped_column(String(25), nullable=False)
    origem: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'pessoa'"))  # pessoa | funcao
    aprovacao_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("aprovacoes.id", ondelete="SET NULL"))
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    autorizado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id"))
    publicado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = _criado()


# ============================================================== Fase 10 — PWA e notificações no celular

class AssinaturaPush(Base):
    """Aparelho que aceitou notificações (Web Push). Ligada à sessão: encerrar a sessão encerra a assinatura."""
    __tablename__ = "assinaturas_push"
    __table_args__ = (Index("ix_assinaturas_push_usuario", "usuario_id", postgresql_where=text("revogada_em is null")),)
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    usuario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    sessao_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sessoes.id", ondelete="SET NULL"))
    endpoint: Mapped[str] = mapped_column(String(1000), nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(String(200), nullable=False)
    auth: Mapped[str] = mapped_column(String(100), nullable=False)
    dispositivo: Mapped[str | None] = mapped_column(String(120))
    so_urgentes: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    falhas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    ultimo_envio_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revogada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_revogacao: Mapped[str | None] = mapped_column(String(200))
    criado_em: Mapped[datetime] = _criado()


class ContadorTaxa(Base):
    """Contagem por janela de um minuto, compartilhada por todos os processos da API (login, portal, rotas públicas, MCP)."""
    __tablename__ = "contadores_taxa"
    chave: Mapped[str] = mapped_column(String(300), primary_key=True)
    janela: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    contagem: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))


class CopiaSeguranca(Base):
    """Cópia de segurança cifrada (banco + arquivos). O arquivo fica fora do banco; aqui ficam o resumo e os testes."""
    __tablename__ = "copias_seguranca"
    __table_args__ = (
        CheckConstraint("situacao in ('executando','concluida','falhou','expirada')", name="ck_copias_situacao"),
        CheckConstraint("teste_situacao is null or teste_situacao in ('aprovado','reprovado')", name="ck_copias_teste"),
        CheckConstraint("externa_situacao is null or externa_situacao in ('pendente','enviada','falhou')", name="ck_copias_externa"),
        Index("ix_copias_seguranca_iniciada", "escritorio_id", "iniciada_em"),
    )
    id: Mapped[uuid.UUID] = _uuid()
    escritorio_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("escritorios.id"), nullable=False)
    situacao: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'executando'"))
    origem: Mapped[str] = mapped_column(String(20), nullable=False)  # agendador, pessoa, funcao
    solicitada_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    iniciada_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    concluida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arquivo: Mapped[str | None] = mapped_column(String(200))
    tamanho: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    chave_id: Mapped[str | None] = mapped_column(String(16))  # identifica a chave usada, sem revelá-la
    manifesto: Mapped[Any] = mapped_column(JSONB, nullable=True)  # revisão do banco, contagens por tabela, arquivos, último hash da auditoria
    erro: Mapped[str | None] = mapped_column(Text)
    teste_situacao: Mapped[str | None] = mapped_column(String(20))
    testada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    teste_detalhes: Mapped[Any] = mapped_column(JSONB, nullable=True)
    expirada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Fase 12: cópia no armazenamento externo (S3 compatível). O EJMF só grava e confere; não apaga lá fora.
    externa_situacao: Mapped[str | None] = mapped_column(String(20))
    externa_chave: Mapped[str | None] = mapped_column(String(300))
    externa_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    externa_erro: Mapped[str | None] = mapped_column(Text)
