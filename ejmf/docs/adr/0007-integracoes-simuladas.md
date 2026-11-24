# ADR-0007 — Conectores padronizados e adaptadores simulados identificados

- Status: aceito · Data: 2026-11-24

## Decisão
Toda fonte externa implementa a mesma interface (`Conector`: `verificar_saude()`, `sincronizar(desde)`, metadados de limites) e tem um registro na tabela `integracoes` com um dos estados oficiais: `implementada_validada`, `ambiente_testes`, `aguardando_credenciais`, `aguardando_autorizacao`, `indisponivel`, `nao_implementada`. Adaptadores simulados têm `simulado = true`, prefixo `Simulado` no nome, selo visível na interface e **nunca** geram registros sem a marca `origem = 'simulado'`.
