# AUTOMATIONS

> Situação: **implementado na Fase 8** (ADR-0012). Tela: Automações.

## Como funciona
- Uma automação é: **gatilho** (lista fechada) → **condições** (todas precisam valer) → **ações** (lista fechada) → **janela de horário** opcional (dias úteis, de/até). Fuso `America/Fortaleza`.
- O worker verifica as automações ativas a cada ciclo (15 s). Cada gatilho é uma varredura idempotente: toda ocorrência tem uma chave e **nunca é tratada duas vezes** (índice único por automação e chave).
- **Teste obrigatório**: a versão atual tem de ser testada antes de ativar. O teste roda sobre os dados de agora (últimos 7 dias para gatilhos de novidade), mostra o que dispararia e **não faz nada**.
- Editar cria **nova versão** e devolve a automação ao rascunho (precisa de novo teste). Automação desativada não é editada.
- Ao ativar, só age sobre o que acontecer dali em diante (e sobre estados atuais, como contrato parado).
- **Três falhas seguidas pausam** a automação e avisam quem tem `automacoes:gerenciar`. Cada ocorrência roda num ponto de salvamento: a falha de uma não desfaz as outras.
- Permissões: `automacoes:ler` (ver), `automacoes:gerenciar` (criar, editar, testar), `automacoes:ativar` (ativar, pausar, desativar com motivo). Tudo auditado.

## Gatilhos
| Gatilho | Parâmetros | Campos para condições |
|---|---|---|
| Novo cliente | — | nome, tipo, origem |
| Documento recebido | — | arquivo, origem, documento previsto |
| Publicação capturada | — | processo, tribunal, tipo, texto |
| Contrato aguardando assinatura | dias parado (3), repetir a cada N horas (24) | documento, situação, dias |
| Compromisso próximo | horas de antecedência (24) | tipo, título, início |
| Processo sem atualização | dias (90), repetir a cada N dias (30) | processo, dias sem movimentação |
| Prazo sem homologação | dias até o vencimento (5) | descrição, processo, vencimento, situação |
| Falha de integração | — (uma vez por dia por fonte) | fonte, motivos |
| Honorário pendente | indisponível até a Fase 9 | — |
| Backup não realizado | indisponível até a Fase 11 | — |

Operadores: é igual a, é diferente de, contém, não contém, é maior que, é menor que.

## Ações
- **Notificar** quem tem uma permissão (título e texto com `{campo}` do evento).
- **Criar pendência** na central de prioridades (chave por automação e ocorrência; não se repete).
- **Pedir uma função virtual** compatível com o gatilho (publicação → organizador de audiências; processo sem atualização → classificador processual; falha de integração → monitor de integrações). A função segue o próprio nível: no organizador, nível 3 gera pedido na central de aprovações.
- Não existe ação de enviar mensagem, e-mail, assinar, protocolar, cobrar ou pagar.

## n8n
Avaliado e não adotado (ADR-0012): exigiria outro serviço, outra base de usuários e credenciais do EJMF guardadas fora dele, para fluxos que o construtor interno já cobre.
