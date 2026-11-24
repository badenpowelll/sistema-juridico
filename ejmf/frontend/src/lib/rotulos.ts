export const ROTULO_PRIORIDADE: Record<string, [string, string]> = {
  atencao_imediata: ["Atenção imediata", "perigo"], com_falha: ["Com falha", "perigo"], alta: ["Alta prioridade", "alerta"],
  aguardando_aprovacao: ["Aguardando aprovação", "dourado"], normal: ["Prioridade normal", "info"],
  aguardando_informacoes: ["Aguardando informações", "neutro"], aguardando_cliente: ["Aguardando cliente", "neutro"],
  aguardando_terceiros: ["Aguardando terceiros", "neutro"], automatizada: ["Automatizada", "ok"], concluida: ["Concluída", "ok"],
};

export const TOM_ESTADO: Record<string, string> = {
  implementada_validada: "ok", ambiente_testes: "info", aguardando_credenciais: "alerta",
  aguardando_autorizacao: "alerta", indisponivel: "perigo", nao_implementada: "neutro",
};

