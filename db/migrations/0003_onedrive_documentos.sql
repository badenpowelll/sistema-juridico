-- OneDrive como fonte dos dados: o sistema lê a árvore de pastas pela Microsoft Graph,
-- guarda um espelho dos itens aqui e liga cada pasta ao cliente ou associado correspondente.
-- Estrutura esperada (especificação): <raiz>/<CLIENTE>/<ASSOCIADO>/01 - DOCUMENTOS PESSOAIS, 02 - DOCUMENTOS JURÍDICOS...
-- Os arquivos continuam no OneDrive; o banco guarda só os metadados e o vínculo.

-- Conta do OneDrive conectada (uma por escritório). O refresh token fica criptografado (AES-256-GCM, chave CHAVE_CRIPTOGRAFIA).
create table onedrive_conexao (
  id smallint primary key default 1 check (id = 1),
  conta text not null,                       -- e-mail da conta Microsoft
  drive_id text,
  pasta_raiz_id text,                        -- item da pasta raiz (ONEDRIVE_PASTA_RAIZ)
  refresh_token_cifrado text not null,
  delta_link text,                           -- continuação da última sincronização incremental
  conectado_por uuid references usuarios(id),
  conectado_em timestamptz not null default now(),
  atualizado_em timestamptz not null default now()
);

create table onedrive_itens (
  item_id text primary key,                  -- id do driveItem na Graph
  pai_id text,
  nome text not null,
  caminho text not null,                     -- relativo à pasta raiz, ex.: SINTICOCIP/JOAO DA SILVA/01 - DOCUMENTOS PESSOAIS/cnh.pdf
  pasta boolean not null,
  mime text,
  tamanho bigint,
  etag text,
  ctag text,                                 -- muda quando o conteúdo muda
  modificado_em timestamptz,
  web_url text,
  removido boolean not null default false,
  -- classificação feita pelo importador (pode ser corrigida pelo advogado)
  nivel text check (nivel in ('raiz','cliente','associado','categoria','arquivo')),
  cliente_id uuid references clientes(id) on delete set null,
  associado_id uuid references associados(id) on delete set null,
  categoria text,                            -- nome da subpasta (01 - DOCUMENTOS PESSOAIS etc.)
  sincronizado_em timestamptz not null default now()
);
create index onedrive_itens_pai_idx on onedrive_itens (pai_id);
create index onedrive_itens_associado_idx on onedrive_itens (associado_id);

create table onedrive_sincronizacoes (
  id bigint generated always as identity primary key,
  tipo text not null check (tipo in ('completa','incremental')),
  iniciada_em timestamptz not null default now(),
  concluida_em timestamptz,
  itens_lidos int not null default 0,
  clientes_criados int not null default 0,
  associados_criados int not null default 0,
  documentos_criados int not null default 0,
  removidos int not null default 0,
  erro text,
  iniciada_por uuid references usuarios(id)
);

alter table clientes add column onedrive_item_id text references onedrive_itens(item_id) on delete set null;
alter table associados add column onedrive_item_id text references onedrive_itens(item_id) on delete set null;

-- Documentos de cada associado. Vêm do OneDrive, do formulário do associado ou são gerados pelo sistema.
create table documentos (
  id uuid primary key default gen_random_uuid(),
  associado_id uuid references associados(id) on delete cascade,
  cliente_id uuid references clientes(id) on delete cascade,
  tipo text not null default 'outro' check (tipo in (
    'documento_foto','cnh','identidade','comprovante_residencia','procuracao','hipossuficiencia',
    'holerite','ctps','trct','planilha_calculo','calculo','peticao','dossie','outro')),
  competencia date,                          -- holerites: 1º dia do mês
  nome_arquivo text not null,
  mime text,
  tamanho bigint,
  sha256 text,
  origem text not null check (origem in ('onedrive','formulario','gerado')),
  onedrive_item_id text references onedrive_itens(item_id) on delete set null,
  situacao text not null default 'pendente_conferencia'
    check (situacao in ('pendente_conferencia','conferido','recusado','substituido')),
  conferido_por uuid references usuarios(id),
  conferido_em timestamptz,
  observacoes text,
  criado_em timestamptz not null default now(),
  atualizado_em timestamptz not null default now(),
  criado_por uuid references usuarios(id)
);
create index documentos_associado_idx on documentos (associado_id);
create unique index documentos_onedrive_uk on documentos (onedrive_item_id) where onedrive_item_id is not null;

-- Link de cadastro do associado (/f/:token): temporário, de uso único e com verificação extra
-- (código enviado ao associado ou data de nascimento + últimos dígitos do CPF).
create table links_formulario (
  id uuid primary key default gen_random_uuid(),
  associado_id uuid not null references associados(id) on delete cascade,
  token_hash text not null unique,
  verificacao_hash text,
  tentativas int not null default 0,
  expira_em timestamptz not null,
  aberto_em timestamptz,
  enviado_em timestamptz,
  revogado boolean not null default false,
  criado_em timestamptz not null default now(),
  criado_por uuid references usuarios(id)
);
create index links_formulario_associado_idx on links_formulario (associado_id);

create trigger trg_documentos_upd before update on documentos for each row execute function set_atualizado_em();
create trigger trg_onedrive_conexao_upd before update on onedrive_conexao for each row execute function set_atualizado_em();
