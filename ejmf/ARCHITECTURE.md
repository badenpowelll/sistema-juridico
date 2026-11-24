# ARCHITECTURE — Escritório Jurídico Márcio Fernandes (EJMF)

Monólito modular + worker, um único PostgreSQL. Decisões em `docs/adr/`.

```
                    ┌──────────────────────────── navegador / PWA ───────────────────────────┐
                    │  site público (/)   ·   central do advogado (/painel)   ·   portal (/portal) │
                    └──────────────────────────────────┬──────────────────────────────────────┘
                                                       │ HTTPS (mesma origem)
                                  ┌────────────────────▼───────────────────┐
                                  │  web: Next.js (App Router, TS, Tailwind) │
                                  │  /api/*  →  proxy para a API            │
                                  └────────────────────┬───────────────────┘
                                                       │
     ┌─────────────────────────────────────────────────▼─────────────────────────────────────────────┐
     │ api: FastAPI  /api/v1  (OpenAPI)                                                               │
     │  core: config · seguranca (Argon2id, sessões, TOTP, RBAC) · banco · logs JSON · trace-id      │
     │  módulos: autenticacao · usuarios · escritorio/config · departamentos · auditoria · painel    │
     │           processos · clientes · importacao · publicacoes · prazos · agenda · documentos ...  │
     │  conectores (interface única): DataJud · DJEN · Gmail · Google Calendar · WhatsApp · ...      │
     └───────────────┬───────────────────────────────────────────────────────────┬───────────────────┘
                     │ SQL (transações)                                          │ enfileira tarefas
     ┌───────────────▼──────────────────────────┐            ┌───────────────────▼──────────────────┐
     │ db: PostgreSQL 16 + pgvector             │◄──────────►│ worker: Python                        │
     │  dados · auditoria encadeada · fila      │  SKIP LOCKED│  agendador (America/Fortaleza)        │
     │  (tarefas_fila) · índices FTS/trigram   │            │  sincronizações, relatórios, OCR, IA  │
     └──────────────────────────────────────────┘            └───────────────────────────────────────┘
                     │ pg_dump cifrado (BACKUP.md)
                     ▼
            armazenamento separado (S3 compatível, privado)
```

## Princípios aplicados

| Requisito do superprompt | Como a arquitetura atende |
|---|---|
| Monólito modular, sem microsserviços prematuros | Um pacote `app/` com módulos por domínio; o worker usa o mesmo código. |
| Eventos, assíncrono, idempotência, repetição segura | Tabela `tarefas_fila` com `chave_idempotencia` única, tentativas, *backoff* exponencial e fila de falhas (`estado = 'falha_definitiva'`). Fase 3. |
| Circuit breaker e rate limit por fonte | No `Conector` base: janela de erros abre o circuito; respeita 429/`Retry-After`. Fase 3. |
| Feature flags | Tabela `configuracoes` (chave `flag.*`) por escritório. |
| Logs estruturados e rastreamento | Logs JSON com `trace_id` por requisição (cabeçalho `X-Trace-Id`), gravado também na auditoria. |
| Ambientes separados | `EJMF_AMBIENTE=desenvolvimento|homologacao|producao`; produção exige `Secure` cookie, MFA e chave secreta forte. |
| Troca de provedores sem reescrever | Interfaces `Conector`, `ProvedorIA`, `Armazenamento`, `Notificador`. |
| Determinismo em datas críticas | Motor de prazos puro em Python, com regras versionadas no banco e memória de cálculo. Fase 3. |
| IA nunca decide sozinha o crítico | Política de autonomia níveis 0–4 (seção 45) aplicada no orquestrador e nas rotas (Fase 8, ADR-0012): permissões da execução = catálogo ∩ nível ∩ quem pediu; nível 3 vira aprovação; nível 4 nunca roda; saída validada contra o material. |

## Módulos e fases

| Módulo | Fase |
|---|---|
| Autenticação, usuários, perfis/permissões, sessões, MFA | 1 |
| Escritório, configurações institucionais, marca | 1 |
| Departamentos configuráveis | 1 |
| Auditoria encadeada | 1 |
| Registro de integrações (estado oficial) | 1 |
| Painel "O que exige minha atenção agora" | 1 (base) e evolui a cada fase |
| Processos, clientes, partes, movimentações, linha do tempo, importação em massa, pesquisa global | 2 |
| Publicações/intimações, conectores DataJud e DJEN, motor de prazos, alertas, contingência | 3 |
| Agenda/Google Calendar, Gmail, secretária (relatório 6h30), prioridades, aprovações | 4 |
| CRM, links de cadastro, entrevista, portal do cliente, recepcionista, WhatsApp | 5 |
| Documentos, OCR, modelos, editor, minutas, assinatura | 6 |
| Biblioteca, jurisprudência, verificação de referências, RAG | 7 |
| Orquestrador e 40 funções, MCP, assistente, custos de IA | 8 |
| Financeiro: lançamentos, honorários, recibos, conciliação por extrato importado, fluxo e rentabilidade (ADR-0013) | 9 |
| PWA instalável sem dados guardados no aparelho, notificações Web Push genéricas, voz opcional no assistente (ADR-0014) | 10 |

## Estrutura de pastas

```
ejmf/
  backend/            FastAPI (app/), migrações Alembic (migracoes/), testes (tests/)
  frontend/           Next.js (src/app, src/marca, src/componentes)
  docs/adr/           decisões arquiteturais
  docs/origem/        superprompt (especificação permanente)
  docker-compose.yml  db · api · worker · web
  *.md                documentação obrigatória
```

## IA (Fase 8)

```
 tela / assistente / automação / agendador
            │ solicitar(função, entrada, escopo)          servidor MCP (/api/v1/mcp, token pessoal)
            ▼                                                        │ só leitura
   orquestrador ── chave, função ligada, permissões ──► fila "ia.executar"      │
            │                                                        ▼
            ▼                                              ferramentas de leitura (escopo no SQL)
   executor da função ─► ferramentas de leitura ─► provedor (Anthropic SDK · compatível OpenAI · simulado)
            │        guardas antes de cada chamada: modelo aprovado, preço, tetos, orçamento, iterações, tempo
            ▼
   validação própria (trecho literal, data no trecho, citação existente) ─► sugestão · aprovação (nível 3)
            │
   ia_execucoes + ia_passos (versão da instrução, modelo, tokens, custo) + auditoria
```
