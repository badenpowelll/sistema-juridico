# DATABASE

PostgreSQL 16 (`ejmf_db`) com extensões `pgcrypto`, `citext`, `pg_trgm`, `unaccent` (e `vector` a partir da Fase 7). Migrações Alembic em `backend/migracoes/`. Toda tabela de negócio tem `escritorio_id` (ADR-0006).

## Fase 1

```
escritorios 1─┬─< usuarios >─┬─< usuario_perfis >── perfis ──< perfil_permissoes >── permissoes
              │              └─< sessoes
              ├─< departamentos
              ├─< configuracoes   (chave/valor JSON: dados institucionais, flags)
              ├─< integracoes     (estado oficial de cada fonte)
              └─< auditoria       (só inserção, hash encadeado)
```

| Tabela | Observações |
|---|---|
| `escritorios` | Um registro hoje (EJMF). |
| `usuarios` | `email` citext único por escritório; `senha_hash` Argon2id; `mfa_segredo` cifrado; `falhas_login`, `bloqueado_ate`. |
| `perfis`, `permissoes`, `perfil_permissoes`, `usuario_perfis` | RBAC. Permissão = `recurso:acao`. |
| `sessoes` | `token_hash` (SHA-256), `expira_em`, `ultimo_uso_em`, `revogada_em`, IP e agente. |
| `departamentos` | 18 áreas + "Outras" semeadas; `ativo`, `ordem`. |
| `configuracoes` | Dados institucionais começam `null` (não inventados). |
| `integracoes` | `estado` restrito aos seis valores oficiais; `simulado`; `ultima_execucao_em`, `ultimo_sucesso_em`, `ultimo_erro`. |
| `auditoria` | `ator_tipo` (usuario/agente/sistema), `operacao`, `entidade`, `entidade_id`, `alteracoes` JSON mascarado, `resultado`, `trace_id`, `hash_anterior`, `hash`. Gatilho bloqueia UPDATE/DELETE/TRUNCATE. |

## Fase 2 (`0002_gestao_processual`)

```
escritorios ─┬─< clientes ──────────────┐
             ├─< processos >── tribunais │
             │      ├─< processo_partes >┘ (cliente_id opcional)
             │      └─< movimentacoes
             └─< importacoes ──< importacao_linhas (processo_id, cliente_id)
```

| Tabela | Observações |
|---|---|
| `tribunais` | Catálogo semeado (95), chave `codigo` "J.TR" (ex.: `8.20` = TJRN). |
| `clientes` | `tipo` PF/PJ; `documento_cifrado` (Fernet), `documento_hash` (HMAC, único por escritório), `documento_mascarado`; `nome_normalizado` com índice trigram; `contatos` JSON; `origem` e `importacao_id`. |
| `processos` | `numero` com 20 dígitos, único por escritório; `tribunal_codigo`, `departamento_id`, `classe`, `assuntos` JSON, `status` (ativo, suspenso, arquivado, encerrado), `valor_causa`, `data_distribuicao`; `texto_busca` mantido pela aplicação, `busca` tsvector gerado, índices GIN (tsvector e trigram). |
| `processo_partes` | `polo` (ativo, passivo, terceiro, outro), `papel`, `cliente_id` opcional. |
| `movimentacoes` | `tipo` (movimentacao, anotacao, sistema), `ocorrido_em`, `descricao`, `codigo_tpu`, `origem`, `autor_id`. Movimentação não é intimação (essas chegam na Fase 3). |
| `importacoes` | Arquivo (nome, SHA-256, formato), colunas, mapeamento, `status`, totais. O arquivo em si não é guardado. |
| `importacao_linhas` | Uma por linha do arquivo, nunca descartada: `original`, `normalizado`, `situacao`, `mensagens`, `candidatos` (homônimos), quem resolveu e quando. |

## Fase 3 (`0003_controladoria`)

```
escritorios ─┬─< calendario
             ├─< regras_prazo (codigo, versao)
             ├─< publicacoes >── processos ──< prazos >── regras_prazo
             │      └─< publicacao_leituras       └─< alertas_prazo
             ├─< execucoes_integracao >── integracoes
             └─< tarefas (chave única)
```

