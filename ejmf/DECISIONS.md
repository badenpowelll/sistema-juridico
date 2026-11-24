# DECISIONS — registro de decisões

Decisões estruturais ficam em ADRs (`docs/adr/`). Decisões menores e reversíveis ficam aqui.

| Data | Decisão | Motivo | ADR |
|---|---|---|---|
| 2026-11-24 | EJMF na pasta `ejmf/` do repositório `sistema-juridico` | Sem permissão para criar repositório novo; `union-counsel-compass` é gerido pelo Lovable | 0001 |
| 2026-11-24 | Núcleo próprio; externos só como biblioteca permissiva ou serviço por API | Pesquisa no GitHub | 0002 |
| 2026-11-24 | FastAPI + SQLAlchemy/Alembic + PostgreSQL/pgvector + Next.js; fila em Postgres | Superprompt + custo | 0003 |
| 2026-11-24 | Autenticação própria (Argon2id, sessões opacas, TOTP, RBAC) | Custo e simplicidade | 0004 |
| 2026-11-24 | Auditoria só-inserção com cadeia de hash | Seção 36 | 0005 |
| 2026-11-24 | `escritorio_id` em todas as tabelas de negócio | Seção 40 (expansão futura) | 0006 |
| 2026-11-24 | Estados oficiais das integrações e adaptadores simulados marcados | Seções 42 e R | 0007 |
| 2026-11-24 | Carnaval, Paixão e Corpus Christi contam como dia útil até o advogado confirmar a suspensão | Prazos | 0008 |
| 2026-11-24 | Relatório diário às **6h30** (não 7h) | O superprompt prevalece sobre a conversa de origem | — |
| 2026-11-24 | Marcas antigas não usadas em nenhum arquivo | Ordem expressa do superprompt | — |
| 2026-11-24 | Dados institucionais (CNPJ, endereço, telefone, e-mail, WhatsApp) começam vazios e aparecem como pendência no painel | Não inventar dados | — |
| 2026-11-24 | Tipografia: Cormorant Garamond (títulos) + Inter (texto), via `next/font` empacotada no build | Sóbria e profissional, sem chamada a CDN em produção | — |
| 2026-11-24 | PRs #1 e #2 antigos do `sistema-juridico` ficam abertos, sem merge | Cabe ao Baden fechar; ideias reaproveitadas listadas no ADR-0003 | 0003 |
| 2026-11-24 | Recepcionista virtual por regras, sem informar dados de processo pelo chat | Sigilo: o WhatsApp identifica um número, não uma pessoa | 0009 |
| 2026-11-24 | Cadastro do cliente cifrado e relato guardado como escrito, com hash | Prova e fidelidade ao que o cliente declarou | — |
