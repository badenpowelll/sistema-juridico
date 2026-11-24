# ADR-0014 — PWA sem dados guardados no aparelho, notificação genérica e voz opcional

Data: 2026-11-24 · Situação: aceita

## Contexto
A Fase 10 transforma o EJMF num aplicativo instalável (PWA) para celular e computador, com notificações e comandos por voz (§29 e §33). A especificação pede proteger sessões e dados locais, não guardar documentos confidenciais offline por padrão e permitir revogar sessões e aparelhos. Celulares se perdem, notificações aparecem na tela bloqueada e o reconhecimento de voz do Chrome e do Edge envia o áudio aos servidores do Google ou da Microsoft.

## Decisão
- **Service worker só guarda arquivos públicos**: a página "Sem conexão" (`/offline`), os ícones e os arquivos estáticos versionados do Next (`/_next/static/`). Navegações vão sempre à rede e, sem conexão, mostram a página "Sem conexão". Nada de `/api`, nenhuma página do painel, documento ou dado de cliente fica no aparelho. Não há modo offline com dados; se um dia houver, será opção explícita e cifrada.
- **Sair apaga** as caches, cancela a assinatura de notificações do navegador e desliga o service worker; o servidor revoga as assinaturas da sessão. Encerrar uma sessão em Segurança (ou todas) também revoga as notificações dos aparelhos daquela sessão.
- **Web Push com VAPID (RFC 8292) e cifragem aes128gcm (RFC 8291)** implementados no próprio EJMF (biblioteca `cryptography`, sem serviço intermediário pago). As chaves são geradas localmente (`python -m app.cli gerar-vapid`) e ficam só em variáveis de ambiente; sem elas, a integração fica "aguardando credenciais" e a tela diz isso.
- **Conteúdo da notificação é genérico** ("Nova notificação no EJMF" ou "Alerta no EJMF" e "Abra o sistema para ver."), sem nome de cliente, número de processo ou prazo: o texto aparece na tela bloqueada e passa pelo serviço de push do fabricante do navegador. O detalhe só é visto depois de entrar.
- **Endereços de push limitados** aos serviços conhecidos (Google, Mozilla, Apple e Microsoft), para que o servidor não seja usado para chamar endereços arbitrários. Até 10 aparelhos por pessoa; 404/410 e cinco falhas seguidas revogam; 429 e 5xx tentam de novo pela fila. Cada pessoa vê e desliga só os próprios aparelhos e pode escolher receber só os alertas urgentes.
- **Voz desligada por padrão.** O reconhecimento usa a Web Speech API do navegador; como o áudio vai aos servidores do fabricante, só o advogado (`ia:gerenciar`) liga a voz para o escritório, com o aviso na tela, e a decisão fica na auditoria. O texto reconhecido passa pelas mesmas regras do assistente por texto (recusa do que altera, confirmação antes de criar pendência) e fica marcado com o canal "voz". A leitura das respostas em voz alta usa a síntese de voz do próprio aparelho e é escolha de cada pessoa.
- **Transcrição de áudio no servidor** (arquivos de áudio, Whisper ou provedor aprovado) continua pendente: exige escolher e aprovar um provedor ou rodar um modelo local (F8-15).

## Consequências
- Sem conexão, o EJMF não mostra dados; é o preço de não deixar dados no aparelho.
- Notificações dizem pouco; a pessoa precisa abrir o sistema para ver o que houve.
- Web Push real só pode ser validado com chaves VAPID e um navegador com serviço de push alcançável (não é o caso deste ambiente).
- iPhone só recebe notificação com o EJMF instalado na tela inicial (iOS 16.4 ou mais).
