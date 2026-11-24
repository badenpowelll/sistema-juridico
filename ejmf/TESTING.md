# TESTING

Regra: nada é declarado concluído sem evidência. Cada fase registra aqui o comando, a data e o resultado real.

## Como rodar
```bash
# backend (precisa de um PostgreSQL; o docker compose sobe um)
cd ejmf/backend && pytest -q
# frontend
cd ejmf/frontend && npm run build && npm run test:e2e
```

## Resultados por fase
### Fase 1 — 2026-11-24 (ambiente local, PostgreSQL 16 + pgvector em Docker)
| Comando | Resultado |
|---|---|
| `cd backend && pytest -q` | **42 passed** (segurança, autenticação, MFA, bloqueio, rate limit, CSRF, RBAC, auditoria encadeada e imutável, painel, configurações) |
| `cd frontend && npm run lint && npx tsc --noEmit` | sem erros |
| `cd frontend && npm run build` | build de produção concluído |
| `cd frontend && npm run test:e2e` | **15 passed, 1 skipped** (8 cenários × desktop e celular Pixel 7; o cenário de MFA roda só no desktop por usar conta própria) |
| `docker compose up` + `criar-admin` + login via `:3000/api/v1/auth/login` | API e banco *healthy*, worker com batimento, web servindo, login e painel respondendo, `verificar-auditoria` íntegra |

Cenários E2E: página pública; login inválido; login → painel com "O que exige minha atenção agora"; indicadores de módulos futuros mostram a fase e não "0"; operador não vê menus de administração; configurações institucionais começam vazias e são editáveis; integração não pode ser marcada como validada manualmente; ativação de MFA e login com segundo fator.

Observação do ambiente de desenvolvimento: o `docker build` desta máquina passa por um proxy com certificado próprio; as imagens foram construídas injetando esse certificado num contexto temporário, sem alterar os Dockerfiles versionados. Em máquina comum, `docker compose up --build` funciona direto.

CI: `.github/workflows/ejmf.yml` roda os mesmos testes (backend + E2E) em cada PR que toca `ejmf/`.
