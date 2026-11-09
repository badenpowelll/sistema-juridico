/* Regras da planilha de rescisões do RN (versão final aprovada pelo Baden em 2026-11-09):
 * - Periculosidade: 30% do salário base (art. 193, §1º, CLT) quando o trabalhador tem direito e a planilha veio em branco.
 * - Honorários contratuais: 15% sobre o custo da rescisão antes dos honorários; custo total = custo + honorários (115%).
 * - Não há honorário sucumbencial e o termo usado é "honorários contratuais". */

export const PERICULOSIDADE_PCT_PADRAO = 30;
export const HONORARIOS_CONTRATUAIS_PCT_PADRAO = 15;

const r2 = (v: number) => Math.round((v + Number.EPSILON) * 100) / 100;

export function adicionalPericulosidade(salarioBase: number, pct = PERICULOSIDADE_PCT_PADRAO) {
  return r2(salarioBase * (pct / 100));
}

export function aplicarHonorariosContratuais(custoRescisao: number, pct = HONORARIOS_CONTRATUAIS_PCT_PADRAO) {
  const honorarios = r2(custoRescisao * (pct / 100));
  return { custoRescisao: r2(custoRescisao), pct, honorarios, custoTotal: r2(custoRescisao + honorarios) };
}
