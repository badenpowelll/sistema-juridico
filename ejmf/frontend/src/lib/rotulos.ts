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

export const SITUACAO_PRAZO: Record<string, [string, string]> = {
  sugerido: ["Sugerido — não confirmado", "alerta"], aguardando_conferencia: ["Aguardando homologação", "info"],
  homologado: ["Homologado", "ok"], alterado: ["Alterado — rever", "alerta"], concluido: ["Concluído", "neutro"],
  vencido: ["Vencido", "perigo"], informacao_insuficiente: ["Informação insuficiente", "perigo"],
};

export const SITUACAO_PUBLICACAO: Record<string, [string, string]> = {
  nao_conferida: ["Não conferida", "alerta"], conferida: ["Conferida", "ok"], descartada: ["Descartada", "neutro"],
  duplicada: ["Duplicada", "neutro"],
};

export const FONTE: Record<string, string> = {
  djen: "DJEN", djen_simulado: "DJEN simulado", manual: "Cadastro manual", arquivo: "Arquivo", datajud: "DataJud",
};

export function diasRestantes(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n < 0) return `venceu há ${-n} dia(s)`;
  if (n === 0) return "vence hoje";
  if (n === 1) return "vence amanhã";
  return `em ${n} dias`;
}

export const TIPO_COMPROMISSO: Record<string, [string, string]> = {
  audiencia: ["Audiência", "perigo"], reuniao: ["Reunião", "info"], atendimento: ["Atendimento", "dourado"],
  compromisso: ["Compromisso", "neutro"], lembrete: ["Lembrete", "neutro"], bloqueio: ["Bloqueio", "neutro"],
  trabalho_concentrado: ["Trabalho concentrado", "info"], pessoal: ["Pessoal", "neutro"], externo: ["Google", "neutro"],
  prazo: ["Prazo", "alerta"],
};

const FZ = "America/Fortaleza";
/** Data (AAAA-MM-DD) no fuso do escritório. */
export function diaLocal(iso: string | Date): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: FZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(iso));
}
export function horaLocal(iso: string): string {
  return new Intl.DateTimeFormat("pt-BR", { timeZone: FZ, hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
}
/** "2026-11-24" + "09:30" no fuso do escritório (UTC−3, sem horário de verão) → ISO com fuso. */
export function isoLocal(dia: string, hora: string): string {
  return `${dia}T${hora}:00-03:00`;
}
export function somarDias(dia: string, n: number): string {
  const d = new Date(`${dia}T12:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}
export function diaSemana(dia: string, formato: "short" | "long" = "short"): string {
  return new Intl.DateTimeFormat("pt-BR", { weekday: formato, timeZone: "UTC" }).format(new Date(`${dia}T12:00:00Z`));
}
