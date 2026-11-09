/* O mesmo motor da calculadora (calculadora/src) rodando no servidor, sem cópia do código:
 * os arquivos são scripts que se registram em globalThis.Juridico. Assim, um cálculo feito na tela,
 * no lote ou no servidor dá sempre o mesmo resultado. */
import '../../calculadora/src/core/tabelas.js';
import '../../calculadora/src/modulos/rescisao/motor.js';
import { adicionalPericulosidade, aplicarHonorariosContratuais, HONORARIOS_CONTRATUAIS_PCT_PADRAO, PERICULOSIDADE_PCT_PADRAO } from '../../shared/honorarios.ts';

type Motor = { calcular: (input: Record<string, unknown>) => any; MOTIVOS: Record<string, { nome: string }> };
const J = (globalThis as any).Juridico as { tabelas: { vigencia: string }; modulos: { rescisao: Motor } };
export const motor = J.modulos.rescisao;
export const versaoRegras = () => `rescisao@tabelas-${J.tabelas.vigencia}`;

export type EntradaRescisao = Record<string, unknown> & {
  motivo: string;
  admissao: string;
  demissao: string;
  salario: number;
  periculosidade?: boolean;
  periculosidadePct?: number;
  honorariosPct?: number;
  /** Outras parcelas que entram no custo (ex.: multa do aviso prévio indenizado usada na planilha do RN). */
  multasAdicionais?: number;
};

/** Calcula a rescisão e acrescenta o custo para o empregador e os honorários contratuais.
 * Custo da rescisão = proventos brutos + depósito do FGTS sobre a rescisão + multa do FGTS + multas adicionais. */
export function calcularRescisao(e: EntradaRescisao) {
  const base = Number(e.salario);
  const peric = e.periculosidade ? adicionalPericulosidade(base, e.periculosidadePct ?? PERICULOSIDADE_PCT_PADRAO) : 0;
  const salarioConsiderado = Math.round((base + peric) * 100) / 100;
  const r = motor.calcular({ ...e, salario: salarioConsiderado });
  if (r.erros?.length) return { ...r, salarioConsiderado };
  const custo = r.totais.proventos + (r.fgts?.depositoRescisorio ?? 0) + (r.fgts?.multa ?? 0) + Number(e.multasAdicionais ?? 0);
  return {
    ...r,
    salarioBase: base,
    periculosidade: peric,
    salarioConsiderado,
    honorarios: aplicarHonorariosContratuais(custo, e.honorariosPct ?? HONORARIOS_CONTRATUAIS_PCT_PADRAO),
    versaoRegras: versaoRegras(),
  };
}
