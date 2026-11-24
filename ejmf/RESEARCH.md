# RESEARCH — pesquisa técnica (Fase 0)

Data da coleta: **2026-11-24** (UTC). Os números (estrelas, datas de push) foram lidos nesse dia e mudam com o tempo.

## Como a pesquisa foi feita (e limites)

- O ambiente de desenvolvimento (contêiner na nuvem) **não tem acesso direto à API do GitHub** para repositórios fora do projeto (`api.github.com` devolve 403 para repositórios de terceiros).
- Por isso os dados vieram de duas fontes intermediárias, ambas lendo o GitHub público:
  - leitura da página do repositório (raspagem da página pública via Firecrawl) para os 7 projetos jurídicos brasileiros;
  - metadados da API pública do GitHub via o provedor `github-com` do catálogo Firecrawl/Alexandria para os 21 projetos de infraestrutura.
- **Não foi feita auditoria de código, nem execução, nem varredura de vulnerabilidades (CVE) de nenhum projeto.** A coluna "Vulnerabilidades" fica como *pendente* até a fase em que o componente for de fato adotado (ver BACKLOG `SEC-010`).
- Documentação oficial consultada: Wiki do DataJud (CNJ) e Swagger do DJEN (`comunicaapi.pje.jus.br`). Ver seção "Fontes oficiais".

Legenda de classificação: **Reutilizar** · **Integrar por API** · **Referência** · **Adaptar** · **Descartar**.

## 1. Projetos jurídicos brasileiros

