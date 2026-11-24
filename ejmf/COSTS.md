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
| IA (LLMs) | Claude/OpenAI/Gemini por uso, com teto mensal configurável | definido pelo advogado (sugestão inicial: teto de R$ 100/mês) | Preços oficiais por milhão de tokens serão lidos das páginas dos provedores na Fase 8; custo registrado por execução. Tarefas simples usam regras, não IA. |
| Monitoramento externo | Uptime Kuma em máquina separada barata | faixa de R$ 0 a R$ 30 | Fase 11. |

**Total inicial estimado (sem IA e sem WhatsApp): na faixa de R$ 110 a R$ 360 por mês.**

## Controles previstos (seção 43)
- Tabela de custos por execução (agente, modelo, departamento, tarefa, processo) — Fase 8.
- Teto diário/mensal com bloqueio automático das funções de IA ao atingir o limite.
- Painel de custos no dashboard.
