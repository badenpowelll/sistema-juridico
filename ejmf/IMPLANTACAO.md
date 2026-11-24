# IMPLANTAÇÃO — roteiro para colocar o EJMF em produção

> Fase 12. Este roteiro **não foi executado**. O código está pronto para ele, mas cada passo marcado com **(responsável)**
> depende de uma decisão, de uma conta ou de um pagamento do escritório e só acontece com autorização expressa. Nenhum
> servidor foi contratado, nenhum domínio foi registrado e nada foi publicado.

## Antes de começar
- A homologação (HOMOLOGACAO.md) está concluída, ou o escritório decidiu por escrito começar com parte dela pendente.
- Em `/painel/producao` (ou `python -m app.cli verificar-producao`), nada aparece como **Bloqueia** no ambiente de
  homologação, configurado como o de produção.

## 1. Infraestrutura (responsável)
| Item | Decisão do escritório | Observação |
|---|---|---|
| Servidor | VPS no Brasil, 4 vCPU, 8 GB de RAM e 160 GB de SSD, com **dois discos** (ou um volume extra) | Região Brasil por causa do DJEN. O teste de carga (TESTING.md, Fase 11) mostra folga para 10 mil processos. O antivírus precisa de uns 3 GB de memória. |
| Domínio | `.adv.br` ou `.com.br` no Registro.br | O DNS aponta para o IP do servidor (registro A/AAAA). |
| E-mail para o certificado | um e-mail do escritório | O Let's Encrypt avisa nele quando há problema com o certificado. |
| Armazenamento externo | conta S3 compatível em **outro provedor** | Crie o bucket com bloqueio de objetos (object lock) e uma regra de ciclo de vida (por exemplo, 90 dias). Crie uma credencial que só grava e lê, sem permissão de apagar. |
| Monitor externo | Uptime Kuma noutra máquina, ou serviço de monitoramento | Vigia `https://DOMINIO/api/v1/saude/componentes` (503 quando algo precisa de alguém). |

## 2. Servidor
```bash
# no servidor (Debian ou Ubuntu), com Docker e o plugin compose instalados
git clone <repositório> ejmf && cd ejmf/ejmf
cp .env.producao.example .env.producao && chmod 600 .env.producao
# preencha .env.producao: domínio, e-mail, senha do banco, EJMF_CHAVE_SECRETA, pastas no segundo disco
docker compose -f docker-compose.producao.yml --env-file .env.producao build
docker compose -f docker-compose.producao.yml --env-file .env.producao run --rm api python -m app.cli gerar-chave-backup
# coloque a chave em EJMF_BACKUP_CHAVE e guarde uma cópia FORA do servidor (cofre de senhas e papel em local seguro)
```
- As pastas `EJMF_COPIAS_DIR` e `EJMF_WAL_DIR` ficam no **segundo disco**, com dono `999` (usuário do PostgreSQL) para
  o WAL e permissão `700`.
- Firewall: só as portas 80 e 443 abertas, além do SSH com chave (sem senha).

## 3. Subir e conferir
```bash
docker compose -f docker-compose.producao.yml --env-file .env.producao up -d
docker compose -f docker-compose.producao.yml --env-file .env.producao exec api python -m app.cli criar-admin --email <e-mail do Dr. Márcio> --nome "Márcio Oliveira Fernandes"
docker compose -f docker-compose.producao.yml --env-file .env.producao exec api python -m app.cli verificar-producao
```
1. Abra `https://DOMINIO`: o certificado deve ser válido e a página de entrada deve aparecer.
2. Entre como administrador. A primeira tela pede a verificação em duas etapas, que em produção é obrigatória.
3. Em **Configurações**, preencha os dados institucionais. O sistema não os inventa.
4. Em **Cópias de segurança**, faça uma cópia agora e teste a restauração. O resultado deve ser "aprovado".
5. Em **Prontidão para produção**, nenhum item deve aparecer como "Bloqueia". Anote os itens com "Atenção" que
   ficam pendentes de propósito (por exemplo, integrações ainda sem conta).

## 4. Ensaio de recuperação, feito por uma pessoa e cronometrado (responsável)
Antes de cadastrar dados reais:
1. **Cópia lógica:** baixe a cópia externa (`baixar-copia-externa`) e restaure num banco vazio de outra máquina com
   `restaurar --confirmar` (BACKUP.md). Anote o tempo.
2. **Ponto no tempo:** com `infra/wal/recuperar.sh`, recupere até um instante escolhido e confira as últimas
   alterações. Anote o tempo.
3. Registre os dois tempos em TESTING.md. A meta de RTO é de 4 h.

## 5. Dados reais
- Importe os processos pela tela Importação. Nada é descartado em silêncio: inconsistências e duplicidades ficam para
  conferência.
- Ligue as integrações uma a uma, cada uma com a sua credencial (INTEGRATIONS.md). Cada integração mostra o próprio
  estado e não depende das outras.
- Na primeira semana, confira todos os dias a Contingência, as Cópias de segurança e a Prontidão para produção.

## 6. Rotina de produção
| Quando | O quê | Onde |
|---|---|---|
| Diária, automática | Cópia lógica cifrada (02:00), envio ao S3 e conferência por SHA-256; cópia física e limpeza do WAL (03:00) | worker e serviço `wal` |
| Semanal, automática | Teste de restauração num banco descartável | worker |
| Contínua | WAL arquivado a cada segmento ou a cada 15 min no máximo | PostgreSQL |
| Contínua | Monitor externo em `/api/v1/saude/componentes` | Uptime Kuma |
| Mensal (pessoa) | Conferir a prontidão, as atualizações de segurança do servidor e `pip-audit`/`npm audit` no CI | Painel e GitHub |
| Trimestral (pessoa) | Ensaio de recuperação do item 4 | Outra máquina |

## 7. Atualizar uma versão
```bash
git pull && docker compose -f docker-compose.producao.yml --env-file .env.producao build
docker compose -f docker-compose.producao.yml --env-file .env.producao exec worker python -m app.cli backup   # cópia antes
docker compose -f docker-compose.producao.yml --env-file .env.producao up -d   # a API aplica as migrações ao subir
docker compose -f docker-compose.producao.yml --env-file .env.producao exec api python -m app.cli verificar-producao
```
Se algo der errado, volte a imagem anterior. Se a migração já tiver rodado, restaure a cópia feita antes da atualização.
Em nenhum dos dois casos se corrige dado direto no banco.
