# OPERATIONS — rotina e contingência

## Rotina diária (automatizada a partir da Fase 4)
- 06h30 (America/Fortaleza): relatório da secretária virtual.
- Antes do expediente: conferir o bloco "O que exige minha atenção agora".
- Fim do expediente (horário configurável): relatório de encerramento.
- 02h00: cópia de segurança cifrada; a cada 7 dias, teste de restauração 30 minutos depois (Fase 11).
- Semanal (pessoa): conferir em Cópias de segurança que a última restauração foi aprovada e copiar a pasta de cópias para fora do servidor enquanto não houver cópia externa.

## Contingência
| Situação | Procedimento manual |
|---|---|
| Fonte judicial indisponível | O painel mostra "monitoramento comprometido". Consultar manualmente o portal da fonte (ex.: comunica.pje.jus.br) para a OAB 12.114/RN no período sem sincronização. **Ausência de dados não significa ausência de intimações.** |
| Sistema fora do ar | Usar os portais oficiais dos tribunais e a agenda do Google; registrar o que foi feito para lançar depois. |
| Suspeita de incidente de segurança | Revogar todas as sessões (`/configuracoes/sessoes`), trocar `EJMF_CHAVE_SECRETA`, verificar a cadeia de auditoria, comunicar o responsável. |
| Banco corrompido ou servidor perdido | Restaurar a última cópia com restauração aprovada, num banco vazio, com `python -m app.cli restaurar` (passo a passo em BACKUP.md). |
| Cópia de segurança atrasada ou teste reprovado | Abrir Cópias de segurança, ver o motivo, pedir "Fazer cópia agora" e "Testar restauração". Se falhar de novo: conferir espaço em disco, a chave `EJMF_BACKUP_CHAVE` e o cliente do PostgreSQL. |
| Antivírus fora do ar | Os arquivos recebidos vão para a quarentena com "Varredura de vírus pendente". Volte o clamd e libere cada arquivo depois de verificá-lo. |
