# Arquitetura do Sistema Jurídico

Documento da Etapa 1. Consolida os cinco prompts de `docs/especificacao-original.md` em uma arquitetura única e define o que será construído, com qual tecnologia e em que ordem (ver `docs/PLANO.md`).

## 1. Visão geral

O sistema tem duas áreas separadas e um conjunto de serviços no servidor.

| Área | Quem usa | Endereço | Acesso |
|---|---|---|---|
| Painel administrativo | Somente advogados do escritório | `/painel/...` | Login com e-mail e senha + segundo fator (TOTP). Contas criadas apenas por convite. |
| Formulário externo | Associado | `/f/<token>` | Link individual, temporário e revogável + verificação de identidade. Não dá acesso a nada além daquele formulário. |
| Serviços (backend) | O próprio sistema | Edge Functions | Únicos que falam com OneDrive, APIs externas e IA. Segredos ficam aqui. |

O associado **não é usuário do sistema**. Ele só recebe um formulário controlado pelo advogado.

```
Navegador do advogado ──► Painel (React) ──► Supabase (Auth + Postgres com RLS)
                                         └─► Edge Functions ──► Microsoft Graph (OneDrive)
                                                             ├─► BrasilAPI / ViaCEP / IBGE
                                                             └─► Claude API (minutas)
Celular do associado ──► /f/<token> ──► Edge Function "formulario" (valida token + código)
                                     └─► upload ──► OneDrive (pasta do associado)
```

## 2. Tecnologias

| Camada | Escolha | Motivo |
|---|---|---|
| Interface | React + Vite + TypeScript + Tailwind + shadcn/ui | É a stack que o Lovable gera e edita. Assim o Lovable e o Claude Code trabalham no mesmo código. |
| Banco e login | Supabase (PostgreSQL, Auth, Row Level Security) | Integração nativa com o Lovable, login pronto com TOTP, RLS garante o isolamento no próprio banco. |
| Regras no servidor | Supabase Edge Functions (Deno/TypeScript) | Guardam os segredos (Microsoft, IA) e executam tudo que não pode rodar no navegador. |
| Documentos | Microsoft OneDrive via Graph API | Pedido do escritório. O banco guarda só o `driveItemId` e metadados. |
| Armazenamento provisório | Bucket privado do Supabase Storage | Usado só até o OneDrive estar conectado (Etapa 4) e como área temporária de upload. |
| Cálculos | Motor próprio em TypeScript (porte do `calculadora/src/modulos/rescisao/motor.js`) | Determinístico, testado, sem IA. |
| Planilhas / PDF / DOCX | SheetJS, jsPDF + autotable (já usados), pdf-lib (juntar dossiê), docxtemplater (petições) | Bibliotecas maduras e já conhecidas no projeto. |
| IA | Claude API chamada por Edge Function | Chave nunca vai para o navegador. Usada só em minutas. |
| Publicação | Domínio próprio apontado para o Lovable (ou Vercel, se o Lovable não for usado) | Ver decisão pendente no item 10. |

**Por que não Next.js:** o Lovable não edita projetos Next.js. Como o Lovable faz parte do fluxo pedido, ficamos com Vite + React e colocamos as regras de negócio nas Edge Functions e no banco (RLS), que é o papel que o backend do Next.js teria.

## 3. Módulos

| Módulo | O que faz | Etapa |
|---|---|---|
| Autenticação | Login de advogados, convite, TOTP obrigatório, sessão curta. | 2 |
| Clientes (entidades) | Cards com logo, nome, CNPJ, nº de associados. Cadastro com consulta de CNPJ. Arquivar. | 3 |
| OneDrive | Conexão da conta Microsoft, criação da árvore de pastas, upload/download, vínculo arquivo ↔ associado. | 4 |
| Associados | Cadastro, listagem, link de cadastro, formulário externo, anexos, conferência. | 5 |
| Empresas e filtros | Empregadoras por CNPJ, vínculos, filtros combináveis, seleção múltipla. | 6 |
| Cálculos | Botão CRIAR CÁLCULO DE RESCISÃO, motor determinístico, memória, XLSX/PDF. | 7 |
| Petições | Botão CRIAR PETIÇÃO, qualificação automática, fatos com apoio de IA, DOCX/PDF após aprovação. | 8 |
| Lote e dossiê | Tela de pré-checagem, execução por associado, dossiê na ordem definida. | 9 |
| Diligências | Pedido de documentos faltantes, link só com os itens pedidos, envio por WhatsApp, conferência. | 5 (base) e 9 |
| Auditoria | Registro de acessos, alterações, envios e exportações. | 2 em diante |