| Tabela | Observações |
|---|---|
| `calendario` | `data`, `nome`, `tipo` (feriado, suspensao, possivel_suspensao), `abrangencia` (nacional, `segmento:N`, `tribunal:J.TR`, `uf:XX`), `fundamento`, `confirmado` e quem confirmou, `origem` (semente ou manual), `ativo`. Feriado previsto em lei não pode ser desativado. |
| `regras_prazo` | Versionadas por `codigo`; `contagem` (uteis, corridos), `termo_inicial` (disponibilizacao_djen, intimacao), `suspensao_recesso`, `segmentos`, `situacao` (nao_homologada, homologada, substituida) e quem homologou. |
| `publicacoes` | `fonte`, `id_externo` (único por fonte), `numero_processo`, `processo_id`, `texto`, `texto_hash`, `original` JSON intacto, `disponibilizado_em`, `publicado_em`, `ciencia_em` e quem registrou, `capturado_em`, `classificacao`, `situacao` (nao_conferida, conferida, descartada, duplicada), `duplicada_de_id`, `simulado`. |
| `publicacao_leituras` | Quem abriu, quantas vezes e quando. Leitura interna não é ciência. |
| `prazos` | `descricao`, `dias`, `dobro` e fundamento, `data_base`, `inicio_contagem`, `vencimento`, `vencimento_alternativo`, `calculo` JSON (memória completa), `regra_id`, `situacao`, conferência, homologação e conclusão com autor e data, `origem`, `simulado`. |
| `alertas_prazo` | Um por prazo, limiar e vencimento (único), com ciência. Se o vencimento muda, os alertas recomeçam. |
| `execucoes_integracao` | Cada sincronização: parâmetros, resultado, contagens e erro. |
| `tarefas` | Fila: `tipo`, `chave` única por escritório (idempotência), `estado`, tentativas, `agendada_para`, erro e resultado. Tirada com `FOR UPDATE SKIP LOCKED`. |

Também nesta migração: `integracoes.falhas_consecutivas` e `circuito_aberto_ate`; `movimentacoes.chave_externa` (única quando preenchida) para não duplicar andamentos do DataJud.

## Fase 4 (`0004_agenda_secretaria`)

| Tabela | Observações |
|---|---|
| `compromissos` | `tipo` (audiencia, reuniao, atendimento, compromisso, lembrete, bloqueio, trabalho_concentrado, pessoal, externo), `titulo`, `inicio`/`fim` com fuso, `dia_inteiro`, `modalidade`, `local`, `link_virtual`, `processo_id` (obrigatório em audiência), `responsavel_id`, `participantes`, `situacao` (agendado, realizado, cancelado), `resultado`, motivo de cancelamento, `origem` (ejmf, google), `google_event_id` (único quando preenchido), `removido_no_google`, `simulado`. |
| `credenciais_integracao` | Uma por escritório e integração: `dados_cifrados` (Fernet: tokens OAuth) e `estado` JSON (syncToken, state e verificador PKCE temporários, conta). Nunca devolvida pela API. |
| `pendencias` | Itens da central de prioridades: `origem` (sistema, manual), `chave` única para os automáticos, `classe`, `pontuacao`, `justificativa`, `critica`, responsável, prazo, `adiada_ate`, resolução. |
| `aprovacoes` | Pedidos que esperam decisão humana: `tipo`, entidade, `dados`, quem pediu, `situacao` (pendente, aprovada, rejeitada, devolvida, cancelada), quem decidiu e motivo. |
| `relatorios` | `tipo` (diario, encerramento) e `referencia` únicos por escritório; `conteudo` JSON e `entregas` por canal. |
| `notificacoes` | Por usuário, com `chave` única opcional (não repete o mesmo aviso), `nivel`, `link` e `lida_em`. |

Também nesta migração: `prazos.google_event_id` e `prazos.google_vencimento`.

## Fase 5 (`0005_atendimento_crm`)

