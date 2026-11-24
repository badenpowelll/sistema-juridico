#!/bin/sh
# Ensaio real de recuperação a um ponto no tempo, com contêineres descartáveis (só dados sintéticos).
# Uso: infra/wal/testar.sh   (precisa de Docker e da imagem pgvector/pgvector:pg16)
set -eu
AQUI="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"; chmod 755 "$TMP"; REDE="ejmf-wal-teste-$$"; DB="ejmf-wal-db-$$"; REC="ejmf-wal-rec-$$"; IMG=pgvector/pgvector:pg16
limpar() { docker rm -f "$DB" "$REC" >/dev/null 2>&1 || true; docker network rm "$REDE" >/dev/null 2>&1 || true
           docker run --rm -v "$TMP:/t" "$IMG" sh -c 'rm -rf /t/*' >/dev/null 2>&1 || true; rm -rf "$TMP"; }
trap limpar EXIT
mkdir -p "$TMP/wal"; chmod 777 "$TMP/wal"
docker network create "$REDE" >/dev/null
docker run -d --name "$DB" --network "$REDE" -e POSTGRES_USER=ejmf -e POSTGRES_PASSWORD=sintetica -e POSTGRES_DB=ejmf_db \
  -e WAL_DIR=/wal -v "$TMP/wal:/wal" -v "$AQUI:/infra/wal:ro" -v "$AQUI/replicacao.sh:/docker-entrypoint-initdb.d/replicacao.sh:ro" \
  "$IMG" -c wal_level=replica -c archive_mode=on -c "archive_command=/infra/wal/arquivar.sh %p %f" -c archive_timeout=60 >/dev/null
until docker exec "$DB" pg_isready -q -U ejmf -d ejmf_db 2>/dev/null; do sleep 1; done; sleep 2
psql() { docker exec -i "$DB" psql -qtAX -U ejmf -d ejmf_db -c "$1"; }
until psql "select 1" >/dev/null 2>&1; do sleep 1; done
psql "create table processos_sinteticos (id serial primary key, numero text not null, criado_em timestamptz default now())"
psql "insert into processos_sinteticos (numero) select 'SINT-' || g from generate_series(1, 100) g"
base() { docker run --rm --network "$REDE" -e PGHOST="$DB" -e PGUSER=ejmf -e PGPASSWORD=sintetica -e WAL_DIR=/wal \
  -e WAL_BASES=1 -v "$TMP/wal:/wal" -v "$AQUI:/infra/wal:ro" "$IMG" /infra/wal/base.sh; }
base
for i in 1 2 3; do psql "insert into processos_sinteticos (numero) values ('troca-$i')"; psql "delete from processos_sinteticos where numero = 'troca-$i'"
  psql "select pg_switch_wal()" >/dev/null; done; sleep 3
antes="$(ls "$TMP/wal/arquivo" | grep -c -v backup)"
inicio=$(date +%s)
base
echo "cópia física em $(( $(date +%s) - inicio )) s"
sleep 2; depois_limpeza="$(ls "$TMP/wal/arquivo" | grep -c -v backup)"; bases="$(ls -1d "$TMP"/wal/bases/base-* | wc -l)"
echo "retenção (1 cópia física): $bases cópia(s) física(s); segmentos de WAL $antes -> $depois_limpeza"
[ "$bases" = "1" ] && [ "$depois_limpeza" -lt "$antes" ] || { echo "REPROVADO: retenção" >&2; exit 1; }
psql "insert into processos_sinteticos (numero) select 'SINT-' || g from generate_series(101, 150) g"
sleep 2; ALVO="$(psql "select to_char(now(), 'YYYY-MM-DD HH24:MI:SS.US TZH')")"; sleep 2
psql "insert into processos_sinteticos (numero) select 'DEPOIS-' || g from generate_series(1, 30) g"
psql "select pg_switch_wal()" >/dev/null; sleep 3
echo "arquivados: $(psql "select archived_count from pg_stat_archiver") segmentos, falhas: $(psql "select failed_count from pg_stat_archiver")"
docker stop "$DB" >/dev/null   # o servidor original "se perde"
BASE="$(ls -1d "$TMP"/wal/bases/base-* | head -n 1)"
docker run --rm -v "$TMP:/t" -v "$AQUI:/infra/wal:ro" "$IMG" sh -c \
  "/infra/wal/recuperar.sh /t/wal/bases/$(basename "$BASE") /t/recuperado '$ALVO' /t/wal/arquivo && chown -R postgres:postgres /t/recuperado"
inicio=$(date +%s)
docker run -d --name "$REC" -v "$TMP:/t" -v "$TMP/wal:/wal" -e PGDATA=/t/recuperado "$IMG" >/dev/null
until docker exec "$REC" pg_isready -q -U ejmf 2>/dev/null && \
      [ "$(docker exec "$REC" psql -qtAX -U ejmf -d ejmf_db -c 'select pg_is_in_recovery()' 2>/dev/null)" = "f" ]; do
  sleep 1; [ $(( $(date +%s) - inicio )) -gt 120 ] && { docker logs "$REC"; echo "recuperação não terminou" >&2; exit 1; }
done
echo "recuperado em $(( $(date +%s) - inicio )) s até $ALVO"
total="$(docker exec "$REC" psql -qtAX -U ejmf -d ejmf_db -c "select count(*) from processos_sinteticos")"
depois="$(docker exec "$REC" psql -qtAX -U ejmf -d ejmf_db -c "select count(*) from processos_sinteticos where numero like 'DEPOIS-%'")"
echo "linhas recuperadas: $total (esperado 150); posteriores ao instante: $depois (esperado 0)"
[ "$total" = "150" ] && [ "$depois" = "0" ] || { echo "REPROVADO" >&2; exit 1; }
docker exec "$REC" psql -qtAX -U ejmf -d ejmf_db -c "insert into processos_sinteticos (numero) values ('escrita-apos-promover')" >/dev/null
echo "APROVADO: recuperação a um ponto no tempo com escrita liberada depois de promover"
