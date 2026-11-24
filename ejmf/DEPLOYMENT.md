# DEPLOYMENT

> **Nenhuma implantação externa foi feita nem será feita sem autorização expressa do responsável.**

## Desenvolvimento local
```bash
cd ejmf
cp .env.example .env          # ajuste os valores
docker compose up --build     # db, api, worker, web
docker compose exec api python -m app.cli criar-admin --email voce@exemplo.com
```
- Web: http://localhost:3000 · API: http://localhost:8000/api/v1/docs

## Produção (Fase 12, depois de autorizada)
- 1 VPS no Brasil (ver COSTS), Docker Compose, proxy reverso com TLS (Caddy), backups externos (BACKUP.md), monitor externo (Uptime Kuma).
- `EJMF_AMBIENTE=producao` ativa cookie `Secure`, MFA obrigatório para administrador e exige chave secreta forte.
- Migrações rodam no início do contêiner da API (`alembic upgrade head`).
