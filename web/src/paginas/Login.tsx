import { useState, type FormEvent } from 'react';
import { api, type Advogado } from '../api.ts';

export function Login({ aoEntrar }: { aoEntrar: (a: Advogado) => void }) {
  const [erro, setErro] = useState('');
  const [enviando, setEnviando] = useState(false);

  async function entrar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setEnviando(true);
    setErro('');
    try {
      const r = await api<{ advogado: Advogado }>('/auth/entrar', { method: 'POST', json: { email: f.get('email'), senha: f.get('senha') } });
      aoEntrar(r.advogado);
    } catch (err) {
      setErro((err as Error).message);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-marinho p-4">
      <form onSubmit={entrar} className="w-full max-w-sm space-y-4 rounded-lg bg-white p-6 shadow-lg">
        <h1 className="text-xl font-semibold text-marinho">Sistema Jurídico</h1>
        <p className="text-sm text-slate-500">Acesso restrito aos advogados do escritório.</p>
        <label className="block text-sm">
          E-mail
          <input name="email" type="email" required autoComplete="username" className="mt-1 w-full rounded border border-slate-300 px-3 py-2" />
        </label>
        <label className="block text-sm">
          Senha
          <input name="senha" type="password" required autoComplete="current-password" className="mt-1 w-full rounded border border-slate-300 px-3 py-2" />
        </label>
        {erro && <p className="text-sm text-red-700">{erro}</p>}
        <button disabled={enviando} className="w-full rounded bg-marinho py-2 font-medium text-white disabled:opacity-60">
          {enviando ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
    </div>
  );
}
