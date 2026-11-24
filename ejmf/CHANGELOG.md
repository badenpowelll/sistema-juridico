# CHANGELOG

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
