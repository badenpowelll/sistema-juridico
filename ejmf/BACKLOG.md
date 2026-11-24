# BACKLOG priorizado

Prioridade: **P0** (bloqueia a fase) · **P1** (necessário na fase) · **P2** (desejável) · **FUT** (futuro).

## Fase 1 — Fundação
| ID | Item | Prioridade |
|---|---|---|
| F1-01 ✓ | Estrutura `backend/` (FastAPI) e `frontend/` (Next.js) | P0 |
| F1-02 ✓ | Configuração por variáveis de ambiente, `.env.example`, validação na partida | P0 |
| F1-03 ✓ | Migrações Alembic: escritórios, usuários, perfis, permissões, sessões, departamentos, configurações, integrações, auditoria | P0 |
| F1-04 ✓ | Login/logout, sessões revogáveis, bloqueio por tentativas, rate limit | P0 |
| F1-05 ✓ | MFA TOTP (cadastro, confirmação, desafio no login) | P1 |
| F1-06 ✓ | RBAC com permissões `recurso:acao` checadas no servidor | P0 |
| F1-07 ✓ | Auditoria encadeada + gatilho de imutabilidade + verificação | P0 |
| F1-08 ✓ | Módulo central de marca (cores, tipografia, textos) no front e no back | P1 |
| F1-09 ✓ | Painel: "O que exige minha atenção agora" + indicadores reais + estado das integrações | P1 |
| F1-10 ✓ | Configurações institucionais editáveis (CNPJ, endereço etc. começam vazios) | P1 |
| F1-11 ✓ | Departamentos configuráveis (18 + "Outras" semeados) | P1 |
| F1-12 ✓ | Docker Compose (db pgvector, api, worker, web) | P0 |
| F1-13 ✓ | Testes: unitários, integração com Postgres real, E2E do login ao painel | P0 |
| F1-14 ✓ | CI no GitHub Actions (lint + testes) | P2 |

## Fase 2 — Gestão processual
| ID | Item | Prioridade |
|---|---|---|
| F2-01 ✓ | Tribunais (tabela de referência a partir de J.TR do número CNJ) | P0 |
| F2-02 ✓ | Processos (número CNJ validado, classe, assuntos, unidade, status, origem) | P0 |
| F2-03 ✓ | Clientes PF/PJ (CPF/CNPJ validados e protegidos) e contatos | P0 |
| F2-04 ✓ | Partes e vínculo cliente-processo | P0 |
| F2-05 ✓ | Movimentações e linha do tempo | P1 |
| F2-06 ✓ | Importação CSV/XLSX/JSON: pré-visualização, mapeamento, validação, duplicidades, lotes, relatório, fila de conferência, reversão | P0 |
| F2-07 ✓ | Pesquisa global (FTS + trigram) respeitando permissões | P1 |
| F2-08 ✓ | Operações em lote auditadas | P2 |
| F2-09 ✓ | Testes de carga 1k/5k/10k processos e 100k movimentações | P0 |

## Fase 3 — Controladoria
| ID | Item | Prioridade |
|---|---|---|
| F3-01 ✓ | Interface `Conector`, circuit breaker, rate limit, fila de tarefas com idempotência | P0 |
| F3-02 ✓ | Conector DJEN (consulta por OAB/UF, certidão por hash) — validação real pendente de servidor no Brasil | P0 |
| F3-03 ✓ | Conector DataJud (chave pública via ambiente; lote por tribunal) — validação real pendente da chave | P1 |
| F3-04 ✓ | Publicações/intimações com quatro datas separadas e original preservado | P0 |
| F3-05 ✓ | Conferência (fila) e vínculo a processo; duplicidades | P0 |
| F3-06 ✓ | Motor de prazos determinístico: calendário, feriados nacionais e por tribunal, suspensões, regras versionadas, memória de cálculo | P0 |
| F3-07 ✓ | Estados do prazo e dupla conferência | P0 |
| F3-08 ✓ | Alertas configuráveis (15/7/5/3/2/1/0 dias) | P1 |
| F3-09 ✓ | Central de contingência (estado por fonte, último sucesso, "monitoramento comprometido") | P0 |

