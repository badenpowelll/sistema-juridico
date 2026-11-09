-- Sistema Jurídico: módulos Associados (vínculos e holerites), Cálculos, Petições, Lotes e Diligências.
-- Mesmo desenho do script preparado para o Lovable (sql/0002_modulos.sql), sem RLS: o acesso é checado no servidor.
-- Acréscimos da planilha de rescisões do RN: periculosidade (30% do salário base) e honorários contratuais (15%).

create table vinculos (
  id uuid primary key default gen_random_uuid(),
  associado_id uuid not null references associados(id) on delete cascade,
  empresa_id uuid references empresas(id),
  admissao date, desligamento date, funcao text, jornada_semanal numeric,
  tipo_rescisao text, aviso text, salario_base numeric(12,2), atual boolean not null default true,
  matricula text,
  periculosidade boolean not null default false,
  periculosidade_pct numeric(5,2) not null default 30,   -- art. 193, §1º, CLT: 30% do salário base
  observacoes text,
  criado_em timestamptz not null default now(), atualizado_em timestamptz not null default now(),
  criado_por uuid references usuarios(id)
);
create index on vinculos(associado_id);
create index on vinculos(empresa_id);

create table holerites (
  id uuid primary key default gen_random_uuid(),
  associado_id uuid not null references associados(id) on delete cascade,
  vinculo_id uuid references vinculos(id) on delete cascade,
  competencia date not null,               -- 1º dia do mês
  salario_base numeric(12,2), total_proventos numeric(12,2), total_descontos numeric(12,2),
  liquido numeric(12,2), verbas jsonb not null default '[]',   -- [{descricao, valor, tipo}]
  origem text not null default 'manual' check (origem in ('manual','extraido')),
  conferido boolean not null default false,
  criado_em timestamptz not null default now(), atualizado_em timestamptz not null default now(),
  criado_por uuid references usuarios(id),
  unique (vinculo_id, competencia)
);

create table calculos (
  id uuid primary key default gen_random_uuid(),
  associado_id uuid not null references associados(id) on delete cascade,
  vinculo_id uuid references vinculos(id),
  versao_regras text not null,
  entrada jsonb not null, resultado jsonb not null, ajustes_manuais jsonb not null default '[]',
  total_liquido numeric(12,2),
  custo_rescisao numeric(12,2),                 -- custo total antes dos honorários
  honorarios_contratuais_pct numeric(5,2) not null default 15,
  honorarios_contratuais numeric(12,2),          -- custo_rescisao × pct
  custo_total numeric(12,2),                     -- custo_rescisao + honorários contratuais
  situacao text not null default 'rascunho' check (situacao in ('rascunho','conferido')),
  conferido_por uuid, conferido_em timestamptz, lote_id uuid,
  criado_em timestamptz not null default now(), atualizado_em timestamptz not null default now(),
  criado_por uuid references usuarios(id)
);
create index on calculos(associado_id);

create table peticoes (
  id uuid primary key default gen_random_uuid(),
  associado_id uuid not null references associados(id) on delete cascade,
  calculo_id uuid references calculos(id),
  titulo text not null default 'Reclamação trabalhista',
  fatos_informados text, secoes jsonb not null default '{}', pendencias jsonb not null default '[]',
  situacao text not null default 'minuta' check (situacao in ('minuta','aprovada')),
  aprovada_por uuid, aprovada_em timestamptz, lote_id uuid,
  criado_em timestamptz not null default now(), atualizado_em timestamptz not null default now(),
  criado_por uuid references usuarios(id)
);
create index on peticoes(associado_id);

create table lotes (
  id uuid primary key default gen_random_uuid(),
  tipo text not null check (tipo in ('calculo','peticao','dossie')),
  filtro jsonb not null default '{}', parametros jsonb not null default '{}',
  situacao text not null default 'preparado' check (situacao in ('preparado','executando','concluido','com_erros')),
  confirmado_por uuid, confirmado_em timestamptz,
  criado_em timestamptz not null default now(), atualizado_em timestamptz not null default now(),
  criado_por uuid references usuarios(id)
);
create table lote_itens (
  id uuid primary key default gen_random_uuid(),
  lote_id uuid not null references lotes(id) on delete cascade,
  associado_id uuid not null references associados(id) on delete cascade,
  situacao text not null default 'pendente' check (situacao in ('pendente','apto','inapto','concluido','erro')),
  pendencias jsonb not null default '[]', erro text, resultado_id uuid,
  criado_em timestamptz not null default now(), atualizado_em timestamptz not null default now(),
  criado_por uuid references usuarios(id),
  unique (lote_id, associado_id)
);
alter table calculos add foreign key (lote_id) references lotes(id);
alter table peticoes add foreign key (lote_id) references lotes(id);

create table diligencias (
  id uuid primary key default gen_random_uuid(),
  associado_id uuid not null references associados(id) on delete cascade,
  itens jsonb not null default '[]',      -- [{codigo, descricao, recebido}]
  mensagem text,
  situacao text not null default 'aberta' check (situacao in ('aberta','enviada','recebida','concluida','recusada')),
  enviada_em timestamptz, recebida_em timestamptz, conferida_por uuid, conferida_em timestamptz,
  observacoes text,
  criado_em timestamptz not null default now(), atualizado_em timestamptz not null default now(),
  criado_por uuid references usuarios(id)
);
create index on diligencias(associado_id);


-- Percentual padrão de honorários contratuais de cada cliente (a planilha do RN usa 15%)
alter table clientes add column honorarios_contratuais_pct numeric(5,2) not null default 15;

do $$ declare t text; begin
  foreach t in array array['vinculos','holerites','calculos','peticoes','lotes','lote_itens','diligencias'] loop
    execute format('create trigger %I before update on %I for each row execute function set_atualizado_em()', 'trg_'||t||'_upd', t);
  end loop;
end $$;
