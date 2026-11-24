# ADR-0013 — Financeiro: registro e controle, sem acesso a banco nem cobrança externa

Data: 2026-11-24 · Situação: aceita

## Contexto
A Fase 9 traz o financeiro do escritório: honorários contratados, lançamentos de receita e despesa, previsto, faturado e recebido, fluxo de caixa e rentabilidade. A especificação proíbe transferências e cobranças externas sem permissão, e a IA não movimenta dinheiro. O roadmap sugeria "reaproveitar o motor da calculadora", e o escritório precisa conferir o que entrou no banco sem dar ao sistema acesso à conta.

## Decisão
- **Registro, não movimentação.** O EJMF guarda contas só pelo nome e saldo inicial (sem agência, senha ou acesso). Recebido e pago são atos de uma pessoa com `financeiro:liquidar`, com data (nunca futura), conta e forma. Não há boleto, Pix, cartão, open finance nem envio de cobrança.
- **Valores em `Numeric(14,2)` e texto decimal na API**, nunca `float`; real e dólar nunca se misturam (o custo de IA continua em US$ e aparece à parte na rentabilidade).
- **Situações separadas**: previsto (vencimento), faturado (cobrado do cliente), liquidado (recebido/pago) e cancelado. Nada é apagado: cancelar e estornar pedem motivo e ficam na auditoria. Estorno é bloqueado se houver recibo ativo ou linha de extrato conciliada.
- **Pagamento parcial** liquida o valor recebido e cria um novo lançamento com o saldo, ligado ao original (`origem_id`).
- **Contratos de honorários** (fixo, parcelado, mensal, êxito, misto) geram as parcelas como lançamentos previstos; o resto da divisão vai para a última. O êxito só é lançado quando uma pessoa informa o valor-base conferido; o EJMF multiplica pelo percentual do contrato.
- **Recibo** só depois do recebimento, com numeração sequencial (trava consultiva no PostgreSQL), valor por extenso e minuta gerada pelo modelo "recibo de honorários" apenas quando ele estiver homologado (Fase 6). Sem modelo homologado, o recibo é registrado e a tela avisa.
- **Lembrete de pagamento só aparece no portal do cliente**, nunca por e-mail ou WhatsApp. Com `financeiro:cobrar` (nível 4 da tabela de permissões) ele é publicado; sem ela vira pedido na central de aprovações. A função 28 (gestor de cobranças) só propõe: o pedido vai à central e quem pediu não decide.
- **Conciliação por extrato importado** (OFX ou CSV baixado do banco, até 2 MB, arquivo repetido recusado pelo SHA-256, linha repetida reconhecida pela chave). As sugestões são por regras (mesmo valor, data próxima, nome do cliente); conciliar é ato de pessoa e pode ser desfeito.
- **A calculadora não foi reaproveitada**: `calculadora/` é uma calculadora de verbas rescisórias trabalhistas (outro domínio), e o financeiro do escritório só precisa de soma, divisão em parcelas e datas mensais, já cobertos por funções pequenas e testadas.
- **Rentabilidade sem rateio**: custos operacionais (aluguel, tarifas etc.) aparecem no total, mas não são distribuídos entre processos, porque qualquer critério de rateio seria uma escolha do escritório ainda não feita.
- **Exportação CSV** com BOM, `;` e vírgula decimal (abre no Excel em pt-BR), neutralização de fórmulas e registro na auditoria.

## Consequências
- Nenhum dinheiro se move pelo EJMF; o extrato precisa ser baixado e importado por uma pessoa.
- O financeiro é tão correto quanto os registros: as telas e as funções avisam que atraso é "o que está registrado em aberto" e pedem conferência do extrato antes de falar com o cliente.
- Se o escritório quiser rateio de custos ou integração bancária, isso exige nova decisão (e, no caso do banco, credenciais e contrato que o EJMF não tem).
