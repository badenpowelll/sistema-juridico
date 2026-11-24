# ROADMAP

Fases do superprompt (seção 47). Cada fase termina com testes reais, atualização de PROGRESS.md e um PR.

| Fase | Entrega | Critérios de aceitação (resumo) | Situação |
|---|---|---|---|
| 0 | Diagnóstico e planejamento | RESEARCH com os 28 repositórios avaliados; ARCHITECTURE; ADRs; BACKLOG priorizado; CLAUDE.md; COSTS | em andamento → PR |
| 1 | Fundação | `docker compose up` sobe db/api/worker/web; migrações do zero; login com Argon2id + sessão revogável + TOTP; RBAC testado (403 sem permissão); auditoria encadeada com verificação; marca centralizada (claro/escuro); painel com "O que exige minha atenção agora" a partir de dados reais; testes automatizados passando | planejada |
| 2 | Gestão processual | CRUD de processos/clientes/partes; número CNJ validado (dígito verificador); importação CSV/XLSX/JSON com pré-visualização, mapeamento, duplicidades, relatório de inconsistências, fila de conferência e reversão; linha do tempo; pesquisa global com permissões; carga de 1k/5k/10k processos e 100k movimentações medida | planejada |
| 3 | Controladoria | Publicações com datas separadas (disponibilização/publicação/ciência/captura); conectores DJEN e DataJud no padrão `Conector`; conferência; motor de prazos determinístico com feriados e memória de cálculo; estados do prazo; alertas configuráveis; central de contingência | planejada |
| 4 | Agenda e secretaria | Google Calendar (OAuth, aguardando credenciais) com adaptador simulado; agenda dia/semana/mês; relatório 6h30 e de encerramento; central de prioridades e de aprovações | planejada |
| 5 | Atendimento e CRM | Funil de 14 etapas; links de cadastro com token, validade e revogação; formulários por departamento; entrevista; portal do cliente isolado | planejada |
| 6 | Documentos | Upload seguro, original preservado, OCR (Tesseract), modelos parametrizados, DOCX/PDF, versões, minutas como rascunho, assinatura via Documenso (API) | planejada |
| 7 | Conhecimento | Biblioteca versionada, jurisprudência com status de verificação, RAG com pgvector respeitando escopo | planejada |
| 8 | IA | Camada `ProvedorIA` (SDK LiteLLM), orquestrador com limites, catálogo das 40 funções, autonomia 0–4, custos | planejada |
| 9 | Financeiro | Honorários, lançamentos, previsto/faturado/recebido, fluxo de caixa, rentabilidade; reaproveitar motor da calculadora | planejada |
| 10 | PWA e experiência | Manifesto, service worker sem cache de documentos confidenciais, voz, notificações | planejada |
| 11 | Homologação | Segurança, carga, restauração de backup, homologação profissional pelo Dr. Márcio | depende do responsável |
| 12 | Produção | Implantação **somente com autorização** | depende do responsável |
