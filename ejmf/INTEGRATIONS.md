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
| Assinatura eletrônica (Documenso) | Aguardando credenciais | Conta no Documenso (nuvem ou instância própria): `EJMF_DOCUMENSO_TOKEN`, `EJMF_DOCUMENSO_URL` e `EJMF_DOCUMENSO_WEBHOOK_SECRET`. Conector pronto; sobe para "em testes" no primeiro envio aceito ou webhook com o segredo. **Sem adaptador simulado** (ADR-0010) | 6 |
| OCR e conversão (Tesseract, Poppler, LibreOffice) | Implementada e validada | Programas locais, sem serviço externo nem custo; instalados na imagem Docker e no CI | 6 |
| Monitor legislativo (fontes oficiais e LexML) | Implementada em ambiente de testes | Sem credencial. Consulta diária (5h) só aos domínios oficiais cadastrados; busca no LexML pelo SRU público. Testado com respostas gravadas; a rede deste ambiente de desenvolvimento bloqueia planalto.gov.br e lexml.gov.br, então **não foi validado contra a fonte real** | 7 |
| Verificador de jurisprudência | Implementada em ambiente de testes | Sem credencial. Baixa o original só do site oficial do tribunal (lista em `fontes_conhecimento`). Testado com páginas gravadas; **não validado contra os sites reais** (bloqueados na rede deste ambiente). Páginas montadas por JavaScript ou atrás de captcha ficam "fonte indisponível" | 7 |
| Anthropic (Claude) | Aguardando credenciais | `EJMF_ANTHROPIC_API_KEY`; o modelo só é usado depois de cadastrado com preço e aprovado pelo advogado (retenção conferida) e com tetos de gasto definidos. SDK oficial `anthropic` 2.7.0. Testado com respostas gravadas; **não chamado de verdade** neste ambiente | 8 |
| IA compatível com a API da OpenAI (OpenAI, Gemini, servidor local) | Aguardando credenciais | `EJMF_IA_OPENAI_COMPATIVEL_URL` e `EJMF_IA_OPENAI_COMPATIVEL_CHAVE` (HTTPS em produção); mesmas exigências de aprovação e tetos | 8 |
| Simulado — IA | Implementada em ambiente de testes | Só com `EJMF_IA_SIMULADO=true`; respostas determinísticas, custo zero, toda saída começa com "[SIMULADO]" | 8 |
| Servidor MCP do EJMF (somente leitura) | Implementada em ambiente de testes | `POST /api/v1/mcp` (JSON-RPC, versões 2025-06-18, 2025-03-26 e 2024-11-05) com token pessoal `Authorization: Bearer ejmf_mcp_…` criado em Inteligência artificial; permissão `ia:mcp` | 8 |
| Notificações no celular (Web Push) | Aguardando credenciais | Chaves VAPID geradas no próprio servidor (`python -m app.cli gerar-vapid`) em `EJMF_VAPID_CHAVE_PUBLICA` e `EJMF_VAPID_CHAVE_PRIVADA`, mais `EJMF_VAPID_CONTATO` (mailto: ou endereço público) e o EJMF em HTTPS. Sem custo; o conteúdo é genérico (ADR-0014) | 10 |
| Reconhecimento de voz do navegador | Implementada em ambiente de testes | Web Speech API do Chrome/Edge/Safari; o áudio vai ao fabricante do navegador, por isso fica desligado até o advogado ligar (ADR-0014) | 10 |
| Cópias de segurança locais cifradas | Implementada em ambiente de testes | `EJMF_BACKUP_CHAVE` (gerada com `python -m app.cli gerar-chave-backup`) e `EJMF_BACKUP_DIR`; cliente do PostgreSQL (pg_dump/pg_restore) no servidor; teste de restauração automático (ADR-0015) | 11 |
| Armazenamento S3 (cópia externa) | Aguardando credenciais | Conta em provedor escolhido pelo escritório | 11 |
| Antivírus (ClamAV, clamd) | Aguardando credenciais | Instalar o ClamAV com assinaturas atualizadas (freshclam) e definir `EJMF_CLAMAV_ENDERECO`; validado aqui contra o clamd real com uma assinatura de teste local, porque o servidor de assinaturas não é alcançável | 11 |

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

