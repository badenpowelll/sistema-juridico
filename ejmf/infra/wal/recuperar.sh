#!/bin/sh
# Recupera o banco até um instante (PITR): cópia física anterior ao instante + WAL arquivado até ele.
# Uso: recuperar.sh PASTA_DA_COPIA_FISICA PASTA_DE_DADOS_VAZIA "2026-11-24 14:30:00-03" [PASTA_DO_WAL]
# Depois: suba um PostgreSQL 16 com essa pasta de dados. Ele aplica o WAL até o instante, promove e passa a aceitar
# escrita. Confira os dados antes de apontar o EJMF para ele (BACKUP.md).
set -eu
BASE="$1"; DADOS="$2"; INSTANTE="$3"; WAL="${4:-/wal/arquivo}"
[ -f "$BASE/base.tar.gz" ] || { echo "cópia física não encontrada em $BASE" >&2; exit 2; }
if [ -d "$DADOS" ] && [ -n "$(ls -A "$DADOS")" ]; then echo "$DADOS não está vazia" >&2; exit 2; fi
mkdir -p "$DADOS"; chmod 700 "$DADOS"
tar -xzf "$BASE/base.tar.gz" -C "$DADOS"
cat >> "$DADOS/postgresql.auto.conf" <<CONF
# recuperação a um ponto no tempo (recuperar.sh)
restore_command = 'cp "$WAL/%f" "%p"'
recovery_target_time = '$INSTANTE'
recovery_target_action = 'promote'
archive_mode = 'off'
CONF
touch "$DADOS/recovery.signal"
echo "pronto: suba o PostgreSQL com $DADOS; ele recupera até $INSTANTE e promove"
