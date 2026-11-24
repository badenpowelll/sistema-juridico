# ADR-0011 — Conhecimento verificado na fonte e escopo aplicado antes da busca

Data: 2026-11-24 · Situação: aceita

## Contexto
A Fase 7 cria a base de conhecimento do escritório: normas, súmulas, julgados, documentos e a memória das decisões internas. Três riscos orientam o desenho: citar um julgado que não existe ou cujo conteúdo foi trocado (o erro típico de referência "lembrada" por modelo de linguagem), usar texto de lei já alterado ou revogado como se fosse atual, e mostrar a um cliente, ou no trabalho de um cliente, informação de outro.

## Decisão
- **Jurisprudência só entra em documento verificada e homologada.** O verificador é independente de qualquer IA: baixa a página original do site oficial do tribunal (lista fechada de domínios em `fontes_conhecimento`) e confere, de forma determinística, número, ementa, relator e data. Os estados são verificada, divergente, não localizada, fonte indisponível e pendente. Só o advogado (`jurisprudencia:homologar`) homologa, e só julgado verificado. Qualquer alteração nos dados conferidos desfaz verificação e homologação. Referência sugerida por IA entra sempre como pendente.
- **Citação em minuta é marcada** (`<span data-jurisprudencia>`). A aprovação reconfere cada citação e recusa se alguma não estiver verificada e homologada; ao aprovar, o texto de cada citação é reescrito a partir dos dados conferidos.
- **Texto de norma tem versão e vigência separadas.** Cada coleta da fonte oficial vira uma versão com data, endereço e SHA-256. Texto novo entra "a conferir" e o anterior continua em uso até a conferência. A vigência é declarada por pessoa (`biblioteca:conferir`) e volta a "a conferir" quando o texto muda. O sistema só alerta: revogado, vigência não conferida, versão nova pendente, fonte não consultada há mais de 30 dias ou com erro.
- **Obra protegida sem licença fica só como referência**, sem texto copiado.
- **Escopo no SQL, antes da ordenação.** Cada trecho indexado guarda `cliente_id`, `processo_id` e `sigiloso`. Sem escopo, a pesquisa só alcança conhecimento do escritório; com cliente, o dele; com processo, o daquele processo; cliente que não é parte do processo é recusado. Sigilo e permissão de cada origem também são condições do SQL. Assim nenhum trecho de outro cliente entra no conjunto que é ordenado, nem chega a um futuro modelo de linguagem (Fase 8).
- **Vetorizador local até a Fase 8.** Sem provedor de IA aprovado, os vetores (384 posições, `pgvector`, índice HNSW) vêm de *feature hashing* dos termos, calculado no servidor, e a ordenação combina semelhança de termos (55%) e relevância textual do PostgreSQL (45%). A tela diz que é "busca por semelhança de termos (sem IA)". A coluna `vetorizador` permite reindexar com embeddings reais sem mudar o esquema.
- **Memória só vale confirmada.** Sugestão automática ou extraída de documento entra "a confirmar" e fica fora da pesquisa. Correção cria registro novo e mantém o anterior como substituído; exclusão é controlada, com motivo, e apaga o conteúdo.

## Consequências
- Julgado de tribunal cujo site exige JavaScript ou captcha fica "fonte indisponível" e não pode ser citado até haver outra forma oficial de conferência; o advogado pode cadastrar o endereço de outra página oficial (inteiro teor, diário).
- O monitor e o verificador não foram validados contra as fontes reais neste ambiente (rede bloqueada); funcionam com respostas gravadas nos testes e dependem de servidor com acesso a esses sites.
- A busca por semelhança local não reconhece sinônimos; a busca textual em português (radicais) compensa parte disso até a Fase 8.