## 4. Modelo de dados

Todas as tabelas têm `id uuid`, `criado_em`, `atualizado_em` e `criado_por` (advogado). RLS ligado em todas: só usuários da tabela `advogados` ativos leem ou escrevem. O formulário externo **nunca** acessa tabelas diretamente; passa pela Edge Function `formulario`, que usa o token para limitar tudo a um associado.

```
advogados            (user_id → auth.users, nome, oab, ativo, papel: 'admin'|'advogado')
clientes             (cnpj único, razao_social, nome_fantasia, endereco jsonb, logo_url,
                      onedrive_pasta_id, arquivado)
empresas             (cnpj único, razao_social, nome_fantasia, endereco jsonb, cnae, situacao,
                      dados_receita jsonb, consultado_em)
associados           (cliente_id, nome [MAIÚSCULAS], cpf único por cliente, rg, orgao_expedidor,
                      nacionalidade [padrão 'brasileira'], estado_civil, naturalidade_uf,
                      naturalidade_municipio_ibge, data_nascimento, cep, logradouro, numero,
                      complemento, bairro, municipio, uf, email, telefone, nome_mae, nome_pai,
                      situacao_cadastro: 'rascunho'|'aguardando_associado'|'recebido'|'conferido',
                      onedrive_pasta_id)
vinculos             (associado_id, empresa_id, admissao, desligamento, funcao, jornada,
                      tipo_rescisao, salario_base, atual bool)   -- histórico de empregos
holerites            (associado_id, vinculo_id, competencia, valores jsonb, arquivo_id,
                      origem: 'manual'|'extraido', conferido bool)
tipos_documento      (codigo: 'doc_foto'|'comprovante_residencia'|'procuracao'|'hipossuficiencia'|
                      'holerite'|..., pasta_destino: '01'..'06', obrigatorio bool)
arquivos             (associado_id, tipo_documento, nome, mime, tamanho, sha256,
                      onedrive_item_id, origem: 'advogado'|'associado', situacao:
                      'recebido'|'aprovado'|'recusado', motivo_recusa)
links_acesso         (associado_id, finalidade: 'cadastro'|'diligencia', diligencia_id,
                      token_hash, expira_em, usado_em, revogado_em, tentativas, contato_verificacao)
codigos_verificacao  (link_id, codigo_hash, expira_em, tentativas)
diligencias          (associado_id, itens jsonb, situacao: 'aberta'|'enviada'|'recebida'|
                      'concluida'|'recusada', enviada_em, recebida_em, conferida_por)
calculos             (associado_id, vinculo_id, versao_regras, entrada jsonb, resultado jsonb,
                      ajustes_manuais jsonb, situacao: 'rascunho'|'conferido', xlsx_id, pdf_id)
peticoes             (associado_id, calculo_id, secoes jsonb, pendencias jsonb,
                      situacao: 'minuta'|'aprovada', aprovada_por, docx_id, pdf_id)
lotes                (filtro jsonb, tipo: 'calculo'|'peticao'|'dossie', confirmado_por,
                      situacao) + lote_itens (lote_id, associado_id, situacao, erro, resultado_id)
auditoria            (quem, acao, entidade, entidade_id, detalhes jsonb, ip, em)   -- só inserção
```

