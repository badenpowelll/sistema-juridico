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


export const STATUS_PROCESSO: Record<string, [string, string]> = {
  ativo: ["Ativo", "ok"], suspenso: ["Suspenso", "alerta"], arquivado: ["Arquivado", "neutro"], encerrado: ["Encerrado", "neutro"],
};

export const SITUACAO_LINHA: Record<string, [string, string]> = {
  pendente: ["Pendente", "neutro"], valida: ["Válida", "info"], invalida: ["Inconsistente", "perigo"],
  duplicada_arquivo: ["Repetida no arquivo", "neutro"], existente: ["Já cadastrada", "neutro"],
  conferencia: ["Aguardando conferência", "alerta"], importada: ["Importada", "ok"], ignorada: ["Ignorada", "neutro"],
  revertida: ["Revertida", "neutro"],
};

export const STATUS_IMPORTACAO: Record<string, [string, string]> = {
  analisado: ["Aguardando mapeamento", "info"], validado: ["Validada", "dourado"], processando: ["Em execução", "alerta"],
  concluido: ["Concluída", "ok"], revertido: ["Revertida", "neutro"], cancelado: ["Cancelada", "neutro"],
};

export const POLO: Record<string, string> = { ativo: "Polo ativo", passivo: "Polo passivo", terceiro: "Terceiro", outro: "Outro" };

export function dataCurta(iso: string | null | undefined): string {
  if (!iso) return "—";
  if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) { const [a, m, d] = iso.split("-"); return `${d}/${m}/${a}`; }
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeZone: "America/Fortaleza" }).format(new Date(iso));
}

export function moeda(v: string | null | undefined): string {
  if (v == null) return "—";
  return Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}
