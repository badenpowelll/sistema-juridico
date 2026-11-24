# ADR-0009 — A recepcionista virtual não informa dados pelo chat

Data: 2026-11-24 · Situação: aceita

## Contexto
O WhatsApp identifica um número de telefone, não uma pessoa. Um número pode estar com um parente, ter sido trocado ou clonado. Se a recepcionista respondesse andamento de processo, valores ou prazos pelo chat, qualquer pessoa com acesso ao aparelho (ou ao número) receberia informação protegida pelo sigilo profissional. Perguntas como "tenho direito?" ou "devo assinar?" exigem análise do advogado.

## Decisão
- A recepcionista é feita por regras (sem IA): saudação e menu, horário de atendimento, abertura de atendimento com envio do link seguro de cadastro, pedido de documentos pelo link, oferta de horários livres e transferência para a equipe.
- Pedido de informação de processo nunca é respondido no chat: ela indica o portal do cliente, que tem login próprio.
- Pergunta que pede análise profissional é transferida para a equipe sem resposta de mérito. Depois de duas mensagens não entendidas, também transfere.
- Agendamento escolhido pelo contato vira pedido na central de aprovações; o compromisso só é criado depois que alguém da equipe aprova.
- Arquivos enviados pelo chat não são guardados: ela pede que o contato use o link seguro.
- Quando alguém da equipe responde, assume a conversa e a recepcionista para até a conversa ser devolvida.

## Consequências
- O contato às vezes precisa de um passo a mais (entrar no portal) para ver o próprio processo.
- Nenhuma informação sigilosa sai por um canal sem autenticação forte.
- A troca para respostas com IA (Fase 8) mantém as mesmas regras como limite.
