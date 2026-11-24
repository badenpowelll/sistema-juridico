# CHANGELOG

## [Fase 9] — 2026-11-24
- Migração `0009_financeiro`: contas, categorias, contratos de honorários, lançamentos, recibos, extratos importados e suas linhas, lembretes de cobrança.
- Financeiro sem acesso a banco e sem cobrança externa (ADR-0013): contas só com nome e saldo; recebido e pago registrados por pessoa com `financeiro:liquidar`, data nunca futura, conta e forma.
- Lançamentos de receita e despesa com previsto, faturado, recebido/pago e cancelado; pagamento parcial cria lançamento com o saldo; estorno e cancelamento com motivo; reembolsável e visível no portal.
- Contratos de honorários fixo, parcelado, mensal, êxito e misto: parcelas viram lançamentos previstos; êxito lançado sobre valor-base informado por pessoa; encerrar mantém e cancelar cancela as parcelas em aberto.
- Recibos numerados (AAAA/NNNN) com valor por extenso e minuta pelo modelo "recibo de honorários" quando homologado.
- Lembretes de pagamento só no portal: publicados por quem tem `financeiro:cobrar` ou pela central de aprovações.
- Conciliação bancária por extrato OFX ou CSV importado, com sugestões por regras, lançar a partir da linha, ignorar com motivo e desfazer.
- Relatórios: resumo mensal (previsto, faturado, recebido, despesas, resultado de caixa), posição do dia e inadimplência, fluxo de caixa realizado e projetado, rentabilidade por processo, cliente e departamento sem rateio, exportação CSV para Excel em pt-BR.
- Ligações: indicadores de honorários a receber e receitas vencidas no painel (e clientes aguardando, documentos em revisão e custo de IA do mês), cartão financeiro no processo, "Honorários e pagamentos" no portal, seção financeira e clientes aguardando retorno no relatório diário, aviso diário de receitas vencidas, funções 26–30 por regras, ferramenta `honorarios_a_receber` e gatilho "honorário pendente".
- Telas: Financeiro (visão geral e contas), Lançamentos (lista e detalhe), Contratos de honorários (lista e detalhe), Conciliação e Fluxo de caixa e rentabilidade. Novas permissões `financeiro:*`.

## [Fase 8] — 2026-11-24
- Migração `0008_ia`: modelos de IA, configuração das 40 funções, instruções versionadas, execuções e passos, comandos do assistente, automações e suas execuções, tokens do MCP.
- Camada de provedores própria (ADR-0012): Claude pelo SDK oficial da Anthropic (saída estruturada, ferramentas estritas, recusa, limite de taxa e sobrecarga tratados), qualquer serviço compatível com a API de chat da OpenAI e um adaptador simulado identificado ("[SIMULADO]", custo zero, só com `EJMF_IA_SIMULADO`). LiteLLM avaliado e descartado.
- Central de IA: provedores e variáveis, modelos com preço, fonte e data de conferência (sugestões com a tabela oficial da Anthropic), aprovação do modelo para dados do escritório com o registro do que foi conferido sobre retenção, revogação, tetos diário e mensal, modelo reserva só com autorização, cotação opcional e painel de custos por função, modelo, departamento, processo e dia.
- Orquestrador: fila com chave contra duplicidade, permissões calculadas no código (catálogo ∩ nível ∩ quem pediu), bloqueio antes da chamada (modelo não aprovado, sem preço, sem tetos, orçamento da execução, teto do dia ou do mês) com aviso a quem gerencia, limite de chamadas e de tempo, retomada única de execução interrompida e registro de cada passo com tokens e custo.
- As 40 funções virtuais com ficha completa e configuração (ligada, nível até o teto, modelo, reserva, limites, orçamento, ferramentas). Executáveis: secretária executiva, assistente, classificador processual, organizador de audiências (nível 3 → central de aprovações → compromisso na agenda), pesquisador (só com trechos que a pesquisa devolveu) e gestor de relacionamento (sugestões de memória a confirmar), com IA; fiscal de pendências, atualizador da base, revisor estrutural, auditor de operações, monitor de integrações e analista de produtividade, por regras. Saídas validadas contra o material; o que não se sustenta é descartado.
- Instruções versionadas com motivo e SHA-256, sempre depois das regras de segurança fixas; material enviado ao modelo entre marcas `<dados>`.
- Assistente por texto: consultas por regras com as permissões de quem pergunta (agenda, publicações, prazos, documentos do cliente, processos parados, assinaturas, documentos pendentes, relatório diário, última movimentação, minutas em revisão), recusa de pedidos que alteram ou enviam algo, pendência criada só com confirmação e perguntas livres pela função com IA, com ferramentas só de leitura.
- Automações: construtor com 8 gatilhos (2 indisponíveis até as fases 9 e 11), condições, 3 ações (notificar, criar pendência, pedir função virtual) e janela de horário; teste obrigatório sem efeito antes de ativar; nova versão volta ao rascunho; cada ocorrência tratada uma vez; pausa após três falhas seguidas.
- Servidor MCP só de leitura em `/api/v1/mcp` com token pessoal (hash, até 90 dias, revogável, 60 chamadas por minuto, auditoria com origem "mcp").
- Telas: Inteligência artificial (central, custos, tokens MCP), Funções virtuais (lista e ficha), Execuções (lista e detalhe com passos), Assistente e Automações (lista e construtor), mais os botões de IA no processo, na publicação, no atendimento, na minuta e na pesquisa. Novas permissões `ia:*` e `automacoes:*`.

