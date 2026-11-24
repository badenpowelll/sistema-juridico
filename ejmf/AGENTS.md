# AGENTS — equipe virtual de 40 funções

> Situação: **implementado na Fase 8** (ADR-0012). As 40 funções estão cadastradas e aparecem em Inteligência artificial > Funções virtuais.
> Seis funções usam IA pelo orquestrador, seis rodam por regras pelo orquestrador, vinte já são serviços do sistema nas próprias telas
> e oito dependem de módulos de fases futuras. Todas começam **desligadas**; o advogado liga, escolhe o modelo e o nível.
> Funções são acionadas sob demanda pelo orquestrador; regras determinísticas são usadas sempre que bastam ("IA: não").
> Nível = teto de autonomia da seção 45 (0 consulta · 1 preparação · 2 automação administrativa · 3 aprovação obrigatória · 4 restrita, nunca autônoma).

Campos completos por função (entradas, saídas, ferramentas, permissões, limites, falhas, dependências, critério de sucesso, auditoria) estão no catálogo em código (`backend/app/servicos/ia/catalogo.py`) e na ficha de cada função no painel; a configuração do escritório (ligada, nível, modelo, reserva, limites, orçamento, ferramentas desligadas) fica na tabela `ia_funcoes`. Regras comuns a todas (aplicadas pelo orquestrador, não configuráveis):

- Ferramentas por lista de permissões, parâmetros validados por schema, saída estruturada validada.
- Conteúdo de e-mails, documentos, páginas e resultados de ferramentas é **dado não confiável**; instruções contidas neles nunca são executadas.
- Escopo de dados limitado ao cliente/processo da tarefa; nenhuma função tem acesso direto ao banco, ao terminal ou a arquivos.
- Limites de iterações, tempo e orçamento por execução; o orquestrador não concede permissões a si nem a outros.
- Toda execução registra função, versão do prompt/regra, modelo, custo, entradas resumidas, saídas e aprovação.
- Modelo real só com aprovação do advogado para dados do escritório, preço cadastrado e tetos diário e mensal definidos.
- Saída de IA passa por validação própria (trecho literal, data no trecho, citação que a pesquisa devolveu); o que não passa é descartado.
- Nível 3 vira pedido na central de aprovações; nível 4 nunca é executado.

