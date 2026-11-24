# DECISIONS — registro de decisões

Decisões estruturais ficam em ADRs (`docs/adr/`). Decisões menores e reversíveis ficam aqui.

| Data | Decisão | Motivo | ADR |
|---|---|---|---|
| 2026-11-24 | EJMF na pasta `ejmf/` do repositório `sistema-juridico` | Sem permissão para criar repositório novo; `union-counsel-compass` é gerido pelo Lovable | 0001 |
| 2026-11-24 | Núcleo próprio; externos só como biblioteca permissiva ou serviço por API | Pesquisa no GitHub | 0002 |
| 2026-11-24 | FastAPI + SQLAlchemy/Alembic + PostgreSQL/pgvector + Next.js; fila em Postgres | Superprompt + custo | 0003 |
| 2026-11-24 | Autenticação própria (Argon2id, sessões opacas, TOTP, RBAC) | Custo e simplicidade | 0004 |
| 2026-11-24 | Auditoria só-inserção com cadeia de hash | Seção 36 | 0005 |
| 2026-11-24 | `escritorio_id` em todas as tabelas de negócio | Seção 40 (expansão futura) | 0006 |
| 2026-11-24 | Estados oficiais das integrações e adaptadores simulados marcados | Seções 42 e R | 0007 |
| 2026-11-24 | Carnaval, Paixão e Corpus Christi contam como dia útil até o advogado confirmar a suspensão | Prazos | 0008 |
| 2026-11-24 | Relatório diário às **6h30** (não 7h) | O superprompt prevalece sobre a conversa de origem | — |
| 2026-11-24 | Marcas antigas não usadas em nenhum arquivo | Ordem expressa do superprompt | — |
| 2026-11-24 | Dados institucionais (CNPJ, endereço, telefone, e-mail, WhatsApp) começam vazios e aparecem como pendência no painel | Não inventar dados | — |
| 2026-11-24 | Tipografia: Cormorant Garamond (títulos) + Inter (texto), via `next/font` empacotada no build | Sóbria e profissional, sem chamada a CDN em produção | — |
| 2026-11-24 | PRs #1 e #2 antigos do `sistema-juridico` ficam abertos, sem merge | Cabe ao Baden fechar; ideias reaproveitadas listadas no ADR-0003 | 0003 |
| 2026-11-24 | Recepcionista virtual por regras, sem informar dados de processo pelo chat | Sigilo: o WhatsApp identifica um número, não uma pessoa | 0009 |
| 2026-11-24 | Cadastro do cliente cifrado e relato guardado como escrito, com hash | Prova e fidelidade ao que o cliente declarou | — |
| 2026-11-24 | Modelos só geram documento depois de homologados; campos só com dado confirmado; pendência bloqueia a aprovação | Efeito jurídico do documento | 0010 |
| 2026-11-24 | Assinatura eletrônica só pelo Documenso real, sem adaptador simulado; envio é ato do advogado | Seção 25: não simular assinatura | 0010 |
| 2026-11-24 | OCR e extração fora do processo da API (subprocesso com tempo e memória limitados); o original nunca é alterado | Segurança e prova | — |
| 2026-11-24 | Arquivo com conteúdo ativo (JavaScript em PDF, macro em Office) vai para quarentena e não é aberto por nenhuma ferramenta até ser liberado | Segurança | — |
| 2026-11-24 | Vetorizador local e determinístico (termos com *feature hashing*, 384 posições) até a Fase 8; pesquisa híbrida com o texto | Sem serviço externo nem custo; a coluna `vetorizador` permite reindexar depois | 0011 |
| 2026-11-24 | Jurisprudência só entra em documento verificada no site oficial e homologada; referência de IA entra pendente | Seção 21: nunca aceitar referência da memória do modelo | 0011 |
| 2026-11-24 | Texto novo da fonte oficial é versão a conferir; o anterior continua valendo | Não tratar texto antigo como atual nem aceitar mudança sem conferência | 0011 |
| 2026-11-24 | Camada própria de provedores de IA (SDK oficial da Anthropic + API compatível com OpenAI + simulado), sem LiteLLM | Só dois formatos de API; dependência grande e incidente de cadeia de suprimentos | 0012 |
| 2026-11-24 | Modelo real só aprovado pelo advogado (retenção conferida), com preço cadastrado e tetos diário e mensal | Sigilo profissional e controle de custo | 0012 |
| 2026-11-24 | Saída de IA validada contra o material (trecho literal, data no trecho, citação que a pesquisa devolveu) antes de virar sugestão | IA não inventa fato nem referência | 0012 |
| 2026-11-24 | Automações com construtor interno e lista fechada de ações; n8n não adotado | Menos um serviço e nenhuma credencial do EJMF fora dele | 0012 |
| 2026-11-24 | Servidor MCP só de leitura, com token pessoal e permissões atuais do dono | Uso do EJMF por clientes MCP sem abrir escrita | 0012 |
| 2026-11-24 | Pedido de aprovação feito por função virtual fica em nome da função | Permite que quem pediu a execução decida a proposta, sem autoaprovação de pedido próprio | 0012 |
