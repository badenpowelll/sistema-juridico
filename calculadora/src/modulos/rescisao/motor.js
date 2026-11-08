/* Módulo Rescisão Trabalhista (CLT) — motor de cálculo puro, sem dependência de tela.
 * Depende de src/core/tabelas.js (Juridico.tabelas, calcularINSS, calcularIRRF, datas). */
(function (root) {
  const J = root.Juridico;
  const D = J.datas, r2 = J.r2;

  /* aviso: 'empregador' (concedido pelo empregador), 'empregado' (devido pelo empregado), null
   * fatorAviso / fatorProp: Súmula 14 TST (culpa recíproca) e art. 484-A CLT (acordo)
   * multaFgts: % sobre o saldo para fins rescisórios; saque: texto do saque do FGTS */
  const MOTIVOS = {
    sem_justa: { nome: 'Dispensa sem justa causa', aviso: 'empregador', fatorAviso: 1, fatorProp: 1, multaFgts: 0.4, saque: 'Saque integral do FGTS (código 01/02)', lei7238: true, seguro: true },
    pedido: { nome: 'Pedido de demissão', aviso: 'empregado', fatorAviso: 1, fatorProp: 1, multaFgts: 0, saque: 'Sem saque do FGTS', lei7238: false },
    justa_causa: { nome: 'Dispensa por justa causa', aviso: null, fatorAviso: 0, fatorProp: 0, multaFgts: 0, saque: 'Sem saque do FGTS', lei7238: false, nota: 'Na justa causa não são devidos 13º proporcional nem férias proporcionais (art. 146, parágrafo único, CLT e Súmula 171 TST). Férias vencidas continuam devidas.' },
    fim_experiencia: { nome: 'Término do contrato de experiência', aviso: null, fatorAviso: 0, fatorProp: 1, multaFgts: 0, saque: 'Saque integral do FGTS (término de contrato a termo)', lei7238: false, experiencia: true },
    antecipada_empregador: { nome: 'Rescisão antecipada da experiência pelo empregador', aviso: null, fatorAviso: 0, fatorProp: 1, multaFgts: 0.4, saque: 'Saque integral do FGTS', lei7238: true, experiencia: true, art479: true },
    antecipada_empregado: { nome: 'Rescisão antecipada da experiência pelo empregado', aviso: null, fatorAviso: 0, fatorProp: 1, multaFgts: 0, saque: 'Sem saque do FGTS', lei7238: false, experiencia: true, art480: true },
    indireta: { nome: 'Rescisão indireta (art. 483 CLT)', aviso: 'empregador', avisoSempreIndenizado: true, fatorAviso: 1, fatorProp: 1, multaFgts: 0.4, saque: 'Saque integral do FGTS (após reconhecimento judicial)', lei7238: true },
    culpa_reciproca: { nome: 'Culpa recíproca', aviso: 'empregador', avisoSempreIndenizado: true, fatorAviso: 0.5, fatorProp: 0.5, multaFgts: 0.2, saque: 'Saque do FGTS (após reconhecimento judicial)', lei7238: false, nota: 'Súmula 14 TST: 50% do aviso prévio, do 13º e das férias proporcionais. Multa do FGTS de 20% (art. 18, §2º, Lei 8.036/90).' },
    acordo: { nome: 'Acordo entre as partes (art. 484-A CLT)', aviso: 'empregador', avisoSempreIndenizado: true, fatorAviso: 0.5, fatorProp: 1, multaFgts: 0.2, saque: 'Saque de até 80% do FGTS; sem seguro-desemprego', lei7238: false, nota: 'Art. 484-A CLT: metade do aviso prévio indenizado e da multa do FGTS (20%); demais verbas integrais.' },
    falecimento: { nome: 'Falecimento do empregado', aviso: null, fatorAviso: 0, fatorProp: 1, multaFgts: 0, saque: 'Saque pelos dependentes habilitados (Lei 6.858/80)', lei7238: false },
    aposentadoria: { nome: 'Aposentadoria', aviso: null, fatorAviso: 0, fatorProp: 1, multaFgts: 0, saque: 'Saque integral do FGTS (aposentadoria)', lei7238: false },
  };

  /** Verbas que o usuário pode marcar e o padrão para o motivo. */
  function verbasDisponiveis(motivo) {
    const m = MOTIVOS[motivo];
    return [
      { id: 'saldo', nome: 'Saldo de salário', ok: true, padrao: true },
      { id: 'aviso', nome: m.aviso === 'empregado' ? 'Aviso prévio (desconto se não cumprido)' : 'Aviso prévio indenizado (Lei 12.506/11)', ok: !!m.aviso, padrao: !!m.aviso },
      { id: 'decimo', nome: '13º salário', ok: true, padrao: true },
      { id: 'ferias', nome: 'Férias + 1/3', ok: true, padrao: true },
      { id: 'art479', nome: 'Indenização art. 479 CLT (50% dos dias restantes)', ok: !!m.art479, padrao: !!m.art479 },
      { id: 'art480', nome: 'Desconto art. 480 CLT (prejuízo ao empregador)', ok: !!m.art480, padrao: false },
      { id: 'multa477', nome: 'Multa por atraso no pagamento (art. 477, §8º)', ok: true, padrao: false },
      { id: 'lei7238', nome: 'Indenização adicional (Lei 7.238/84, art. 9º)', ok: m.lei7238, padrao: false },
      { id: 'salarioFamilia', nome: 'Salário-família', ok: true, padrao: false },
      { id: 'fgts', nome: 'FGTS 8% sobre as verbas rescisórias', ok: true, padrao: true },
      { id: 'multaFgts', nome: m.multaFgts ? `Multa de ${m.multaFgts * 100}% sobre o FGTS` : 'Multa sobre o FGTS', ok: m.multaFgts > 0, padrao: m.multaFgts > 0 },
      { id: 'inss', nome: 'Desconto de INSS (tabela 2026)', ok: true, padrao: true },
      { id: 'irrf', nome: 'Desconto de IRRF (tabela 2026)', ok: true, padrao: true },
    ];
  }

  /** Dias de férias conforme faltas injustificadas no período aquisitivo (art. 130 CLT). */
  function diasFeriasPorFaltas(f) {
    if (f <= 5) return 30; if (f <= 14) return 24; if (f <= 23) return 18; if (f <= 32) return 12; return 0;
  }

  /** Avos de 13º no ano civil: mês com 15 dias ou mais de trabalho conta 1/12 (Lei 4.090/62). */
  function avos13(ano, ini, fim) {
    let n = 0;
    for (let m = 0; m < 12; m++) {
      const a = new Date(Date.UTC(ano, m, 1)), b = new Date(Date.UTC(ano, m, D.diasNoMes(ano, m)));
      const s = ini > a ? ini : a, e = fim < b ? fim : b;
      if (e >= s && D.diasEntre(s, e) + 1 >= 15) n++;
    }
    return n;
  }

  /** Avos de férias a partir do início do período aquisitivo: fração acima de 14 dias conta 1/12 (art. 146). */
  function avosFerias(inicio, fim) {
    if (fim < inicio) return 0;
    let n = 0;
    for (let i = 0; i < 12; i++) {
      const a = D.addMeses(inicio, i), b = D.addDias(D.addMeses(inicio, i + 1), -1);
      if (a > fim) break;
      if (b <= fim) n++; else if (D.diasEntre(a, fim) + 1 >= 15) n++;
    }
    return n;
  }

  function diasAvisoProporcional(adm, dem) {
    const anos = D.anosCompletos(adm, dem);
    return { anos, dias: Math.min(90, 30 + 3 * Math.min(anos, 20)) };
  }

  /** Quantos dias de aviso entram como indenizados e projetam o contrato (OJ 82 e 83 SDI-1 TST). */
  function infoAviso(input) {
    const m = MOTIVOS[input.motivo];
    const adm = D.parse(input.admissao), dem = D.parse(input.demissao);
    const { anos, dias } = diasAvisoProporcional(adm, dem);
    let indenizados = 0;
    let tipo = input.avisoTipo || 'indenizado';
    if (m.aviso === 'empregador') {
      if (m.avisoSempreIndenizado) tipo = 'indenizado';
      if (tipo === 'indenizado') indenizados = dias;
      else if (tipo === 'trabalhado') indenizados = dias - 30; // dias acrescidos pela Lei 12.506 são indenizados
    }
    const usaProjecao = input.projetarAviso !== false && indenizados > 0;
    const projecao = usaProjecao ? indenizados : 0;
    return { anos, dias, indenizados, tipo, projecao, fimProjetado: D.addDias(dem, projecao) };
  }

  /** Lista os períodos de 13º e de férias do contrato inteiro, para o usuário escolher quais calcular. */
  function listarPeriodos(input) {
    const adm = D.parse(input.admissao), dem = D.parse(input.demissao);
    const { fimProjetado } = infoAviso(input);
    const decimos = [];
    for (let y = adm.getUTCFullYear(); y <= fimProjetado.getUTCFullYear(); y++) {
      const de = y === adm.getUTCFullYear() ? adm : new Date(Date.UTC(y, 0, 1));
      const ateAno = new Date(Date.UTC(y, 11, 31));
      const ate = fimProjetado < ateAno ? fimProjetado : ateAno;
      const avosTotal = avos13(y, adm, fimProjetado);
      const avosTrab = y > dem.getUTCFullYear() ? 0 : avos13(y, adm, dem);
      decimos.push({
        key: '13-' + y, ano: y, de: D.iso(de), ate: D.iso(ate), avosTrab, avosProj: avosTotal - avosTrab, avos: avosTotal,
        rescisao: y >= dem.getUTCFullYear(),
      });
    }
    const ferias = [];
    for (let k = 0; ; k++) {
      const de = D.addAnos(adm, k);
      if (de > fimProjetado) break;
      const fimAquis = D.addDias(D.addAnos(adm, k + 1), -1);
      const vencida = fimAquis <= fimProjetado;
      const avosTotal = vencida ? 12 : avosFerias(de, fimProjetado);
      const avosTrab = de > dem ? 0 : (fimAquis <= dem ? 12 : avosFerias(de, dem));
      const fimConcessivo = D.addDias(D.addAnos(adm, k + 2), -1);
      if (avosTotal === 0) continue;
      ferias.push({
        key: 'F-' + D.iso(de), de: D.iso(de), ate: D.iso(vencida ? fimAquis : fimProjetado),
        fimConcessivo: D.iso(fimConcessivo), vencida, avos: avosTotal, avosTrab, avosProj: avosTotal - avosTrab,
        dobroAuto: vencida && fimConcessivo < dem,
      });
    }
    return { decimos, ferias };
  }

  /** Seleção padrão: 13º do ano da rescisão, última férias vencida e as proporcionais. */
  function selecaoPadrao(periodos) {
    const dec = {}, fer = {};
    periodos.decimos.forEach((p) => { dec[p.key] = p.rescisao; });
    const vencidas = periodos.ferias.filter((p) => p.vencida);
    const ultimaVencida = vencidas[vencidas.length - 1];
    periodos.ferias.forEach((p) => {
      const incluir = !p.vencida || (ultimaVencida && p.key === ultimaVencida.key && !p.dobroAuto);
      fer[p.key] = { incluir: !!incluir, faltas: 0, dobro: p.dobroAuto };
    });
    return { decimos: dec, ferias: fer };
  }

  function validar(input) {
    const erros = [];
    if (!input.admissao) erros.push('Informe a data de admissão.');
    if (!input.demissao) erros.push('Informe a data de demissão.');
    if (input.admissao && input.demissao && D.parse(input.demissao) < D.parse(input.admissao)) erros.push('A data de demissão precisa ser igual ou posterior à admissão.');
    if (!(input.salario > 0)) erros.push('Informe o último salário bruto.');
    if (!MOTIVOS[input.motivo]) erros.push('Escolha o motivo da rescisão.');
    const m = MOTIVOS[input.motivo];
    if (m && m.experiencia && !input.fimExperiencia) erros.push('Informe a data prevista para o fim da experiência.');
    if (m && m.experiencia && input.fimExperiencia && input.demissao && D.parse(input.fimExperiencia) < D.parse(input.demissao)) erros.push('O fim previsto da experiência não pode ser anterior à demissão.');
    return erros;
  }

  /** Cálculo completo. input:
   *  admissao, demissao, salario, motivo, avisoTipo, dependentes, filhosSalarioFamilia, faltasMes,
   *  fimExperiencia, mesDataBase, dataPagamento, saldoFgts, estimarFgtsPeriodo, inssSobreAviso,
   *  outrosDescontos, verbas{id:bool}, selecao{decimos, ferias} */
  function calcular(input) {
    const erros = validar(input);
    if (erros.length) return { erros };
    const T = J.tabelas;
    const m = MOTIVOS[input.motivo];
    const sal = Number(input.salario);
    const diaria = sal / 30;
    const adm = D.parse(input.admissao), dem = D.parse(input.demissao);
    const av = infoAviso(input);
    const periodos = listarPeriodos(input);
    const sel = input.selecao || selecaoPadrao(periodos);
    const disp = Object.fromEntries(verbasDisponiveis(input.motivo).map((v) => [v.id, v]));
    const quer = (id) => disp[id].ok && (input.verbas && id in input.verbas ? !!input.verbas[id] : disp[id].padrao);
    const deps = Number(input.dependentes) || 0;
    const verbas = [], avisos = [];
    const add = (v) => { v.valor = r2(v.valor); if (v.valor > 0) verbas.push(v); return v; };

    // Saldo de salário
    let saldo = null;
    if (quer('saldo')) {
      const inicioMes = new Date(Date.UTC(dem.getUTCFullYear(), dem.getUTCMonth(), 1));
      const ini = adm > inicioMes ? adm : inicioMes;
      const ultimoDia = D.diasNoMes(dem.getUTCFullYear(), dem.getUTCMonth());
      let dias = (ini.getUTCDate() === 1 && dem.getUTCDate() === ultimoDia) ? 30 : Math.min(30, D.diasEntre(ini, dem) + 1);
      const faltas = Math.min(dias, Number(input.faltasMes) || 0);
      dias -= faltas;
      saldo = add({ id: 'saldo', grupo: 'provento', descricao: 'Saldo de salário', referencia: `${dias} dia(s)`, valor: diaria * dias,
        memoria: `${J.fmt(sal)} ÷ 30 × ${dias} dia(s)${faltas ? ` (descontadas ${faltas} falta(s))` : ''}`, fundamento: 'Art. 462 e 477 CLT', inss: true, irrf: true, fgts: true });
    }

    // Salário-família proporcional aos dias do mês
    if (quer('salarioFamilia')) {
      const filhos = Number(input.filhosSalarioFamilia) || 0;
      const diasSF = saldo ? parseInt(saldo.referencia, 10) : 0;
      if (sal > T.salarioFamilia.limiteRemuneracao) avisos.push(`Salário-família não devido: remuneração acima de ${J.fmt(T.salarioFamilia.limiteRemuneracao)}.`);
      else if (!filhos) avisos.push('Salário-família marcado, mas nenhum filho de até 14 anos informado.');
      else add({ id: 'salarioFamilia', grupo: 'provento', descricao: 'Salário-família', referencia: `${filhos} cota(s)`, valor: T.salarioFamilia.cota / 30 * diasSF * filhos,
        memoria: `${J.fmt(T.salarioFamilia.cota)} ÷ 30 × ${diasSF} dia(s) × ${filhos}`, fundamento: T.salarioFamilia.fonte });
    }

    // Aviso prévio
    let avisoVerba = null;
    if (quer('aviso')) {
      if (m.aviso === 'empregador' && av.indenizados > 0) {
        const dias = av.indenizados;
        const extra = av.tipo === 'trabalhado' ? ' (dias acrescidos ao aviso trabalhado)' : '';
        avisoVerba = add({ id: 'aviso', grupo: 'provento', descricao: `Aviso prévio indenizado${m.fatorAviso < 1 ? ' (50%)' : ''}${extra}`, referencia: `${dias} dia(s)`,
          valor: diaria * dias * m.fatorAviso,
          memoria: `${J.fmt(sal)} ÷ 30 × ${dias} dia(s)${m.fatorAviso < 1 ? ' × 50%' : ''} — ${av.anos} ano(s) completo(s): 30 + 3 × ${Math.min(av.anos, 20)} = ${av.dias} dias`,
          fundamento: 'Art. 487 CLT e Lei 12.506/11', inss: !!input.inssSobreAviso, irrf: false, fgts: true });
      } else if (m.aviso === 'empregado' && input.avisoTipo === 'descontado') {
        add({ id: 'avisoDesc', grupo: 'desconto', descricao: 'Aviso prévio não cumprido pelo empregado', referencia: '30 dias', valor: sal,
          memoria: '30 dias de salário (a proporcionalidade da Lei 12.506/11 só beneficia o empregado)', fundamento: 'Art. 487, §2º, CLT' });
      }
    }

    // 13º salário
    if (quer('decimo')) {
      const anoDem = dem.getUTCFullYear();
      periodos.decimos.forEach((p) => {
        if (!sel.decimos[p.key]) return;
        const fator = p.ano >= anoDem ? m.fatorProp : 1; // anos já completos são direito adquirido
        if (fator === 0) { avisos.push(`13º de ${p.ano} não devido neste motivo de rescisão.`); return; }
        const pct = fator < 1 ? ' × 50%' : '';
        if (p.avosTrab > 0) add({ id: 'decimo-' + p.ano, grupo: 'provento', descricao: `13º salário ${p.ano}${p.ano >= anoDem && p.avosTrab < 12 ? ' proporcional' : ''}`, referencia: `${p.avosTrab}/12`,
          valor: sal / 12 * p.avosTrab * fator, memoria: `${J.fmt(sal)} ÷ 12 × ${p.avosTrab}${pct} (${D.br(p.de)} a ${D.br(p.ano === anoDem ? D.iso(dem) : p.ate)})`,
          fundamento: 'Lei 4.090/62', inss: true, irrf: true, fgts: true, decimo: true });
        if (p.avosProj > 0) add({ id: 'decimoInd-' + p.ano, grupo: 'provento', descricao: `13º salário ${p.ano} sobre aviso indenizado`, referencia: `${p.avosProj}/12`,
          valor: sal / 12 * p.avosProj * fator, memoria: `${J.fmt(sal)} ÷ 12 × ${p.avosProj}${pct} (projeção do aviso até ${D.br(av.fimProjetado)})`,
          fundamento: 'Art. 487, §1º, CLT e OJ 82 SDI-1 TST', inss: true, irrf: true, fgts: true, decimo: true });
      });
    }

    // Férias
    if (quer('ferias')) {
      periodos.ferias.forEach((p) => {
        const s = sel.ferias[p.key];
        if (!s || !s.incluir) return;
        const fator = p.vencida ? 1 : m.fatorProp;
        if (fator === 0) { avisos.push(`Férias proporcionais (${D.br(p.de)} a ${D.br(p.ate)}) não devidas na justa causa.`); return; }
        const faltas = Number(s.faltas) || 0;
        const diasDireito = diasFeriasPorFaltas(faltas);
        const dobro = p.vencida && !!s.dobro;
        const mult = (dobro ? 2 : 1) * fator;
        const rotulo = p.vencida ? `Férias vencidas${dobro ? ' em dobro' : ''}` : 'Férias proporcionais';
        const partes = [];
        if (p.avosTrab > 0) partes.push({ avos: p.avosTrab, proj: false });
        if (p.avosProj > 0) partes.push({ avos: p.avosProj, proj: true });
        partes.forEach((pt) => {
          const dias = diasDireito * pt.avos / 12;
          const valor = diaria * dias * mult;
          const desc = pt.proj ? `Férias sobre aviso indenizado` : rotulo;
          const per = `${D.br(p.de)} a ${D.br(p.ate)}`;
          const memo = `${J.fmt(sal)} ÷ 30 × ${J.fmtN(dias)} dia(s)${dobro ? ' × 2' : ''}${fator < 1 ? ' × 50%' : ''} — direito a ${diasDireito} dias${faltas ? ` (${faltas} faltas, art. 130)` : ''} × ${pt.avos}/12`;
          add({ id: `ferias-${p.key}-${pt.proj ? 'p' : 't'}`, grupo: 'provento', descricao: `${desc} (${per})`, referencia: p.vencida && !pt.proj ? `${diasDireito} dias` : `${pt.avos}/12`,
            valor, memoria: memo, fundamento: p.vencida ? (dobro ? 'Art. 137 CLT' : 'Art. 146 CLT') : 'Art. 146, parágrafo único, CLT e Súmulas 171 e 261 TST', inss: false, irrf: false, fgts: false });
          add({ id: `terco-${p.key}-${pt.proj ? 'p' : 't'}`, grupo: 'provento', descricao: `1/3 constitucional — ${desc.toLowerCase()} (${per})`, referencia: '1/3',
            valor: valor / 3, memoria: `${J.fmt(r2(valor))} ÷ 3`, fundamento: 'Art. 7º, XVII, CF', inss: false, irrf: false, fgts: false });
        });
      });
    }

    // Contrato de experiência: arts. 479 e 480
    if (m.experiencia) {
      const fimExp = D.parse(input.fimExperiencia);
      const restantes = Math.max(0, D.diasEntre(dem, fimExp));
      if (quer('art479') && restantes > 0) add({ id: 'art479', grupo: 'provento', descricao: 'Indenização art. 479 CLT', referencia: `${restantes} dia(s) restantes`,
        valor: diaria * restantes / 2, memoria: `${J.fmt(sal)} ÷ 30 × ${restantes} dia(s) × 50%`, fundamento: 'Art. 479 CLT', inss: false, irrf: false, fgts: false });
      if (quer('art480') && restantes > 0) add({ id: 'art480', grupo: 'desconto', descricao: 'Indenização ao empregador art. 480 CLT', referencia: `${restantes} dia(s) restantes`,
        valor: diaria * restantes / 2, memoria: `Limite: ${J.fmt(sal)} ÷ 30 × ${restantes} dia(s) × 50% (exige prejuízo comprovado)`, fundamento: 'Art. 480, §1º, CLT' });
    }

    // Lei 7.238/84, art. 9º
    if (quer('lei7238')) {
      const mes = Number(input.mesDataBase);
      if (!mes) avisos.push('Indenização da Lei 7.238/84 marcada, mas o mês da data-base da categoria não foi informado.');
      else {
        const fim = av.fimProjetado;
        let db = new Date(Date.UTC(fim.getUTCFullYear(), mes - 1, 1));
        if (db <= fim) db = new Date(Date.UTC(fim.getUTCFullYear() + 1, mes - 1, 1));
        const antecede = D.diasEntre(fim, db);
        if (antecede <= 30) add({ id: 'lei7238', grupo: 'provento', descricao: 'Indenização adicional (Lei 7.238/84, art. 9º)', referencia: '1 salário', valor: sal,
          memoria: `Término do contrato (com projeção do aviso) em ${D.br(fim)}, ${antecede} dia(s) antes da data-base ${D.br(db)}`, fundamento: 'Lei 7.238/84, art. 9º e Súmulas 182 e 314 TST', inss: false, irrf: false, fgts: false });
        else avisos.push(`Indenização da Lei 7.238/84 não devida: o contrato termina em ${D.br(fim)}, ${antecede} dias antes da data-base ${D.br(db)} (precisa ser até 30 dias).`);
      }
    }

    // Multa do art. 477, §8º
    if (quer('multa477')) {
      const prazo = D.addDias(dem, 10);
      if (input.dataPagamento && D.parse(input.dataPagamento) <= prazo) avisos.push(`Multa do art. 477 não devida: pagamento em ${D.br(input.dataPagamento)}, dentro do prazo de 10 dias (até ${D.br(prazo)}).`);
      else add({ id: 'multa477', grupo: 'provento', descricao: 'Multa por atraso na rescisão (art. 477, §8º)', referencia: '1 salário', valor: sal,
        memoria: `Prazo de pagamento: até ${D.br(prazo)} (10 dias do término)${input.dataPagamento ? `; pago em ${D.br(input.dataPagamento)}` : ''}`, fundamento: 'Art. 477, §§6º e 8º, CLT', inss: false, irrf: false, fgts: false });
    }

    // INSS
    const proventos = () => verbas.filter((v) => v.grupo === 'provento');
    const soma = (arr) => r2(arr.reduce((s, v) => s + v.valor, 0));
    const baseInssMes = soma(proventos().filter((v) => v.inss && !v.decimo));
    const baseInss13 = soma(proventos().filter((v) => v.inss && v.decimo));
    let inssMes = { valor: 0 }, inss13 = { valor: 0 };
    if (quer('inss')) {
      inssMes = J.calcularINSS(baseInssMes); inss13 = J.calcularINSS(baseInss13);
      const memoInss = (b, c) => `Base ${J.fmt(b)}: ` + c.detalhe.map((d) => `${(d.aliquota * 100).toLocaleString('pt-BR')}% = ${J.fmtN(d.valor)}`).join(' + ');
      add({ id: 'inss', grupo: 'desconto', descricao: 'INSS sobre salário', referencia: baseInssMes ? `${J.fmtN(inssMes.valor / baseInssMes * 100)}% efetiva` : '', valor: inssMes.valor, memoria: memoInss(baseInssMes, inssMes), fundamento: T.inss.fonte });
      add({ id: 'inss13', grupo: 'desconto', descricao: 'INSS sobre 13º salário', referencia: baseInss13 ? `${J.fmtN(inss13.valor / baseInss13 * 100)}% efetiva` : '', valor: inss13.valor, memoria: memoInss(baseInss13, inss13), fundamento: T.inss.fonte });
    }

    // IRRF (aviso indenizado, férias indenizadas e indenizações são isentos)
    if (quer('irrf')) {
      const rendMes = soma(proventos().filter((v) => v.irrf && !v.decimo));
      const rend13 = soma(proventos().filter((v) => v.irrf && v.decimo));
      const memoIr = (rend, c) => `Rendimento ${J.fmt(rend)} − deduções ${J.fmt(c.deducoes)}${c.usaSimplificado ? ' (desconto simplificado)' : ` (INSS + ${deps} dependente(s))`} = base ${J.fmt(c.base)}; ${(c.aliquota * 100).toLocaleString('pt-BR')}% − ${J.fmtN(c.deducaoFaixa)} = ${J.fmtN(c.impostoTabela)}${c.reducao ? `; redução Lei 15.270 de ${J.fmtN(c.reducao)}` : ''}`;
      if (rendMes > 0) {
        const c = J.calcularIRRF(rendMes, inssMes.valor, deps);
        const v = add({ id: 'irrf', grupo: 'desconto', descricao: 'IRRF sobre salário', referencia: `${(c.aliquota * 100).toLocaleString('pt-BR')}%`, valor: c.valor, memoria: memoIr(rendMes, c), fundamento: T.irrf.fonte });
        if (!c.valor) avisos.push(`IRRF sobre salário isento (${memoIr(rendMes, c)}).`);
      }
      if (rend13 > 0) {
        const c = J.calcularIRRF(rend13, inss13.valor, deps, { simplificado: false });
        add({ id: 'irrf13', grupo: 'desconto', descricao: 'IRRF sobre 13º (tributação exclusiva)', referencia: `${(c.aliquota * 100).toLocaleString('pt-BR')}%`, valor: c.valor, memoria: memoIr(rend13, c), fundamento: T.irrf.fonte });
        if (!c.valor) avisos.push(`IRRF sobre 13º isento (${memoIr(rend13, c)}).`);
      }
    }

    const outros = Number(input.outrosDescontos) || 0;
    if (outros > 0) add({ id: 'outros', grupo: 'desconto', descricao: 'Adiantamentos e outros descontos', referencia: '', valor: outros, memoria: 'Informado pelo usuário', fundamento: 'Art. 462 CLT' });

    // FGTS (depositado na conta vinculada, não entra no líquido do TRCT)
    const fgts = { baseRescisoria: 0, depositoRescisorio: 0, estimativaPeriodo: 0, saldoInformado: Number(input.saldoFgts) || 0, multaPct: m.multaFgts, multa: 0, totalDepositar: 0, saque: m.saque, memoria: [] };
    if (quer('fgts')) {
      fgts.baseRescisoria = soma(proventos().filter((v) => v.fgts));
      fgts.depositoRescisorio = r2(fgts.baseRescisoria * T.fgts.aliquota);
      fgts.memoria.push(`Depósito rescisório: 8% × ${J.fmt(fgts.baseRescisoria)} (saldo de salário, aviso indenizado e 13º) = ${J.fmt(fgts.depositoRescisorio)}`);
      if (input.estimarFgtsPeriodo) {
        const inicioMesDem = new Date(Date.UTC(dem.getUTCFullYear(), dem.getUTCMonth(), 1));
        let meses = 0;
        for (let d = new Date(Date.UTC(adm.getUTCFullYear(), adm.getUTCMonth(), 1)); d < inicioMesDem; d = D.addMeses(d, 1)) {
          const fimMes = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), D.diasNoMes(d.getUTCFullYear(), d.getUTCMonth())));
          const ini = adm > d ? adm : d;
          meses += Math.min(30, D.diasEntre(ini, fimMes) + 1) / 30;
        }
        const avos13Ant = periodos.decimos.filter((p) => p.ano < dem.getUTCFullYear()).reduce((s, p) => s + p.avos, 0);
        fgts.estimativaPeriodo = r2(T.fgts.aliquota * sal * (meses + avos13Ant / 12));
        fgts.memoria.push(`Estimativa de FGTS não depositado no contrato: 8% × ${J.fmt(sal)} × (${J.fmtN(meses)} meses + ${J.fmtN(avos13Ant / 12)} de 13º) = ${J.fmt(fgts.estimativaPeriodo)} (sem correção/JAM)`);
      }
    }
    if (quer('multaFgts')) {
      const base = fgts.saldoInformado + fgts.estimativaPeriodo + fgts.depositoRescisorio;
      fgts.multa = r2(base * m.multaFgts);
      fgts.memoria.push(`Multa de ${m.multaFgts * 100}%: ${J.fmt(base)} × ${m.multaFgts * 100}% = ${J.fmt(fgts.multa)} (art. 18, Lei 8.036/90)`);
      if (!fgts.saldoInformado && !fgts.estimativaPeriodo) avisos.push('A multa do FGTS foi calculada só sobre os depósitos da rescisão. Informe o saldo para fins rescisórios do extrato da Caixa ou marque a estimativa do período.');
    }
    fgts.totalDepositar = r2(fgts.depositoRescisorio + fgts.estimativaPeriodo + fgts.multa);

    if (m.nota) avisos.unshift(m.nota);
    const totalProventos = soma(verbas.filter((v) => v.grupo === 'provento'));
    const totalDescontos = soma(verbas.filter((v) => v.grupo === 'desconto'));
    return {
      erros: [], motivo: m, aviso: av, periodos, selecao: sel, verbas, avisos, fgts,
      totais: { proventos: totalProventos, descontos: totalDescontos, liquido: r2(totalProventos - totalDescontos), comFgts: r2(totalProventos - totalDescontos + fgts.totalDepositar + fgts.saldoInformado) },
      tempoServico: diasAvisoProporcional(adm, dem).anos,
    };
  }

  J.modulos = J.modulos || {};
  J.modulos.rescisao = { MOTIVOS, verbasDisponiveis, listarPeriodos, selecaoPadrao, infoAviso, calcular, diasFeriasPorFaltas, avos13, avosFerias };
})(typeof window !== 'undefined' ? window : globalThis);
