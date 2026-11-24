# ADR-0001 — Onde o EJMF vive

- Status: aceito · Data: 2026-11-24

## Contexto
O superprompt sugere um repositório novo `escritorio-juridico-marcio-fernandes`. Nesta sessão o acesso ao GitHub está limitado a dois repositórios do Baden: `sistema-juridico` (calculadora de rescisão CLT em uso, mais dois PRs abertos de arquitetura) e `union-counsel-compass` (app ligado ao Lovable, cujo `AGENTS.md` proíbe mexer em migrações e cuja branch principal sincroniza com o editor do Lovable). Criar repositório novo está fora do escopo autorizado da sessão.

## Decisão
O EJMF fica na pasta **`ejmf/`** do repositório `sistema-juridico`, ao lado de `calculadora/`, que é preservada sem alterações.

## Consequências
- A calculadora continua funcionando como está; o EJMF poderá reutilizar o motor (`calculadora/src/modulos/rescisao/motor.js`) no módulo financeiro/cálculos.
- `union-counsel-compass` fica como referência de telas (cadastro por CNPJ, empresas); não recebe código do EJMF, para não quebrar o projeto Lovable.
- Se o Baden criar o repositório `escritorio-juridico-marcio-fernandes`, a pasta `ejmf/` pode ser movida com `git subtree split --prefix ejmf` preservando o histórico.
