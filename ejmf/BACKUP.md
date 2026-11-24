# BACKUP — cópias e recuperação

> Situação: **procedimento definido; automação e teste de restauração na Fase 11.** Um backup só conta como confiável depois de um teste de restauração registrado em TESTING.md.

- **O quê:** `pg_dump -Fc` do `ejmf_db` + arquivos do armazenamento privado.
- **Cifra:** `age` ou `gpg` com chave guardada fora do servidor.
- **Onde:** armazenamento S3 compatível em outro provedor (separado do servidor).
- **Frequência e retenção (proposta):** diário, 30 diários + 12 mensais.
- **Integridade:** guardar SHA-256 do arquivo e o último hash da cadeia de auditoria.
- **RPO/RTO propostos:** RPO 24 h (meta 1 h com WAL na Fase 11) · RTO 4 h.
- **Teste de restauração:** mensal, restaurando em banco descartável e conferindo contagens e a cadeia de auditoria.
