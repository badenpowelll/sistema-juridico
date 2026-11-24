#!/usr/bin/env bash
# Sobe a API para os testes E2E num banco descartável (dados 100% sintéticos).
set -euo pipefail
PORTA="${1:-8010}"
ADMIN_URL="${EJMF_E2E_DB_ADMIN:-postgresql://ejmf:ejmf@localhost:5433/postgres}"
cd "$(dirname "$0")/../backend"
[ -d .venv ] && . .venv/bin/activate
psql "$ADMIN_URL" -qc 'DROP DATABASE IF EXISTS ejmf_e2e WITH (FORCE)' -c 'CREATE DATABASE ejmf_e2e'
export EJMF_DATABASE_URL="${ADMIN_URL%/postgres}/ejmf_e2e"
EJMF_DATABASE_URL="postgresql+psycopg://${EJMF_DATABASE_URL#postgresql://}"
export EJMF_DATABASE_URL EJMF_AMBIENTE=teste EJMF_CHAVE_SECRETA="e2e-chave-sintetica-0000000000000000000000"
alembic upgrade head
python -m app.cli semear >/dev/null
EJMF_SENHA_INICIAL="senha-e2e-sintetica" python -m app.cli criar-admin --email advogado.e2e@example.com --nome "Advogado Sintético" >/dev/null
EJMF_SENHA_INICIAL="senha-e2e-sintetica" python -m app.cli criar-admin --email operador.e2e@example.com --nome "Operador Sintético" --perfil operador >/dev/null
EJMF_SENHA_INICIAL="senha-e2e-sintetica" python -m app.cli criar-admin --email mfa.e2e@example.com --nome "Usuário MFA Sintético" --perfil operador >/dev/null
export EJMF_LOGIN_LIMITE_POR_MINUTO_IP=500  # todos os testes saem do mesmo IP
exec uvicorn app.main:app --port "$PORTA" --log-level warning
