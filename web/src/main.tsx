import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api, type Advogado } from './api.ts';
import { Clientes } from './paginas/Clientes.tsx';
import { Configuracoes } from './paginas/Configuracoes.tsx';
import { Login } from './paginas/Login.tsx';
import './estilos.css';

const MENU = [
  { caminho: '/', nome: 'Clientes', ativo: true },
  { caminho: '/associados', nome: 'Associados' },
  { caminho: '/empresas', nome: 'Empresas' },
  { caminho: '/calculos', nome: 'Cálculos' },
  { caminho: '/peticoes', nome: 'Petições' },
  { caminho: '/lotes', nome: 'Lotes' },
  { caminho: '/diligencias', nome: 'Diligências' },
  { caminho: '/configuracoes', nome: 'Configurações', ativo: true },
];

function App() {
  const [advogado, setAdvogado] = useState<Advogado | null | undefined>(undefined);
  const [rota, setRota] = useState(location.pathname);

  useEffect(() => {
    api<{ advogado: Advogado }>('/auth/eu').then((r) => setAdvogado(r.advogado)).catch(() => setAdvogado(null));
    const voltar = () => setRota(location.pathname);
    addEventListener('popstate', voltar);
    return () => removeEventListener('popstate', voltar);
  }, []);

  const ir = (caminho: string) => {
    history.pushState(null, '', caminho);
    setRota(caminho);
  };

  if (advogado === undefined) return <p className="p-8 text-slate-500">Carregando…</p>;
  if (!advogado) return <Login aoEntrar={setAdvogado} />;

  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="bg-marinho text-slate-200 md:w-60 md:shrink-0">
        <div className="px-5 py-4 text-lg font-semibold text-white">Sistema Jurídico</div>
        <nav className="flex flex-wrap gap-1 px-2 pb-3 md:flex-col">
          {MENU.map((m) =>
            m.ativo ? (
              <button
                key={m.caminho}
                onClick={() => ir(m.caminho)}
                className={`rounded px-3 py-2 text-left text-sm ${rota === m.caminho ? 'bg-marinho-claro text-white' : 'hover:bg-marinho-claro'}`}
              >
                {m.nome}
              </button>
            ) : (
              <span key={m.caminho} className="flex items-center justify-between rounded px-3 py-2 text-sm text-slate-400">
                {m.nome} <span className="ml-2 rounded bg-slate-700 px-1.5 text-[10px] uppercase">em breve</span>
              </span>
            ),
          )}
        </nav>
        <div className="border-t border-marinho-claro px-5 py-3 text-xs text-slate-400">
          {advogado.nome}
          <button
            className="ml-2 underline"
            onClick={async () => {
              await api('/auth/sair', { method: 'POST' });
              setAdvogado(null);
            }}
          >
            Sair
          </button>
        </div>
      </aside>
      <main className="flex-1 p-4 md:p-8">
        {rota === '/configuracoes' ? <Configuracoes advogado={advogado} /> : <Clientes />}
      </main>
    </div>
  );
}

createRoot(document.getElementById('app')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
