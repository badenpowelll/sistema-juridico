"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { BuscaCliente } from "@/componentes/BuscaCliente";
import { Aviso, Botao, Cartao, Selo, Vazio } from "@/componentes/ui";
import { api } from "@/lib/api";
import { ORIGENS, partesDestaque, type Resultado } from "@/lib/conhecimento";
import type { Cliente } from "@/lib/tipos";

type Resposta = { q: string; escopo: { cliente_id: string | null; processo_id: string | null }; metodo: string; resultados: Resultado[] };

export default function Conhecimento() {
  const params = useSearchParams();
  const processoId = params.get("processo_id");
  const clienteFixo = params.get("cliente_id");
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [origens, setOrigens] = useState<string[]>([]);
  const [r, setR] = useState<Resposta | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function pesquisar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const q = String(new FormData(e.currentTarget).get("q") ?? "").trim();
    if (q.length < 2) return;
    const qs = new URLSearchParams({ q });
    if (cliente) qs.set("cliente_id", cliente.id);
    else if (clienteFixo) qs.set("cliente_id", clienteFixo);
    if (processoId) qs.set("processo_id", processoId);
    origens.forEach((o) => qs.append("origem", o));
    setErro(null);
    setCarregando(true);
    try { setR(await api<Resposta>(`/conhecimento/pesquisa?${qs}`)); } catch (x) { setErro((x as Error).message); setR(null); }
    setCarregando(false);
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-serif text-3xl font-semibold">Pesquisa no conhecimento</h1>
        <p className="text-sm text-suave">
          Procura na <Link className="text-dourado underline" href="/painel/biblioteca">biblioteca</Link>, na{" "}
          <Link className="text-dourado underline" href="/painel/jurisprudencia">jurisprudência</Link>, nos documentos e na{" "}
          <Link className="text-dourado underline" href="/painel/memoria">memória</Link>. Dados de cliente só aparecem no escopo daquele cliente ou processo.
        </p>
      </div>
      <Cartao>
        <form onSubmit={pesquisar} className="grid gap-3 sm:grid-cols-3" aria-label="Pesquisar no conhecimento">
          <div className="flex flex-col gap-1 sm:col-span-2">
            <label htmlFor="pq-q" className="text-sm font-medium">O que procura</label>
            <input id="pq-q" name="q" type="search" required minLength={2} maxLength={300}
              className="rounded-md border border-borda bg-superficie px-3 py-2 text-sm" placeholder="ex.: horas extras habituais" />
          </div>
          {processoId || clienteFixo ? <Aviso tom="info">No escopo {processoId ? "do processo" : "do cliente"}. <Link className="underline" href="/painel/conhecimento">Pesquisar sem escopo</Link></Aviso>
            : <BuscaCliente id="pq-cliente" rotulo="Escopo: cliente (opcional)" aoEscolher={setCliente} />}
          <fieldset className="flex flex-wrap gap-3 text-sm sm:col-span-2">
            <legend className="sr-only">Onde procurar</legend>
            {Object.entries(ORIGENS).map(([k, v]) => (
              <label key={k} className="flex items-center gap-1">
                <input type="checkbox" checked={origens.includes(k)} onChange={(e) => setOrigens((o) => e.target.checked ? [...o, k] : o.filter((x) => x !== k))} /> {v}
              </label>
            ))}
            <span className="text-xs text-suave">(nenhum marcado: procura em tudo)</span>
          </fieldset>
          <div className="self-end"><Botao type="submit" disabled={carregando}>{carregando ? "Pesquisando…" : "Pesquisar"}</Botao></div>
        </form>
      </Cartao>
      {erro && <Aviso>{erro}</Aviso>}
      {r && (
        <Cartao titulo={`Resultados (${r.resultados.length})`} acao={<span className="text-xs text-suave">{r.metodo}</span>}>
          {r.resultados.length === 0 ? <Vazio>Nada encontrado neste escopo.</Vazio> : (
            <ol className="flex flex-col divide-y divide-borda" aria-label="Resultados da pesquisa">
              {r.resultados.map((x) => (
                <li key={`${x.origem}-${x.ref_id}`} className="flex flex-col gap-1 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Selo tom="dourado">{ORIGENS[x.origem]}</Selo>
                    {x.link ? <Link href={x.link} className="font-medium text-dourado hover:underline">{x.titulo}</Link> : <span>{x.titulo}</span>}
                    {(x.cliente_id || x.processo_id) && <Selo tom="info">{x.processo_id ? "Do processo" : "Do cliente"}</Selo>}
                    {x.alertas.map((a) => <Selo key={a} tom="alerta">{a}</Selo>)}
                  </div>
                  <p className="whitespace-pre-line text-sm text-suave">
                    {partesDestaque(x.trecho).map((p, i) => p.marca ? <mark key={i} className="bg-dourado/20 text-texto">{p.texto}</mark> : <span key={i}>{p.texto}</span>)}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </Cartao>
      )}
    </div>
  );
}
