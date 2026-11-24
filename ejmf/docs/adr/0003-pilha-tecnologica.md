# ADR-0003 — Pilha tecnológica

- Status: aceito · Data: 2026-11-24

## Decisão
| Camada | Escolha | Por quê |
|---|---|---|
| API | Python 3.13 + FastAPI, Pydantic v2, OpenAPI em `/api/v1/openapi.json` | Pedido do superprompt; ecossistema de IA/OCR/dados em Python. |
| ORM e migrações | SQLAlchemy 2 + Alembic, psycopg 3 | Migrações versionadas, transações explícitas. |
| Banco | PostgreSQL 16 + pgvector (imagem `pgvector/pgvector:pg16`) | Relacional, busca textual (`tsvector`, `unaccent`, `pg_trgm`) e vetorial no mesmo lugar, com o mesmo controle de acesso. |
| Filas e agendamento | **Fila em PostgreSQL** (`SELECT … FOR UPDATE SKIP LOCKED`) com worker Python separado; Redis só se medirmos necessidade | Uma peça a menos para operar e fazer backup; idempotência e reprocessamento ficam em SQL e auditáveis. Temporal descartado por custo (RESEARCH). |
| Interface | Next.js (App Router) + React + TypeScript + Tailwind CSS, componentes próprios acessíveis no estilo shadcn/ui | Pedido do superprompt; PWA na Fase 10. |
| Comunicação web↔API | O Next.js faz *proxy* de `/api/*` para a FastAPI (mesma origem) | Cookie de sessão `HttpOnly; SameSite=Lax` sem CORS aberto. |
| Contêineres | Docker Compose (db, api, worker, web) | Mesmo ambiente em dev, homologação e produção. |

## Alternativa considerada
O PR #2 do `sistema-juridico` (Node 22 + Hono + React/Vite, Railway) ainda está aberto. Foi substituído por esta pilha porque o superprompt pede FastAPI/Next.js e o ecossistema Python para IA/OCR. Ideias reaproveitadas daquele PR: sessão com hash do token no banco, auditoria imutável por gatilho, sincronização com OneDrive (vai para a Fase 6). O PR fica aberto para o Baden decidir se fecha.
