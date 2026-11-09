/* Regras para entender a árvore do OneDrive (sem acesso à rede, para poder testar).
 * <raiz>/<CLIENTE>/<ASSOCIADO>/<CATEGORIA>/arquivo  — a categoria é opcional. */

export const normalizar = (s: string) =>
  s.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/\s+/g, ' ').trim().toUpperCase();

/** "01 - DOCUMENTOS PESSOAIS" -> "DOCUMENTOS PESSOAIS" */
export const semNumeracao = (s: string) => normalizar(s).replace(/^\d+\s*[-–.]\s*/, '');

export type TipoDocumento =
  | 'documento_foto' | 'cnh' | 'identidade' | 'comprovante_residencia' | 'procuracao' | 'hipossuficiencia'
  | 'holerite' | 'ctps' | 'trct' | 'planilha_calculo' | 'calculo' | 'peticao' | 'dossie' | 'outro';

const REGRAS: [RegExp, TipoDocumento][] = [
  [/\bCNH\b|HABILITACAO/, 'cnh'],
  [/\bRG\b|IDENTIDADE|\bCIN\b/, 'identidade'],
  [/COMPROVANTE.*(RESID|ENDERE)|CONTA DE (LUZ|AGUA|ENERGIA)/, 'comprovante_residencia'],
  [/PROCURACAO/, 'procuracao'],
  [/HIPOSSUFICIENCIA|HIPOSUFICIENCIA|POBREZA|GRATUIDADE/, 'hipossuficiencia'],
  [/HOLERITE|CONTRACHEQUE|CONTRA-CHEQUE|CONTRA CHEQUE|RECIBO DE PAGAMENTO|FOLHA DE PAGAMENTO/, 'holerite'],
  [/\bCTPS\b|CARTEIRA DE TRABALHO/, 'ctps'],
  [/\bTRCT\b|TERMO DE RESCISAO/, 'trct'],
  [/PETICAO|INICIAL|RECLAMACAO TRABALHISTA/, 'peticao'],
  [/DOSSIE/, 'dossie'],
  [/CALCULO|RESCISAO|PLANILHA/, 'calculo'],
];

/** Adivinha o tipo pelo nome do arquivo e, se não der, pela pasta onde ele está. */
export function tipoDocumento(nomeArquivo: string, categoria?: string | null): TipoDocumento {
  const nome = normalizar(nomeArquivo);
  for (const [re, tipo] of REGRAS) if (re.test(nome)) return ajustarPlanilha(tipo, nome);
  const cat = categoria ? semNumeracao(categoria) : '';
  if (/CALCULO/.test(cat)) return ajustarPlanilha('calculo', nome);
  if (/PETIC/.test(cat)) return 'peticao';
  if (/DOSSIE/.test(cat)) return 'dossie';
  if (/HOLERITE|CONTRACHEQUE/.test(cat)) return 'holerite';
  return 'outro';
}

const ajustarPlanilha = (t: TipoDocumento, nome: string): TipoDocumento =>
  t === 'calculo' && /\.(XLSX|XLS|CSV)$/.test(nome) ? 'planilha_calculo' : t;

/** Mês de competência no nome do holerite: "holerite 09-2026.pdf", "contracheque_2026_09", "SET 2026". */
const MESES = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ'];
export function competencia(nomeArquivo: string): string | null {
  const n = normalizar(nomeArquivo);
  let m = n.match(/(?<!\d)(0?[1-9]|1[0-2])[-_./ ](20\d{2})(?!\d)/);
  if (m) return `${m[2]}-${m[1].padStart(2, '0')}-01`;
  m = n.match(/(?<!\d)(20\d{2})[-_./ ](0?[1-9]|1[0-2])(?!\d)/);
  if (m) return `${m[1]}-${m[2].padStart(2, '0')}-01`;
  m = n.match(new RegExp(`(?<![A-Z])(${MESES.join('|')})[A-Z]*[-_./ ]*(20\\d{2})(?!\\d)`));
  if (m) return `${m[2]}-${String(MESES.indexOf(m[1]) + 1).padStart(2, '0')}-01`;
  return null;
}

/** Nível do item pela profundidade abaixo da raiz (1 = cliente, 2 = associado, 3 = categoria ou arquivo). */
export function nivel(profundidade: number, pasta: boolean) {
  if (profundidade === 0) return 'raiz';
  if (!pasta) return 'arquivo';
  if (profundidade === 1) return 'cliente';
  if (profundidade === 2) return 'associado';
  return 'categoria';
}
