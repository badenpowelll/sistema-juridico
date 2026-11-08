/* Tela do módulo Rescisão. Usa Juridico.modulos.rescisao (motor.js). */
(function () {
  const J = window.Juridico, R = J.modulos.rescisao, D = J.datas;
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  const state = { verbas: {}, selecao: null, ultimoMotivo: null, chavePeriodos: null };

  function lerForm() {
    const f = $('#form-dados');
    const v = (id) => f.elements[id] ? f.elements[id].value : '';
    const num = (id) => { const s = v(id).replace(/\./g, '').replace(',', '.'); const n = parseFloat(s); return isNaN(n) ? 0 : n; };
    return {
      admissao: v('admissao'), demissao: v('demissao'), salario: num('salario'), motivo: v('motivo'),
      avisoTipo: v('avisoTipo'), dependentes: num('dependentes'), filhosSalarioFamilia: num('filhos'), faltasMes: num('faltasMes'),
      fimExperiencia: v('fimExperiencia'), mesDataBase: Number(v('mesDataBase')) || 0, dataPagamento: v('dataPagamento'),
      saldoFgts: num('saldoFgts'), estimarFgtsPeriodo: f.elements.estimarFgts.checked, inssSobreAviso: f.elements.inssSobreAviso.checked,
      outrosDescontos: num('outrosDescontos'),
    };
  }

  function lerQual() {
    const q = $('#form-qual').elements, v = (id) => q[id].value.trim();
    return {
      empregado: { nome: v('qNome'), cpf: v('qCpf'), pis: v('qPis'), ctps: v('qCtps'), matricula: v('qMatricula'), cargo: v('qCargo'), nascimento: q.qNascimento.value, endereco: v('qEndereco') },
      empregador: { nome: v('qEmpregador'), documento: v('qCnpj'), endereco: v('qEndEmpregador') },
    };
  }

  function ajustarCamposMotivo(motivo) {
    const m = R.MOTIVOS[motivo];
    $('#campo-experiencia').hidden = !m.experiencia;
    const sel = $('#avisoTipo');
    const opcoes = m.aviso === 'empregado'
      ? [['trabalhado', 'Cumprido (trabalhado)'], ['descontado', 'Não cumprido (descontar)'], ['dispensado', 'Dispensado pelo empregador']]
      : m.aviso === 'empregador' && !m.avisoSempreIndenizado
        ? [['indenizado', 'Indenizado'], ['trabalhado', 'Trabalhado']]
        : m.aviso === 'empregador' ? [['indenizado', 'Indenizado']] : [['nenhum', 'Não se aplica']];
    const atual = sel.value;
    sel.innerHTML = opcoes.map(([k, t]) => `<option value="${k}">${t}</option>`).join('');
    sel.value = opcoes.some(([k]) => k === atual) ? atual : opcoes[0][0];
    sel.disabled = opcoes.length === 1;
    $('#dica-motivo').textContent = m.saque + (m.multaFgts ? ` · multa de ${m.multaFgts * 100}% do FGTS` : ' · sem multa do FGTS');
  }

  function renderVerbas(motivo) {
    if (state.ultimoMotivo !== motivo) { state.verbas = {}; state.ultimoMotivo = motivo; }
    const lista = R.verbasDisponiveis(motivo);
    $('#lista-verbas').innerHTML = lista.map((v) => {
      const marcado = v.ok && (v.id in state.verbas ? state.verbas[v.id] : v.padrao);
      return `<label class="verba ${v.ok ? '' : 'na'}"><input type="checkbox" id="verba-${v.id}" data-verba="${v.id}" ${marcado ? 'checked' : ''} ${v.ok ? '' : 'disabled'}>
        <span>${esc(v.nome)}${v.ok ? '' : ' <em>não se aplica</em>'}</span></label>`;
    }).join('');
  }

  function renderPeriodos(input) {
    const per = R.listarPeriodos(input);
    const padrao = R.selecaoPadrao(per);
    const antiga = state.selecao || { decimos: {}, ferias: {} };
    const sel = { decimos: {}, ferias: {} };
    per.decimos.forEach((p) => { sel.decimos[p.key] = p.key in antiga.decimos ? antiga.decimos[p.key] : padrao.decimos[p.key]; });
    per.ferias.forEach((p) => {
      const a = antiga.ferias[p.key];
      sel.ferias[p.key] = a ? { ...a, dobro: a.dobroManual ? a.dobro : p.dobroAuto } : padrao.ferias[p.key];
    });
    state.selecao = sel;

    $('#tab-13').innerHTML = per.decimos.map((p) => `<tr class="${sel.decimos[p.key] ? 'on' : ''}">
      <td><input type="checkbox" id="d-${p.key}" data-dec="${p.key}" ${sel.decimos[p.key] ? 'checked' : ''} aria-label="Calcular 13º de ${p.ano}"></td>
      <td>${p.ano}</td><td>${D.br(p.de)} a ${D.br(p.ate)}</td>
      <td class="num">${p.avosTrab}/12${p.avosProj ? ` <span class="proj">+${p.avosProj} aviso</span>` : ''}</td></tr>`).join('');

    $('#tab-ferias').innerHTML = per.ferias.map((p) => {
      const s = sel.ferias[p.key];
      const sit = p.vencida ? (p.dobroAuto ? '<span class="pill alerta">vencida · concessivo expirado</span>' : '<span class="pill">vencida</span>') : '<span class="pill neutra">proporcional</span>';
      return `<tr class="${s.incluir ? 'on' : ''}">
        <td><input type="checkbox" id="f-${p.key}" data-fer="${p.key}" data-campo="incluir" ${s.incluir ? 'checked' : ''} aria-label="Calcular férias de ${D.br(p.de)}"></td>
        <td>${D.br(p.de)} a ${D.br(p.ate)}</td><td>${sit}</td>
        <td class="num">${p.vencida ? '12/12' : `${p.avosTrab}/12${p.avosProj ? ` <span class="proj">+${p.avosProj} aviso</span>` : ''}`}</td>
        <td><input type="number" min="0" max="365" class="mini" id="fa-${p.key}" data-fer="${p.key}" data-campo="faltas" value="${s.faltas || 0}" aria-label="Faltas injustificadas"></td>
        <td>${p.vencida ? `<input type="checkbox" id="fd-${p.key}" data-fer="${p.key}" data-campo="dobro" ${s.dobro ? 'checked' : ''} aria-label="Pagar em dobro">` : '—'}</td></tr>`;
    }).join('');
    $('#resumo-periodos').textContent = `${per.decimos.length} períodos de 13º e ${per.ferias.length} períodos aquisitivos de férias no contrato.`;
  }

  function linha(v) {
    return `<tr><td><div class="desc">${esc(v.descricao)}</div><div class="memo">${esc(v.memoria)}<span class="fund"> · ${esc(v.fundamento)}</span></div></td>
      <td class="ref">${esc(v.referencia)}</td><td class="num valor">${J.fmtN(v.valor)}</td></tr>`;
  }

  function renderResultado(input, r) {
    const out = $('#resultado');
    if (r.erros.length) { out.innerHTML = `<div class="erro">${r.erros.map(esc).join('<br>')}</div>`; return; }
    const prov = r.verbas.filter((v) => v.grupo === 'provento'), desc = r.verbas.filter((v) => v.grupo === 'desconto');
    const f = r.fgts;
    const q = lerQual(), e = q.empregado, p = q.empregador;
    const det = (pares) => pares.filter(([, x]) => x).map(([k, x]) => `${k} ${esc(x)}`).join(' · ');
    out.innerHTML = `
      <div class="partes-res">
        <div><span class="rotulo">Empregado</span><strong>${esc(e.nome || 'Não informado')}</strong><span class="det">${det([['CPF', e.cpf], ['PIS', e.pis], ['CTPS', e.ctps], ['Matr.', e.matricula], ['', e.cargo]])}</span></div>
        <div><span class="rotulo">Empregador</span><strong>${esc(p.nome || 'Não informado')}</strong><span class="det">${det([['CNPJ/CPF', p.documento], ['', p.endereco]])}</span></div>
      </div>
      <div class="cabecalho-trct">
        <div><span class="rotulo">Motivo</span><strong>${esc(r.motivo.nome)}</strong></div>
        <div><span class="rotulo">Contrato</span><strong>${D.br(input.admissao)} a ${D.br(input.demissao)}</strong></div>
        <div><span class="rotulo">Tempo de serviço</span><strong>${r.tempoServico} ano(s) completo(s)</strong></div>
        <div><span class="rotulo">Aviso prévio</span><strong>${r.aviso.dias} dias${r.aviso.projecao ? ` · projeção até ${D.br(r.aviso.fimProjetado)}` : ''}</strong></div>
        <div><span class="rotulo">Último salário</span><strong>${J.fmt(input.salario)}</strong></div>
      </div>
      <div class="totais">
        <div class="tot"><span class="rotulo">Proventos</span><span class="v">${J.fmt(r.totais.proventos)}</span></div>
        <div class="tot"><span class="rotulo">Descontos</span><span class="v neg">− ${J.fmt(r.totais.descontos)}</span></div>
        <div class="tot destaque"><span class="rotulo">Líquido a receber</span><span class="v">${J.fmt(r.totais.liquido)}</span></div>
        <div class="tot"><span class="rotulo">FGTS a depositar</span><span class="v">${J.fmt(f.totalDepositar)}</span></div>
      </div>
      <div class="tabela-wrap"><table class="trct">
        <thead><tr><th>Proventos</th><th>Ref.</th><th class="num">Valor (R$)</th></tr></thead>
        <tbody>${prov.map(linha).join('') || '<tr><td colspan="3" class="vazio">Nenhuma verba marcada.</td></tr>'}</tbody>
        <tfoot><tr><td colspan="2">Total de proventos</td><td class="num">${J.fmtN(r.totais.proventos)}</td></tr></tfoot>
      </table></div>
      <div class="tabela-wrap"><table class="trct">
        <thead><tr><th>Descontos</th><th>Ref.</th><th class="num">Valor (R$)</th></tr></thead>
        <tbody>${desc.map(linha).join('') || '<tr><td colspan="3" class="vazio">Sem descontos.</td></tr>'}</tbody>
        <tfoot><tr><td colspan="2">Total de descontos</td><td class="num">${J.fmtN(r.totais.descontos)}</td></tr>
        <tr class="liquido"><td colspan="2">Valor líquido</td><td class="num">${J.fmtN(r.totais.liquido)}</td></tr></tfoot>
      </table></div>
      <div class="fgts">
        <h3>FGTS — depósito na conta vinculada</h3>
        <dl>
          <dt>Saldo para fins rescisórios informado</dt><dd>${J.fmt(f.saldoInformado)}</dd>
          ${f.estimativaPeriodo ? `<dt>FGTS do período não depositado (estimativa)</dt><dd>${J.fmt(f.estimativaPeriodo)}</dd>` : ''}
          <dt>8% sobre as verbas rescisórias</dt><dd>${J.fmt(f.depositoRescisorio)}</dd>
          <dt>Multa ${f.multaPct ? `de ${f.multaPct * 100}%` : '(não devida neste motivo)'}</dt><dd>${J.fmt(f.multa)}</dd>
          <dt class="forte">Total a depositar pelo empregador</dt><dd class="forte">${J.fmt(f.totalDepositar)}</dd>
          <dt>Saque</dt><dd class="txt">${esc(f.saque)}</dd>
        </dl>
        <ul class="memo-lista">${f.memoria.map((t) => `<li>${esc(t)}</li>`).join('')}</ul>
      </div>
      ${r.avisos.length ? `<div class="observacoes"><h3>Observações do cálculo</h3><ul>${r.avisos.map((a) => `<li>${esc(a)}</li>`).join('')}</ul></div>` : ''}
      <p class="rodape-calc">Cálculo estimativo com tabelas de ${J.tabelas.vigencia}: INSS (${esc(J.tabelas.inss.fonte)}), IRRF (${esc(J.tabelas.irrf.fonte)}). Não considera médias de variáveis, convenção coletiva, correção monetária nem juros. Gerado em ${new Date().toLocaleDateString('pt-BR')}.</p>`;
    window.__ultimo = { input, r, qual: q };
  }

  function recalcular({ periodos = true } = {}) {
    const input = lerForm();
    ajustarCamposMotivo(input.motivo);
    input.avisoTipo = $('#avisoTipo').value;
    renderVerbas(input.motivo);
    const valido = input.admissao && input.demissao && D.parse(input.demissao) >= D.parse(input.admissao);
    if (valido && periodos) renderPeriodos(input);
    input.verbas = Object.fromEntries($$('[data-verba]').map((c) => [c.dataset.verba, c.checked]));
    input.selecao = state.selecao;
    const r = R.calcular(input);
    renderResultado(input, r);
  }

  function resumoTexto() {
    const u = window.__ultimo; if (!u || u.r.erros.length) return '';
    const { input, r } = u;
    const l = [`CÁLCULO DE RESCISÃO — ${r.motivo.nome}`, `Empregado: ${u.qual.empregado.nome || '-'} · Empregador: ${u.qual.empregador.nome || '-'}`, `Contrato: ${D.br(input.admissao)} a ${D.br(input.demissao)} · Salário: ${J.fmt(input.salario)}`, '', 'PROVENTOS'];
    r.verbas.filter((v) => v.grupo === 'provento').forEach((v) => l.push(`${v.descricao} (${v.referencia}): ${J.fmt(v.valor)}`));
    l.push('', 'DESCONTOS');
    r.verbas.filter((v) => v.grupo === 'desconto').forEach((v) => l.push(`${v.descricao}: ${J.fmt(v.valor)}`));
    l.push('', `Total proventos: ${J.fmt(r.totais.proventos)}`, `Total descontos: ${J.fmt(r.totais.descontos)}`, `LÍQUIDO: ${J.fmt(r.totais.liquido)}`, '',
      `FGTS a depositar: ${J.fmt(r.fgts.totalDepositar)} (multa ${J.fmt(r.fgts.multa)})`, r.fgts.saque);
    return l.join('\n');
  }

  function init() {
    const f = $('#form-dados');
    f.addEventListener('submit', (e) => { e.preventDefault(); recalcular(); $('#sec-resultado').scrollIntoView({ behavior: 'smooth', block: 'start' }); });
    f.addEventListener('input', (e) => { if (e.target.id === 'motivo') state.verbas = {}; recalcular(); });
    f.addEventListener('change', () => recalcular());
    $('#lista-verbas').addEventListener('change', (e) => { const c = e.target; if (c.dataset.verba) { state.verbas[c.dataset.verba] = c.checked; recalcular({ periodos: false }); } });
    $('#sec-periodos').addEventListener('change', (e) => {
      const c = e.target;
      if (c.dataset.dec) state.selecao.decimos[c.dataset.dec] = c.checked;
      if (c.dataset.fer) {
        const s = state.selecao.ferias[c.dataset.fer];
        if (c.dataset.campo === 'faltas') s.faltas = Number(c.value) || 0;
        else { s[c.dataset.campo] = c.checked; if (c.dataset.campo === 'dobro') s.dobroManual = true; }
      }
      recalcular();
    });
    $('#sec-periodos').addEventListener('click', (e) => {
      const b = e.target.closest('[data-marcar]'); if (!b) return;
      const [tipo, val] = b.dataset.marcar.split(':'); const on = val === 'todos';
      if (tipo === 'dec') Object.keys(state.selecao.decimos).forEach((k) => { state.selecao.decimos[k] = on; });
      else Object.values(state.selecao.ferias).forEach((s) => { s.incluir = on; });
      recalcular();
    });
    $('#btn-copiar').addEventListener('click', async () => {
      const t = resumoTexto(), msg = $('#msg-copiar');
      try { await navigator.clipboard.writeText(t); msg.textContent = 'Resumo copiado.'; }
      catch { const ta = $('#texto-resumo'); ta.hidden = false; ta.value = t; ta.select(); msg.textContent = 'Selecione e copie o texto abaixo.'; }
    });
    $('#form-qual').addEventListener('input', () => recalcular({ periodos: false }));
    $('#form-qual').addEventListener('submit', (e) => e.preventDefault());
    $('#btn-pdf').addEventListener('click', async () => {
      const u = window.__ultimo, msg = $('#msg-copiar');
      if (!u || u.r.erros.length) { msg.textContent = 'Corrija os dados do contrato antes de exportar.'; return; }
      try {
        msg.textContent = 'Gerando PDF...';
        const blob = R.pdf.gerarPDF([u]);
        const nome = `Rescisao-${J.nomeArquivo(u.qual.empregado.nome || 'calculo')}.pdf`;
        const res = await J.salvarArquivo(nome, blob);
        msg.textContent = res === 'declined' ? 'Download cancelado.' : `PDF pronto: ${nome}`;
      } catch (err) { msg.textContent = err.message || String(err); }
    });
    document.querySelectorAll('.aba').forEach((b) => b.addEventListener('click', () => {
      document.querySelectorAll('.aba').forEach((x) => { const on = x === b; x.classList.toggle('ativa', on); x.setAttribute('aria-selected', on); });
      $('#view-individual').hidden = b.dataset.view !== 'individual';
      $('#view-lote').hidden = b.dataset.view !== 'lote';
    }));
    const emFrame = (() => { try { return window.self !== window.top; } catch { return true; } })();
    const bp = $('#btn-imprimir');
    if (emFrame) bp.hidden = true; else bp.addEventListener('click', () => window.print());
    $('#btn-limpar-exemplo').addEventListener('click', () => {
      ['admissao', 'demissao', 'salario', 'saldoFgts', 'fimExperiencia', 'dataPagamento', 'outrosDescontos'].forEach((id) => { f.elements[id].value = ''; });
      Array.from($('#form-qual').elements).forEach((el) => { el.value = ''; });
      ['dependentes', 'filhos', 'faltasMes'].forEach((id) => { f.elements[id].value = '0'; });
      $('#selo-exemplo').hidden = true; state.selecao = null; recalcular(); f.elements.admissao.focus();
    });
    recalcular();
  }
  document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', init) : init();
})();
