# ADR-0006 — Isolamento por escritório desde o início

- Status: aceito · Data: 2026-11-24

## Decisão
Toda tabela de negócio tem `escritorio_id` (FK) e todas as consultas filtram por ele no serviço. Hoje existe um único escritório (EJMF). Não usamos RLS do Postgres na Fase 1 para não complicar migrações e testes; a decisão será revista na Fase 5 (portal do cliente), quando o isolamento entre **clientes** passa a ser crítico.
