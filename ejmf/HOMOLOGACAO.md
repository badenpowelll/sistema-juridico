# HOMOLOGAÇÃO — roteiro para o Dr. Márcio

> Fase 11. Este roteiro serve para o advogado responsável conferir, no próprio sistema, que o EJMF faz o que a
> especificação pede antes de qualquer uso real. Cada cenário já tem teste automático (coluna "Teste"), mas a
> homologação profissional é a conferência humana: só o Dr. Márcio pode dizer que a regra jurídica, o texto e o fluxo
> estão certos. Use apenas dados sintéticos até a homologação terminar.

## Como usar
1. Suba o EJMF num ambiente de homologação (`EJMF_AMBIENTE=homologacao`), separado do que um dia será produção.
2. Para cada cenário abaixo, siga "Onde conferir" e marque o resultado na coluna "Conferido" (data e rubrica).
3. O que depender de credencial ou conta (coluna "Depende de") fica como **não homologado** até a credencial existir:
   o cenário pode ser conferido com o adaptador simulado, que aparece sempre com o selo "Simulado".
4. Anote qualquer divergência como item do BACKLOG; nada vai para produção com divergência aberta em prazo,
   publicação, documento ou dado de cliente.

## Cenários de aceitação (especificação, seção E)

| # | Cenário | Onde conferir | Teste automático | Depende de | Conferido |
|---|---|---|---|---|---|
| 1 | Início do expediente: relatório das 6h30 e painel só com prioridades | Central de comando; Relatórios > Diário | `test_secretaria::test_relatorio_diario_e_de_encerramento_idempotentes_com_entregas`, `test_agendador_dos_relatorios_respeita_horario_e_nao_repete`; E2E `secretaria.spec.ts` | Envio por e-mail ou WhatsApp (ainda não sai) | |
| 2 | Novo cliente pelo WhatsApp recebe link seguro, preenche, envia documentos e vai para conferência | Atendimentos; simulador do WhatsApp; link de cadastro | `test_atendimento::test_recepcionista_abre_atendimento_manda_link_e_transfere_duvida_juridica`, `test_link_de_cadastro_fluxo_completo_com_minimizacao_cifra_e_documentos` | Conta Meta Business e `EJMF_WHATSAPP_*` | |
| 3 | Preparação documental com modelos aprovados (procuração, hipossuficiência, contrato) | Documentos > Modelos; Minutas | E2E `documentos.spec.ts`; `test_documentos` | **Homologar os 4 modelos iniciais** | |
| 4 | Nova publicação: original preservado, processo identificado, duplicidade verificada, conferência criada, prazo sugerido pendente | Publicações; Prazos | E2E `controladoria.spec.ts`; `test_controladoria` | DJEN validado num servidor no Brasil; **homologar as 5 regras de contagem e os feriados locais** | |
| 5 | Pesquisa de jurisprudência com originais e situação de verificação | Conhecimento > Jurisprudência | E2E `conhecimento.spec.ts`; `test_conhecimento` | Rede com acesso aos sites dos tribunais | |
| 6 | Minuta a partir do processo e do modelo, com dados confirmados e referências selecionadas, pendente de revisão | Processo > Minuta; Minutas | E2E `documentos.spec.ts` | Modelos homologados | |
| 7 | Cliente consulta o processo no portal: última movimentação, data da sincronização e dúvidas jurídicas ao advogado | Portal do cliente | `test_atendimento::test_portal_isolado_so_mostra_o_liberado` | `EJMF_URL_PUBLICA` | |
| 8 | Falha de integração: registro, tentativas limitadas, processos afetados e instruções de contingência | Contingência | E2E `controladoria.spec.ts` (central de contingência); `test_controladoria` (circuit breaker) | — | |
| 9 | Importação de 5 mil processos sem descartar nada em silêncio | Importação | `testes_carga` (5.100 linhas: 5.000 importadas, 50 inválidas e 50 duplicadas apontadas); E2E `gestao.spec.ts` | — | |
| 10 | Comando por voz: "processos sem atualização registrada nos últimos 90 dias" | Assistente (ligar a voz) | E2E `pwa.spec.ts` (voz com reconhecimento simulado); `test_ia` (consulta por regras) | Decidir se a voz fica ligada (o áudio vai ao Google ou à Microsoft) | |
| 11 | Encerramento do expediente: concluídas, pendências e compromissos do dia seguinte | Relatórios > Encerramento | `test_secretaria::test_relatorio_diario_e_de_encerramento_idempotentes_com_entregas` | — | |
| 12 | Financeiro: honorários recebidos, pendentes, despesas e rentabilidade | Financeiro | E2E `financeiro.spec.ts`; `test_financeiro` | Cadastrar as contas reais e homologar o modelo de recibo | |
| 13 | Recuperação de falha: importação interrompida retomada sem duplicidade | Importação | `test_importacao::test_execucao_interrompida_retoma_sem_duplicar` | — | |
| 14 | Atualização da biblioteca: mudança normativa detectada, origem registrada, versões preservadas, conferência | Conhecimento > Biblioteca | `test_conhecimento::test_monitor_coleta_detecta_mudanca_preserva_versao_e_exige_conferencia` | Rede com acesso ao Planalto e ao LexML | |

## Requisitos para produção (especificação, seção R)

"Não pronto para produção enquanto segurança, recuperação, isolamento de dados e homologação não forem atendidos."

| Requisito | Situação no código | O que falta (responsável) |
|---|---|---|
| Segurança | Argon2id, MFA, sessões revogáveis, permissões por ato, CSRF, limite de tentativas compartilhado, auditoria encadeada, política de conteúdo (CSP), antivírus pronto, varredura de dependências no CI (ver SECURITY.md) | Ativar MFA de todas as contas; instalar o ClamAV no servidor; HTTPS com certificado; revisão de segurança externa recomendada |
| Recuperação | Cópia cifrada diária com retenção, teste de restauração semanal num banco descartável, alertas, restauração pela linha de comando (BACKUP.md, ADR-0015) | Gerar e guardar a chave fora do servidor; cópia em outro provedor (conta S3 compatível); um ensaio de restauração completo feito por pessoa, cronometrado |
| Isolamento de dados | Tudo com `escritorio_id`; teste de isolamento entre escritórios (listas, pesquisa, pesquisa no conteúdo, detalhes e vínculos); portal isolado; escopo de cliente e processo na pesquisa e nas ferramentas de IA | — |
| Homologação | Este roteiro | Conferência dos 14 cenários, das regras de prazo, dos feriados locais, dos modelos e das instruções das funções de IA |

## Pendências de configuração que bloqueiam a homologação completa
Lista viva em PROGRESS.md, seção "Pendências que dependem do responsável".
