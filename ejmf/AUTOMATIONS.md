# AUTOMATIONS

> Situação: **não implementado** (Fases 4 e 8). Este arquivo registra o desenho.

- Motor próprio de automações: gatilho (evento ou horário) → condições → ações → aprovação (quando o nível exigir) → notificação. Execuções registradas e auditadas.
- Modo de teste obrigatório antes de ativar; fluxos podem ser pausados, editados e desativados.
- Fluxos iniciais previstos: novo cliente cadastrado; documento recebido; publicação capturada; contrato aguardando assinatura; compromisso próximo; honorário pendente; processo sem atualização há N dias; falha de integração; backup não realizado.
- n8n (fair-code) fica como serviço opcional para integrações de cauda longa, chamando a API do EJMF com token de escopo limitado.
- Agendamentos usam o fuso `America/Fortaleza` (sem horário de verão).
