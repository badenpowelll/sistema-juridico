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
| Google Calendar | Aguardando credenciais | Idem | 4 |
| WhatsApp Business (Cloud API) | Aguardando credenciais | Conta Meta Business verificada (CNPJ) | 5 |
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