## Fase 4 — Agenda e secretaria
| ID | Item | Prioridade |
|---|---|---|
| F4-01 ✓ | Compromissos (audiência, reunião, atendimento, lembrete, bloqueio, trabalho concentrado, pessoal) com conflito, sobrecarga e disponibilidade | P0 |
| F4-02 ✓ | Agenda dia, semana e mês; compromissos no prontuário | P0 |
| F4-03 ✓ | Google Calendar: OAuth com PKCE, tokens cifrados, sincronização incremental bidirecional, regras de não apagar e aprovação de audiência | P0 — validação real pendente das credenciais |
| F4-04 ✓ | Google simulado identificado para testes | P1 |
| F4-05 ✓ | Central de prioridades com classes, justificativa e ações | P0 |
| F4-06 ✓ | Central de aprovações | P0 |
| F4-07 ✓ | Relatório diário (6h30) e de encerramento | P0 |
| F4-08 ✓ | Notificações internas | P1 |
| F4-09 | Envio dos relatórios por e-mail e WhatsApp | P1 — depende de Gmail (Fase 4, credenciais) e WhatsApp (Fase 5) |
| F4-10 | Delegação a funções virtuais | Fase 8 |

## Fase 5 — Atendimento e CRM
| ID | Item | Prioridade |
|---|---|---|
| F5-01 ✓ | Funil de 14 etapas com regras de avanço, encerramento e reabertura | P0 |
| F5-02 ✓ | Link seguro de cadastro: token em hash, validade, revogação, registro de uso, link só de documentos | P0 |
| F5-03 ✓ | Formulários por departamento, ajustáveis na configuração | P0 |
| F5-04 ✓ | Cadastro em etapas com relato original preservado, entrevista e cronologia declarada/documentada | P0 |
| F5-05 ✓ | Recebimento de documentos com checagem de conteúdo, deduplicação e conferência | P0 |
| F5-06 ✓ | Portal do cliente isolado (convite, senha, bloqueio, processos liberados, pendências, mensagens) | P0 |
| F5-07 ✓ | Recepcionista virtual por regras (ADR-0009) | P0 |
| F5-08 ✓ | WhatsApp Business: envio pela fila, webhook assinado, status, janela de 24 h, simulador | P0 — validação real pendente das credenciais |
| F5-09 | Modelos de mensagem aprovados pela Meta (fora da janela de 24 h) | P1 — depende da conta Meta |
| F5-10 | Redefinição de senha do portal por e-mail | P1 — depende do Gmail |
| F5-11 | Varredura de vírus nos arquivos recebidos | P1 — Fase 11 |
| F5-12 ✓ | Contrato e assinatura no funil (contrato aprovado → "contrato preparado"; envio para assinatura → "assinatura pendente") | Fase 6 |

## Fase 6 — Documentos
| ID | Item | Prioridade |
|---|---|---|
| F6-01 ✓ | Upload seguro com original preservado, versões separadas, deduplicação e limite configurável | P0 |
| F6-02 ✓ | Extração de texto e OCR em português, fora do processo da API, com confiança registrada | P0 |
| F6-03 ✓ | Classificação por regras, busca no conteúdo com trecho, filtro por cliente e processo | P0 |
| F6-04 ✓ | Quarentena de conteúdo ativo, sigilo, arquivamento com motivo | P0 |
| F6-05 ✓ | Central de modelos com versão, homologação, favoritos e campos só de dados confirmados | P0 |
| F6-06 ✓ | Editor de minutas: salvamento automático, cabeçalho/rodapé, página, comentários, versões e comparação | P0 |
| F6-07 ✓ | Aprovação profissional, DOCX e PDF, versão final no acervo | P0 |
| F6-08 ✓ | Assinatura pelo Documenso: preparo, envio autorizado, acompanhamento por webhook | P0 — validação real pendente das credenciais |
| F6-09 | Baixar sozinho o PDF assinado do Documenso ao concluir | P1 — depende da conta real para confirmar o endpoint |
| F6-10 | Posição dos campos de assinatura escolhida na tela (hoje: pé da última página) | P2 |
| F6-11 | Transcrição de áudio e OCR de HEIC | Fase 8 |
| F6-12 | Documentos e contratos assinados visíveis no portal do cliente | P1 |
| F6-13 | Varredura de vírus e cópia de segurança dos arquivos | Fase 11 |

## Fase 7 — Conhecimento

