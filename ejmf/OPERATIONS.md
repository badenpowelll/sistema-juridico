# OPERATIONS — rotina e contingência

## Rotina diária (automatizada a partir da Fase 4)
- 06h30 (America/Fortaleza): relatório da secretária virtual.
- Antes do expediente: conferir o bloco "O que exige minha atenção agora".
- Fim do expediente (horário configurável): relatório de encerramento.

## Contingência
| Situação | Procedimento manual |
|---|---|
| Fonte judicial indisponível | O painel mostra "monitoramento comprometido". Consultar manualmente o portal da fonte (ex.: comunica.pje.jus.br) para a OAB 12.114/RN no período sem sincronização. **Ausência de dados não significa ausência de intimações.** |
| Sistema fora do ar | Usar os portais oficiais dos tribunais e a agenda do Google; registrar o que foi feito para lançar depois. |
| Suspeita de incidente de segurança | Revogar todas as sessões (`/configuracoes/sessoes`), trocar `EJMF_CHAVE_SECRETA`, verificar a cadeia de auditoria, comunicar o responsável. |
| Banco corrompido | Restaurar o último backup testado (BACKUP.md). |
