# ADR-0016 — Produção autohospedada: Caddy, WAL arquivado, cópia externa S3 e prontidão verificável

Data: 2026-11-24 · Situação: aceita

## Contexto
O Baden autorizou o início da Fase 12 (produção) em 2026-11-24. A especificação (§37 e seção R) pede RPO de 1 h,
cópia em outro lugar, monitoramento e "não pronto para produção enquanto segurança, recuperação, isolamento e
homologação não forem atendidos". O escritório ainda não tem servidor, domínio nem conta de armazenamento, e nada pago
é contratado sem autorização. Por isso, a fase deixa tudo pronto e testado localmente, e a implantação real fica no
roteiro (IMPLANTACAO.md), a cargo do responsável.

## Decisão
- **Um Docker Compose de produção** (`docker-compose.producao.yml`). Só o Caddy expõe as portas 80 e 443; banco, API,
  worker, web e antivírus ficam na rede interna. O HTTPS é automático (Let's Encrypt), e o domínio e o e-mail vêm do
  `.env.producao`. Kubernetes foi descartado: é demais para um escritório solo num único servidor.
- **WAL arquivado pelo próprio PostgreSQL** (`archive_command` com script de cópia sem sobrescrita, `archive_timeout`
  de 15 min) e **cópia física diária** (`pg_basebackup`) num serviço `wal`, com limpeza do WAL que nenhuma cópia
  física mantida ainda usa (`pg_archivecleanup`). A recuperação a um ponto no tempo é feita por `infra/wal/recuperar.sh`.
  O pgBackRest foi descartado: não tem imagem oficial alcançável aqui e traz mais uma ferramenta e mais uma
  configuração, sem ganho para um banco desse tamanho. O RPO passa de 24 h para no máximo 15 min de WAL.
- **Cópia externa pelo SDK oficial da AWS (boto3)**, que atende qualquer provedor S3 compatível pelo endpoint. Vai o
  arquivo já cifrado, que é lido de volta e conferido por tamanho e SHA-256. A credencial recomendada só grava e lê,
  e o EJMF nunca apaga lá fora: a retenção externa é a regra de ciclo de vida do bucket, com bloqueio de objetos, para
  que um servidor invadido não apague as cópias externas. Escrever a assinatura SigV4 à mão foi descartado: seria
  código de segurança próprio, onde há SDK oficial.
- **Prontidão verificável** (`verificar-producao`, `/api/v1/producao/prontidao` e uma tela própria). Os itens perigosos
  demais, como adaptador simulado ligado, endereço sem HTTPS, senha de exemplo do banco ou chave fraca, também
  impedem a API de subir com `EJMF_AMBIENTE=producao`. A verificação em duas etapas do administrador é sempre
  obrigatória em produção.
- **Monitor externo** em `/api/v1/saude/componentes`, que só devolve nomes e situações (banco, worker, cópias, WAL e
  disco) e responde 503 quando algo precisa de alguém.
- **Acesso perdido:** o administrador redefine o de outra pessoa pela tela, e a senha provisória é mostrada uma vez.
  Para o próprio administrador, quando não há outro, a redefinição é feita só pela linha de comando no servidor. Uma
  rota pública de "esqueci a senha" por e-mail fica de fora enquanto o e-mail institucional não existir.

## Consequências
- O WAL fica em claro no segundo disco do servidor, como o próprio banco. Ele não deve ser copiado para fora sem
  cifra (BACKUP.md). A cópia externa continua sendo a lógica cifrada, diária.
- A imagem Docker não foi construída neste ambiente, porque a rede bloqueia os repositórios do Debian e do PGDG dentro
  do build. A primeira construção acontece no servidor.
- Implantar, registrar domínio, contratar servidor e S3, e fazer o ensaio cronometrado continuam a cargo do
  responsável.
