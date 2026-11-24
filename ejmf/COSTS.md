# COSTS — custos de infraestrutura (estimativas)

> **Nada foi contratado.** Valores são estimativas de ordem de grandeza para planejamento, **sem cotação feita** e sujeitos a confirmação na Fase 12. Nenhum serviço pago será usado sem autorização expressa.

## Cenário recomendado para um advogado solo (até ~10 mil processos)

| Item | Opção | Custo mensal estimado | Observação |
|---|---|---|---|
| Servidor de aplicação + banco | 1 VPS com 4 vCPU / 8 GB RAM / 160 GB SSD **no Brasil** | faixa de R$ 100 a R$ 300 | Região Brasil é importante: relatos indicam bloqueio do DJEN a origens estrangeiras (RESEARCH §6). Testes de carga da Fase 2 vão confirmar o dimensionamento. |
| Backups | Armazenamento S3 compatível, outro provedor | faixa de R$ 5 a R$ 30 | ~50 GB com retenção de 30 dias. |
| Domínio | `.adv.br` ou `.com.br` | ~R$ 40/ano (Registro.br, a confirmar) | Requer CNPJ/CPF do titular. |
| E-mail institucional | Google Workspace (já usado para Gmail/Agenda) | conforme plano já contratado pelo escritório | Integração via OAuth. |
| DataJud, DJEN | APIs públicas do CNJ | R$ 0 | Limites de taxa. |
| OCR | Tesseract local | R$ 0 | Usa CPU do servidor. |
| WhatsApp Business (Cloud API da Meta) | cobrança por conversa iniciada pela empresa | variável; a confirmar na tabela oficial da Meta para o Brasil | Fase 5. Respostas a mensagens do cliente dentro da janela de atendimento costumam ter custo menor. |
| Assinatura eletrônica | Documenso auto-hospedado | R$ 0 de licença (AGPL) + recursos do servidor | Assinatura ICP-Brasil exige certificado/provedor próprio. |
| IA (LLMs) | Claude (Anthropic) ou serviço compatível com a API da OpenAI, por uso, com tetos diário e mensal | definido pelo advogado (sugestão inicial: teto de R$ 100/mês) | Fase 8. Nada é chamado sem tetos definidos. Preços de referência da tabela oficial da Anthropic, em US$ por milhão de tokens de entrada/saída: Opus 5.5 4/20, Sonnet 5.5 2/10, Haiku 5.5 0,10/0,50 (conferir na fonte antes de aprovar; escrita em cache custa 1,25× a entrada e leitura 0,1×). Tarefas simples usam regras, não IA. |
| Monitoramento externo | Uptime Kuma em máquina separada barata | faixa de R$ 0 a R$ 30 | Fase 11. |

**Total inicial estimado (sem IA e sem WhatsApp): na faixa de R$ 110 a R$ 360 por mês.**

## Controles de IA (seção 43, implementados na Fase 8)
- Custo registrado por execução e por passo (função, modelo, tokens de entrada, saída e cache, processo e cliente), calculado com o preço cadastrado do modelo.
- Painel de custos em Inteligência artificial: por função, modelo, departamento, processo e dia; gasto de hoje e do mês contra os tetos; valor em reais se o escritório informar a cotação.
- Bloqueio antes da chamada: sem preço, sem aprovação do modelo ou sem tetos, nada é chamado; se o custo estimado passar do orçamento da execução (padrão US$ 0,50) ou dos tetos do dia ou do mês, a execução fica "bloqueada" e quem gerencia a IA é avisado.
- Limite de chamadas ao modelo (padrão 5) e de tempo (padrão 120 s) por execução.
- Modelo simulado com custo zero para testes e demonstração.
