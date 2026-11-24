# BACKUP — cópias e recuperação

> Situação: **cópia cifrada diária, retenção e teste de restauração automáticos (Fase 11, ADR-0015).** A cópia em outro
> provedor (S3 compatível) aguarda a conta do escritório. Um backup só conta como confiável depois de um teste de
> restauração aprovado; o EJMF trata "nunca testada" como atenção.

## O que entra na cópia
- `pg_dump -Fc` do banco inteiro, tirado no mesmo instante (snapshot exportado) em que são contadas as linhas de cada tabela.
- Os arquivos de `EJMF_ARQUIVOS_DIR` (originais e versões dos documentos, arquivos recebidos de clientes).
- Um manifesto: versão do banco (revisão do Alembic), linhas por tabela, SHA-256 e tamanho de cada arquivo, SHA-256 do
  dump e o último hash da cadeia de auditoria.

## Versão do cliente do PostgreSQL
`pg_dump` e `pg_restore` têm de ser da **mesma versão principal do servidor** (hoje 16). Um cliente mais novo grava
comandos que o servidor antigo não conhece (o 17 em diante grava `SET transaction_timeout`) e a cópia não restaura; um
mais antigo nem conecta. O EJMF confere isso antes de copiar e de restaurar e recusa com a instrução. A imagem Docker e
o CI instalam o `postgresql-client-16` do repositório oficial do PostgreSQL; fora deles, use `EJMF_PG_BIN_DIR`.

## Cifra
- AES-256-GCM em blocos de 1 MiB; cada bloco autentica a própria posição e se é o último. Arquivo trocado, cortado,
  reordenado ou aberto com a chave errada é recusado.
- A chave fica só em `EJMF_BACKUP_CHAVE` (base64url de 32 bytes), gerada com `python -m app.cli gerar-chave-backup`.
  **Guarde uma cópia da chave fora do servidor** (cofre de senhas do escritório ou papel em local seguro): sem ela,
  nenhuma cópia pode ser aberta, e com ela, qualquer cópia pode. A tela mostra só um identificador da chave.
- Sem a chave, o EJMF não faz cópia nenhuma (cópia sem cifra não existe) e o painel avisa "aguardando configuração".
- O dump em claro existe só por alguns segundos, numa pasta temporária com permissão 0700, e é apagado em seguida.
  O arquivo final é gravado com permissão 0600.

## Onde
- `EJMF_BACKUP_DIR` (padrão `dados/backups`). Use outro disco do servidor.
- **Pendente:** cópia em outro provedor (conta S3 compatível, a ser escolhida pelo escritório). Até lá, copie a pasta de
  cópias para fora do servidor regularmente (por exemplo, para um disco externo). Os arquivos já vão cifrados.

## Frequência, retenção e alertas
- Cópia diária a partir de `backup.hora` (padrão 02:00, fuso do escritório), pelo worker.
- Teste de restauração a cada `backup.teste_dias` (padrão 7), 30 minutos depois da cópia do dia.
- Retenção: 7 diárias, 5 semanais e 12 mensais (`backup.retencao_diarias`, `_semanais`, `_mensais`). A última cópia com
  restauração aprovada nunca é apagada pela retenção. Cada cópia apagada fica registrada na auditoria.
- Avisos (notificação e painel) para quem tem `backups:ler`: cópia que falhou, teste reprovado, última cópia há mais de
  `backup.horas_alerta` (padrão 26 h), teste com mais de 7 dias ou nunca feito. O aviso de atraso sai no máximo uma vez
  por dia. A automação "Cópia de segurança atrasada" e a função 38 (gestor de backups) leem o mesmo estado.

## Teste de restauração (automático)
1. Confere o SHA-256 do arquivo gravado.
2. Decifra, extrai e confere o SHA-256 do dump e de cada arquivo contra o manifesto.
3. Cria um banco descartável `ejmf_restauracao_<aleatório>`, restaura com `pg_restore --exit-on-error`.
4. Compara as linhas de cada tabela com o manifesto e verifica a cadeia de auditoria restaurada (íntegra e com o mesmo
   último hash).
5. Apaga o banco descartável e a pasta temporária, em qualquer resultado.

O resultado fica na cópia (tela Cópias de segurança) e na auditoria.

## RPO e RTO
- RPO: 24 h (cópia diária). Para chegar a 1 h é preciso arquivamento contínuo do WAL (pgBackRest ou similar) no servidor
  de produção: fica para a implantação, com o servidor escolhido.
- RTO: medido no teste de carga (ver TESTING.md, Fase 11): com 10 mil processos e 100 mil movimentações, a cópia e a
  restauração completas levam poucos segundos. A meta de 4 h cobre folgadamente reinstalar o servidor e restaurar.

## Procedimentos

### Restaurar depois de perder o servidor ou corromper o banco
1. Instale o EJMF num servidor novo (DEPLOYMENT.md) sem rodar `semear`.
2. Crie um banco **vazio** (`createdb ejmf_restaurado`) e tenha à mão a chave e o arquivo da cópia mais recente com
   restauração aprovada.
3. Rode, com a chave no ambiente:
   ```bash
   EJMF_BACKUP_CHAVE=... python -m app.cli restaurar --arquivo /caminho/ejmf-AAAAMMDDTHHMMSSZ-xxxx.ejmfbk \
     --destino postgresql+psycopg://usuario:senha@host:5432/ejmf_restaurado --arquivos-destino /dados/arquivos --confirmar
   ```
   O comando recusa banco com tabelas e pasta de arquivos com conteúdo, confere tudo pelo SHA-256 e mostra as contagens.
4. Aponte `EJMF_DATABASE_URL` e `EJMF_ARQUIVOS_DIR` para o restaurado, suba a API e o worker e rode
   `python -m app.cli verificar-auditoria`.
5. Confira a central de contingência: o que aconteceu entre a cópia e a falha (publicações, prazos) precisa ser
   recuperado pelas fontes oficiais. Ausência de informação não é ausência de acontecimentos.

### Exclusão acidental de um registro
Restaure a cópia anterior num banco à parte (passo 2 e 3 acima com outro nome), localize o registro e refaça-o no
sistema pela tela, para que a correção fique na auditoria. Nunca copie linhas direto entre bancos.

### Indisponibilidade de provedor ou integração
Ver OPERATIONS.md e a central de contingência (procedimento manual de cada fonte).

### Incidente de segurança
Ver SECURITY.md (relato de incidentes). Se a chave das cópias vazar: gere outra, faça uma cópia nova, teste a restauração
e apague as cópias antigas da pasta e de onde mais houver cópia.
