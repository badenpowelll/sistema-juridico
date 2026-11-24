# CHANGELOG

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
