/* Núcleo: salvar arquivos gerados e ler planilhas. Reutilizável por todos os módulos.
 * Dentro do claude.ai usa a capacidade "downloads"; fora dele (arquivo aberto no navegador) baixa direto. */
(function (root) {
  const J = root.Juridico = root.Juridico || {};
  let downloadsPromise = null;
  function obterDownloads() {
    if (!downloadsPromise) {
      downloadsPromise = (root.claude && typeof root.claude.use === 'function')
        ? root.claude.use('downloads').catch(() => null)
        : Promise.resolve(null);
    }
    return downloadsPromise;
  }
  if (typeof window !== 'undefined') setTimeout(obterDownloads, 0);

  /** Salva um Blob. Resolve 'saved' | 'declined'. Rejeita com mensagem legível em outros casos. */
  J.salvarArquivo = async function (filename, blob) {
    const d = await obterDownloads();
    if (d) {
      try { await d.save({ filename, data: blob }); return 'saved'; }
      catch (e) {
        if (e && e.code === 'declined') return 'declined';
        if (e && e.code === 'rate_limited') throw new Error('Já existe um download aguardando confirmação. Confirme ou feche e tente de novo.');
        if (e && !['unavailable', 'not_granted', 'capability_disabled', 'capability_removed'].includes(e.code)) throw new Error(e.message || 'Não foi possível salvar o arquivo.');
      }
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
    return 'saved';
  };

  /** Normaliza cabeçalho de planilha: sem acento, minúsculo, só letras e números. */
  J.normalizarChave = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]/g, '');

  /** Converte célula de data (Date, serial do Excel, dd/mm/aaaa ou aaaa-mm-dd) em ISO. */
  J.lerData = function (v) {
    if (v === null || v === undefined || v === '') return '';
    if (v instanceof Date && !isNaN(v)) {
      const d = new Date(v.getTime() + 12 * 3600000); // evita deslocamento de fuso
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    }
    if (typeof v === 'number') return new Date(Date.UTC(1899, 11, 30) + Math.round(v) * 86400000).toISOString().slice(0, 10);
    const s = String(v).trim();
    let m = s.match(/^(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{2,4})$/);
    if (m) { const y = m[3].length === 2 ? '20' + m[3] : m[3]; return `${y}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`; }
    m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    return m ? `${m[1]}-${m[2]}-${m[3]}` : '';
  };

  /** Converte valor monetário ("R$ 3.200,50", 3200.5) em número. */
  J.lerValor = function (v) {
    if (typeof v === 'number') return v;
    let s = String(v || '').replace(/[R$\s]/g, '');
    if (!s) return 0;
    if (s.includes(',')) s = s.replace(/\./g, '').replace(',', '.');
    const n = parseFloat(s); return isNaN(n) ? 0 : n;
  };

  J.nomeArquivo = (s) => String(s || 'arquivo').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^\w.-]+/g, '-').replace(/-+/g, '-').replace(/^-|-$/g, '').slice(0, 80) || 'arquivo';
})(typeof window !== 'undefined' ? window : globalThis);
