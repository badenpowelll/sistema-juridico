# Arquitetura

Sistema privado do escritório para clientes sindicais (ex.: SINTICOCIP), associados, documentos, cálculos trabalhistas, petições, lotes e diligências. Fora do Lovable: o código vive neste repositório e roda no Railway.

## Visão geral

```
                 domínio próprio (DNS na Hostinger, CNAME → Railway)
                                   │
                    ┌──────────────▼──────────────┐
  navegador ──────► │  Railway: serviço "app"     │ ──► Microsoft Graph ──► OneDrive (pasta "Clientes")
  (advogados)       │  Node 22 · Hono · React     │
                    │  /api/*  +  tela (web/dist) │
                    └──────────────┬──────────────┘
                                   │ DATABASE_URL (rede interna)
                    ┌──────────────▼──────────────┐
                    │  Railway: PostgreSQL         │
                    └─────────────────────────────┘
```

| Peça | Escolha | Por quê |
|---|---|---|
| Servidor | Node 22 + [Hono](https://hono.dev) + TypeScript (rodando com `tsx`) | Leve, um único serviço no Railway serve a API e a tela. |
| Tela | React 19 + Vite + Tailwind | Mesma base do protótipo do Lovable, então as telas de lá (clientes, empresas, associados, CNPJ, CEP) podem ser trazidas aos poucos. |
| Banco | PostgreSQL do Railway, SQL puro em `db/migrations` | O esquema é o mesmo do protótipo, sem depender do Supabase. |
| Login | Próprio: e-mail e senha (scrypt), sessão em cookie httpOnly, só o hash do token no banco | Sem cadastro público; o admin cria os advogados. |
| Acesso | Checado no servidor: toda rota de `/api` exige advogado ativo (`exigirAdvogado`), e as de configuração exigem admin | Substitui as políticas RLS do Supabase (`is_advogado_ativo()`). |
| Arquivos | OneDrive via Microsoft Graph | O OneDrive é a fonte: o sistema puxa as pastas que já existem. Os arquivos ficam lá; o banco guarda metadados e vínculos. |
| Cálculos | O motor da calculadora (`calculadora/src`) importado sem cópia pelo servidor | Mesma conta na tela, no lote e no servidor. |
| Auditoria | Tabela `auditoria`, que um gatilho impede de alterar ou apagar | Histórico de quem fez o quê. |

## OneDrive como fonte

Estrutura esperada (da especificação):

```
Clientes/                         ← ONEDRIVE_PASTA_RAIZ
  SINTICOCIP/                     ← cliente (ligado pelo nome fantasia ou razão social)
    Consolidado.xlsx              ← arquivos do cliente (planilhas de rescisão)
    JOÃO DA SILVA/                ← associado (criado em "rascunho" se não existir)
      01 - DOCUMENTOS PESSOAIS/   ← categoria
        CNH.pdf                   ← documento (tipo adivinhado: cnh)
      02 - DOCUMENTOS JURÍDICOS/
      03 - HOLERITES/
        Contracheque 09-2026.pdf  ← holerite, competência 09/2026
```

1. Um admin clica em **Conectar OneDrive** (Configurações). O login é da Microsoft, com os escopos `Files.ReadWrite.All` e `offline_access`. O refresh token fica cifrado (AES-256-GCM) na tabela `onedrive_conexao`.
2. **Sincronizar agora** (ou `npm run onedrive:sincronizar`, que pode virar tarefa agendada no Railway) percorre a árvore e grava cada item em `onedrive_itens`.
3. A pasta de 1º nível vira cliente quando o nome bate com um cliente cadastrado. Se não bater, aparece como "pasta sem cliente" até alguém informar o CNPJ, porque o cliente exige CNPJ.
4. A pasta de 2º nível vira associado. Os arquivos dentro dela viram `documentos` com situação `pendente_conferencia`, porque nada do que vem de fora é usado em peça sem conferência.
5. Nada é apagado no OneDrive. O que sumiu de lá fica marcado como `removido`.

Funciona com OneDrive pessoal (`MS_TENANT=consumers`) e com Microsoft 365 (`organizations` ou o id do locatário).

## Regras de cálculo herdadas da planilha do RN

- Periculosidade: 30% do salário base quando o vínculo tem direito (`vinculos.periculosidade`, `periculosidade_pct`).
- Honorários contratuais: 15% sobre o custo da rescisão antes dos honorários; custo total = custo + honorários (115%). O percentual é por cliente (`clientes.honorarios_contratuais_pct`) e fica gravado em cada cálculo.
- Não há honorário sucumbencial, e o termo usado é "honorários contratuais".
- Ver `shared/honorarios.ts` e `server/calculo/rescisao.ts`.

## Tabelas

| Migração | Tabelas |
|---|---|
| `0001_base.sql` | usuarios, sessoes, convites, advogados, clientes, empresas, associados, auditoria |
| `0002_modulos.sql` | vinculos, holerites, calculos, peticoes, lotes, lote_itens, diligencias |
| `0003_onedrive_documentos.sql` | onedrive_conexao, onedrive_itens, onedrive_sincronizacoes, documentos, links_formulario |

As migrações rodam sozinhas antes de cada deploy (`preDeployCommand`). Migração aplicada não se edita: crie a próxima (`0004_...sql`).

## Próximas etapas

1. Trazer do protótipo as telas de Clientes (com CNPJ automático), Empresas e Associados (CEP e DDD automáticos).
2. Tela para ligar "pastas sem cliente" e conferir documentos importados.
3. Importar as planilhas de rescisão do OneDrive (o `lote.js` já reconhece as colunas) e gravar em `vinculos` e `calculos`.
4. Cálculos no associado, com PDF (reaproveita `pdf.js`) salvo de volta na pasta do associado no OneDrive.
5. Formulário do associado por link (`/f/:token`) com verificação extra.
6. Petições, lotes, dossiê final (petição → documentos pessoais → procuração/declaração → cálculos) e diligências.
