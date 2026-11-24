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
(preenchido ao final de cada fase)
