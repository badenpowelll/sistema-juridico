# CHANGELOG

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