| ID | Item | Prioridade |
|---|---|---|
| F7-01 ✓ | Biblioteca versionada com tipos, licença, vigência conferida, coleções, favoritos e departamentos | P0 |
| F7-02 ✓ | Monitor de fontes oficiais com versão a conferir, comparação e alerta de desatualização | P0 — validação real pendente (rede) |
| F7-03 ✓ | Busca e importação pelo LexML (SRU) | P1 — validação real pendente (rede) |
| F7-04 ✓ | Jurisprudência com verificador independente no site do tribunal e homologação pelo advogado | P0 — validação real pendente (rede) |
| F7-05 ✓ | Pesquisa híbrida (texto + vetor pgvector) com escopo por cliente, processo, sigilo e permissão | P0 |
| F7-06 ✓ | Documentos do acervo indexados depois da extração; saem do índice ao arquivar | P0 |
| F7-07 ✓ | Citação de julgado na minuta só homologado, reconferida na aprovação | P0 |
| F7-08 ✓ | Memória permanente: confirmação de sugestões, correção sem apagar, exclusão controlada e exportação | P0 |
| F7-09 | Embeddings de um provedor aprovado (reindexar trechos com outro `vetorizador`) | Fase 8 |
| F7-10 | Monitor por dispositivo (artigo) e diff estruturado da norma | P2 |
| F7-11 | Leitura de páginas de tribunal montadas por JavaScript (hoje: fonte indisponível) | P2 |
| F7-12 | Súmulas e temas importados em lote das páginas oficiais | P1 |

## Fase 8 — IA

| ID | Item | Prioridade |
|---|---|---|
| F8-01 ✓ | Camada de provedores: Anthropic (SDK oficial), compatível com OpenAI e simulado identificado | P0 — Claude real aguardando chave |
| F8-02 ✓ | Modelos com preço, fonte, aprovação para dados do escritório e revogação | P0 |
| F8-03 ✓ | Orquestrador: fila, chave contra duplicidade, permissões catálogo ∩ nível ∩ quem pediu, limites de chamadas, tempo e orçamento, tetos diário e mensal, retomada única | P0 |
| F8-04 ✓ | Catálogo das 40 funções com ficha completa; 6 com IA e 6 por regras executáveis | P0 |
| F8-05 ✓ | Validação própria das saídas (trecho literal, data no trecho, citações, departamento, números do relatório) | P0 |
| F8-06 ✓ | Nível 3 pela central de aprovações (agendar audiência) e aplicação de sugestão por pessoa (classificação, memória) | P0 |
| F8-07 ✓ | Instruções versionadas com SHA-256 e regras de segurança fixas | P0 |
| F8-08 ✓ | Custos por execução, função, modelo, departamento, processo e dia | P0 |
| F8-09 ✓ | Assistente por texto: consultas por regras, recusa do que altera, pendência com confirmação, perguntas livres pela função com IA | P0 |
| F8-10 ✓ | Construtor de automações com teste obrigatório, versões, deduplicação e pausa após falhas | P0 |
| F8-11 ✓ | Servidor MCP só de leitura com token pessoal | P1 |
| F8-12 ✓ | Botões de IA nas telas de processo, publicação, atendimento, minuta e pesquisa | P1 |
| F8-13 | Redação de minuta por IA (função 22) | P2 — exige revisão de risco própria |
| F8-14 | Embeddings de um provedor aprovado para a pesquisa (era F7-09) | P2 |
| F8-15 | Transcrição de áudio (era F6-11) | Fase 10 |
| F8-16 | Funções 5, 24 e 38 (Gmail, evidências, backup) | Fases 9 a 11 |
| F8-17 | Agendamento periódico de funções por regras pelo worker (hoje: sob demanda e por automação) | P2 |

## Demais fases
Itens detalhados ao abrir cada fase (ver ROADMAP). Itens registrados desde já:

| ID | Item | Origem |
|---|---|---|
| SEC-010 | Varredura de dependências (pip-audit, npm audit) no CI | Seção 34 |
| SEC-011 | Varredura de vulnerabilidades dos componentes externos antes de adotar | RESEARCH |
| FUT-01 | Controle de horas trabalhadas | Conversa de origem |
| FUT-02 | Gestão de correspondentes e colaboradores | Conversa de origem |
| FUT-03 | Organizador de provas documentais | Conversa de origem |
| FUT-04 | Estrutura multiempresa para eventual comercialização | Conversa de origem (ADR-0006 já prepara) |
| FUT-05 | Aplicativo Android/iOS nativo | Conversa de origem |
| FUT-06 | Integrar motor da calculadora de rescisão (`calculadora/`) como módulo de cálculos | Projeto existente |
| FUT-07 | Sincronização com OneDrive (ideia do PR #2) | Projeto existente |
