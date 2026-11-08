/* Núcleo compartilhado do sistema jurídico: tabelas oficiais e funções fiscais.
 * Outros módulos (férias, horas extras, correção monetária...) reutilizam este arquivo.
 * Atualize os valores aqui quando sair nova portaria/lei. */
(function (root) {
  const J = root.Juridico = root.Juridico || {};

  J.tabelas = {
    vigencia: '2026',
    salarioMinimo: 1621.00,
    // Portaria Interministerial MPS/MF nº 13/2026 — empregado, doméstico e avulso (progressiva)
    inss: {
      faixas: [
        { ate: 1621.00, aliquota: 0.075 },
        { ate: 2902.84, aliquota: 0.09 },
        { ate: 4354.27, aliquota: 0.12 },
        { ate: 8475.55, aliquota: 0.14 },
      ],
      fonte: 'Portaria Interministerial MPS/MF nº 13/2026',
    },
    // Lei 15.191/2025 (tabela mensal) + redução da Lei 15.270/2025 a partir de jan/2026
    irrf: {
      faixas: [
        { ate: 2428.80, aliquota: 0, deducao: 0 },
        { ate: 2826.65, aliquota: 0.075, deducao: 182.16 },
        { ate: 3751.05, aliquota: 0.15, deducao: 394.16 },
        { ate: 4664.68, aliquota: 0.225, deducao: 675.49 },
        { ate: Infinity, aliquota: 0.275, deducao: 908.73 },
      ],
      deducaoDependente: 189.59,
      descontoSimplificado: 607.20,
      reducao: { isencaoAte: 5000.00, reducaoMaxima: 312.89, faixaFinal: 7350.00, a: 978.62, b: 0.133145 },
      fonte: 'Lei 15.191/2025 e Lei 15.270/2025',
    },
    salarioFamilia: { cota: 67.54, limiteRemuneracao: 1980.38, fonte: 'Portaria Interministerial MPS/MF nº 13/2026' },
    fgts: { aliquota: 0.08 },
  };

  const r2 = (v) => Math.round((v + Number.EPSILON) * 100) / 100;
  J.r2 = r2;

  /** INSS progressivo, por faixa, limitado ao teto. */
  J.calcularINSS = function (base, t = J.tabelas.inss) {
    let resto = Math.max(0, base), anterior = 0, total = 0;
    const detalhe = [];
    for (const f of t.faixas) {
      if (resto <= 0) break;
      const fatia = Math.min(resto, f.ate - anterior);
      const v = fatia * f.aliquota;
      if (fatia > 0) detalhe.push({ de: anterior, ate: Math.min(base, f.ate), aliquota: f.aliquota, valor: r2(v) });
      total += v; resto -= fatia; anterior = f.ate;
    }
    return { valor: r2(total), detalhe };
  };

  /** IRRF com deduções legais x desconto simplificado (o mais vantajoso) e redução da Lei 15.270. */
  J.calcularIRRF = function (rendimento, inss, dependentes = 0, opts = {}, t = J.tabelas.irrf) {
    const permitirSimplificado = opts.simplificado !== false;
    const legal = inss + dependentes * t.deducaoDependente;
    const usaSimplificado = permitirSimplificado && t.descontoSimplificado > legal;
    const deducoes = usaSimplificado ? t.descontoSimplificado : legal;
    const base = Math.max(0, rendimento - deducoes);
    const faixa = t.faixas.find((f) => base <= f.ate);
    const impostoTabela = Math.max(0, base * faixa.aliquota - faixa.deducao);
    const R = t.reducao;
    let reducao = 0;
    if (rendimento <= R.isencaoAte) reducao = Math.min(R.reducaoMaxima, impostoTabela);
    else if (rendimento <= R.faixaFinal) reducao = Math.min(Math.max(0, R.a - R.b * rendimento), impostoTabela);
    return {
      valor: r2(Math.max(0, impostoTabela - reducao)),
      base: r2(base), aliquota: faixa.aliquota, deducaoFaixa: faixa.deducao,
      impostoTabela: r2(impostoTabela), reducao: r2(reducao),
      deducoes: r2(deducoes), usaSimplificado,
    };
  };

  /* ---------- Datas (sempre em UTC, formato ISO yyyy-mm-dd) ---------- */
  const D = J.datas = {};
  D.parse = (s) => { const [y, m, d] = s.split('-').map(Number); return new Date(Date.UTC(y, m - 1, d)); };
  D.iso = (dt) => dt.toISOString().slice(0, 10);
  D.br = (dt) => { if (typeof dt === 'string') dt = D.parse(dt); return dt.toISOString().slice(0, 10).split('-').reverse().join('/'); };
  D.addDias = (dt, n) => new Date(dt.getTime() + n * 86400000);
  D.diasEntre = (a, b) => Math.round((b - a) / 86400000); // b - a
  D.diasNoMes = (y, m) => new Date(Date.UTC(y, m + 1, 0)).getUTCDate();
  /** Soma meses preservando o dia; se o mês não tiver o dia, usa o último dia. */
  D.addMeses = (dt, n) => {
    const y = dt.getUTCFullYear(), m = dt.getUTCMonth() + n, d = dt.getUTCDate();
    const ny = y + Math.floor(m / 12), nm = ((m % 12) + 12) % 12;
    return new Date(Date.UTC(ny, nm, Math.min(d, D.diasNoMes(ny, nm))));
  };
  D.addAnos = (dt, n) => D.addMeses(dt, 12 * n);
  /** Anos completos entre a e b (inclusive b como último dia). */
  D.anosCompletos = (a, b) => { let n = 0; while (D.addDias(D.addAnos(a, n + 1), -1) <= b) n++; return n; };
  const moeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  J.fmt = (v) => moeda.format(v || 0);
  J.fmtN = (v) => (v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
})(typeof window !== 'undefined' ? window : globalThis);