## [Fase 7] — 2026-11-24
- Migração `0007_conhecimento`: extensão `vector` (pgvector), fontes oficiais, biblioteca e versões, coleções, favoritos, jurisprudência, trechos indexados (vetor + texto) e memória.
- Biblioteca: normas, súmulas, temas, doutrina licenciada e materiais internos, com tipo, licença, esfera, departamento, assuntos, vigência conferida pelo advogado (com período e autor), versões com origem, data e SHA-256, comparação entre versões, coleções e favoritos. Obra protegida sem licença fica só como referência. Constituição, CLT, CPC e Estatuto da Advocacia entram sem texto, com o endereço oficial do Planalto e vigência a conferir.
- Monitor legislativo: consulta diária às fontes oficiais cadastradas (só domínios da lista), texto riscado de dispositivos revogados separado, versão nova a conferir com notificação, texto anterior preservado e alertas de item desatualizado. Busca e importação no LexML.
- Jurisprudência: cadastro com tribunal, número, classe, órgão, relator, datas, ementa e endereço do original (só site oficial do tribunal); verificador independente (número, ementa, relator e data, sem IA) com os estados verificada, pendente, não localizada, fonte indisponível e divergente; homologação pelo advogado; descarte com motivo (ADR-0011).
- Citação em minuta: o editor insere só julgado homologado; a aprovação recusa citação não verificada ou não homologada e reescreve o texto da citação com os dados conferidos.
- Pesquisa no conhecimento: híbrida (texto em português + semelhança de termos no pgvector), com trecho destacado e alertas, filtrando cliente, processo, sigilo e permissão antes de ordenar. Documentos do acervo entram no índice depois da extração e saem ao arquivar.
- Memória do escritório: decisões, orientações, preferências e fatos, gerais ou de um cliente ou processo; sugestão só vale confirmada; correção sem apagar; exclusão controlada com motivo; exportação em JSON.
- Telas: Pesquisa, Biblioteca (lista e item), Jurisprudência, Memória, citação na minuta e o quadro de memória na ficha do cliente e no processo. Novas permissões de conhecimento, biblioteca, jurisprudência e memória.

## [Fase 6] — 2026-11-24
- Migração `0006_documentos_modelos`: documentos e versões (com índice de busca em português), modelos com versão, favoritos, minutas e suas versões, comentários e pedidos de assinatura.
- Acervo de documentos: upload com o tipo checado pelo conteúdo e limite configurável (50 MB), o original nunca alterado, deduplicação pelo SHA-256, versões, comparação de texto entre versões, vínculo com cliente, processo e atendimento, arquivamento com motivo e documentos sigilosos.
- Extração de texto e OCR em português (Tesseract) fora do processo da API, com tempo e memória limitados: PDF com texto é lido direto; PDF digitalizado e fotos passam pelo OCR, com a confiança registrada e leitura duvidosa sinalizada. O texto vira uma versão "texto extraído" ao lado do original.
- Classificação por regras (21 categorias) pelo nome e pelo conteúdo; a pessoa pode corrigir.
- Quarentena: PDF com JavaScript ou arquivo anexado e documento do Office com macro ou ActiveX não são abertos por nenhuma ferramenta até serem liberados, com motivo, por quem tem acesso a sigilosos.
- Busca no título e no conteúdo, com o trecho encontrado destacado.
- Central de modelos: modelos com campos de dados confirmados (`{{cliente.qualificacao}}`, `{{escritorio.oab}}`, `{{data.hoje}}`…) e campos manuais; versão, homologação pelo advogado e favoritos. Procuração, declaração de hipossuficiência, contrato de honorários e recibo entram como rascunho sugerido, para conferência (ADR-0010).
- Minutas: editor no estilo Word (títulos, listas, citação recuada, alinhamento, negrito, itálico, sublinhado), salvamento automático com controle de conflito, cabeçalho e rodapé com número de página, pendências destacadas, comentários por trecho, revisão, devolução com motivo, versões e comparação.
- Aprovação profissional: só sem pendências e sem comentários abertos; gera DOCX (A4, Times 12, margens de 3/2 cm) e PDF, guarda a versão final no acervo e trava o texto. Antes disso, os arquivos baixados saem marcados como RASCUNHO. Contrato aprovado move o atendimento para "contrato preparado".
- Assinatura eletrônica pelo Documenso: preparação com participantes e papéis, envio autorizado pelo advogado, acompanhamento pelo webhook (abriu, assinou, concluído, recusado). Sem credenciais o envio fica bloqueado; nada é simulado. O envio move o atendimento para "assinatura pendente".
- Documento aceito na conferência do atendimento entra no acervo, sem cópia do arquivo.
- Telas: Documentos (acervo e detalhe), Modelos (biblioteca e editor), Minutas (lista e editor) e documentos vinculados na ficha do cliente e no processo; minutas em revisão no relatório diário.
- Imagem Docker e CI com Tesseract (`por`), Poppler e LibreOffice; `.env.example` corrigido com os nomes `EJMF_GOOGLE_*` e `EJMF_WHATSAPP_*` e as variáveis do Documenso.

