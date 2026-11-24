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
