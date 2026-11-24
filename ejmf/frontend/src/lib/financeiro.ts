/** Tipos e formatação do financeiro. Valores chegam como texto decimal ("1234.50") para não perder centavos. */
export type Lancamento = {
  id: string; tipo: "receita" | "despesa"; descricao: string; valor: string; vencimento: string; competencia: string;
  situacao: "previsto" | "faturado" | "liquidado" | "cancelado"; situacao_rotulo: string; vencido: boolean; dias_atraso: number;
  categoria_id: string; categoria: string | null; cliente_id: string | null; cliente: string | null; processo_id: string | null;
  processo: string | null; contrato_id: string | null; contrato: string | null; departamento_id: string | null;
  parcela: number | null; total_parcelas: number | null; origem_id: string | null; reembolsavel: boolean; portal_visivel: boolean;
  faturado_em: string | null; liquidado_em: string | null; conta_id: string | null; conta: string | null; forma: string | null;
  forma_rotulo: string | null; observacao: string | null; motivo_cancelamento: string | null; criado_em: string;
};
export type Pode = { gerenciar: boolean; liquidar: boolean; conciliar: boolean; recibos: boolean; cobrar: boolean; exportar: boolean };
export type Recibo = {
  id: string; numero: string; valor: string; valor_extenso: string; referente: string; lancamento_id: string;
  situacao: "emitido" | "cancelado"; motivo_cancelamento: string | null; minuta_id: string | null; minuta_situacao: string | null;
  emitido_em: string; aviso?: string | null;
};
export type Lembrete = { id: string; lancamento_id: string; texto: string; situacao: string; origem: string; publicado_em: string | null; criado_em: string };
export type LinhaExtrato = {
  id: string; conta_id: string; data: string; valor: string; descricao: string; sentido: "entrada" | "saida";
  situacao: "pendente" | "conciliada" | "ignorada"; lancamento_id: string | null; motivo: string | null; conciliada_em: string | null;
  sugestoes?: { lancamento: Lancamento; pontos: number; motivos: string[] }[];
};
export type LancamentoDetalhe = Lancamento & { recibos: Recibo[]; lembretes: Lembrete[]; conciliacao: LinhaExtrato | null; pode: Pode };
export type Categoria = { id: string; codigo: string; nome: string; tipo: "receita" | "despesa"; honorario: boolean; operacional: boolean; ativa: boolean };
export type Conta = {
  id: string; nome: string; tipo: string; tipo_rotulo: string; ativa: boolean; saldo_inicial: string; data_saldo_inicial: string;
  saldo_atual: string; linhas_pendentes: number;
};
export type Contrato = {
  id: string; numero: string; descricao: string; modalidade: string; modalidade_rotulo: string; valor_fixo: string | null;
  parcelas: number | null; primeiro_vencimento: string | null; percentual_exito: string | null; data_contrato: string;
  situacao: "vigente" | "encerrado" | "cancelado"; motivo_situacao: string | null; portal_visivel: boolean; cliente_id: string;
  cliente: string | null; processo_id: string | null; processo: string | null; minuta_id: string | null;
  totais: { contratado: string; recebido: string; em_aberto: string; vencido: string }; criado_em: string; lancamentos?: Lancamento[];
};
export type MesResumo = {
  mes: number; rotulo: string; receitas_previstas: string; receitas_faturadas: string; receitas_recebidas: string;
  despesas_previstas: string; despesas_pagas: string; resultado_caixa: string;
};
export type Posicao = {
  data: string; a_receber: string; a_receber_vencido: string; honorarios_a_receber: string; a_receber_30_dias: string; a_pagar: string;
  a_pagar_vencido: string; a_pagar_7_dias: string; reembolsos_pendentes: string; inadimplencia_percentual: string | null;
  contas: { id: string; nome: string; saldo: string }[]; saldo_total: string;
};
export type VisaoGeral = {
  resumo: { ano: number; meses: MesResumo[]; totais: Omit<MesResumo, "mes" | "rotulo">; posicao: Posicao };
  categorias: Categoria[]; contas: Conta[]; proximos: Lancamento[]; vencidos: { itens: Lancamento[]; total: number; somas: Record<string, string> };
  formas: Record<string, string>; modalidades: Record<string, string>; tipos_conta: Record<string, string>; pode: Pode; aviso: string;
};

const BRL = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
export const reais = (v: string | number | null | undefined) => (v === null || v === undefined || v === "" ? "—" : BRL.format(Number(v)));
export const dolares = (v: number | string) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "USD", maximumFractionDigits: 4 }).format(Number(v));
export const dia = (iso: string | null | undefined) => (iso ? iso.slice(0, 10).split("-").reverse().join("/") : "—");
export const hojeIso = () => new Intl.DateTimeFormat("en-CA", { timeZone: "America/Fortaleza" }).format(new Date());

export function tomSituacao(l: Pick<Lancamento, "situacao" | "vencido">): string {
  if (l.situacao === "cancelado") return "neutro";
  if (l.situacao === "liquidado") return "ok";
  if (l.vencido) return "perigo";
  return l.situacao === "faturado" ? "info" : "alerta";
}

/** "1.234,56" → "1234.56" (o backend valida; aqui só normaliza a escrita brasileira). */
export const paraDecimal = (v: FormDataEntryValue | string | null) => String(v ?? "").trim().replace(/\./g, "").replace(",", ".");
