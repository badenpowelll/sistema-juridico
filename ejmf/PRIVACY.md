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
- **Desenvolvimento:** apenas dados sintéticos. Planilhas reais de trabalhadores (pasta `saidas/` do projeto) **não** entram no EJMF nem no Git.
- **Provedores de IA:** só aprovados pelo responsável, com retenção de dados verificada; dados sensíveis mascarados quando possível.