## [Fase 5] — 2026-11-24
- Migração `0005_atendimento_crm`: atendimentos, links de cadastro, cadastros (cifrados), documentos recebidos, acesso e sessões do portal, pedidos do portal, conversas e mensagens; processos ganham "visível no portal"; a auditoria aceita o cliente como autor.
- Funil de atendimento em 14 etapas, do primeiro contato ao arquivamento, com motivo obrigatório para encerrar ou reabrir e com avanço depois da conferência profissional reservado ao advogado.
- Link seguro de cadastro: token mostrado uma única vez (o banco guarda só o hash), validade de 72 h configurável, revogação, registro de cada uso e um link só para documentos.
- Formulários por departamento (geral, trabalhista, previdenciário, consumidor e família), ajustáveis nas configurações. Só os campos do formulário são guardados.
- Cadastro pelo cliente em etapas: dados, endereço, dados do caso, relato com as próprias palavras, entrevista, linha do tempo e documentos, com revisão antes de confirmar. O relato é guardado como escrito e com hash; a cronologia separa o que é declarado do que é documentado.
- Documentos recebidos: tipo checado pelo conteúdo, limite de tamanho e de quantidade, duplicados reconhecidos, arquivos fora do Git, download só como anexo; conferência com aceite ou recusa com motivo que o cliente vê.
- Portal do cliente, separado do painel: convite de uso único, senha de 12+ caracteres, bloqueio após 5 erros, sessão própria. Mostra só processos liberados, andamentos oficiais, audiências futuras e documentos pendentes; aceita mensagens, pedidos de atendimento, atualização de dados e envio de documentos.
- Recepcionista virtual por regras (ADR-0009): menu, horário, abertura de atendimento com link, agendamento que passa pela central de aprovações e transferência para a equipe. Nunca informa dado de processo pelo chat.
- WhatsApp Business (Cloud API): envio pela fila, webhook com assinatura verificada, idempotência, status de entrega e a janela de 24 h. Sem credenciais fica "Aguardando credenciais"; o simulador identificado permite testar com dados fictícios.
- Telas: Atendimentos (funil e detalhe), Conversas, cadastro público, portal do cliente, seção do portal na ficha do cliente e "Mostrar no portal" no processo.

## [Fase 4] — 2026-11-24
- Migração `0004_agenda_secretaria`: compromissos, credenciais de integração cifradas, pendências, aprovações, relatórios e notificações; prazos ganham o vínculo com o evento do Google.
- Agenda com visões dia, semana e mês: audiências (sempre ligadas a processo), reuniões, atendimentos, lembretes, bloqueios, trabalho concentrado e compromissos pessoais (visíveis só para o dono). Avisa conflito de horário e sobrecarga do dia (limites configuráveis), mostra disponibilidade e guarda o histórico de reagendamentos.
- Cancelar audiência exige o advogado; o operador faz um pedido que vai para a central de aprovações.
- Google Calendar: OAuth com PKCE e escopo mínimo (`calendar.events.owned`), tokens cifrados, sincronização incremental a cada 15 min, prazos homologados enviados como eventos de dia inteiro. Eventos de fora entram como "externos" somente leitura e nunca são apagados; audiência movida no Google só muda no EJMF com aprovação. Sem credenciais fica "Aguardando credenciais"; há um Google simulado identificado para testes.
- Central de prioridades com dez classes, justificativa de cada posição e ações (adiar, delegar, solicitar informações, aguardar cliente ou terceiros, devolver, concluir, reabrir). Item crítico não pode ser adiado; item automático fecha sozinho quando a origem se resolve.
- Central de aprovações: pedidos da equipe, prazos por homologar, regras não homologadas e possíveis suspensões; quem pediu não decide o próprio pedido.
- Relatório diário às 6h30 e de encerramento às 18h00, com entrega no painel e nas notificações; e-mail e WhatsApp aparecem com o estado da integração e só enviam depois de validados.
- Notificações no cabeçalho; agenda, prioridades, aprovações e relatórios no menu; compromissos no prontuário; audiências da semana e reuniões de hoje passam a ser indicadores reais do painel.