Regras que o banco garante:
- CPF validado (dígitos verificadores) e único dentro de cada cliente.
- `arquivos.associado_id` é obrigatório e não pode ser trocado depois de gravado (trigger). Evita que um documento migre para outro associado.
- `auditoria` não aceita `update` nem `delete`.
- O token do link nunca é gravado em texto; só o `sha256`.

## 5. OneDrive

Estrutura criada pela Edge Function `onedrive`:

```
CLIENTES/
  <NOME DO CLIENTE>/
    ASSOCIADOS/
      <NOME DO ASSOCIADO> - <CPF parcial: ***.456.789-**>/
        01 - DOCUMENTOS PESSOAIS/
        02 - DOCUMENTOS JURÍDICOS/
        03 - HOLERITES/
        04 - CÁLCULOS TRABALHISTAS/
        05 - PETIÇÕES/
        06 - DOSSIÊ FINAL/
```

- Conexão: registro de aplicativo no Microsoft Entra ID, OAuth com permissão delegada `Files.ReadWrite` + `offline_access` (mínima necessária). O refresh token fica criptografado no Supabase (Vault), nunca no código.
- Antes de criar uma pasta, a função procura pelo `onedrive_pasta_id` gravado; se não houver, procura por nome; só então cria. Isso evita duplicadas.
- O banco guarda o `driveItemId`, não o caminho. Renomear a pasta no OneDrive não quebra o vínculo.
- Nenhum link público é criado. Downloads passam pela Edge Function, que confere a permissão.
- Uploads do associado: o arquivo vai para a Edge Function, que confere tipo (PDF, JPG, PNG, HEIC) e tamanho (até 15 MB), calcula o `sha256` e envia ao OneDrive na pasta certa.

## 6. Formulário externo e segurança dos links

Fluxo para cada link (cadastro ou diligência):

1. O advogado gera o link. O sistema cria um token aleatório de 32 bytes, grava só o hash, define validade (padrão 7 dias) e liga o link a **um** associado e a **uma** finalidade.
2. O associado abre `/f/<token>`. Antes de mostrar qualquer dado já existente, o sistema pede verificação:
   - **Fase 1:** código de 6 dígitos enviado ao e-mail cadastrado pelo advogado, ou confirmação de CPF + data de nascimento quando não houver e-mail.
   - **Fase 2:** código pelo WhatsApp, quando a API oficial do WhatsApp Business estiver configurada.
3. Verificado, abre uma sessão curta (30 minutos) presa àquele link. O formulário mostra só os campos e anexos daquele pedido.
4. Ao clicar em SALVAR E ENVIAR, os dados vão para conferência (`situacao = recebido`) e não substituem nada até o advogado aprovar.
5. O link pode ser revogado a qualquer momento. Após o envio final, fica bloqueado. Tentativas erradas demais bloqueiam o link.

Outras regras:
- Toda leitura e gravação é autorizada no servidor pelo token. Trocar IDs na URL ou no corpo da requisição não muda nada, porque o associado é sempre o do token.
- Envio em lote de links: cada associado recebe um token diferente, com validade e histórico próprios.
- WhatsApp fase 1: botão que abre `wa.me/<telefone>?text=<mensagem pronta com o link>` no WhatsApp do advogado. O sistema não diz que "enviou" nada; registra apenas que o advogado abriu o envio.

Segurança geral:
- Painel com TOTP obrigatório, sessão curta, contas só por convite.
- RLS em todas as tabelas; chaves de serviço só nas Edge Functions.
- Segredos em variáveis de ambiente do Supabase. `.env` fora do Git.
- Auditoria de login, visualização de documentos, exportações, envios de link e aprovações.
- Backup diário do banco (Supabase) e os documentos já ficam no OneDrive.
- LGPD: coletar só o necessário, prever prazo de retenção e exclusão, registrar a base legal (exercício regular de direitos em processo). O sistema não presume conformidade automática; o escritório revisa.

## 7. Integrações de consulta

