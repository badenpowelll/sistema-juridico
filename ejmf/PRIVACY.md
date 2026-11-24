# PRIVACY — proteção de dados (LGPD)

> Este arquivo descreve recursos técnicos. As políticas jurídicas (finalidades, bases legais, prazos de retenção) devem ser **definidas e homologadas pelo advogado responsável**.

- **Minimização (Fase 5):** formulários por departamento pedem só o necessário; o servidor descarta qualquer campo que não esteja no formulário do link.
- **Registro de finalidade (Fase 5):** cada link guarda a finalidade (cadastro ou documentos) e a cópia do formulário usado; o cliente vê o aviso de que o cadastro não cria contratação.
- **Retenção:** políticas configuráveis por tipo de dado; exclusão controlada com registro (Fase 11).
- **Direitos do titular:** exportação, correção e exclusão controlada pelo portal e pelo painel (Fases 5 e 11).
- **Registro de acessos:** a auditoria registra leituras de dados sensíveis (CPF, documentos), não só alterações.
- **CPF/CNPJ (Fase 2):** guardado cifrado; telas e relatórios mostram a versão mascarada; ver o documento completo é uma ação permitida só a quem tem a permissão e fica registrada na auditoria.
- **Importação (Fase 2):** o arquivo enviado não é guardado; ficam só as linhas necessárias para conferência e reversão.
- **Publicações (Fase 3):** o texto e o original ficam guardados porque são prova; leituras internas ficam registradas por pessoa. O sistema nunca registra ciência oficial sozinho.
- **Dados simulados (Fase 3):** o adaptador simulado gera só dados fictícios, marcados no texto, no banco (`simulado`) e na tela.
- **Agenda (Fase 4):** compromisso pessoal aparece como "Compromisso pessoal", sem título, local ou descrição, para quem não é o dono nem o responsável; o mesmo vale nos relatórios. Eventos marcados como privados no Google entram como "Ocupado". Só os eventos da agenda escolhida são lidos.
- **Atendimento (Fase 5):** o cadastro fica cifrado; abrir o cadastro de um atendimento fica registrado na auditoria. O relato é guardado como o cliente escreveu, sem correção ou interpretação. Arquivos enviados ficam fora do Git e do código.
- **Portal (Fase 5):** o cliente vê só os processos que a equipe liberou, só andamentos oficiais e audiências futuras; anotações internas, prazos e publicações nunca aparecem. O CPF aparece mascarado.
- **WhatsApp (Fase 5):** a recepcionista não informa dados de processo pelo chat (ADR-0009) e não guarda arquivos recebidos por ele.
- **Documentos (Fase 6):** o original fica guardado sem alteração, com o SHA-256, porque pode ser prova; o texto do OCR é uma versão separada e pode conter erros de leitura. Documentos sigilosos só aparecem para quem tem a permissão. O arquivo de um cliente recebido no atendimento entra no acervo ligado só a ele. Os campos dos modelos usam apenas dados confirmados pelo cliente ou pela equipe; o CPF é lido cifrado na hora de gerar e não fica copiado nos registros da minuta. O OCR roda no próprio servidor: nenhum documento é enviado a serviço externo para leitura.
- **Assinatura (Fase 6):** o Documenso recebe só o PDF aprovado e o nome e e-mail dos participantes indicados pela equipe.
- **Isolamento:** dados de um cliente nunca aparecem para outro; a recuperação semântica (RAG) filtra por escopo antes da busca.
- **Conhecimento (Fase 7):** os vetores da pesquisa são calculados no próprio servidor (sem enviar texto a serviço externo). Documentos e memórias de cliente só entram na pesquisa feita no escopo daquele cliente ou processo; documento arquivado, em quarentena ou excluído sai do índice. O monitor e o verificador só enviam aos sites oficiais o endereço da página consultada.
- **Memória (Fase 7):** memória sugerida automaticamente ou extraída de documento só vale depois de confirmada por pessoa; resposta de IA não vira fato sozinha. Correção cria registro novo e mantém o anterior como substituído. A exclusão controlada (`memoria:excluir`, com motivo) apaga título e texto e mantém só o registro de que existiu; a exportação traz as memórias do cliente (ou só as gerais) em JSON, com o histórico de correções, e fica registrada na auditoria.
- **Desenvolvimento:** apenas dados sintéticos. Planilhas reais de trabalhadores (pasta `saidas/` do projeto) **não** entram no EJMF nem no Git.
- **Provedores de IA (Fase 8):** nenhum dado vai a um modelo real sem que o advogado tenha aprovado aquele modelo registrando o que conferiu sobre retenção e uso para treino. Cada função envia só o material da própria tarefa (o texto da publicação, os dados do processo, o relato do atendimento, os trechos que a pesquisa devolveu no escopo do cliente ou processo); as ferramentas aplicam o mesmo escopo no SQL. Cada execução guarda o que foi pedido, o que voltou e quanto custou, para conferência. O modelo simulado não envia nada a lugar nenhum. Resposta de IA não vira fato: classificação, audiência e memória só valem depois que uma pessoa aplica ou aprova.
- **MCP (Fase 8):** quem conecta um cliente MCP recebe só o que já pode ver no painel, por ferramentas de leitura; o uso fica na auditoria.
