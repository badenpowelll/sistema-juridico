# INTEGRATIONS — estado das integrações externas

Estados oficiais: **Implementada e validada · Implementada em ambiente de testes · Aguardando credenciais · Aguardando autorização · Indisponível · Não implementada.** O mesmo estado fica na tabela `integracoes` e aparece no painel.

| Integração | Estado atual | Dependência | Fase |
|---|---|---|---|
| DJEN (comunicações do CNJ) | Não implementada | API pública, sem credencial; exigir servidor no Brasil | 3 |
| DataJud (CNJ) | Não implementada | Chave pública da wiki do CNJ em `DATAJUD_API_KEY` | 3 |
| Domicílio Judicial Eletrônico | Aguardando autorização | Acesso gov.br/certificado do titular | — |
| PJe / eproc / e-SAJ / PROJUDI | Não implementada | Convênios/MNI; sem contornar captcha | — |
| Gmail institucional | Aguardando credenciais | Projeto Google Cloud + OAuth do escritório | 4 |
| Google Calendar | Aguardando credenciais | Idem | 4 |
| WhatsApp Business (Cloud API) | Aguardando credenciais | Conta Meta Business verificada (CNPJ) | 5 |
| Assinatura eletrônica (Documenso) | Não implementada | Instância própria | 6 |
| Provedores de IA | Aguardando credenciais | Chaves e aprovação de tratamento de dados | 8 |
| Armazenamento S3 (backups) | Aguardando credenciais | Conta em provedor escolhido | 11 |

Regra: um conector só sobe para "Implementada e validada" depois de teste contra a fonte real, registrado em TESTING.md com data e resultado.
