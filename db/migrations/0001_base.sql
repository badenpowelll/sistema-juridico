-- Sistema Jurídico — base (Postgres no Railway).
-- Portado do esquema do protótipo no Lovable (union-counsel-compass): as tabelas e colunas são as mesmas,
-- mas sem Supabase. O login é do próprio sistema (usuarios + sessoes) e o controle de acesso fica no
-- servidor: toda rota de /api, exceto login e formulário do associado, exige advogado ativo.

create table usuarios (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  senha_hash text,                       -- scrypt; nulo até o convidado definir a senha
  ativo boolean not null default true,
  ultimo_acesso timestamptz,
  criado_em timestamptz not null default now(),
  atualizado_em timestamptz not null default now()
);
create unique index usuarios_email_uk on usuarios (lower(email));

create table sessoes (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios(id) on delete cascade,
  token_hash text not null unique,       -- sha256 do token do cookie; o token em si nunca é gravado
  expira_em timestamptz not null,
  ip text,
  user_agent text,
  criado_em timestamptz not null default now()
);
create index sessoes_usuario_idx on sessoes (usuario_id);

-- Convites e redefinição de senha (link de uso único)
create table convites (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null references usuarios(id) on delete cascade,
  token_hash text not null unique,
  expira_em timestamptz not null,
  usado_em timestamptz,
  criado_em timestamptz not null default now()
);

create or replace function set_atualizado_em() returns trigger language plpgsql as $$
begin new.atualizado_em = now(); return new; end; $$;

create table advogados (
  id uuid primary key default gen_random_uuid(),
  usuario_id uuid not null unique references usuarios(id) on delete cascade,
  nome text not null,
  oab text,
  papel text not null default 'advogado' check (papel in ('admin','advogado')),
  ativo boolean not null default true,
  criado_em timestamptz not null default now(),
  atualizado_em timestamptz not null default now(),
  criado_por uuid references usuarios(id)
);

-- Clientes: as entidades sindicais (ex.: SINTICOCIP)
create table clientes (
  id uuid primary key default gen_random_uuid(),
  cnpj text not null unique check (cnpj ~ '^[0-9]{14}$'),
  razao_social text not null,
  nome_fantasia text,
  endereco jsonb,
  logo_url text,
  arquivado boolean not null default false,
  cnae text,
  situacao text,
  data_situacao date,
  natureza_juridica text,
  data_inicio_atividade date,
  porte text,
  telefone text,
  email text,
  representante_nome text,
  representante_qualificacao text,
  dados_receita jsonb,
  consultado_em timestamptz,
  criado_em timestamptz not null default now(),
  atualizado_em timestamptz not null default now(),
  criado_por uuid references usuarios(id)
);

-- Empresas: empregadoras dos associados
create table empresas (
  id uuid primary key default gen_random_uuid(),
  cnpj text not null unique check (cnpj ~ '^[0-9]{14}$'),
  razao_social text not null,
  nome_fantasia text,
  endereco jsonb,
  cnae text,
  situacao text,
  data_situacao date,
  natureza_juridica text,
  data_inicio_atividade date,
  porte text,
  telefone text,
  email text,
  representante_nome text,
  representante_qualificacao text,
  dados_receita jsonb,
  consultado_em timestamptz,
  criado_em timestamptz not null default now(),
  atualizado_em timestamptz not null default now(),
  criado_por uuid references usuarios(id)
);

create table associados (
  id uuid primary key default gen_random_uuid(),
  cliente_id uuid not null references clientes(id) on delete cascade,
  nome text not null,
  cpf text check (cpf ~ '^[0-9]{11}$'),    -- pode faltar em associado importado do OneDrive até a conferência
  rg text,
  orgao_expedidor text,
  nacionalidade text not null default 'brasileira',
  estado_civil text,
  naturalidade_uf text,
  naturalidade_municipio text,
  data_nascimento date,
  cep text,
  logradouro text,
  numero text,
  complemento text,
  bairro text,
  municipio text,
  uf text,
  email text,
  telefone text,
  nome_mae text,
  nome_pai text,
  situacao_cadastro text not null default 'rascunho'
    check (situacao_cadastro in ('rascunho','aguardando_associado','recebido','conferido')),
  criado_em timestamptz not null default now(),
  atualizado_em timestamptz not null default now(),
  criado_por uuid references usuarios(id),
  unique (cliente_id, cpf)
);
create index associados_cliente_idx on associados (cliente_id);
create index associados_nome_idx on associados (cliente_id, lower(nome));

-- Auditoria: só inserção. O papel do aplicativo não tem UPDATE/DELETE aqui (ver o gatilho abaixo).
create table auditoria (
  id bigint generated always as identity primary key,
  quem uuid references usuarios(id),
  acao text not null,
  entidade text not null,
  entidade_id uuid,
  detalhes jsonb,
  ip text,
  em timestamptz not null default now()
);
create index auditoria_entidade_idx on auditoria (entidade, entidade_id);

create or replace function auditoria_somente_insercao() returns trigger language plpgsql as $$
begin raise exception 'auditoria não pode ser alterada nem apagada'; end; $$;
create trigger trg_auditoria_imutavel before update or delete on auditoria
  for each row execute function auditoria_somente_insercao();

do $$ declare t text; begin
  foreach t in array array['usuarios','advogados','clientes','empresas','associados'] loop
    execute format('create trigger %I before update on %I for each row execute function set_atualizado_em()', 'trg_'||t||'_upd', t);
  end loop;
end $$;
