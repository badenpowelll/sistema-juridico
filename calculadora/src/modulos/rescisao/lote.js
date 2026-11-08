/* Rescisão em lote: lê planilha (xlsx/xls/csv), calcula cada trabalhador e exporta PDF/ZIP/planilha.
 * Aceita o modelo do sistema e planilhas de prévia rescisória com cabeçalho em qualquer linha. */
(function () {
  const J = window.Juridico, R = J.modulos.rescisao, D = J.datas;
  const $ = (s, el = document) => el.querySelector(s);
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  // campo -> padrões de cabeçalho (normalizados). A ordem importa: o primeiro que casar vence.
  const COLUNAS = [
    ['matricula', /^matricula|^registro$|^chapa$/], ['nome', /^nome(doempregado|dotrabalhador|completo)?$|^empregado$|^trabalhador$|^colaborador$/],
    ['cpf', /^cpf/], ['pis', /^pis|^nit/], ['ctps', /^ctps/], ['cargo', /^funcao|^cargo/], ['nascimento', /^(datade)?nascimento/],
    ['endereco', /^endereco(doempregado)?$/], ['municipio', /^municipio|^cidade/], ['obra', /^obra|^lotacao|^setor/],
    ['empregador', /^empregador|^empresa|^razaosocial/], ['cnpj', /^cnpj/], ['enderecoEmpregador', /^enderecodoempregador|^enderecoempresa/],
    ['admissao', /^(datade)?admissao/], ['demissao', /^(datade)?(demissao|desligamento|afastamento)$/],
    ['remuneracao', /^remuneracao/], ['salarioBase', /^salariobase/], ['periculosidade', /^periculosidade/], ['insalubridade', /^insalubridade/],
    ['salario', /^(ultimo)?salario(bruto)?$/],
    ['motivo', /^motivo/], ['aviso', /^(tipode)?aviso(previo)?$|^tipoaviso/], ['dependentes', /^dependentes/], ['filhos', /^filhos/],
    ['saldoFgts', /^saldo(do)?fgts/], ['faltasMes', /^faltas/], ['fimExperiencia', /^fim(da)?experiencia/], ['dataPagamento', /^(datado)?pagamento/],
    ['mesDataBase', /^(mes)?(da)?database/], ['outrosDescontos', /^(outros)?descontos|^adiantamento/], ['feriasVencidas', /^feriasvencidas/],
    ['multa477', /^multa477/], ['obs', /^observacoesdaconferencia|^observacoes?$|^obs$/],
  ];

  const MOTIVO_TEXTO = [
    [/antecipad.*empregad[oa]\b|antecipad.*funcionari|antecipad.*trabalhador/, 'antecipada_empregado'], [/antecipad/, 'antecipada_empregador'],
    [/sem ?justa/, 'sem_justa'], [/justa/, 'justa_causa'], [/pedido|demissao a pedido|pediu/, 'pedido'], [/experiencia|termino|fim do contrato/, 'fim_experiencia'],
    [/indireta/, 'indireta'], [/culpa/, 'culpa_reciproca'], [/acordo|484/, 'acordo'], [/falec|obito|morte/, 'falecimento'], [/aposent/, 'aposentadoria'],
  ];
  function lerMotivo(v, padrao) {
    if (!v) return padrao;
    if (R.MOTIVOS[v]) return v;
    const s = String(v).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
    const hit = MOTIVO_TEXTO.find(([re]) => re.test(s));
    return hit ? hit[1] : null;
  }
  function lerAviso(v, padrao) {
    const s = J.normalizarChave(v);
    if (!s) return padrao;
    if (s.startsWith('indeniz')) return 'indenizado'; if (s.startsWith('trabalh') || s.startsWith('cumpri')) return 'trabalhado';
    if (s.startsWith('descont') || s.startsWith('naocumpri')) return 'descontado'; if (s.startsWith('dispens')) return 'dispensado';
    return padrao;
  }
  const sim = (v) => /^(s|sim|x|1|true|verdadeiro)$/i.test(String(v ?? '').trim());

  const st = { wb: null, nomeArquivo: '', aba: null, linhas: [], itens: [], params: {} };

  /** Encontra a linha de cabeçalho: a que tiver "nome" e "admissão" entre as 20 primeiras. */
  function acharCabecalho(aoa) {
    for (let i = 0; i < Math.min(aoa.length, 20); i++) {
      const k = aoa[i].map(J.normalizarChave);
      if (k.some((x) => /^nome|^empregado$|^trabalhador$/.test(x)) && k.some((x) => /admissao/.test(x))) return i;
    }
    return -1;
  }
  /** Lê parâmetros escritos acima do cabeçalho (ex.: "Data do desligamento | 31/10/2026"). */
  function acharParametros(aoa, ate) {
    const p = {};
    for (let i = 0; i < ate; i++) {
      const row = aoa[i];
      row.forEach((c, j) => {
        const k = J.normalizarChave(c);
        if (/datadodesligamento|datadademissao|datadeafastamento/.test(k)) { const d = J.lerData(row[j + 1]); if (d) p.demissao = d; }
        if (/avisoprevioindenizado/.test(k)) p.aviso = 'indenizado';
        if (/avisopreviotrabalhado/.test(k)) p.aviso = 'trabalhado';
        if (/semjustacausa/.test(k)) p.motivo = 'sem_justa';
      });
    }
    return p;
  }

  function lerAba(nome) {
    const ws = st.wb.Sheets[nome];
    const aoa = XLSX.utils.sheet_to_json(ws, { header: 1, raw: true, defval: '' });
    const h = acharCabecalho(aoa);
    if (h < 0) return { erro: 'Não encontrei uma linha de cabeçalho com as colunas "Nome" e "Admissão" nesta aba.', linhas: [], params: {} };
    const heads = aoa[h].map(J.normalizarChave);
    const mapa = {};
    heads.forEach((k, j) => { if (!k) return; const c = COLUNAS.find(([campo, re]) => !(campo in mapa) && re.test(k)); if (c) mapa[c[0]] = j; });
    const linhas = [];
    for (let i = h + 1; i < aoa.length; i++) {
      const row = aoa[i];
      const o = { _linha: i + 1 };
      Object.entries(mapa).forEach(([campo, j]) => { o[campo] = row[j]; });
      const nome = String(o.nome ?? '').trim();
      if (!nome && !o.admissao) continue;
      if (/^(sub)?total/i.test(nome) || /^(sub)?total/i.test(String(o.matricula ?? ''))) continue;
      linhas.push(o);
    }
    return { linhas, params: acharParametros(aoa, h), colunas: Object.keys(mapa) };
  }

  function padroes() {
    const f = $('#form-lote');
    return {
      demissao: f.elements.loteDemissao.value, motivo: f.elements.loteMotivo.value, aviso: f.elements.loteAviso.value,
      empregador: f.elements.loteEmpregador.value.trim(), cnpj: f.elements.loteCnpj.value.trim(), enderecoEmpregador: f.elements.loteEndEmpregador.value.trim(),
      multa477: f.elements.loteMulta477.checked, lei7238: f.elements.loteLei7238.checked, mesDataBase: Number(f.elements.loteDataBase.value) || 0,
      inssSobreAviso: f.elements.loteInssAviso.checked,
    };
  }

  function montarItem(o, p) {
    const erros = [];
    const motivo = lerMotivo(o.motivo, p.motivo);
    if (!motivo) erros.push(`Motivo "${o.motivo}" não reconhecido.`);
    let salario = J.lerValor(o.remuneracao);
    if (!salario) salario = J.lerValor(o.salarioBase) + J.lerValor(o.periculosidade) + J.lerValor(o.insalubridade);
    if (!salario) salario = J.lerValor(o.salario);
    const input = {
      admissao: J.lerData(o.admissao), demissao: J.lerData(o.demissao) || p.demissao, salario, motivo: motivo || 'sem_justa',
      avisoTipo: lerAviso(o.aviso, p.aviso), dependentes: J.lerValor(o.dependentes), filhosSalarioFamilia: J.lerValor(o.filhos),
      faltasMes: J.lerValor(o.faltasMes), fimExperiencia: J.lerData(o.fimExperiencia), dataPagamento: J.lerData(o.dataPagamento),
      mesDataBase: Number(o.mesDataBase) || p.mesDataBase, saldoFgts: J.lerValor(o.saldoFgts), outrosDescontos: J.lerValor(o.outrosDescontos),
      inssSobreAviso: p.inssSobreAviso, verbas: { multa477: o.multa477 !== undefined && o.multa477 !== '' ? sim(o.multa477) : p.multa477, lei7238: p.lei7238, salarioFamilia: J.lerValor(o.filhos) > 0 },
    };
    const qual = {
      empregado: { nome: String(o.nome ?? '').trim(), cpf: String(o.cpf ?? ''), pis: String(o.pis ?? ''), ctps: String(o.ctps ?? ''), cargo: String(o.cargo ?? ''),
        matricula: String(o.matricula ?? ''), nascimento: J.lerData(o.nascimento), endereco: String(o.endereco ?? ''), lotacao: [o.obra, o.municipio].filter(Boolean).join(' · ') },
      empregador: { nome: String(o.empregador || p.empregador || ''), documento: String(o.cnpj || p.cnpj || ''), endereco: String(o.enderecoEmpregador || p.enderecoEmpregador || '') },
    };
    let r = null;
    if (!erros.length && input.admissao && input.demissao) {
      const per = R.listarPeriodos(input);
      const sel = R.selecaoPadrao(per);
      const nv = o.feriasVencidas === undefined || o.feriasVencidas === '' ? null : Number(o.feriasVencidas);
      if (nv !== null && !isNaN(nv)) {
        const venc = per.ferias.filter((x) => x.vencida);
        venc.forEach((x, i) => { sel.ferias[x.key].incluir = i >= venc.length - nv; });
      }
      input.selecao = sel;
      r = R.calcular(input);
      if (r.erros.length) { erros.push(...r.erros); r = null; }
      else if (o.obs && String(o.obs).trim() && String(o.obs).trim() !== '0') r.avisos.push('Observação da planilha: ' + String(o.obs).trim());
    } else {
      if (!input.admissao) erros.push('Data de admissão ausente ou inválida.');
      if (!input.demissao) erros.push('Informe a data de demissão (na planilha ou no campo "Data do desligamento").');
      if (!salario) erros.push('Salário ausente.');
    }
    return { input, qual, r, erros, linha: o._linha };
  }

  function recalcularLote() {
    const p = padroes();
    st.itens = st.linhas.map((o) => montarItem(o, p));
    renderTabela();
  }

  function renderTabela() {
    const ok = st.itens.filter((i) => i.r), falhas = st.itens.filter((i) => !i.r);
    const soma = (f) => ok.reduce((s, i) => s + f(i.r), 0);
    $('#lote-resumo').innerHTML = st.itens.length ? `
      <div class="totais">
        <div class="tot"><span class="rotulo">Trabalhadores calculados</span><span class="v">${ok.length}${falhas.length ? ` <small class="neg">· ${falhas.length} com erro</small>` : ''}</span></div>
        <div class="tot"><span class="rotulo">Proventos</span><span class="v">${J.fmt(soma((r) => r.totais.proventos))}</span></div>
        <div class="tot destaque"><span class="rotulo">Líquido total</span><span class="v">${J.fmt(soma((r) => r.totais.liquido))}</span></div>
        <div class="tot"><span class="rotulo">FGTS a depositar</span><span class="v">${J.fmt(soma((r) => r.fgts.totalDepositar))}</span></div>
      </div>` : '';
    $('#lote-tabela').innerHTML = st.itens.map((i, n) => `<tr class="${i.r ? '' : 'falha'}">
      <td class="num">${i.linha}</td><td><strong>${esc(i.qual.empregado.nome || '(sem nome)')}</strong><div class="memo">${esc([i.qual.empregado.matricula, i.qual.empregado.cargo, i.qual.empregado.lotacao].filter(Boolean).join(' · '))}</div></td>
      <td>${i.input.admissao ? D.br(i.input.admissao) : '—'}</td><td>${i.input.demissao ? D.br(i.input.demissao) : '—'}</td>
      <td class="num">${J.fmtN(i.input.salario)}</td>
      ${i.r ? `<td class="num">${J.fmtN(i.r.totais.proventos)}</td><td class="num">${J.fmtN(i.r.totais.descontos)}</td><td class="num"><strong>${J.fmtN(i.r.totais.liquido)}</strong></td><td class="num">${J.fmtN(i.r.fgts.totalDepositar)}</td>
        <td><button type="button" class="link" data-pdf-um="${n}">PDF</button></td>`
        : `<td colspan="5" class="erro-linha">${esc(i.erros.join(' '))}</td>`}</tr>`).join('');
    $('#lote-resultado').hidden = !st.itens.length;
    $('#btn-lote-pdf').disabled = $('#btn-lote-zip').disabled = $('#btn-lote-xlsx').disabled = !ok.length;
  }

  async function carregarArquivo(file) {
    const msg = $('#lote-msg');
    if (typeof XLSX === 'undefined') { msg.textContent = 'A biblioteca de planilhas não carregou. Verifique a conexão e recarregue a página.'; return; }
    msg.textContent = 'Lendo planilha...';
    try {
      const buf = await file.arrayBuffer();
      st.wb = XLSX.read(buf, { type: 'array', cellDates: true });
      st.nomeArquivo = file.name;
      const abas = st.wb.SheetNames.map((n) => ({ n, l: lerAba(n) }));
      const melhor = abas.slice().sort((a, b) => b.l.linhas.length - a.l.linhas.length)[0];
      $('#lote-aba').innerHTML = abas.map((a) => `<option value="${esc(a.n)}" ${a.n === melhor.n ? 'selected' : ''}>${esc(a.n)} (${a.l.linhas.length} linha(s))</option>`).join('');
      $('#campo-aba').hidden = abas.length < 2;
      usarAba(melhor.n, true);
    } catch (e) { msg.textContent = 'Não consegui ler o arquivo: ' + e.message; }
  }

  function usarAba(nome, aplicarParams) {
    const res = lerAba(nome);
    const msg = $('#lote-msg');
    st.aba = nome; st.linhas = res.linhas;
    if (res.erro) { msg.textContent = res.erro; st.itens = []; renderTabela(); return; }
    const f = $('#form-lote');
    if (aplicarParams) {
      if (res.params.demissao && !f.elements.loteDemissao.value) f.elements.loteDemissao.value = res.params.demissao;
      if (res.params.motivo) f.elements.loteMotivo.value = res.params.motivo;
      if (res.params.aviso) f.elements.loteAviso.value = res.params.aviso;
    }
    msg.textContent = `${st.nomeArquivo}: aba "${nome}", ${res.linhas.length} trabalhador(es). Colunas reconhecidas: ${res.colunas.join(', ')}.`;
    recalcularLote();
  }

  const dormir = () => new Promise((r) => setTimeout(r, 0));
  async function exportar(tipo, idx) {
    const msg = $('#lote-acao-msg');
    const ok = idx !== undefined ? [st.itens[idx]] : st.itens.filter((i) => i.r);
    try {
      let blob, nome;
      const base = J.nomeArquivo((st.nomeArquivo || 'rescisoes').replace(/\.\w+$/, ''));
      if (tipo === 'pdf') {
        msg.textContent = `Gerando PDF com ${ok.length} termo(s)...`; await dormir();
        blob = R.pdf.gerarPDF(ok);
        nome = ok.length === 1 ? `Rescisao-${J.nomeArquivo(ok[0].qual.empregado.nome)}.pdf` : `${base}-termos.pdf`;
      } else if (tipo === 'zip') {
        if (typeof JSZip === 'undefined') throw new Error('A biblioteca de ZIP não carregou.');
        const zip = new JSZip(); const usados = {};
        for (let n = 0; n < ok.length; n++) {
          if (n % 5 === 0) { msg.textContent = `Gerando PDFs: ${n + 1} de ${ok.length}...`; await dormir(); }
          const it = ok[n];
          let nm = `${it.qual.empregado.matricula ? it.qual.empregado.matricula + '-' : ''}${J.nomeArquivo(it.qual.empregado.nome || 'linha-' + it.linha)}`;
          if (usados[nm]) nm += '-' + (++usados[nm]); else usados[nm] = 1;
          zip.file(`${nm}.pdf`, R.pdf.gerarPDF([it]));
        }
        msg.textContent = 'Compactando...'; await dormir();
        blob = await zip.generateAsync({ type: 'blob' });
        nome = `${base}-pdfs.zip`;
      } else {
        const linhas = [['Linha', 'Matrícula', 'Nome', 'Função', 'Lotação', 'Admissão', 'Demissão', 'Motivo', 'Salário', 'Aviso (dias)', 'Proventos', 'Descontos', 'Líquido', 'FGTS 8% rescisão', 'Multa FGTS', 'FGTS a depositar', 'Custo total (líquido + descontos + FGTS)', 'Situação']];
        st.itens.forEach((i) => {
          const e = i.qual.empregado;
          if (i.r) linhas.push([i.linha, e.matricula, e.nome, e.cargo, e.lotacao, D.br(i.input.admissao), D.br(i.input.demissao), i.r.motivo.nome, i.input.salario, i.r.aviso.dias,
            i.r.totais.proventos, i.r.totais.descontos, i.r.totais.liquido, i.r.fgts.depositoRescisorio, i.r.fgts.multa, i.r.fgts.totalDepositar, J.r2(i.r.totais.proventos + i.r.fgts.totalDepositar), 'Calculado']);
          else linhas.push([i.linha, e.matricula, e.nome, e.cargo, e.lotacao, i.input.admissao ? D.br(i.input.admissao) : '', i.input.demissao ? D.br(i.input.demissao) : '', '', i.input.salario, '', '', '', '', '', '', '', '', 'Erro: ' + i.erros.join(' ')]);
        });
        const ws = XLSX.utils.aoa_to_sheet(linhas);
        ws['!cols'] = linhas[0].map((h, j) => ({ wch: j === 2 ? 36 : j === 17 ? 40 : 14 }));
        const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, ws, 'Consolidado');
        blob = new Blob([XLSX.write(wb, { type: 'array', bookType: 'xlsx' })]);
        nome = `${base}-consolidado.xlsx`;
      }
      msg.textContent = 'Confirme o download...';
      const res = await J.salvarArquivo(nome, blob);
      msg.textContent = res === 'declined' ? 'Download cancelado.' : `Arquivo pronto: ${nome}`;
    } catch (e) { msg.textContent = e.message || String(e); }
  }

  async function baixarModelo() {
    const msg = $('#lote-msg');
    if (typeof XLSX === 'undefined') { msg.textContent = 'A biblioteca de planilhas não carregou.'; return; }
    const cab = ['Matrícula', 'Nome', 'CPF', 'PIS', 'CTPS', 'Função', 'Lotação', 'Admissão', 'Demissão', 'Salário', 'Motivo', 'Aviso', 'Dependentes', 'Saldo FGTS', 'Filhos', 'Faltas mês', 'Fim experiência', 'Data pagamento', 'Férias vencidas', 'Outros descontos', 'Empregador', 'CNPJ'];
    const ex = [
      ['1001', 'Fulano de Tal (exemplo)', '000.000.000-00', '000.00000.00-0', '0000000 série 000-RN', 'Pedreiro', 'Obra Centro', '10/02/2024', '31/10/2026', 2800, 'Sem justa causa', 'Indenizado', 1, 6500, 0, 0, '', '', 1, 0, '', ''],
      ['1002', 'Beltrana de Souza (exemplo)', '', '', '', 'Ajudante', 'Obra Centro', '01/08/2026', '30/10/2026', 1800, 'Antecipada pelo empregador', '', 0, 0, 0, 0, '29/11/2026', '', '', 0, '', ''],
    ];
    const ajuda = [['Coluna', 'Como preencher'], ['Admissão / Demissão', 'Data (dd/mm/aaaa). Se a demissão ficar vazia, usa a data do desligamento informada na tela.'],
      ['Salário', 'Remuneração bruta. Também aceita as colunas "Salário Base" + "Periculosidade" ou "Remuneração".'],
      ['Motivo', 'Sem justa causa, Pedido de demissão, Justa causa, Fim da experiência, Antecipada pelo empregador, Antecipada pelo empregado, Indireta, Culpa recíproca, Acordo, Falecimento, Aposentadoria. Vazio usa o motivo da tela.'],
      ['Aviso', 'Indenizado, Trabalhado, Descontado ou Dispensado. Vazio usa o da tela.'],
      ['Saldo FGTS', 'Saldo para fins rescisórios (extrato da Caixa); base da multa.'], ['Férias vencidas', 'Quantos períodos vencidos (os mais recentes) ainda não foram pagos. Vazio = o último, se não estiver em dobro.'],
      ['Empregador / CNPJ', 'Opcional por linha; vazio usa o empregador informado na tela.']];
    const wb = XLSX.utils.book_new();
    const ws = XLSX.utils.aoa_to_sheet([cab, ...ex]); ws['!cols'] = cab.map((h) => ({ wch: Math.max(12, h.length + 4) }));
    XLSX.utils.book_append_sheet(wb, ws, 'Trabalhadores');
    const wa = XLSX.utils.aoa_to_sheet(ajuda); wa['!cols'] = [{ wch: 22 }, { wch: 110 }];
    XLSX.utils.book_append_sheet(wb, wa, 'Instruções');
    const res = await J.salvarArquivo('modelo-rescisao-em-lote.xlsx', new Blob([XLSX.write(wb, { type: 'array', bookType: 'xlsx' })]));
    msg.textContent = res === 'declined' ? 'Download cancelado.' : 'Modelo pronto: modelo-rescisao-em-lote.xlsx';
  }

  function init() {
    $('#lote-arquivo').addEventListener('change', (e) => { const f = e.target.files[0]; if (f) carregarArquivo(f); });
    const drop = $('#lote-drop');
    ['dragover', 'dragenter'].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add('sobre'); }));
    ['dragleave', 'drop'].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove('sobre')));
    drop.addEventListener('drop', (e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) carregarArquivo(f); });
    $('#lote-aba').addEventListener('change', (e) => usarAba(e.target.value, true));
    $('#form-lote').addEventListener('submit', (e) => e.preventDefault());
    $('#form-lote').addEventListener('change', (e) => { if (e.target.id !== 'lote-arquivo' && e.target.id !== 'lote-aba' && st.linhas.length) recalcularLote(); });
    $('#btn-modelo').addEventListener('click', baixarModelo);
    $('#btn-lote-pdf').addEventListener('click', () => exportar('pdf'));
    $('#btn-lote-zip').addEventListener('click', () => exportar('zip'));
    $('#btn-lote-xlsx').addEventListener('click', () => exportar('xlsx'));
    $('#lote-tabela').addEventListener('click', (e) => { const b = e.target.closest('[data-pdf-um]'); if (b) exportar('pdf', Number(b.dataset.pdfUm)); });
  }
  document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', init) : init();
  R.lote = { lerAba, montarItem, acharCabecalho, carregarArquivo, _st: st };
})();