| # | Departamento | Função | Objetivo | Gatilho principal | IA | Nível |
|---|---|---|---|---|---|---|
| 1 | Secretaria executiva | Diretor-geral de operações | Orquestrar tarefas, dependências e prioridades | Eventos do sistema | Sim (roteamento) + regras | 2 |
| 2 | Secretaria executiva | Secretária executiva | Relatórios 6h30 e de encerramento | Agendador | Opcional (redação) | 1 |
| 3 | Secretaria executiva | Recepcionista virtual | Atendimento administrativo e envio de links | Mensagem recebida | Sim | 2 (respostas profissionais: 3) |
| 4 | Secretaria executiva | Assistente de voz | Transcrever comandos e responder | Áudio do advogado | Sim (STT) | 0–1 |
| 5 | Secretaria executiva | Gestor de e-mails | Classificar e organizar o Gmail | Novo e-mail | Sim + regras | 1 (envio: 3) |
| 6 | Controladoria | Monitor de intimações | Capturar publicações (DJEN, Gmail) | Agendador | Não | 2 |
| 7 | Controladoria | Controlador de prazos | Sugerir prazos pelo motor determinístico | Publicação conferida | Não | 1 (homologar: 3) |
| 8 | Controladoria | Conferente de registros | Dupla conferência e divergências | Prazo sugerido | Não | 1 |
| 9 | Controladoria | Gestor de agenda | Conflitos, bloqueios e sincronização | Evento/prazo homologado | Não | 2 |
| 10 | Controladoria | Fiscal de pendências | Detectar pendências vencendo | Agendador | Não | 1 |
| 11 | Gestão processual | Monitor processual | Movimentações via DataJud | Agendador | Não | 2 |
| 12 | Gestão processual | Importador de processos | Importação em massa e reconciliação | Upload | Não | 2 (ambíguos: fila) |
| 13 | Gestão processual | Classificador processual | Sugerir departamento/assunto | Processo novo | Opcional | 1 |
| 14 | Gestão processual | Organizador de audiências | Extrair e agendar audiências | Publicação | Opcional | 1 (agendar: 3) |
| 15 | Gestão processual | Gestor de histórico processual | Linha do tempo consolidada | Movimentação | Não | 2 |
| 16 | Pesquisa | Pesquisador de jurisprudência | Buscar em fontes oficiais | Pedido do advogado | Sim (consulta) | 0–1 |
| 17 | Pesquisa | Monitor legislativo | Detectar alterações normativas | Agendador | Não | 1 |
| 18 | Pesquisa | Bibliotecário institucional | Versionar e indexar a biblioteca | Item novo | Opcional | 2 |
| 19 | Pesquisa | Verificador de referências | Confirmar cada citação na fonte | Minuta/pesquisa | Não (busca exata) | 1 |
| 20 | Pesquisa | Atualizador da base | Reindexar e marcar vigência | Agendador | Não | 2 |
| 21 | Documental | Organizador de documentos | OCR, classificação, duplicidades | Upload | Opcional | 2 |
| 22 | Documental | Assistente de modelos e minutas | Preencher modelos e montar rascunhos | Pedido do advogado | Sim | 1 |
| 23 | Documental | Revisor estrutural | Checar campos pendentes e estrutura | Minuta pronta | Opcional | 1 |
| 24 | Documental | Organizador de evidências | Ligar fatos a documentos | Atendimento | Opcional | 1 |
| 25 | Documental | Gestor de assinaturas | Acompanhar envelopes | Evento do provedor | Não | 2 (envio: 3; assinar: 4) |
| 26 | Financeiro | Gestor financeiro | Consolidar lançamentos | Agendador | Não | 1 |
| 27 | Financeiro | Controlador de honorários | Parcelas e atrasos | Agendador | Não | 1 |
| 28 | Financeiro | Gestor de cobranças | Preparar lembretes autorizados | Parcela vencida | Opcional | 3 (cobrar externamente: 4) |
| 29 | Financeiro | Conciliador financeiro | Conciliar extratos importados | Importação | Não | 1 |
| 30 | Financeiro | Analista de rentabilidade | Indicadores por processo/departamento | Agendador | Não | 0 |
| 31 | Relacionamento | Cadastrador de clientes | Links de cadastro e validação | Atendimento novo | Não | 2 |
| 32 | Relacionamento | Assistente de WhatsApp | Canal WhatsApp Business oficial | Mensagem | Sim | 2 (dados de processo só após identificar o cliente) |
| 33 | Relacionamento | Gestor do portal do cliente | O que é publicado no portal | Mudança autorizada | Não | 3 |
| 34 | Relacionamento | Monitor de solicitações | Fila de pedidos de clientes | Solicitação | Não | 1 |
| 35 | Relacionamento | Gestor de relacionamento | Retornos pendentes | Agendador | Opcional | 1 |
| 36 | Auditoria e segurança | Auditor de operações | Verificar a cadeia de auditoria | Agendador | Não | 0 |
| 37 | Auditoria e segurança | Fiscal de segurança | Acessos anômalos, sessões | Evento de login | Não | 1 |
| 38 | Auditoria e segurança | Gestor de backups | Executar e testar restauração | Agendador | Não | 2 |
| 39 | Auditoria e segurança | Monitor de integrações e contingência | Saúde das fontes e alertas | Agendador | Não | 2 |
| 40 | Auditoria e segurança | Analista de produtividade | Métricas coletadas, gargalos | Agendador | Opcional | 0 |

## Situação de cada função (Fase 8)