| Projeto | Existe? | Licença | Linguagem | Atividade (último commit visível) | O que oferece | Classificação | Justificativa |
|---|---|---|---|---|---|---|---|
| [andrecccruz/juris-br-mcp](https://github.com/andrecccruz/juris-br-mcp) | **Não** (HTTP 404 em 2026-11-24). Ainda aparece listado no diretório glama.ai | — | — | — | (segundo o diretório: DataJud + 91 tribunais, monitoramento) | **Descartar** | Repositório removido ou privado; não há código auditável. |
| [lab-dados/juscraper-mcp](https://github.com/lab-dados/juscraper-mcp) | Sim | MIT | Python | 2026-06-13 · 7 commits · 8★ | Servidor MCP do `juscraper` (FGV): `buscar_jurisprudencia`, `buscar_julgados_primeira_instancia`, `consultar_processo`, `datajud_*`, `buscar_comunicacoes_cnj`. Só fontes sem autenticação/captcha | **Referência** (e candidato a *Integrar* na Fase 7) | Licença permissiva e escopo correto (não contorna captcha). Pouco maduro (7 commits); usar a biblioteca `juscraper` por trás, não o servidor, depois de auditar. |
| [lab-dados/juscraper-app](https://github.com/lab-dados/juscraper-app) | Sim | **Não informada** | TypeScript/Python (Pyodide) | 2026-11-18 · 58 commits · 3★ | App estático que roda o `juscraper` no navegador: jurisprudência (cjsg/cjpg), DataJud por data | **Referência** | Sem licença declarada ⇒ não pode ser copiado. Útil como referência de UX de busca. |
| [edilsonfs/datajud-mcp](https://github.com/edilsonfs/datajud-mcp) | Sim | MIT | Python | 2026-09-01 · 7 commits · 2★ | MCP do DataJud: `consultar_processo`, `movimentacoes_processo`, `buscar_processos`, `contar_processos`, `listar_tribunais`… | **Referência** | Conector DataJud é simples (POST Elasticsearch por tribunal); escrevemos o nosso no padrão de conectores do EJMF, usando este como referência de mapeamento tribunal→endpoint. |
| [Lucianoartur/consulta-processual](https://github.com/Lucianoartur/consulta-processual) | Sim | **Não informada** | JavaScript | 2026-06-17 · 2 commits · 2★ | Consulta DataJud por número CNJ + DJEN por OAB/UF, monitoramento com cron | **Referência** | Sem licença; confirma o desenho DataJud (andamento) + DJEN (comunicações). |
| [rdrgzma/robo-juridico-api](https://github.com/rdrgzma/robo-juridico-api) | Sim | MIT | Go / Python / PHP | 2026-10-17 · 18 commits · 0★ | API DataJud + DJEN, certidão do DJEN, correlação DataJud↔DJEN, cálculos judiciais, portal, app desktop | **Referência** | Pilha poliglota (Go+Python+PHP) aumenta a complexidade; aproveitar ideias (certidão por `hash`, correlação), não o código. |
| [Filipe-Araujo0/pydatajud](https://github.com/Filipe-Araujo0/pydatajud) | Sim | Unlicense (domínio público) | Python | 2026-08-05 · 3 commits · 0★ | Validação/normalização do número CNJ, resolução tribunal→endpoint a partir de `J.TR`, consulta em lote agrupada por tribunal, `mode="status"` com `script_fields` | **Adaptar** | Licença permite cópia; é exatamente o que precisamos para o monitor DataJud em lote. Avaliar vendorizar trechos na Fase 3, com testes próprios. |

Achado extra da busca: [pdmtt/brlaw_mcp_server](https://github.com/pdmtt/brlaw_mcp_server) (MCP de pesquisa de legislação/jurisprudência brasileira) — **Referência** para a Fase 7, licença a confirmar.

Conclusão: **nenhum repositório público reúne o sistema pedido.** Os jurídicos brasileiros são pequenos (0–8★, 2–58 commits) e servem como referência de integração com DataJud e DJEN. A decisão é construir o núcleo próprio (ver ADR-0002).

## 2. Automação e inteligência artificial

| Projeto | Licença (GitHub) | Linguagem | Último push | ★ | Classificação | Justificativa |
|---|---|---|---|---|---|---|
| [n8n-io/n8n](https://github.com/n8n-io/n8n) | "Other" — *Sustainable Use License* (fair-code) | TypeScript | 2026-11-24 | 211.864 | **Integrar por API** (opcional, Fase 8) | Uso interno do próprio escritório é permitido pela licença fair-code; revenda não. Roda como serviço separado (~300–500 MB RAM). O EJMF terá automações próprias e determinísticas; n8n só para integrações de cauda longa. |
| [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | MIT | Python | 2026-11-24 | 45.327 | **Reutilizar** (Fase 8, como biblioteca) | Grafo de estados persistente, *checkpoints* em Postgres, limites de passos — casa com os requisitos do orquestrador (seção 28). |
| [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) | MIT | Python | 2026-11-23 | 61.215 | **Referência** | Modelo de "papéis" é útil para documentar as 40 funções, mas o controle fino de estado/aprovação é melhor no LangGraph. Evitar duas bibliotecas de agentes. |
| [langgenius/dify](https://github.com/langgenius/dify) | "Other" (Apache-2.0 com condições extras) | Python/TS | 2026-11-24 | 161.778 | **Descartar** | Plataforma completa e pesada (vários serviços); duplicaria o núcleo do EJMF e criaria dependência. |
| [FlowiseAI/Flowise](https://github.com/FlowiseAI/Flowise) | "Other" | TypeScript | 2026-08-13 | 55.593 | **Descartar** | **Repositório arquivado** (somente leitura) em 2026-11-24. |
| [BerriAI/litellm](https://github.com/BerriAI/litellm) | "Other" (núcleo MIT + pasta `enterprise` proprietária) | Python (núcleo Rust) | 2026-11-24 | 63.782 | **Reutilizar** (Fase 8, só o SDK) | Camada única para Claude/OpenAI/Gemini/Ollama com contagem de custo. Usar apenas o SDK MIT, sem o proxy/enterprise. Por trás de uma interface própria (`ProvedorIA`) para poder trocar. |
| [ollama/ollama](https://github.com/ollama/ollama) | MIT | Go | 2026-11-24 | 187.925 | **Integrar por API** (opcional) | Modelos locais para tarefas simples/sigilosas, se houver hardware. Exige GPU/RAM; custo de servidor maior. Desligado por padrão. |
| [temporalio/temporal](https://github.com/temporalio/temporal) | MIT | Go | 2026-11-24 | 24.574 | **Descartar (por ora)** | Excelente para execução durável, mas exige cluster próprio (Temporal + Cassandra/Postgres + UI). Para um advogado solo, fila em Postgres (`SKIP LOCKED`) atende com muito menos custo. Reavaliar se passar de ~100 mil tarefas/dia. |

## 3. Gestão documental e assinatura

| Projeto | Licença | Linguagem | Último push | ★ | Classificação | Justificativa |
|---|---|---|---|---|---|---|
| [paperless-ngx/paperless-ngx](https://github.com/paperless-ngx/paperless-ngx) | GPL-3.0 | Python/Django | 2026-11-24 | 48.543 | **Referência** / *Integrar por API* opcional | Ótimo DMS com OCR, mas é um sistema à parte (Django + Redis + Celery). Copiar código GPL obrigaria o EJMF a ser GPL. Usar como referência do pipeline (OCR → classificação → índice). |
| [documenso/documenso](https://github.com/documenso/documenso) | AGPL-3.0 | TypeScript/Next.js | 2026-11-24 | 15.891 | **Integrar por API** (Fase 6) | Rodar como serviço separado e falar por API não "contamina" o EJMF; modificar o Documenso obrigaria publicar as mudanças (AGPL). Assinatura simples/avançada; ICP-Brasil exige certificado — avaliar provedores comerciais compatíveis. |
| [jhpyle/docassemble](https://github.com/jhpyle/docassemble) | MIT | Python/JS | 2026-11-13 | 1.018 | **Referência** | Entrevistas guiadas e montagem de documentos (YAML). Conceito ótimo para a Entrevista Digital (seção 16), mas a pilha é pesada; implementar formulários dinâmicos próprios em JSON Schema. |
| [tesseract-ocr/tesseract](https://github.com/tesseract-ocr/tesseract) | Apache-2.0 | C++ | 2026-11-23 | 77.630 | **Reutilizar** (Fase 6) | Motor de OCR local, gratuito, com modelo `por`. Rodar no worker isolado (`ocrmypdf` + tesseract). |

## 4. Atendimento e administração

| Projeto | Licença | Linguagem | Último push | ★ | Classificação | Justificativa |
|---|---|---|---|---|---|---|
| [chatwoot/chatwoot](https://github.com/chatwoot/chatwoot) | "Other" (MIT + pasta `enterprise`) | Ruby/Vue | 2026-11-24 | 40.440 | **Referência** / *Integrar por API* opcional | Caixa de entrada multicanal com WhatsApp Cloud API. Rails + Sidekiq + Redis ⇒ ~1–2 GB RAM. Para um advogado solo, integrar a WhatsApp Cloud API diretamente é mais barato. |
| [calcom/cal.com](https://github.com/calcom/cal.com) | MIT (o endereço agora redireciona para **calcom/cal.diy**) | TypeScript | 2026-11-13 | 50.347 | **Referência** | A agenda do EJMF fica no Google Calendar (seção 13). Cal.diy é pesado para só agendamento; a página pública de horários será própria. Observação: o repositório mudou de nome; confirmar licença do fork antes de qualquer uso. |
| [twentyhq/twenty](https://github.com/twentyhq/twenty) | "Other" (AGPL-3.0 + partes comerciais) | TypeScript | 2026-11-24 | 61.389 | **Referência** | CRM moderno; as etapas do funil jurídico (seção 15) são específicas, então o CRM será um módulo próprio. |
| [frappe/erpnext](https://github.com/frappe/erpnext) | GPL-3.0 | Python | 2026-11-24 | 41.586 | **Descartar** | ERP completo, muito acima da necessidade de um escritório solo. |
| [metabase/metabase](https://github.com/metabase/metabase) | "Other" (AGPL-3.0 + enterprise) | Clojure | 2026-11-24 | 50.489 | **Integrar** (opcional, leitura) | Pode apontar para uma réplica/visão de leitura do Postgres para relatórios ad hoc. JVM ~1 GB RAM. Desligado por padrão. |

## 5. Segurança e infraestrutura

| Projeto | Licença | Linguagem | Último push | ★ | Classificação | Justificativa |
|---|---|---|---|---|---|---|
| [keycloak/keycloak](https://github.com/keycloak/keycloak) | Apache-2.0 | Java | 2026-11-23 | 38.017 | **Descartar (por ora)** | IAM completo exige JVM (~1 GB) e operação dedicada. Com 1 advogado + clientes no portal, autenticação própria (Argon2id + TOTP + sessões revogáveis) é suficiente e auditável. A interface de autenticação fica isolada para trocar por OIDC/Keycloak no futuro (ADR-0004). |
| [louislam/uptime-kuma](https://github.com/louislam/uptime-kuma) | MIT | JavaScript | 2026-11-24 | 94.804 | **Reutilizar** (Fase 11/12) | Monitor externo leve (~100 MB) para `/saude` da API, do site e das fontes judiciais. Deve rodar **fora** do servidor principal. |
| [qdrant/qdrant](https://github.com/qdrant/qdrant) | Apache-2.0 | Rust | 2026-11-23 | 35.679 | **Descartar (por ora)** | pgvector no mesmo PostgreSQL atende ~10⁵–10⁶ vetores e mantém o controle de acesso em SQL (seção 22: RAG respeita escopo). Reavaliar acima de alguns milhões de trechos. |

## 6. Fontes oficiais (integrações judiciais)

| Fonte | O que a documentação oficial diz (consultada em 2026-11-24) | Consequência para o EJMF |
|---|---|---|
| **DataJud — API Pública (CNJ)** — [wiki](https://datajud-wiki.cnj.jus.br/api-publica/acesso/) | Metadados de processos **públicos**. Autenticação por *Chave Pública* publicada na própria wiki, enviada em `Authorization: APIKey <chave>`; o CNJ pode trocar a chave a qualquer momento. Um endpoint por tribunal (`api-publica.datajud.cnj.jus.br/api_publica_<tribunal>/_search`). | Conector com chave em variável de ambiente (`DATAJUD_API_KEY`), nunca no código. Tratar 401 como "chave mudou" → alerta na central de contingência. **Não é canal de intimação.** Não traz processos sigilosos. |
| **DJEN — Comunicações processuais (CNJ)** — [Swagger 1.0.4](https://comunicaapi.pje.jus.br/swagger/index.html) | Consulta `GET /api/v1/comunicacao` **sem autenticação**; filtros `numeroOab`, `ufOab`, `numeroProcesso`, `siglaTribunal`, datas de disponibilização; `itensPorPagina` 5 ou 100; limite de taxa com HTTP 429 ("aguardar 1 minuto"); certidão em `/api/v1/comunicacao/{hash}/certidao`; cadernos diários por tribunal. Escrita é exclusiva dos tribunais. | Fonte primária de publicações/intimações por OAB 12.114/RN. Respeitar 429 com espera e *backoff*. Guardar `hash` e certidão como original. Relatos de terceiros indicam 403 para origem fora do Brasil ⇒ o servidor de produção deve estar no Brasil (ver COSTS). OAB com variações de grafia: consultar todas. |
| Domicílio Judicial Eletrônico (CNJ) | Exige autenticação gov.br/certificado da pessoa/empresa destinatária. | **Aguardando autorização**: não há API pública de leitura; não contornar. |
| PJe / eproc / e-SAJ / PROJUDI | Consultas públicas com captcha em muitos tribunais; APIs de integração (MNI) restritas a convênios. | **Não implementada** / *Aguardando autorização*. Não contornar captcha. |

## 7. Material de apoio do responsável

- `docs/origem/SUPERPROMPT-MASTER-5.0.md`: especificação principal.
- Conversa do ChatGPT compartilhada pelo Baden em 2026-11-24 (`chatgpt.com/share/6b04fe21-…`): é a **conversa que originou o superprompt**. O link público trouxe a primeira resposta completa (projeto inicial, módulos 01–08, ordem de desenvolvimento) e apenas as perguntas das rodadas seguintes; as respostas posteriores não vieram no compartilhamento. O que ela acrescenta ao superprompt e foi incorporado ao BACKLOG como itens futuros:
  - controle de horas trabalhadas, gestão de correspondentes/colaboradores, organizador de provas, linha do tempo visual por atendimento, estrutura multiempresa para eventual comercialização (`FUT-*`);
  - fontes oficiais prioritárias para a biblioteca: Planalto, CNJ, STF, STJ, TST, TJRN, TRT21, TRF5, JFRN, DJEN, LexML.
  - Divergência registrada: a conversa sugeria resumo diário às 7h; **o superprompt (mais recente) fixa 6h30**, que prevalece.
  - A conversa usava a marca antiga (proibida); não foi reaproveitada.

## 8. Decisão resultante

Construir o EJMF como **monólito modular próprio** (FastAPI + PostgreSQL + Next.js), reaproveitando por biblioteca o que é permissivo e maduro (LangGraph, SDK do LiteLLM, Tesseract, trechos do pydatajud) e integrando por API, como serviços separados e opcionais, os produtos com licença copyleft ou fair-code (Documenso, n8n, Metabase). Ver `DECISIONS.md` e `docs/adr/`.
