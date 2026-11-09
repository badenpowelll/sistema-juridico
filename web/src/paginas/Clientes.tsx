import { useEffect, useState } from 'react';
import { api, formatarCnpj } from '../api.ts';

type Cliente = {
  id: string;
  cnpj: string;
  razao_social: string;
  nome_fantasia: string | null;
  logo_url: string | null;
  associados: number;
  no_onedrive: boolean;
};

export function Clientes() {
  const [clientes, setClientes] = useState<Cliente[] | null>(null);
  const [erro, setErro] = useState('');

  useEffect(() => {
    api<Cliente[]>('/clientes').then(setClientes).catch((e) => setErro(e.message));
  }, []);

  return (
    <section>
      <h1 className="mb-6 text-2xl font-semibold text-marinho">Clientes</h1>
      {erro && <p className="text-red-700">{erro}</p>}
      {clientes === null && !erro && <p className="text-slate-500">Carregando…</p>}
      {clientes?.length === 0 && (
        <div className="rounded-lg border border-dashed border-slate-300 bg-white p-10 text-center text-slate-500">
          Nenhum cliente cadastrado. Conecte o OneDrive em Configurações para puxar as pastas dos clientes.
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {clientes?.map((c) => (
          <article key={c.id} className="rounded-lg bg-white p-5 shadow-sm">
            <div className="flex items-center gap-3">
              {c.logo_url ? (
                <img src={c.logo_url} alt="" className="h-12 w-12 rounded object-contain" />
              ) : (
                <div className="flex h-12 w-12 items-center justify-center rounded bg-slate-200 font-semibold text-marinho">
                  {(c.nome_fantasia ?? c.razao_social).slice(0, 2)}
                </div>
              )}
              <div className="min-w-0">
                <h2 className="truncate font-semibold">{c.nome_fantasia ?? c.razao_social}</h2>
                <p className="text-sm text-slate-500">{formatarCnpj(c.cnpj)}</p>
              </div>
            </div>
            <p className="mt-4 text-sm text-slate-600">
              {c.associados} associado(s) {c.no_onedrive ? '· pasta no OneDrive' : '· sem pasta no OneDrive'}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
