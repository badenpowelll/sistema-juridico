# DATABASE

PostgreSQL 16 (`ejmf_db`) com extensões `pgcrypto`, `citext`, `pg_trgm`, `unaccent` (e `vector` a partir da Fase 7). Migrações Alembic em `backend/migracoes/`. Toda tabela de negócio tem `escritorio_id` (ADR-0006).

## Fase 1

```
escritorios 1─┬─< usuarios >─┬─< usuario_perfis >── perfis ──< perfil_permissoes >── permissoes
              │              └─< sessoes
              ├─< departamentos
              ├─< configuracoes   (chave/valor JSON: dados institucionais, flags)
              ├─< integracoes     (estado oficial de cada fonte)
              └─< auditoria       (só inserção, hash encadeado)
```

| Tabela | Observações |
|---|---|
| `escritorios` | Um registro hoje (EJMF). |
| `usuarios` | `email` citext único por escritório; `senha_hash` Argon2id; `mfa_segredo` cifrado; `falhas_login`, `bloqueado_ate`. |
| `perfis`, `permissoes`, `perfil_permissoes`, `usuario_perfis` | RBAC. Permissão = `recurso:acao`. |
| `sessoes` | `token_hash` (SHA-256), `expira_em`, `ultimo_uso_em`, `revogada_em`, IP e agente. |
| `departamentos` | 18 áreas + "Outras" semeadas; `ativo`, `ordem`. |
| `configuracoes` | Dados institucionais começam `null` (não inventados). |
| `integracoes` | `estado` restrito aos seis valores oficiais; `simulado`; `ultima_execucao_em`, `ultimo_sucesso_em`, `ultimo_erro`. |
| `auditoria` | `ator_tipo` (usuario/agente/sistema), `operacao`, `entidade`, `entidade_id`, `alteracoes` JSON mascarado, `resultado`, `trace_id`, `hash_anterior`, `hash`. Gatilho bloqueia UPDATE/DELETE/TRUNCATE. |

As tabelas das fases seguintes são documentadas aqui quando a migração correspondente é criada.
