/* PDF do termo de rescisão (jsPDF + jspdf-autotable). Um ou vários cálculos no mesmo arquivo. */
(function (root) {
  const J = root.Juridico, D = J.datas;
  const t = (s) => String(s ?? '').replace(/[—–−]/g, '-').replace(/…/g, '...').replace(/[“”]/g, '"');
  const COR = [31, 92, 79], CINZA = [93, 107, 103];

  // Espaço reservado no rodapé para assinaturas e nota (mm). Tudo acima disso é conteúdo.
  const RESERVA = 34;

  function qualTabela(doc, y, qual, e) {
    const em = qual.empregado || {}, p = qual.empregador || {};
    doc.autoTable({
      startY: y, theme: 'grid', margin: { left: 14, right: 14, bottom: RESERVA },
      styles: { fontSize: 8 * e, cellPadding: 1.2 * e, lineColor: [200, 208, 204], lineWidth: 0.2 },
      headStyles: { fillColor: [226, 238, 233], textColor: COR, fontStyle: 'bold' },
      head: [['Empregador', 'Empregado']],
      body: [
        [`Nome/Razão social: ${t(p.nome) || '-'}`, `Nome: ${t(em.nome) || '-'}`],
        [`CNPJ/CPF: ${t(p.documento) || '-'}`, `CPF: ${t(em.cpf) || '-'}    PIS/NIT: ${t(em.pis) || '-'}`],
        [`Endereço: ${t(p.endereco) || '-'}`, `CTPS: ${t(em.ctps) || '-'}    Cargo: ${t(em.cargo) || '-'}`],
        [em.matricula || em.lotacao ? `Matrícula: ${t(em.matricula) || '-'}    Lotação: ${t(em.lotacao) || '-'}` : '', `Nascimento: ${em.nascimento ? D.br(em.nascimento) : '-'}    Endereço: ${t(em.endereco) || '-'}`],
      ],
      columnStyles: { 0: { cellWidth: 82 } },
    });
    return doc.lastAutoTable.finalY;
  }

  function verbasTabela(doc, y, titulo, verbas, total, extraFoot, e) {
    const body = verbas.map((v) => [{ content: `${t(v.descricao)}\n${t(v.memoria)} · ${t(v.fundamento)}` }, t(v.referencia), J.fmtN(v.valor)]);
    if (!body.length) body.push([{ content: titulo === 'Proventos' ? 'Nenhuma verba marcada.' : 'Sem descontos.', colSpan: 3, styles: { textColor: CINZA, halign: 'center' } }]);
    const foot = [[{ content: `Total de ${titulo.toLowerCase()}`, colSpan: 2 }, J.fmtN(total)]].concat(extraFoot || []);
    doc.autoTable({
      startY: y, theme: 'striped', margin: { left: 14, right: 14, bottom: RESERVA },
      styles: { fontSize: 7.5 * e, cellPadding: 1.1 * e, valign: 'top' },
      headStyles: { fillColor: COR, textColor: 255 }, footStyles: { fillColor: [240, 243, 241], textColor: 20, fontStyle: 'bold' },
      alternateRowStyles: { fillColor: [248, 250, 249] },
      head: [[titulo, 'Ref.', 'Valor (R$)']], body, foot,
      columnStyles: { 1: { cellWidth: 28, textColor: CINZA }, 2: { cellWidth: 28, halign: 'right' } },
      didParseCell: (d) => { if (d.section !== 'body' && d.column.index === 2) d.cell.styles.halign = 'right'; },
    });
    return doc.lastAutoTable.finalY;
  }

  /** Desenha um termo a partir da página atual, com escala e (1 = tamanho normal). Devolve o y final do conteúdo. */
  function desenharTermo(doc, item, e = 1) {
    const { input, qual, r } = item;
    const W = doc.internal.pageSize.getWidth(), H = doc.internal.pageSize.getHeight();
    const gap = 3 * e;
    let y = 14 + 2 * e;
    doc.setFont('helvetica', 'bold'); doc.setFontSize(14 * e); doc.setTextColor(20);
    doc.text('Demonstrativo de cálculo de rescisão do contrato de trabalho', 14, y);
    y += 5.5 * e; doc.setFont('helvetica', 'normal'); doc.setFontSize(9.5 * e); doc.setTextColor(...CINZA);
    doc.text(t(r.motivo.nome), 14, y);
    doc.setDrawColor(20); doc.setLineWidth(0.5); doc.line(14, y + 2.5 * e, W - 14, y + 2.5 * e);
    y = qualTabela(doc, y + 6 * e, qual, e) + gap;

    doc.autoTable({
      startY: y, theme: 'plain', margin: { left: 14, right: 14, bottom: RESERVA }, styles: { fontSize: 8 * e, cellPadding: 0.8 * e },
      body: [[
        `Admissão: ${D.br(input.admissao)}`, `Afastamento: ${D.br(input.demissao)}`, `Último salário: ${J.fmt(input.salario)}`,
      ], [
        `Tempo de serviço: ${r.tempoServico} ano(s)`, `Aviso prévio: ${r.aviso.dias} dias`, r.aviso.projecao ? `Projeção do aviso: ${D.br(r.aviso.fimProjetado)}` : `Dependentes IRRF: ${input.dependentes || 0}`,
      ]],
    });
    y = doc.lastAutoTable.finalY + gap;

    const prov = r.verbas.filter((v) => v.grupo === 'provento'), desc = r.verbas.filter((v) => v.grupo === 'desconto');
    y = verbasTabela(doc, y, 'Proventos', prov, r.totais.proventos, null, e) + gap;
    y = verbasTabela(doc, y, 'Descontos', desc, r.totais.descontos,
      [[{ content: 'VALOR LÍQUIDO A RECEBER', colSpan: 2, styles: { textColor: COR, fontSize: 10 * e } }, { content: J.fmtN(r.totais.liquido), styles: { textColor: COR, fontSize: 10 * e, halign: 'right' } }]], e) + gap;

    const f = r.fgts;
    const fgtsBody = [['Saldo para fins rescisórios informado', J.fmt(f.saldoInformado)]];
    if (f.estimativaPeriodo) fgtsBody.push(['FGTS do período não depositado (estimativa)', J.fmt(f.estimativaPeriodo)]);
    fgtsBody.push(['8% sobre as verbas rescisórias', J.fmt(f.depositoRescisorio)], [`Multa ${f.multaPct ? `de ${f.multaPct * 100}%` : '(não devida)'}`, J.fmt(f.multa)],
      [{ content: 'Total a depositar pelo empregador', styles: { fontStyle: 'bold' } }, { content: J.fmt(f.totalDepositar), styles: { fontStyle: 'bold' } }], ['Saque', t(f.saque)]);
    doc.autoTable({
      startY: y, theme: 'grid', margin: { left: 14, right: 14, bottom: RESERVA }, styles: { fontSize: 7.5 * e, cellPadding: 1 * e, lineColor: [200, 208, 204], lineWidth: 0.2 },
      headStyles: { fillColor: [226, 238, 233], textColor: COR }, head: [['FGTS - depósito na conta vinculada', '']], body: fgtsBody,
      columnStyles: { 1: { halign: 'right', cellWidth: 70 } },
    });
    y = doc.lastAutoTable.finalY + gap;

    if (r.avisos.length) {
      doc.autoTable({
        startY: y, theme: 'plain', margin: { left: 14, right: 14, bottom: RESERVA }, styles: { fontSize: 7 * e, cellPadding: 0.6 * e, textColor: 60 },
        head: [['Observações do cálculo']], headStyles: { fontSize: 8 * e, textColor: CINZA },
        body: r.avisos.map((a) => ['• ' + t(a)]),
      });
      y = doc.lastAutoTable.finalY + gap;
    }

    // Assinaturas: sempre na mesma página do fim do conteúdo, dentro da faixa reservada.
    const yAss = Math.max(y + 12, H - 24);
    doc.setDrawColor(120); doc.setLineWidth(0.3);
    doc.line(20, yAss, 92, yAss); doc.line(W - 92, yAss, W - 20, yAss);
    doc.setFontSize(8); doc.setTextColor(60);
    doc.text(t((qual.empregador && qual.empregador.nome) || 'Empregador'), 56, yAss + 4, { align: 'center', maxWidth: 76 });
    doc.text(t((qual.empregado && qual.empregado.nome) || 'Empregado'), W - 56, yAss + 4, { align: 'center', maxWidth: 76 });
    doc.setFontSize(6.5); doc.setTextColor(...CINZA);
    doc.text(t(`Cálculo estimativo com tabelas de ${J.tabelas.vigencia} (INSS: ${J.tabelas.inss.fonte}; IRRF: ${J.tabelas.irrf.fonte}). Não considera médias de variáveis, convenção coletiva, correção monetária nem juros. Gerado em ${new Date().toLocaleDateString('pt-BR')}.`), 14, H - 11, { maxWidth: W - 50 });
    return y;
  }

  /** Maior escala em que o termo inteiro (com assinaturas) cabe em uma página A4. */
  const ESCALAS = [1, 0.93, 0.86, 0.8, 0.74, 0.69, 0.64, 0.6, 0.56, 0.52];
  function escalaQueCabe(item) {
    for (const e of ESCALAS) {
      const teste = new root.jspdf.jsPDF({ unit: 'mm', format: 'a4' });
      desenharTermo(teste, item, e);
      if (teste.getNumberOfPages() === 1) return e;
    }
    return ESCALAS[ESCALAS.length - 1]; // conteúdo enorme: usa a menor letra; tabelas continuam na página seguinte
  }

  function numerarPaginas(doc) {
    const n = doc.getNumberOfPages(), W = doc.internal.pageSize.getWidth(), H = doc.internal.pageSize.getHeight();
    for (let i = 1; i <= n; i++) { doc.setPage(i); doc.setFontSize(7); doc.setTextColor(...CINZA); doc.text(`Página ${i} de ${n}`, W - 14, H - 7, { align: 'right' }); }
  }

  /** Gera um PDF com um termo por pessoa (cada um começa em página nova). */
  function gerarPDF(itens) {
    if (!root.jspdf || !root.jspdf.jsPDF) throw new Error('A biblioteca de PDF não carregou. Verifique a conexão e recarregue a página.');
    const doc = new root.jspdf.jsPDF({ unit: 'mm', format: 'a4' });
    doc.setProperties({ title: itens.length === 1 ? `Rescisão - ${itens[0].qual.empregado?.nome || ''}` : `Rescisões em lote (${itens.length})`, creator: 'Sistema Jurídico' });
    itens.forEach((it, i) => { if (i) doc.addPage(); desenharTermo(doc, it, escalaQueCabe(it)); });
    numerarPaginas(doc);
    return doc.output('blob');
  }

  J.modulos.rescisao.pdf = { gerarPDF, desenharTermo, escalaQueCabe };
})(typeof window !== 'undefined' ? window : globalThis);
