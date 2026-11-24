#!/bin/sh
# Chamado pelo PostgreSQL (archive_command = '/infra/wal/arquivar.sh %p %f') a cada segmento de WAL completo.
# Grava em $WAL_DIR/arquivo sem sobrescrever: se o segmento já existe e é igual, confirma; se é diferente, falha
# (o PostgreSQL guarda o segmento e tenta de novo, e o painel mostra "archive_mode" com falhas em pg_stat_archiver).
set -eu
ORIGEM="$1"; NOME="$2"
DESTINO="${WAL_DIR:-/wal}/arquivo"
mkdir -p "$DESTINO"
if [ -f "$DESTINO/$NOME" ]; then
  cmp -s "$ORIGEM" "$DESTINO/$NOME" && exit 0
  echo "segmento $NOME já arquivado com conteúdo diferente" >&2
  exit 1
fi
cp "$ORIGEM" "$DESTINO/$NOME.parcial"
sync "$DESTINO/$NOME.parcial" 2>/dev/null || sync
mv "$DESTINO/$NOME.parcial" "$DESTINO/$NOME"
