"""Fase 7 — conhecimento: biblioteca versionada, jurisprudência verificada, trechos vetorizados (pgvector) e memória permanente

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-24 06:25:20.195550
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table('fontes_conhecimento',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('escritorio_id', sa.UUID(), nullable=False),
    sa.Column('codigo', sa.String(length=40), nullable=False),
    sa.Column('nome', sa.String(length=200), nullable=False),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('dominios', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('oficial', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('ativa', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('observacao', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['escritorio_id'], ['escritorios.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('escritorio_id', 'codigo')
    )
    op.create_table('trechos_conhecimento',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('escritorio_id', sa.UUID(), nullable=False),
    sa.Column('origem', sa.String(length=20), nullable=False),
    sa.Column('ref_id', sa.UUID(), nullable=False),
    sa.Column('versao', sa.Integer(), nullable=True),
    sa.Column('ordem', sa.Integer(), nullable=False),
    sa.Column('cliente_id', sa.UUID(), nullable=True),
    sa.Column('processo_id', sa.UUID(), nullable=True),
    sa.Column('sigiloso', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('texto', sa.Text(), nullable=False),
    sa.Column('vetorizador', sa.String(length=40), nullable=False),
    sa.Column('vetor', pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=False),
    sa.Column('busca', postgresql.TSVECTOR(), sa.Computed("to_tsvector('portuguese'::regconfig, texto)", persisted=True), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("origem in ('biblioteca','jurisprudencia','documento','memoria')"),
    sa.ForeignKeyConstraint(['escritorio_id'], ['escritorios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_trechos_busca', 'trechos_conhecimento', ['busca'], unique=False, postgresql_using='gin')
    op.create_index('ix_trechos_escopo', 'trechos_conhecimento', ['escritorio_id', 'cliente_id', 'processo_id'], unique=False)
    op.create_index('ix_trechos_origem', 'trechos_conhecimento', ['origem', 'ref_id'], unique=False)
    op.create_index('ix_trechos_vetor', 'trechos_conhecimento', ['vetor'], unique=False, postgresql_using='hnsw', postgresql_ops={'vetor': 'vector_cosine_ops'})
    op.create_table('colecoes_conhecimento',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('escritorio_id', sa.UUID(), nullable=False),
    sa.Column('nome', sa.String(length=200), nullable=False),
    sa.Column('descricao', sa.Text(), nullable=True),
    sa.Column('departamento_id', sa.UUID(), nullable=True),
    sa.Column('criado_por', sa.UUID(), nullable=True),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['criado_por'], ['usuarios.id'], ),
    sa.ForeignKeyConstraint(['departamento_id'], ['departamentos.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['escritorio_id'], ['escritorios.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('escritorio_id', 'nome')
    )
    op.create_table('favoritos_conhecimento',
    sa.Column('usuario_id', sa.UUID(), nullable=False),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('ref_id', sa.UUID(), nullable=False),
    sa.Column('escritorio_id', sa.UUID(), nullable=False),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['escritorio_id'], ['escritorios.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('usuario_id', 'tipo', 'ref_id')
    )
    op.create_table('itens_biblioteca',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('escritorio_id', sa.UUID(), nullable=False),
    sa.Column('tipo', sa.String(length=30), nullable=False),
    sa.Column('titulo', sa.String(length=400), nullable=False),
    sa.Column('identificador', sa.String(length=200), nullable=True),
    sa.Column('esfera', sa.String(length=20), nullable=True),
    sa.Column('orgao', sa.String(length=200), nullable=True),
    sa.Column('ementa', sa.Text(), nullable=True),
    sa.Column('departamento_id', sa.UUID(), nullable=True),
    sa.Column('fonte_id', sa.UUID(), nullable=True),
    sa.Column('url_origem', sa.String(length=1000), nullable=True),
    sa.Column('licenca', sa.String(length=20), server_default=sa.text("'publico'"), nullable=False),
    sa.Column('vigencia', sa.String(length=30), server_default=sa.text("'a_conferir'"), nullable=False),
    sa.Column('vigencia_desde', sa.Date(), nullable=True),
    sa.Column('vigencia_ate', sa.Date(), nullable=True),
    sa.Column('vigencia_conferida_por', sa.UUID(), nullable=True),
    sa.Column('vigencia_conferida_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('situacao', sa.String(length=30), server_default=sa.text("'ativo'"), nullable=False),
    sa.Column('monitorar', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('versao_atual', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('coletado_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('verificado_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('erro_verificacao', sa.Text(), nullable=True),
    sa.Column('assuntos', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('criado_por', sa.UUID(), nullable=True),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("licenca in ('publico','licenciado','interno','referencia')"),
    sa.CheckConstraint("situacao in ('ativo','alteracao_a_conferir','arquivado')"),
    sa.CheckConstraint("vigencia in ('vigente','revogado','parcialmente_revogado','a_conferir','nao_se_aplica')"),
    sa.ForeignKeyConstraint(['criado_por'], ['usuarios.id'], ),
    sa.ForeignKeyConstraint(['departamento_id'], ['departamentos.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['escritorio_id'], ['escritorios.id'], ),
    sa.ForeignKeyConstraint(['fonte_id'], ['fontes_conhecimento.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['vigencia_conferida_por'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_biblioteca_titulo_trgm', 'itens_biblioteca', ['titulo'], unique=False, postgresql_using='gin', postgresql_ops={'titulo': 'gin_trgm_ops'})
    op.create_table('jurisprudencias',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('escritorio_id', sa.UUID(), nullable=False),
    sa.Column('tribunal', sa.String(length=20), nullable=False),
    sa.Column('numero', sa.String(length=120), nullable=False),
    sa.Column('numero_normalizado', sa.String(length=120), nullable=False),
    sa.Column('classe', sa.String(length=120), nullable=True),
    sa.Column('orgao_julgador', sa.String(length=200), nullable=True),
    sa.Column('relator', sa.String(length=200), nullable=True),
    sa.Column('data_julgamento', sa.Date(), nullable=True),
    sa.Column('data_publicacao', sa.Date(), nullable=True),
    sa.Column('ementa', sa.Text(), nullable=False),
    sa.Column('url_original', sa.String(length=1000), nullable=True),
    sa.Column('fonte_id', sa.UUID(), nullable=True),
    sa.Column('origem', sa.String(length=20), server_default=sa.text("'manual'"), nullable=False),
    sa.Column('assuntos', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
    sa.Column('verificacao', sa.String(length=30), server_default=sa.text("'pendente'"), nullable=False),
    sa.Column('verificacao_detalhe', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('verificada_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('consultado_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('sha256_original', sa.String(length=64), nullable=True),
    sa.Column('homologada_por', sa.UUID(), nullable=True),
    sa.Column('homologada_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('situacao', sa.String(length=20), server_default=sa.text("'ativa'"), nullable=False),
    sa.Column('motivo_descarte', sa.Text(), nullable=True),
    sa.Column('criado_por', sa.UUID(), nullable=True),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("situacao in ('ativa','descartada')"),
    sa.CheckConstraint("verificacao in ('pendente','verificada','nao_localizada','fonte_indisponivel','divergente')"),
    sa.ForeignKeyConstraint(['criado_por'], ['usuarios.id'], ),
    sa.ForeignKeyConstraint(['escritorio_id'], ['escritorios.id'], ),
    sa.ForeignKeyConstraint(['fonte_id'], ['fontes_conhecimento.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['homologada_por'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('uq_jurisprudencia_numero', 'jurisprudencias', ['escritorio_id', 'tribunal', 'numero_normalizado'], unique=True, postgresql_where=sa.text("situacao = 'ativa'"))
    op.create_table('itens_colecao',
    sa.Column('colecao_id', sa.UUID(), nullable=False),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('ref_id', sa.UUID(), nullable=False),
    sa.Column('adicionado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['colecao_id'], ['colecoes_conhecimento.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('colecao_id', 'tipo', 'ref_id')
    )
    op.create_table('versoes_item_biblioteca',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('item_id', sa.UUID(), nullable=False),
    sa.Column('numero', sa.Integer(), nullable=False),
    sa.Column('texto', sa.Text(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('url_coleta', sa.String(length=1000), nullable=True),
    sa.Column('coletado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('motivo', sa.String(length=30), nullable=False),
    sa.Column('situacao', sa.String(length=20), server_default=sa.text("'a_conferir'"), nullable=False),
    sa.Column('conferida_por', sa.UUID(), nullable=True),
    sa.Column('conferida_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('autor_id', sa.UUID(), nullable=True),
    sa.CheckConstraint("motivo in ('cadastro','alteracao_detectada','manual','importacao')"),
    sa.CheckConstraint("situacao in ('a_conferir','conferida','descartada')"),
    sa.ForeignKeyConstraint(['autor_id'], ['usuarios.id'], ),
    sa.ForeignKeyConstraint(['conferida_por'], ['usuarios.id'], ),
    sa.ForeignKeyConstraint(['item_id'], ['itens_biblioteca.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('item_id', 'numero')
    )
    op.create_index(op.f('ix_versoes_item_biblioteca_item_id'), 'versoes_item_biblioteca', ['item_id'], unique=False)
    op.create_table('memorias',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('escritorio_id', sa.UUID(), nullable=False),
    sa.Column('tipo', sa.String(length=20), nullable=False),
    sa.Column('titulo', sa.String(length=300), nullable=False),
    sa.Column('texto', sa.Text(), nullable=False),
    sa.Column('cliente_id', sa.UUID(), nullable=True),
    sa.Column('processo_id', sa.UUID(), nullable=True),
    sa.Column('departamento_id', sa.UUID(), nullable=True),
    sa.Column('origem', sa.String(length=20), server_default=sa.text("'pessoa'"), nullable=False),
    sa.Column('referencia', sa.String(length=500), nullable=True),
    sa.Column('situacao', sa.String(length=20), server_default=sa.text("'confirmada'"), nullable=False),
    sa.Column('confirmada_por', sa.UUID(), nullable=True),
    sa.Column('confirmada_em', sa.DateTime(timezone=True), nullable=True),
    sa.Column('substituida_por', sa.UUID(), nullable=True),
    sa.Column('motivo_exclusao', sa.Text(), nullable=True),
    sa.Column('criado_por', sa.UUID(), nullable=True),
    sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('atualizado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("origem in ('pessoa','documento','sugestao_ia')"),
    sa.CheckConstraint("situacao in ('a_confirmar','confirmada','substituida','excluida')"),
    sa.CheckConstraint("tipo in ('decisao','orientacao','preferencia','fato')"),
    sa.ForeignKeyConstraint(['cliente_id'], ['clientes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['confirmada_por'], ['usuarios.id'], ),
    sa.ForeignKeyConstraint(['criado_por'], ['usuarios.id'], ),
    sa.ForeignKeyConstraint(['departamento_id'], ['departamentos.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['escritorio_id'], ['escritorios.id'], ),
    sa.ForeignKeyConstraint(['processo_id'], ['processos.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('memorias')
    op.drop_index(op.f('ix_versoes_item_biblioteca_item_id'), table_name='versoes_item_biblioteca')
    op.drop_table('versoes_item_biblioteca')
    op.drop_table('itens_colecao')
    op.drop_index('uq_jurisprudencia_numero', table_name='jurisprudencias', postgresql_where=sa.text("situacao = 'ativa'"))
    op.drop_table('jurisprudencias')
    op.drop_index('ix_biblioteca_titulo_trgm', table_name='itens_biblioteca', postgresql_using='gin', postgresql_ops={'titulo': 'gin_trgm_ops'})
    op.drop_table('itens_biblioteca')
    op.drop_table('favoritos_conhecimento')
    op.drop_table('colecoes_conhecimento')
    op.drop_index('ix_trechos_vetor', table_name='trechos_conhecimento', postgresql_using='hnsw', postgresql_ops={'vetor': 'vector_cosine_ops'})
    op.drop_index('ix_trechos_origem', table_name='trechos_conhecimento')
    op.drop_index('ix_trechos_escopo', table_name='trechos_conhecimento')
    op.drop_index('ix_trechos_busca', table_name='trechos_conhecimento', postgresql_using='gin')
    op.drop_table('trechos_conhecimento')
    op.drop_table('fontes_conhecimento')
    # ### end Alembic commands ###
    op.execute("DROP EXTENSION IF EXISTS vector")
