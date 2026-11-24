# ADR-0010 — Documentos só com dado confirmado, aprovação do advogado e assinatura real

Data: 2026-11-24 · Situação: aceita

## Contexto
Procurações, declarações e contratos produzem efeito jurídico. Um campo preenchido com dado errado (um CPF trocado, uma qualificação incompleta) ou um documento "assinado" por um simulador cria risco real para o cliente e para o escritório. A especificação proíbe simular assinatura e pede aprovação profissional antes de qualquer versão final.

## Decisão
- Modelos têm versão e situação. Só o modelo **homologado** pelo advogado (`modelos:homologar`) gera minuta. Os quatro modelos iniciais entram em rascunho, marcados como sugeridos pelo sistema. Editar um modelo homologado cria uma nova versão em rascunho e a homologada continua valendo até a nova ser homologada.
- Os campos `{{...}}` só são preenchidos com dados confirmados: a ficha do cliente e o cadastro que o próprio cliente confirmou pelo link. A qualificação só é montada com nacionalidade, estado civil, profissão, CPF e endereço; faltando qualquer um, o campo fica **[PENDENTE]**, destacado no editor e no DOCX. Campos `{{manual.*}}` são preenchidos na minuta por quem a edita. O CPF não é guardado no registro de campos da minuta.
- A aprovação (`minutas:aprovar`) exige zero pendências e nenhum comentário aberto. Ela trava o texto, gera o PDF e o guarda no acervo. Antes disso, qualquer exportação sai com "RASCUNHO — documento não aprovado, não assinar" no cabeçalho.
- Assinatura eletrônica só pelo Documenso real. **Não há adaptador simulado.** Sem a chave da API, o pedido pode ser preparado, mas o envio é recusado e a integração fica "Aguardando credenciais". O envio exige `assinaturas:enviar` (advogado); quem assina é cada participante, no Documenso. O EJMF nunca assina por ninguém.
- O acompanhamento vem do webhook do Documenso, aceito só com o segredo configurado (comparação em tempo constante).

## Consequências
- Sem as credenciais do Documenso, o fluxo para em "preparada": o escritório colhe a assinatura por outro meio e anexa o arquivo como nova versão.
- O documento assinado é baixado do Documenso e guardado como nova versão manualmente, até a integração ser validada contra a conta real.
- A equipe precisa homologar os modelos antes do primeiro uso (pendência listada em PROGRESS.md).
