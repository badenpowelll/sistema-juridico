"use client";
import { useEffect, useState, type FormEvent } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { Aviso, Botao, Campo, Cartao, Selo } from "@/componentes/ui";
import { api, enviar } from "@/lib/api";

type Dep = { id: string; codigo: string; nome: string; descricao: string | null; ativo: boolean; ordem: number };

export default function Departamentos() {
  const { eu } = useEu();
  const pode = eu.permissoes.includes("departamentos:gerenciar");
  const [lista, setLista] = useState<Dep[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const carregar = () => api<Dep[]>("/departamentos").then(setLista).catch((e) => setErro(e.message));
  useEffect(() => { carregar(); }, []);

  async function criar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    setErro(null);
    try { await enviar("/departamentos", "POST", { nome: new FormData(form).get("nome") }); form.reset(); carregar(); }
    catch (x) { setErro((x as Error).message); }
  }
  async function alternar(d: Dep) { await enviar(`/departamentos/${d.id}`, "PATCH", { ativo: !d.ativo }); carregar(); }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="font-serif text-3xl font-semibold">Departamentos</h1>
      <p className="text-sm text-suave">Áreas de atuação do escritório. Novos departamentos entram sem alterar o sistema.</p>
      {erro && <Aviso>{erro}</Aviso>}
      {pode && (
        <Cartao titulo="Novo departamento">
          <form onSubmit={criar} className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1"><Campo id="nome-dep" name="nome" rotulo="Nome" required minLength={2} /></div>
            <Botao type="submit">Adicionar</Botao>
          </form>
        </Cartao>
      )}
      <Cartao>
        <ul className="grid gap-2 sm:grid-cols-2">
          {lista.map((d) => (
            <li key={d.id} className="flex items-center justify-between rounded-md border border-borda px-3 py-2 text-sm">
              <span>{d.nome} {!d.ativo && <Selo>Inativo</Selo>}</span>
              {pode && <button onClick={() => alternar(d)} className="text-xs text-dourado hover:underline">{d.ativo ? "Desativar" : "Ativar"}</button>}
            </li>
          ))}
        </ul>
      </Cartao>
    </div>
  );
}
