# TESTING

Regra: nada é declarado concluído sem evidência. Cada fase registra aqui o comando, a data e o resultado real.

## Como rodar
```bash
# backend (precisa de um PostgreSQL; o docker compose sobe um)
cd ejmf/backend && pytest -q
# frontend
cd ejmf/frontend && npm run build && npm run test:e2e
```

## Resultados por fase
### Fase 1 — 2026-11-24 (ambiente local, PostgreSQL 16 + pgvector em Docker)
| Comando | Resultado |
|---|---|
| `cd backend && pytest -q` | **42 passed** (segurança, autenticação, MFA, bloqueio, rate limit, CSRF, RBAC, auditoria encadeada e imutável, painel, configurações) |
| `cd frontend && npm run lint && npx tsc --noEmit` | sem erros |
| `cd frontend && npm run build` | build de produção concluído |
| `cd frontend && npm run test:e2e` | **15 passed, 1 skipped** (8 cenários × desktop e celular Pixel 7; o cenário de MFA roda só no desktop por usar conta própria) |
| `docker compose up` + `criar-admin` + login via `:3000/api/v1/auth/login` | API e banco *healthy*, worker com batimento, web servindo, login e painel respondendo, `verificar-auditoria` íntegra |

Cenários E2E: página pública; login inválido; login → painel com "O que exige minha atenção agora"; indicadores de módulos futuros mostram a fase e não "0"; operador não vê menus de administração; configurações institucionais começam vazias e são editáveis; integração não pode ser marcada como validada manualmente; ativação de MFA e login com segundo fator.

Observação do ambiente de desenvolvimento: o `docker build` desta máquina passa por um proxy com certificado próprio; as imagens foram construídas injetando esse certificado num contexto temporário, sem alterar os Dockerfiles versionados. Em máquina comum, `docker compose up --build` funciona direto.

### Fase 2 — 2026-11-24 (mesmo ambiente)
| Comando | Resultado |
|---|---|
| `cd backend && pytest -q` | **73 passed** (identificadores CNJ/CPF/CNPJ, processos, clientes, partes, linha do tempo, pesquisa, lote, importação CSV/XLSX/JSON/TXT, homônimos, reenvio, falha isolada em lote, execução interrompida e retomada com 1.203 linhas, reversão, permissões) |
| `alembic upgrade head` / `downgrade -1` / `upgrade head` e `alembic check` | ida e volta sem erro; modelos e migração sem diferença |
| `cd frontend && npm run lint && npx tsc --noEmit && npm run build` | sem erros |
| `cd frontend && npm run test:e2e` | **23 passed, 1 skipped** (inclui 4 cenários novos × desktop e celular: cadastro de cliente e processo com anotação e pesquisa global; importação CSV com inconsistências, execução e conferência; operador sem lote nem reversão; advogado altera processos em lote) |
| `cd backend && python -m testes_carga.carga` | resultado em `backend/testes_carga/resultado.json` (resumo abaixo) |

Teste de carga (API via TestClient, PostgreSQL local, 30 repetições por rota; tempos p50/p95 em ms):

| Cenário | Lista pág. 1 | Busca por número | Busca por cliente | Prontuário | Pesquisa global | Central de comando | Banco |
|---|---|---|---|---|---|---|---|
| 1k processos / 3k mov. | 22.6 / 26.7 | 19.7 / 21.5 | 19.7 / 22.1 | 17.9 / 18.9 | 18.0 / 21.3 | 27.2 / 32.7 | 51 MB |
| 5k / 15k | 21.2 / 28.2 | 26.5 / 31.0 | 26.9 / 28.2 | 19.1 / 22.0 | 20.1 / 23.1 | 34.9 / 39.0 | 39 MB |
| 10k / 100k | 23.1 / 33.1 | 34.8 / 39.7 | 31.9 / 34.7 | 20.5 / 22.9 | 21.0 / 24.0 | 38.9 / 44.0 | 78 MB |

Importação de 5.100 linhas (2% com problema): analisar 0,22 s, validar 0,84 s, executar 9,5 s em 2 chamadas; 5.000 importadas, 50 inválidas e 50 duplicadas, nenhuma descartada. Memória máxima do processo: 215 MB. Cadeia de auditoria íntegra ao final de cada cenário.

