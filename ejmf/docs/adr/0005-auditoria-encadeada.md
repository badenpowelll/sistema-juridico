# ADR-0005 — Auditoria encadeada e imutável

- Status: aceito · Data: 2026-11-24

## Decisão
Tabela `auditoria` só aceita `INSERT` (gatilho bloqueia `UPDATE`/`DELETE`/`TRUNCATE`). Cada registro guarda `hash = SHA-256(hash_anterior || conteúdo canônico)`. O endpoint `/api/v1/auditoria/verificar` recalcula a cadeia e aponta o primeiro registro adulterado. Segredos e dados sensíveis são mascarados antes de gravar (`app/servicos/auditoria.py`).

## Consequências
Adulteração direta no banco é detectável; quem tem superusuário do banco ainda pode desligar o gatilho, por isso a verificação periódica e a cópia do último hash no backup (BACKUP.md).
