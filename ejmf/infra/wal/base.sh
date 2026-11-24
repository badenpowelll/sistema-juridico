#!/bin/sh
# Cópia física (pg_basebackup) e limpeza do WAL que nenhuma cópia física guardada ainda precisa.
# Uso: base.sh            (uma vez)        base.sh --diario HH:MM   (laço: todo dia no horário, fuso do contêiner)
# Variáveis: PGHOST, PGUSER, PGPASSWORD (usuário com REPLICATION), WAL_DIR (padrão /wal), WAL_BASES (padrão 7).
set -eu
WAL_DIR="${WAL_DIR:-/wal}"
MANTER="${WAL_BASES:-7}"

uma() {
  nome="base-$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -p "$WAL_DIR/bases"
  pg_basebackup -D "$WAL_DIR/bases/$nome.parcial" -Ft -z -X none --checkpoint=fast --label="$nome" --no-password
  mv "$WAL_DIR/bases/$nome.parcial" "$WAL_DIR/bases/$nome"
  echo "cópia física $nome concluída"
  # mantém as $MANTER mais recentes; o WAL anterior à mais antiga mantida não serve mais para recuperar
  ls -1d "$WAL_DIR"/bases/base-* 2>/dev/null | grep -v '\.parcial$' | sort | head -n "-$MANTER" | while read -r velha; do
    rm -rf "$velha"; echo "cópia física antiga apagada: $(basename "$velha")"
  done
  mais_antiga="$(ls -1d "$WAL_DIR"/bases/base-* | grep -v '\.parcial$' | sort | head -n 1)"
  rotulo="$(ls -1 "$WAL_DIR"/arquivo/*.backup 2>/dev/null | while read -r f; do
    grep -q "LABEL: $(basename "$mais_antiga")\$" "$f" && basename "$f"; done | head -n 1)"
  if [ -n "$rotulo" ]; then
    pg_archivecleanup "$WAL_DIR/arquivo" "$rotulo"
  else
    echo "aviso: rótulo da cópia mais antiga ainda não arquivado; WAL mantido" >&2
  fi
}

if [ "${1:-}" = "--diario" ]; then
  hora="${2:-03:00}"
  while true; do
    agora="$(date +%H:%M)"
    if [ "$agora" = "$hora" ]; then uma || echo "cópia física falhou" >&2; sleep 61; fi
    sleep 20
  done
else
  uma
fi
