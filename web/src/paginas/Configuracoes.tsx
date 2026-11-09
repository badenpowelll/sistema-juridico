import { useEffect, useState } from 'react';
import { api, type Advogado } from '../api.ts';

type Status = {
  configurado: boolean;
  pastaRaiz: string;
  conexao: { conta: string; pasta_encontrada: boolean; conectado_em: string } | null;
  ultimaSincronizacao: {
    iniciada_em: string; concluida_em: string | null; itens_lidos: number; associados_criados: number;
    documentos_criados: number; removidos: number; erro: string | null;
  } | null;
  pastasSemCliente: number;
};

export function Configuracoes({ advogado }: { advogado: Advogado }) {
  const [status, setStatus] = useState<Status | null>(null);
  const [msg, setMsg] = useState(new URLSearchParams(location.search).get('onedrive') ?? '');
  const [ocupado, setOcupado] = useState(false);

  const carregar = () => api<Status>('/onedrive/status').then(setStatus).catch((e) => setMsg(e.message));
  useEffect(() => {
    carregar();
  }, []);

  async function sincronizar() {
    setOcupado(true);
    setMsg('');
    try {
      const r = await api<{ itens: number; associados: number; documentos: number }>('/onedrive/sincronizar', { method: 'POST' });
      setMsg(`Sincronizado: ${r.itens} itens lidos, ${r.associados} associados novos, ${r.documentos} documentos novos.`);
      carregar();
    } catch (e) {
      setMsg((e as Error).message);
    } finally {
      setOcupado(false);
    }
  }

  const s = status;
  return (
    <section className="max-w-2xl">
      <h1 className="mb-6 text-2xl font-semibold text-marinho">Configurações</h1>
      <div className="space-y-3 rounded-lg bg-white p-5 shadow-sm">
        <h2 className="font-semibold">OneDrive</h2>
        {!s && <p className="text-slate-500">Carregando…</p>}
        {s && !s.configurado && (
          <p className="text-sm text-amber-800">Faltam as variáveis MS_CLIENT_ID, MS_CLIENT_SECRET e CHAVE_CRIPTOGRAFIA no Railway.</p>
        )}
        {s?.conexao ? (
          <p className="text-sm">
            Conectado à conta <b>{s.conexao.conta}</b>. Pasta raiz “{s.pastaRaiz}”{' '}
            {s.conexao.pasta_encontrada ? 'encontrada.' : 'não encontrada: crie a pasta no OneDrive e conecte de novo.'}
          </p>
        ) : (
          s && <p className="text-sm">Nenhuma conta conectada. O sistema lê as pastas a partir de “{s.pastaRaiz}”.</p>
        )}
        {s?.ultimaSincronizacao && (
          <p className="text-sm text-slate-600">
            Última leitura: {new Date(s.ultimaSincronizacao.iniciada_em).toLocaleString('pt-BR')}
            {s.ultimaSincronizacao.erro ? ` — erro: ${s.ultimaSincronizacao.erro}` : ` — ${s.ultimaSincronizacao.itens_lidos} itens`}
          </p>
        )}
        {!!s?.pastasSemCliente && (
          <p className="text-sm text-amber-800">{s.pastasSemCliente} pasta(s) de cliente ainda sem cadastro (informe o CNPJ para ligar).</p>
        )}
        <div className="flex flex-wrap gap-2 pt-2">
          {advogado.papel === 'admin' && s?.configurado && (
            <a href="/api/onedrive/conectar" className="rounded border border-marinho px-4 py-2 text-sm text-marinho">
              {s.conexao ? 'Reconectar conta' : 'Conectar OneDrive'}
            </a>
          )}
          {s?.conexao && (
            <button onClick={sincronizar} disabled={ocupado} className="rounded bg-marinho px-4 py-2 text-sm text-white disabled:opacity-60">
              {ocupado ? 'Lendo o OneDrive…' : 'Sincronizar agora'}
            </button>
          )}
        </div>
        {msg && <p className="text-sm text-slate-700">{msg === 'ok' ? 'OneDrive conectado.' : msg}</p>}
      </div>
    </section>
  );
}