| Tabela | Observações |
|---|---|
| `atendimentos` | `protocolo` único (AT + ano/mês + 5 caracteres), contato (nome, telefone, e-mail), `assunto`, `canal`, `etapa` (14 valores) e `etapa_em`, `cliente_id`, `processo_id`, `departamento_id`, `responsavel_id`, observações internas, motivo de encerramento, quem conferiu e quando, `simulado`. |
| `links_cadastro` | `token_hash` único (o token nunca é guardado), `finalidade` (cadastro, documentos), `formulario` (cópia do formulário no momento da geração), `expira_em`, revogação, `concluido_em`, `usos`, primeiro e último uso, último IP e canal de envio. |
| `cadastros_atendimento` | Um por atendimento: `conteudo_cifrado` (Fernet: dados, relato, cronologia e entrevista), campos preenchidos, passo, `relato_hash` (SHA-256 do relato no momento da confirmação), confirmação e IP. |
| `documentos_recebidos` | Nome original, tipo detectado pelo conteúdo, tamanho, `sha256` (deduplicação por atendimento), `caminho` relativo em `EJMF_ARQUIVOS_DIR`, documento previsto, `origem` (link, portal, whatsapp, painel), `situacao` (recebido, aceito, recusado) e motivo. |
| `acessos_portal` | Um por cliente: e-mail (único), `senha_hash` (Argon2id), convite (hash e validade), falhas e bloqueio, ativação e último login. |
| `sessoes_portal` | Sessões do cliente, separadas das da equipe: hash do token, IP, último uso e expiração. |
| `solicitacoes_portal` | Pedidos do cliente (mensagem, atendimento, atualizar dados), situação e resposta da equipe. |
| `conversas` | Uma por canal e contato (único): `estado` (recepcionista, humano, encerrada), `contexto` JSON da recepcionista, última mensagem do contato (janela de 24 h), não lidas, vínculos com cliente e atendimento, `simulado`. |
| `mensagens` | Entrada e saída, `autor` (contato, recepcionista, equipe), `intencao` reconhecida, `id_externo` único quando preenchido, `situacao` (recebida, pendente, enviada, entregue, lida, falha, simulada) e erro. |

Também nesta migração: `processos.portal_visivel` e o tipo de autor `cliente` na auditoria.

## Fase 6 (`0006_documentos_modelos`)

| Tabela | Observações |
|---|---|
| `documentos` | Título, `categoria` (21 valores) e quem classificou (`regra`/`pessoa`), vínculos com cliente, processo e atendimento, `origem` (upload, recebido, gerado, assinado), `situacao` (ativo, arquivado, quarentena) e motivo, `sigiloso`, `sha256` do original (deduplicação por escritório), `versao_atual`, documento recebido e minuta de origem. Índice trigrama no título. |
| `versoes_documento` | `numero` único por documento, `tipo` (original, texto_extraido, nova_versao, pdf_gerado, assinado), `derivada_de`, arquivo (nome, tipo, tamanho, `sha256`, `caminho` em `EJMF_ARQUIVOS_DIR`), páginas, `texto`, `extracao` (pendente, concluida, ilegivel, sem_texto, nao_aplicavel, falha, indisponivel), método, confiança do OCR e erro. Coluna `busca` (tsvector em português, gerada) com índice GIN. |
| `modelos_documento` | `codigo` + `versao` únicos, título, categoria, departamento, conteúdo HTML restrito, cabeçalho, rodapé, `situacao` (rascunho, homologado, substituido, arquivado), sugerido pelo sistema, quem homologou e quando. |
| `modelos_favoritos` | Favorito por usuário e código do modelo. |
| `minutas` | Título, modelo e versão usados, categoria, vínculos, conteúdo, cabeçalho, rodapé, `campos` (valor e fonte de cada campo, sem o CPF), `pendentes`, `situacao` (rascunho, em_revisao, aprovada, arquivada), versão atual, revisão pedida, aprovação e documento final. |
| `versoes_minuta` | Cópia do conteúdo por versão, com motivo (criação, automática, manual, aprovação, devolução) e autor. |
| `comentarios_minuta` | Trecho, texto, autor e resolução. |
| `assinaturas` | Provedor (`documenso`), `id_externo` único por provedor, `situacao` (preparada, enviando, enviada, parcial, concluida, recusada, cancelada, falha), participantes e eventos (JSON), mensagem, quem preparou e quem autorizou o envio, datas e erro. |

As tabelas das fases seguintes são documentadas aqui quando a migração correspondente é criada.