### Fase 3 — 2026-11-24 (mesmo ambiente)
| Comando | Resultado |
|---|---|
| `cd backend && pytest -q` | **101 passed**: 13 casos do motor de prazos conferidos à mão (CPC art. 224, DJEN Lei 11.419 art. 4º §§3º-4º, dias corridos do CPP com prorrogação, recesso de 20/12 a 20/01 do art. 220, dobro, Justiça Federal pela Lei 5.010 art. 62, 20/11 nacional, Carnaval como possível suspensão e vencimento alternativo) e 15 de controladoria (DJEN e DataJud com respostas gravadas via `httpx.MockTransport`, idempotência da sincronização, circuit breaker, contingência, movimentos do DataJud sem duplicar, dupla conferência, regra penal, recálculo ao confirmar Carnaval, alertas e vencidos, publicação manual, duplicada entre fontes, vínculo, descarte, ciência, permissões do operador, importação do JSON do DJEN, fila com reagendamento, agendador e adaptador simulado) |
| `alembic upgrade head` / `downgrade -1` / `upgrade head` e `alembic check` (migração `0003_controladoria`) | ida e volta sem erro; modelos e migração sem diferença |
| `cd frontend && npm run lint && npx tsc --noEmit && npm run build` | sem erros |
| `cd frontend && npx playwright test --trace off` | **29 passed, 1 skipped** (3 cenários novos × desktop e celular: publicação manual → prazo sugerido de 15 dias úteis com vencimento 09/12/2026 conferido pelo operador e homologado pelo advogado depois de homologar a regra; quem cadastra o prazo não consegue homologar o próprio cálculo; central de contingência com DJEN comprometido, procedimento manual com o endereço de consulta e sincronização do adaptador simulado) |
| Acesso real ao DJEN (`comunicaapi.pje.jus.br`) a partir deste ambiente | **HTTP 403** (bloqueio geográfico do CloudFront fora do Brasil). Por isso o DJEN fica "Implementada em ambiente de testes": o conector foi testado contra respostas no formato documentado, e só sobe para "validada" após a primeira sincronização real num servidor no Brasil |
| DataJud | não testado contra a fonte real: falta `DATAJUD_API_KEY` (estado "Aguardando credenciais") |

Verificação manual do cenário E2E: 16/11/2026 (segunda) é a disponibilização; a publicação é 17/11; a contagem começa em 18/11; 20/11 (Dia da Consciência Negra, Lei 14.759/2023) não conta; o 15º dia útil é 09/12/2026.

### Fase 4 — 2026-11-24 (mesmo ambiente)
| Comando | Resultado |
|---|---|
| `cd backend && pytest -q` | **109 passed**. Os 8 novos (`tests/test_secretaria.py`): agenda com conflito, sobrecarga (limite de horas e de audiências por dia), disponibilidade e validações (audiência exige processo; tipo "externo" não é criado à mão); compromisso pessoal oculto para os outros; operador pede cancelamento de audiência e o advogado aprova; Google simulado de ida e volta (sem duplicar, eventos de fora nunca apagados, audiência movida no Google só muda com aprovação, rejeição devolve o horário do EJMF, evento excluído no Google vira pendência, token de sincronização expirado (410) refaz a carga completa); OAuth real com PKCE simulado por `httpx.MockTransport` (state validado, tokens cifrados, prazo homologado enviado como evento de dia inteiro, renovação do token, 401 volta para "Aguardando credenciais", revogação ao desconectar); prioridades (classes, justificativa, item crítico não adiável, item automático fecha sozinho); relatórios diário e de encerramento (idempotentes, entregas por canal); agendador (6h30, 18h00 e prioridades a cada 5 min, sem duplicar) |
| `alembic upgrade head` / `downgrade -1` / `upgrade head` e `alembic check` (migração `0004_agenda_secretaria`) | ida e volta sem erro; modelos e migração sem diferença |
| `cd frontend && npm run lint && npx tsc --noEmit && npm run build` | sem erros |
| `cd frontend && npx playwright test --trace off` | **35 passed, 1 skipped** (3 cenários novos × desktop e celular: reunião e audiência em conflito com aviso, visões dia, semana e mês, operador pede o cancelamento da audiência e o advogado aprova na central de aprovações, compromisso no prontuário; Google simulado com eventos "[SIMULADO" somente leitura e sem duplicar na segunda sincronização; pendência manual com justificativa, "aguardando cliente", delegação a função virtual recusada até a Fase 8, relatório diário gerado na hora e notificação no sino) |
| Google Calendar real | não testado contra a conta real: falta o projeto do Google Cloud (`EJMF_GOOGLE_CLIENT_ID`, `EJMF_GOOGLE_CLIENT_SECRET`, `EJMF_GOOGLE_REDIRECT_URI`). Estado "Aguardando credenciais" |

CI: `.github/workflows/ejmf.yml` roda os mesmos testes (backend + E2E) em cada PR que toca `ejmf/`.
