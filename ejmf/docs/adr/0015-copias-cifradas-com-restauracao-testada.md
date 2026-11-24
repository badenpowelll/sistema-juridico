# ADR-0015 — Cópias de segurança cifradas, com restauração testada, e homologação sem serviço externo

Data: 2026-11-24 · Situação: aceita

## Contexto
A especificação (§37) pede backups automatizados, criptografados, versionados, em armazenamento separado, com retenção,
integridade, testes periódicos de restauração e alertas: "backup sem teste de restauração não é confiável". A Fase 11
também pede segurança (§34: antivírus de uploads, verificação de dependências, limite de requisições) e isolamento. O
escritório ainda não tem conta em provedor de armazenamento, e não se contrata serviço pago sem autorização.

## Decisão
- **Cópia própria, sem ferramenta externa:** `pg_dump -Fc` + arquivos + manifesto num tar, cifrado por AES-256-GCM em
  blocos (formato `EJMFBK01`) com a biblioteca `cryptography`, já usada pelo projeto. `age`, `gpg`, restic e pgBackRest
  foram considerados: exigiriam outro binário e outra gestão de chave sem ganho para um escritório solo; pgBackRest
  continua indicado para o WAL contínuo em produção (RPO de 1 h).
- **Chave só no ambiente**, separada de `EJMF_CHAVE_SECRETA`, guardada também fora do servidor. Sem chave, nada é feito.
- **Contagens no mesmo instante do dump** (snapshot exportado), para o teste de restauração poder comparar linha a linha.
- **Teste de restauração real e automático** num banco descartável, com contagens, SHA-256 de cada arquivo e a cadeia de
  auditoria restaurada; o banco descartável é sempre apagado.
- **Restaurar de verdade só pela linha de comando**, num banco vazio e com `--confirmar`. A API não baixa nem restaura
  cópia: baixar seria exfiltração de tudo numa chamada, e restaurar por cima do banco em uso é irreversível.
- **Retenção** diária, semanal e mensal; a última cópia aprovada no teste nunca é apagada.
- **Cópia externa** (S3 compatível) fica "aguardando credenciais"; a pasta local já guarda só arquivos cifrados.
- **Antivírus pelo clamd** (protocolo INSTREAM, socket local ou TCP), sem enviar arquivo para fora. Infectado é recusado
  e não é gravado; com o antivírus configurado e fora do ar, o arquivo entra em quarentena (não se perde nem entra às
  cegas); sem configuração, vale a checagem de conteúdo ativo da Fase 6.
- **Limite de tentativas no PostgreSQL** (`contadores_taxa`, janela deslizante aproximada), compartilhado por todos os
  processos da API: login, portal, rotas públicas e MCP. Redis foi descartado: mais um serviço para um contador pequeno.
- **CSP** só com a própria origem; os scripts embutidos do Next pedem `'unsafe-inline'` (nonce exigiria renderização
  dinâmica de todas as páginas). `frame-ancestors 'none'`, `object-src 'none'`, `form-action 'self'`, HSTS em produção.
- **pip-audit e npm audit no CI.**

## Consequências
- O RPO fica em 24 h até haver WAL contínuo no servidor de produção.
- A chave das cópias é um segredo crítico: perdida, as cópias não abrem; vazada, todas abrem.
- A cópia local não protege contra perda do servidor inteiro enquanto não houver cópia externa ou cópia manual para fora.
- O antivírus depende de assinaturas atualizadas (freshclam); neste ambiente o servidor de assinaturas não é alcançável,
  e o teste usa o clamd real com uma assinatura de teste local.