## [Fase 3] — 2026-11-24
- Migração `0003_controladoria`: calendário, regras de prazo, publicações, leituras, prazos, alertas, execuções de integração e fila de tarefas.
- Calendário forense: feriados nacionais (inclusive 20/11), datas da Justiça Federal (Lei 5.010 art. 62), recesso do art. 220 do CPC, e Carnaval, Paixão e Corpus Christi como "possível suspensão" a confirmar. Feriados locais cadastráveis por tribunal, UF ou segmento.
- Motor de prazos determinístico com memória de cálculo: dias úteis ou corridos, termo inicial pela disponibilização no DJEN ou pela intimação, dobro com fundamento, e vencimento alternativo caso as possíveis suspensões se confirmem. Cinco regras versionadas (CPC, CPC por intimação, CLT, Juizados e CPP), todas não homologadas até o advogado conferir.
- Prazo: sugerido → conferido → homologado por outra pessoa, com regra homologada; alterado, vencido, concluído e informação insuficiente. Recalcula sozinho quando o calendário muda e volta para conferência.
- Publicações: original preservado, quatro datas (disponibilização, publicação, ciência, captura), deduplicação por fonte e entre fontes, classificação por regras, vínculo a processo, conferência, descarte com motivo, ciência só registrada por pessoa e leituras internas separadas da ciência.
- Conectores DJEN e DataJud com limite de taxa, circuit breaker, idempotência e fila com reagendamento exponencial; adaptador "Simulado — DJEN" sempre marcado. Importação do arquivo JSON do DJEN como contingência.
- Central de contingência: estado de cada fonte, último sucesso, processos afetados, procedimento manual com o endereço de consulta pronto, fila e worker.
- Telas: Publicações, Prazos (com alertas), Regras e calendário, Contingência, e prazos e publicações no prontuário, com prévia do cálculo ao cadastrar.
- Indicadores do painel passam a ser reais: publicações pendentes, intimações das últimas 24 h, prazos de hoje e prazos futuros.

## [Fase 2] — 2026-11-24
- Migração `0002_gestao_processual`: tribunais, clientes, processos, partes, movimentações, importações e linhas de importação.
- Número CNJ validado pelo dígito verificador (módulo 97) e tribunal identificado pelo código J.TR (95 tribunais; TJRN, TRT21 e TRF5 prioritários).
- Clientes PF/PJ: CPF e CNPJ validados (CNPJ alfanumérico da IN RFB 2.229/2024), guardados cifrados, com hash para busca exata e deduplicação e cópia mascarada para exibição; ver o documento completo exige permissão própria e fica na auditoria.
- Prontuário do processo: dados, partes e clientes, linha do tempo (movimentações, anotações e histórico da auditoria) e próximos módulos.
- Pesquisa global por número (com ou sem máscara, ou trecho), parte, cliente e classe, respeitando permissões.
- Operações em lote (situação e departamento), tudo ou nada, auditadas.
- Importação em massa: pré-visualização, sugestão de mapeamento, validação, duplicidades no arquivo e no banco, execução em lotes de 500 retomável, relatório CSV, fila de conferência para homônimos e reversão.
- Teste de carga com 1k, 5k e 10k processos (100 mil movimentações).

## [Fase 1] — 2026-11-24
- Backend FastAPI + SQLAlchemy/Alembic + PostgreSQL 16 (pgvector), migração `0001_fundacao`.
- Autenticação própria: Argon2id, sessões opacas revogáveis, MFA TOTP, bloqueio após 5 falhas, limite por IP, proteção CSRF.
- Permissões `recurso:acao` em quatro perfis (advogado_admin, operador, cliente, agente_ia).
- Auditoria só de inserção, com cadeia de hashes, gatilho que impede alteração e comando de verificação.
- Configurações institucionais vazias e editáveis; 19 departamentos; 10 integrações nos 6 estados oficiais.
- Frontend Next.js com marca centralizada em `src/marca/`, tema claro/escuro, login com MFA, painel "Central de comando" e telas de integrações, configurações, segurança, auditoria, departamentos e usuários.
- Docker Compose (db, api, worker, web) e CI no GitHub Actions.

## [Fase 0] — 2026-11-24
- Diagnóstico do ambiente e dos repositórios existentes.
- Pesquisa de 28 repositórios do GitHub e das APIs oficiais (DataJud, DJEN) em RESEARCH.md.
- Arquitetura, 7 ADRs, roadmap, backlog priorizado, catálogo das 40 funções, custos estimados e documentação obrigatória inicial.
- Superprompt preservado em `docs/origem/`.
