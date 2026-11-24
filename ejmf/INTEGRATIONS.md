# INTEGRATIONS — estado das integrações externas

Estados oficiais: **Implementada e validada · Implementada em ambiente de testes · Aguardando credenciais · Aguardando autorização · Indisponível · Não implementada.** O mesmo estado fica na tabela `integracoes` e aparece no painel.

| Integração | Estado atual | Dependência | Fase |
|---|---|---|---|
| DJEN (comunicações do CNJ) | Implementada em ambiente de testes | API pública, sem credencial; responde 403 fora do Brasil (verificado em 24/11/2026), então o EJMF precisa rodar num servidor no Brasil | 3 |
| DataJud (CNJ) | Aguardando credenciais | Chave pública da wiki do CNJ em `DATAJUD_API_KEY`. Não é canal de intimação: traz só andamentos | 3 |
| Simulado — DJEN | Implementada em ambiente de testes | Só com `EJMF_CONECTORES_SIMULADOS=true`; gera comunicações fictícias marcadas "[SIMULADO — dado fictício]" | 3 |
| Domicílio Judicial Eletrônico | Aguardando autorização | Acesso gov.br/certificado do titular | — |
| PJe / eproc / e-SAJ / PROJUDI | Não implementada | Convênios/MNI; sem contornar captcha | — |
| Gmail institucional | Aguardando credenciais | Projeto Google Cloud + OAuth do escritório | 4 |
| Google Calendar | Aguardando credenciais | Projeto Google Cloud do escritório: `EJMF_GOOGLE_CLIENT_ID`, `EJMF_GOOGLE_CLIENT_SECRET`, `EJMF_GOOGLE_REDIRECT_URI` (…/api/v1/agenda/google/retorno). Conector pronto; sobe para "em testes" ao conectar e para "validada" na primeira sincronização real | 4 |
| Simulado — Google Calendar | Implementada em ambiente de testes | Só com `EJMF_CONECTORES_SIMULADOS=true`; servidor falso em memória com eventos "[SIMULADO — dado fictício]". Não convive com a conta real | 4 |
| WhatsApp Business (Cloud API) | Aguardando credenciais | Conta Meta Business verificada (CNPJ), número e `EJMF_WHATSAPP_TOKEN`, `EJMF_WHATSAPP_PHONE_NUMBER_ID`, `EJMF_WHATSAPP_APP_SECRET`, `EJMF_WHATSAPP_VERIFY_TOKEN`. Conector pronto; sobe para "em testes" no primeiro webhook assinado e para "validada" no primeiro envio aceito | 5 |
| Simulado — WhatsApp | Implementada em ambiente de testes | Só com `EJMF_CONECTORES_SIMULADOS=true`; conversas com nome "[SIMULADO]" e mensagens "simuladas", que nunca saem do sistema | 5 |
| Assinatura eletrônica (Documenso) | Não implementada | Instância própria | 6 |
| Provedores de IA | Aguardando credenciais | Chaves e aprovação de tratamento de dados | 8 |
| Armazenamento S3 (backups) | Aguardando credenciais | Conta em provedor escolhido | 11 |

Regra: um conector só sobe para "Implementada e validada" depois de teste contra a fonte real, registrado em TESTING.md com data e resultado.

## Como os conectores se comportam (Fase 3)
- Agenda: o worker enfileira uma sincronização por fonte às 6 h, 12 h e 18 h (configurável em `controladoria.sincronizacao_horas`), com chave única por horário, então reiniciar o worker não duplica.
- Janela: desde o último sucesso menos 1 dia de sobreposição (3 dias na primeira vez). Itens já capturados são ignorados pelo id da fonte e pelo conteúdo.
- Falhas: 429 respeita o `Retry-After`; 403, 5xx e tempo esgotado reagendam com espera exponencial (1 min a 1 h). Três falhas seguidas abrem o circuito por 15 min, dobrando até 6 h, e a fonte vira "Indisponível". Credencial ausente ou recusada não é tentada de novo.
- Promoção: a primeira sincronização real com sucesso sobe a fonte para "Implementada e validada". Adaptador simulado nunca sobe.
- Contingência: sem sucesso há mais de 26 h (`controladoria.horas_sem_sucesso_alerta`), a fonte é tratada como "monitoramento comprometido" no painel e na Central de contingência, com o procedimento manual. Ausência de informação não é ausência de acontecimentos.

## Google Calendar (Fase 4)
- Escopo único: `https://www.googleapis.com/auth/calendar.events.owned` (só eventos das agendas da conta conectada). OAuth "authorization code" com PKCE S256, `access_type=offline` e `prompt=consent`; o state vale 10 min e é ligado ao usuário que iniciou.
- Sincronização a cada 15 min pelo worker (ou "Sincronizar agora"), incremental por `syncToken`; resposta 410 refaz a carga completa. Usa o mesmo circuit breaker e registro de execução dos outros conectores.
- O EJMF só altera ou apaga eventos que ele criou (marcados com `extendedProperties.private.ejmf_id`). Eventos de fora entram como compromissos "externos", somente leitura; eventos privados aparecem como "Ocupado".
- Audiência movida no Google vira pedido de aprovação; se rejeitado, o horário do EJMF volta para o Google. Outros compromissos movidos no Google são aplicados com histórico. Evento do EJMF apagado no Google não cancela nada: vira pendência.
- Prazos só vão ao Google depois de homologados (evento de dia inteiro); se deixam de estar homologados, o evento sai.
- Token recusado (401) volta o estado para "Aguardando credenciais". Desconectar revoga o token e não apaga nada no Google.

## WhatsApp Business (Fase 5)
- Envio: `POST {EJMF_WHATSAPP_API_URL}/{phone_number_id}/messages` (padrão `https://graph.facebook.com/v23.0`) com o token no cabeçalho `Authorization: Bearer`, mensagem de texto. Cada envio é uma tarefa da fila (`whatsapp.enviar`), com até 4 tentativas e o mesmo tratamento de 429, 5xx e credencial recusada dos outros conectores.
- Recebimento: webhook em `/api/v1/publico/whatsapp/webhook`. A verificação (GET) compara `hub.verify_token`; cada POST precisa da assinatura `X-Hub-Signature-256` (HMAC-SHA256 do corpo com o app secret), senão 403. Corpo limitado a 1 MB. Mensagem repetida (mesmo id da Meta) é ignorada.
- Janela de atendimento: a equipe e a recepcionista só respondem até 24 h depois da última mensagem do contato. Fora dela a Meta só aceita modelos aprovados, ainda não configurados (BACKLOG F5-09).
- O contato é ligado ao cliente pelo telefone só quando há um único cliente com aquele número.
- Arquivos recebidos pelo WhatsApp não são baixados: a recepcionista pede o envio pelo link seguro.
