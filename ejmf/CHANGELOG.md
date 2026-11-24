# CHANGELOG

## [Fase 2] — 2026-11-24
- Migração `0002_gestao_processual`: tribunais, clientes, processos, partes, movimentações, importações e linhas de importação.
- Número CNJ validado pelo dígito verificador (módulo 97) e tribunal identificado pelo código J.TR (95 tribunais; TJRN, TRT21 e TRF5 prioritários).
- Clientes PF/PJ: CPF e CNPJ validados (CNPJ alfanumérico da IN RFB 2.229/2024), guardados cifrados, com hash para busca exata e deduplicação e cópia mascarada para exibição; ver o documento completo exige permissão própria e fica na auditoria.
- Prontuário do processo: dados, partes e clientes, linha do tempo (movimentações, anotações e histórico da auditoria) e próximos módulos.
- Pesquisa global por número (com ou sem máscara, ou trecho), parte, cliente e classe, respeitando permissões.
- Operações em lote (situação e departamento), tudo ou nada, auditadas.
- Importação em massa: pré-visualização, sugestão de mapeamento, validação, duplicidades no arquivo e no banco, execução em lotes de 500 retomável, relatório CSV, fila de conferência para homônimos e reversão.
- Teste de carga com 1k, 5k e 10k processos (100 mil movimentações).

## [Fase 1] — 2026-11-24
- Backend FastAPI + SQLAlchemy/Alembic + PostgreSQL 16 (pgvector), migração `0001_fundacao`.
- Autenticação própria: Argon2id, sessões opacas revogáveis, MFA TOTP, bloqueio após 5 falhas, limite por IP, proteção CSRF.
- Permissões `recurso:acao` em quatro perfis (advogado_admin, operador, cliente, agente_ia).
- Auditoria só de inserção, com cadeia de hashes, gatilho que impede alteração e comando de verificação.
- Configurações institucionais vazias e editáveis; 19 departamentos; 10 integrações nos 6 estados oficiais.
- Frontend Next.js com marca centralizada em `src/marca/`, tema claro/escuro, login com MFA, painel "Central de comando" e telas de integrações, configurações, segurança, auditoria, departamentos e usuários.
- Docker Compose (db, api, worker, web) e CI no GitHub Actions.

## [Fase 0] — 2026-11-24
- Diagnóstico do ambiente e dos repositórios existentes.
- Pesquisa de 28 repositórios do GitHub e das APIs oficiais (DataJud, DJEN) em RESEARCH.md.
- Arquitetura, 7 ADRs, roadmap, backlog priorizado, catálogo das 40 funções, custos estimados e documentação obrigatória inicial.
- Superprompt preservado em `docs/origem/`.
