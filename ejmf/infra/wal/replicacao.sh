#!/bin/sh
# /docker-entrypoint-initdb.d: só na criação do banco. Permite a cópia física (pg_basebackup) pela rede interna.
set -eu
echo "host replication ${POSTGRES_USER} samenet scram-sha-256" >> "$PGDATA/pg_hba.conf"