## Documenso (Fase 6)
- API v2 (documentação oficial consultada em 24/11/2026): `POST {EJMF_DOCUMENSO_URL}/envelope/create` em multipart, com o campo `payload` (tipo DOCUMENT, título, `externalId` = id do pedido no EJMF, participantes com papel SIGNER, APPROVER, CC ou VIEWER, ordem e campos de assinatura e data) e o PDF em `files`; depois `POST /envelope/distribute` com o `envelopeId`. Chave da API no cabeçalho `Authorization`.
- Os campos de assinatura e data ficam no pé da última página, dois por linha, só para quem assina.
- Cada envio é uma tarefa da fila (`assinatura.enviar`), com até 3 tentativas; numa nova tentativa o envelope já criado é reaproveitado. 401 marca o pedido como "falha" e a integração volta para "Aguardando credenciais".
- Webhook em `/api/v1/publico/documenso/webhook`: o segredo chega no cabeçalho `X-Documenso-Secret` e é comparado em tempo constante; sem segredo configurado, tudo é recusado (403). Eventos tratados: DOCUMENT_SENT, DOCUMENT_OPENED, DOCUMENT_SIGNED, DOCUMENT_RECIPIENT_COMPLETED, DOCUMENT_COMPLETED, DOCUMENT_REJECTED e DOCUMENT_CANCELLED. O pedido é achado pelo `externalId` ou pelo id do envelope; evento de outro envelope é ignorado.
- Conclusão, recusa e cancelamento geram notificação para quem pode enviar assinaturas. O PDF assinado é guardado como nova versão manualmente (F6-09).

## OCR e extração (Fase 6)
- PDF: `pdftotext` primeiro; com menos de 40 caracteres por página, a página vira imagem (`pdftoppm`, 200 dpi, tons de cinza) e passa pelo Tesseract em português. Até 30 páginas por arquivo (`documentos.ocr_max_paginas`).
- Imagens (PNG, JPG, TIFF, WebP): Tesseract direto. Confiança média abaixo de 45 (`documentos.ocr_confianca_minima`) marca "leitura duvidosa".
- Word e Excel: python-docx e openpyxl (sem fórmulas nem macros). Texto e CSV: lidos direto.
- Cada ferramenta roda num subprocesso sem shell, numa pasta temporária, com 120 s e 1 GB de memória no máximo. Sem o Tesseract instalado, o arquivo fica "OCR indisponível", sem texto inventado.
- DOCX → PDF: LibreOffice sem interface, com perfil temporário e 120 s no máximo. Sem LibreOffice, a aprovação guarda o DOCX e a assinatura eletrônica fica indisponível para aquela minuta.

## Monitor legislativo e LexML (Fase 7)
- O monitor consulta, uma vez por dia a partir de `conhecimento.monitor_hora` (padrão 05:00), cada item marcado para monitorar. Só endereços HTTPS de domínios cadastrados em `fontes_conhecimento` saem da rede; redirecionamento para fora deles é recusado.
- A página vira texto simples. O texto riscado (`<strike>`, `<s>`, `<del>`), como o Planalto marca dispositivos revogados, é separado e não entra no texto coletado; script, estilo e navegação também ficam de fora.
- Texto diferente do último coletado (pelo SHA-256) vira versão nova **a conferir**; o texto em uso continua o anterior até alguém com `biblioteca:conferir` aceitar a versão. Ao aceitar, a vigência volta para "a conferir".
- 401, 403 e 429 são tratados como "fonte indisponível": o EJMF não contorna bloqueio nem captcha. Falha de rede ou 5xx volta para a fila (3 tentativas) e o erro fica no item.
- LexML: `https://www.lexml.gov.br/busca/SRU?operation=searchRetrieve&version=1.1&query=<CQL>`; o registro importado entra **sem texto** e com vigência a conferir, apontando para `https://www.lexml.gov.br/urn/<URN>`.

## Verificador de jurisprudência (Fase 7)
- O julgado é conferido contra a página original no site do tribunal: número do processo (só dígitos), cobertura da ementa (sequências de 4 palavras; mínimo em `conhecimento.cobertura_minima_ementa`, padrão 60%), relator (nome completo sem o título) e data de julgamento, quando informados. Tudo determinístico, sem IA.
- Resultados: verificada; divergente (número achado, conteúdo não confere); não localizada (404 ou número ausente); fonte indisponível (rede, bloqueio, erro do tribunal, formato que não é HTML/texto); pendente (sem endereço).
- Repositórios privados de jurisprudência não são aceitos como original.

