# PRIVACY — proteção de dados (LGPD)

> Este arquivo descreve recursos técnicos. As políticas jurídicas (finalidades, bases legais, prazos de retenção) devem ser **definidas e homologadas pelo advogado responsável**.

- **Minimização:** formulários por departamento pedem só o necessário (Fase 5).
- **Registro de finalidade:** cada coleta guarda a finalidade declarada (Fase 5).
- **Retenção:** políticas configuráveis por tipo de dado; exclusão controlada com registro (Fase 11).
- **Direitos do titular:** exportação, correção e exclusão controlada pelo portal e pelo painel (Fases 5 e 11).
- **Registro de acessos:** a auditoria registra leituras de dados sensíveis (CPF, documentos), não só alterações.
- **Isolamento:** dados de um cliente nunca aparecem para outro; a recuperação semântica (RAG) filtra por escopo antes da busca.
- **Desenvolvimento:** apenas dados sintéticos. Planilhas reais de trabalhadores (pasta `saidas/` do projeto) **não** entram no EJMF nem no Git.
- **Provedores de IA:** só aprovados pelo responsável, com retenção de dados verificada; dados sensíveis mascarados quando possível.