| # | Função | Como roda hoje | Onde |
|---|---|---|---|
| 1 | Diretor-geral de operações | Serviço do sistema | É o orquestrador do EJMF: fila persistente, deduplicação por chave, limites e retomada de tarefas interrompidas. |
| 2 | Secretária executiva | Com IA (orquestrador) | Relatórios da Fase 4; o resumo por IA só usa o próprio relatório como fonte. |
| 3 | Recepcionista virtual | Serviço do sistema | Recepcionista por regras da Fase 5 (ADR-0009). Agendamentos vão para a central de aprovações. |
| 4 | Assistente de voz e texto | Com IA (orquestrador) | Assistente por texto (Fase 8) e por voz (Fase 10, reconhecimento do navegador, desligado até o advogado ligar; ADR-0014). Comandos conhecidos são resolvidos por regras; IA só para o que as regras não entendem. O comando falado passa pelas mesmas regras do texto. Transcrição de arquivos de áudio no servidor ainda pendente (F8-15). |
| 5 | Gestor de e-mails | Fase futura | Depende da integração com o Gmail (aguardando credenciais). |
| 6 | Monitor de intimações | Serviço do sistema | Sincronização da Fase 3 (6h, 12h e 18h). |
| 7 | Controlador de prazos | Serviço do sistema | Motor de prazos da Fase 3. IA nunca calcula datas. |
| 8 | Conferente de registros | Serviço do sistema | Estados do prazo e dupla conferência da Fase 3. |
| 9 | Gestor de agenda | Serviço do sistema | Agenda da Fase 4. |
| 10 | Fiscal de pendências | Por regras (orquestrador) | Central de prioridades da Fase 4. |
| 11 | Monitor processual | Serviço do sistema | Conector DataJud da Fase 3 (aguardando chave). |
| 12 | Importador de processos | Serviço do sistema | Importação da Fase 2 com fila de conferência. |
| 13 | Classificador processual | Com IA (orquestrador) | Usa só os dados do próprio processo e suas movimentações. |
| 14 | Organizador de audiências | Com IA (orquestrador) | Usa só o texto da publicação. O trecho citado precisa existir literalmente no texto. |
| 15 | Gestor de histórico processual | Serviço do sistema | Prontuário da Fase 2. |
| 16 | Pesquisador de jurisprudência e conhecimento | Com IA (orquestrador) | Pesquisa com escopo da Fase 7; julgado citado sem verificação fica marcado. |
| 17 | Monitor legislativo | Serviço do sistema | Monitor da Fase 7 (5h). |
| 18 | Bibliotecário institucional | Serviço do sistema | Biblioteca da Fase 7. |
| 19 | Verificador de referências | Serviço do sistema | Verificador da Fase 7 (sem IA). |
| 20 | Atualizador da base de conhecimento | Por regras (orquestrador) | Indexação da Fase 7. |
| 21 | Organizador de documentos | Serviço do sistema | Acervo e extração da Fase 6. |
| 22 | Assistente de modelos e minutas | Serviço do sistema | Preenchimento por regras da Fase 6 (campo sem dado confirmado fica [PENDENTE]). Redação por IA não foi ativada: exige revisão de risco própria. |
| 23 | Revisor estrutural | Por regras (orquestrador) | Regras sobre a minuta da Fase 6 e as citações da Fase 7. |
| 24 | Organizador de evidências | Fase futura | Planejada; depende de revisão do fluxo de atendimento. |
| 25 | Gestor de assinaturas | Serviço do sistema | Documenso da Fase 6 (aguardando credenciais). |
| 26 | Gestor financeiro | Por regras (orquestrador) | Posição do dia e alertas (vencidos, despesas da semana, extrato por conciliar ou sem importação há 35 dias). Números saem dos lançamentos da Fase 9. |
| 27 | Controlador de honorários | Por regras (orquestrador) | Atrasos por cliente (vencido e a vencer em 15 dias) e contratos com êxito de processo encerrado ainda sem lançamento. |
| 28 | Gestor de cobranças | Por regras (orquestrador) | Prepara o texto do lembrete de uma receita vencida visível no portal; nível 3 vira pedido na central de aprovações (`financeiro:cobrar`). Só no portal: nada por e-mail ou WhatsApp. |
| 29 | Conciliador financeiro | Por regras (orquestrador) | Lista linhas de extrato pendentes com sugestão única, várias ou nenhuma. Conciliar continua sendo ato de pessoa. |
| 30 | Analista de rentabilidade | Por regras (orquestrador) | Resultado por processo e por departamento no período; custos operacionais à parte, sem rateio; custo de IA em US$. |
| 31 | Cadastrador de clientes | Serviço do sistema | Links de cadastro da Fase 5. |
| 32 | Assistente de WhatsApp | Serviço do sistema | Cloud API da Fase 5 (aguardando credenciais). |
| 33 | Gestor do portal do cliente | Serviço do sistema | Portal da Fase 5; liberar processo é ato de pessoa. |
| 34 | Monitor de solicitações | Serviço do sistema | Pedidos do portal (Fase 5) entram na central de prioridades. |
| 35 | Gestor de relacionamento | Com IA (orquestrador) | Memória da Fase 7: sugestão entra como 'a confirmar'. |
| 36 | Auditor de operações | Por regras (orquestrador) | Verificação encadeada da Fase 1. |
| 37 | Fiscal de segurança | Serviço do sistema | Bloqueio após falhas e limite por IP da Fase 1. |
| 38 | Gestor de backups | Fase futura | Backup externo: Fase 11. |
| 39 | Monitor de integrações e contingência | Por regras (orquestrador) | Central de contingência da Fase 3. |
| 40 | Analista de produtividade | Por regras (orquestrador) | Métricas das filas, pendências e execuções. |
