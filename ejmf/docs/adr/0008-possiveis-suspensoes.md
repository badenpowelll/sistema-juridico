# ADR-0008 — Datas incertas contam como dia útil até confirmação

Data: 2026-11-24 · Situação: aceita

## Contexto
Carnaval, Sexta-feira da Paixão (fora da Justiça Federal) e Corpus Christi não são feriados nacionais por lei, mas muitos tribunais suspendem o expediente por portaria, e a portaria sai em datas variadas. Se o motor presumir a suspensão e ela não acontecer, o prazo calculado vence depois do real e o escritório perde o prazo.

## Decisão
- Essas datas entram no calendário como `possivel_suspensao`, não confirmadas.
- O motor as conta como dia útil (vencimento mais cedo, conservador) e informa, ao lado, o vencimento alternativo caso todas se confirmem, calculado de forma iterativa até estabilizar.
- Só o advogado (permissão `regras_prazo:homologar`) confirma que não houve expediente; a confirmação recalcula os prazos afetados e os devolve para conferência.
- O mesmo vale para feriados locais: enquanto não cadastrados, o erro possível é vencer antes, nunca depois.

## Consequências
- Nenhum prazo fica mais longo do que o real por presunção do sistema.
- O advogado precisa confirmar as datas a cada ano, por tribunal. O aviso aparece na memória de cálculo e na tela de Regras e calendário.
