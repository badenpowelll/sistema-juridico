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

### Fase 5 — 2026-11-24 (mesmo ambiente)
| Comando | Resultado |
|---|---|
| `cd backend && pytest -q` | **120 passed**. Os 11 novos (`tests/test_atendimento.py`): link de cadastro do começo ao fim (token só em hash, campos fora do formulário descartados, CPF e datas validados, cadastro cifrado no banco, relato guardado como escrito e com hash de integridade, cronologia "declarada pelo cliente", arquivo checado pelo conteúdo e não pela extensão, duplicado reconhecido pelo SHA-256, download só como anexo, recusa com motivo volta para "documentos pendentes", cliente criado sem duplicar pelo CPF, revogação e histórico); link expirado (410), novo link revoga o anterior, link só de documentos não altera cadastro; etapas do funil (encerrar e reabrir exigem motivo, arquivar só depois de encerrar, só o advogado passa da conferência profissional); portal isolado (cliente só vê processos marcados como visíveis e só andamentos oficiais; sessão do portal não abre rotas da equipe e vice-versa); bloqueio do portal após 5 senhas erradas e operador sem permissão de convidar; recepcionista envia link e transfere pergunta de mérito; agendamento pela recepcionista só vale depois de aprovado; simulador desligado por padrão; webhook do WhatsApp com assinatura HMAC, reenvio idempotente, fila de envio por `httpx.MockTransport`, status entregue/lido e janela de 24 h; token recusado (401) volta para "Aguardando credenciais"; webhook sem credenciais recusado (403) |
| `alembic upgrade head` / `downgrade -1` / `upgrade head` e `alembic check` (migração `0005_atendimento_crm`) | ida e volta sem erro; modelos e migração sem diferença |
| `cd frontend && npm run lint && npx tsc --noEmit && npm run build` | sem erros |
| `cd frontend && npx playwright test --trace off` | **39 passed, 1 skipped** (2 cenários novos × desktop e celular: a equipe abre o atendimento e gera o link, o cliente sem login preenche o cadastro em etapas, tem o CPF inválido recusado, envia identidade e comprovante, tem um executável recusado pelo conteúdo e confirma; a equipe vê o relato íntegro, aceita um documento e recusa outro com motivo, cria o cliente, convida para o portal; o cliente cria a senha, entra, vê o documento a reenviar com o motivo, confirma que a sessão do portal recebe 401 nas rotas da equipe, manda mensagem e vê a resposta. Simulador de WhatsApp com selo "Simulado": menu, recusa de dado de processo pelo chat, transferência para a equipe, resposta da equipe marcada "simulada" e devolução à recepcionista) |
| WhatsApp Business real | não testado contra a Meta: falta a conta Meta Business verificada e as variáveis `EJMF_WHATSAPP_*`. Estado "Aguardando credenciais" |

### Fase 6 — 2026-11-24 (mesmo ambiente, com Tesseract 5 `por`, Poppler e LibreOffice instalados)
| Comando | Resultado |
|---|---|
| `cd backend && pytest -q` | **135 passed**. Os 15 novos (`tests/test_documentos.py`, arquivos sintéticos gerados na hora por `tests/arquivos_sinteticos.py`): PDF com texto lido sem OCR, reclassificado pelo conteúdo ("procuração"), achado pela busca no texto com trecho destacado, e o original baixado idêntico ao enviado (anexo, `sandbox`); PNG e PDF digitalizado (só imagem) lidos pelo OCR em português com confiança acima de 60% e classificados (contracheque, rescisão); OCR ausente registrado como "indisponível" sem inventar texto; duplicado pelo SHA-256 devolvido sem cópia, executável recusado (415), PDF com JavaScript e DOCX com macro em quarentena (nenhuma tarefa de extração, download bloqueado para o operador, liberação só com permissão e motivo; nova versão com conteúdo ativo recusada); documento sigiloso invisível (404 e fora da lista) para quem não tem permissão; versões com comparação de texto, filtro por cliente e arquivamento com motivo e nível; documento aceito no atendimento entra no acervo reaproveitando o arquivo; modelos iniciais em rascunho não geram minuta (409); modelo com `<script>` e `onclick` sanitizado, campo inexistente recusado (422), operador não homologa, edição de homologado cria a v2 em rascunho e a v1 segue em uso até a v2 ser homologada (v1 vira "substituído"); favorito; minuta sem cadastro confirmado deixa a qualificação pendente, campo do cadastro não aceita digitação, campo manual é preenchido, salvamento com conflito (409), comentário aberto e pendência bloqueiam a aprovação, revisão trava a edição do operador, devolução exige motivo, DOCX de rascunho com "RASCUNHO" no cabeçalho e campo de página no rodapé; aprovação gera PDF (LibreOffice) no acervo, ligado ao cliente, sem a marca de rascunho, e trava a minuta; sem credencial do Documenso o envio é recusado (409) e o webhook também (403); com respostas gravadas (`httpx.MockTransport`): envelope criado com o PDF, papéis SIGNER/CC e campos de assinatura e data só para quem assina, distribuição, integração em "ambiente de testes", webhook com segredo errado recusado, assinatura parcial, conclusão com notificação, evento de envelope alheio ignorado, e chave recusada (401) marca "falha" e volta a integração para "Aguardando credenciais" |
| `alembic upgrade head` / `downgrade -1` / `upgrade head` e `alembic check` (migração `0006_documentos_modelos`) | ida e volta sem erro; modelos e migração sem diferença |
| `cd frontend && npm run lint && npx tsc --noEmit && npm run build` | sem erros |
| `cd frontend && npx playwright test --trace off` | **43 passed, 1 skipped** (2 cenários novos × desktop e celular: o advogado envia um arquivo, processa, acha pela palavra do conteúdo com o trecho destacado e vê que o reenvio não duplica; cria um modelo, escreve no editor, insere o campo do cliente e um campo manual, salva e homologa; gera a minuta para um cliente, vê a pendência destacada e a aprovação desabilitada, preenche o campo manual, edita e vê o "Salvo às" do salvamento automático, comenta e resolve, aprova; prepara a assinatura e vê "Autorizar envio" desabilitado com o aviso de credenciais; abre o documento final no acervo ligado ao cliente. O operador não cria nem homologa modelo e vê o texto somente leitura) |
| Documenso real | não testado contra a conta real: faltam `EJMF_DOCUMENSO_TOKEN` e `EJMF_DOCUMENSO_WEBHOOK_SECRET`. Estado "Aguardando credenciais" |
| `docker compose config` (volume `arquivos` compartilhado entre API e worker) | válido |
| `docker build` da API com os pacotes de OCR | **não concluído neste ambiente**: o build não alcança o repositório do Debian pela rede desta máquina (DNS e proxy bloqueados dentro do build). Os mesmos pacotes (`tesseract-ocr`, `tesseract-ocr-por`, `poppler-utils`, LibreOffice) foram instalados por apt na máquina de desenvolvimento e são os usados nos testes acima; o CI instala os mesmos pacotes antes do pytest |

CI: `.github/workflows/ejmf.yml` roda os mesmos testes (backend + E2E) em cada PR que toca `ejmf/`.