| Dado | Fonte principal | Alternativa | Observação |
|---|---|---|---|
| CNPJ | BrasilAPI (`/api/cnpj/v1/{cnpj}`) | ReceitaWS / CNPJá | Resultado guardado em `empresas.dados_receita`, com data. Campos ficam editáveis. |
| CEP | ViaCEP | BrasilAPI CEP v2 | O associado digita só número e complemento. |
| UF e municípios | IBGE Localidades | lista embutida no código | Para naturalidade. |

Se a consulta não retornar, o campo fica vazio e editável. **Nada é inventado.** As chamadas passam por uma Edge Function com cache, para não depender do navegador e não estourar limite das APIs.

## 8. Cálculos

- O motor atual (`calculadora/src/modulos/rescisao/motor.js` + `core/tabelas.js`) vira o pacote `src/lib/calculo/` em TypeScript, mantendo as mesmas regras e os mesmos resultados.
- Antes de portar, criamos testes com casos conhecidos gerados pela calculadora atual (dados anonimizados). O porte só é aceito se der os mesmos valores.
- Cada cálculo grava a `versao_regras` (ex.: `2026.1`: INSS 2026, IRRF 2026 com Lei 15.270). Mudança de tabela gera nova versão; cálculos antigos continuam reproduzíveis.
- Entrada: dados do vínculo + holerites conferidos + parâmetros do advogado. Faltando dado obrigatório, o sistema diz qual e não calcula.
- Holerites podem ser lidos por extração (Etapa 7, opcional), mas o resultado sempre vai para conferência e é marcado como `extraido`. A IA nunca gera salário, data ou verba.
- Três holerites não são tratados como suficientes para tudo: o sistema pede o que faltar (médias de variáveis, férias vencidas, FGTS, etc.).
- Ajuste manual é permitido, fica registrado em `ajustes_manuais` com autor e motivo.
- Saídas: XLSX (memória de cálculo) e PDF (termo), salvos em `04 - CÁLCULOS TRABALHISTAS`.

## 9. Petições e dossiê

- Modelo DOCX da reclamação trabalhista com seções: endereçamento, qualificação do reclamante, qualificação da reclamada, fatos, fundamentos, pedidos (com valores do cálculo), valor da causa, requerimentos, documentos anexos.
- Qualificação e valores vêm do banco. O advogado escreve as informações iniciais dos fatos; a IA organiza o texto **somente com o que foi informado** e marca com `[CONFIRMAR]` qualquer ponto que dependa de dado ausente.
- Fundamentos e pedidos partem de blocos-modelo editáveis pelo escritório; a IA não cria jurisprudência nem citações.
- Exportação em DOCX/PDF só depois de `situacao = aprovada`, com registro de quem aprovou.
- Dossiê final (PDF único, pdf-lib) na ordem: 1) petição; 2) documentos pessoais; 3) procuração e declaração de hipossuficiência; 4) planilha de cálculos. Também são mantidos os arquivos individuais. Salvo em `06 - DOSSIÊ FINAL`.

## 10. Decisões pendentes e riscos

| Tema | Situação |
|---|---|
| Lovable com este repositório | Pelo que conheço, o Lovable sincroniza com um repositório que **ele mesmo** cria no GitHub; não importa um repositório existente. Opções: (a) criar o projeto no Lovable, deixá-lo criar o repositório e trazer para lá a pasta `docs/` e `calculadora/`; (b) construir aqui com a mesma stack e publicar na Vercel, usando o Lovable só se quiser depois. |
| Conta Microsoft | Precisa ser a conta do OneDrive do escritório. Se for conta pessoal (outlook.com), o registro de app funciona, mas a conta corporativa (Microsoft 365) dá mais controle. |
| Verificação por WhatsApp | Exige WhatsApp Business Platform aprovada (Meta), com modelos de mensagem aprovados. Até lá: e-mail ou CPF + nascimento. |
| Custos | Supabase (plano gratuito serve no início; Pro recomendado para backup diário), Lovable, domínio, uso da Claude API. |
| Extração de holerites | Formatos variam muito; a extração é ajuda, não fonte. |
