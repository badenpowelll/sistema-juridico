"use client";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { BuscaCliente } from "@/componentes/BuscaCliente";
import { BuscaProcesso } from "@/componentes/BuscaProcesso";
import { ListaLancamentos, Submenu } from "@/componentes/Financeiro";
import { Aviso, Botao, Campo, Cartao, Paginacao, Selecao } from "@/componentes/ui";
import { api, enviar } from "@/lib/api";
import { hojeIso, paraDecimal, reais, type Categoria, type Lancamento, type LancamentoDetalhe, type Pode } from "@/lib/financeiro";
import type { Cliente, ProcessoResumo } from "@/lib/tipos";

type Lista = { itens: Lancamento[]; total: number; pagina: number; por_pagina: number; pode: Pode;
  somas: { receitas_abertas: string; receitas_recebidas: string; despesas_abertas: string; despesas_pagas: string } };
const SITUACOES: [string, string][] = [["", "Todas"], ["aberto", "Em aberto"], ["vencido", "Vencidas"], ["previsto", "Previstas / a pagar"],
  ["faturado", "Faturadas"], ["liquidado", "Recebidas / pagas"], ["cancelado", "Canceladas"]];

function NovoLancamento({ categorias, aoCriar }: { categorias: Categoria[]; aoCriar: (l: LancamentoDetalhe) => void }) {
  const [tipo, setTipo] = useState<"receita" | "despesa">("receita");
  const [cli, setCli] = useState<Cliente | null>(null);
  const [proc, setProc] = useState<ProcessoResumo | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const cats = categorias.filter((c) => c.tipo === tipo && c.ativa);

  async function salvar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setErro(null);
    try {
      aoCriar(await enviar<LancamentoDetalhe>("/financeiro/lancamentos", "POST", {
        tipo, categoria_id: f.get("categoria"), descricao: String(f.get("descricao")).trim(),
        valor: paraDecimal(f.get("valor")) || "0", vencimento: f.get("vencimento"),
        cliente_id: cli?.id ?? null, processo_id: proc?.id ?? null,
        portal_visivel: f.get("portal") === "on", reembolsavel: f.get("reembolsavel") === "on",
        observacao: String(f.get("observacao") ?? "").trim() || null,
      }));
    } catch (x) { setErro((x as Error).message); }
  }

  return (
    <form aria-label="Novo lançamento" onSubmit={salvar} className="grid gap-3 sm:grid-cols-2">
      {erro && <div className="sm:col-span-2"><Aviso>{erro}</Aviso></div>}
      <Selecao id="nl-tipo" rotulo="Tipo" value={tipo} onChange={(e) => setTipo(e.target.value as "receita" | "despesa")}>
        <option value="receita">Receita</option><option value="despesa">Despesa</option></Selecao>
      <Selecao id="nl-cat" name="categoria" rotulo="Categoria" required key={tipo}>
        {cats.map((c) => <option key={c.id} value={c.id}>{c.nome}</option>)}</Selecao>
      <Campo id="nl-desc" name="descricao" rotulo="Descrição" required minLength={3} maxLength={300} />
      <Campo id="nl-valor" name="valor" rotulo="Valor (R$)" required inputMode="decimal" placeholder="0,00" pattern="[0-9.]*[,]?[0-9]{0,2}" />
      <Campo id="nl-venc" name="vencimento" type="date" rotulo="Vencimento" required defaultValue={hojeIso()} />
      <Campo id="nl-obs" name="observacao" rotulo="Observação (opcional)" maxLength={2000} />
      <BuscaCliente id="nl-cliente" rotulo="Cliente (opcional)" aoEscolher={setCli} />
      <BuscaProcesso id="nl-processo" rotulo="Processo (opcional)" aoEscolher={setProc} />
      {tipo === "receita" ? (
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="portal" disabled={!cli} /> Mostrar ao cliente no portal</label>
      ) : (
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" name="reembolsavel" disabled={!cli} /> Reembolsável pelo cliente</label>
      )}
      <div className="sm:col-span-2"><Botao type="submit">Lançar</Botao>
        <p className="mt-1 text-xs text-suave">O lançamento nasce previsto. Recebido ou pago é registrado depois, na tela do lançamento, com a data e a conta.</p></div>
    </form>
  );
}

export default function Lancamentos() {
  const router = useRouter();
  const caminho = usePathname();
  const params = useSearchParams();
  const tipo = params.get("tipo") ?? "";
  const situacao = params.get("situacao") ?? "aberto";
  const q = params.get("q") ?? "";
  const processo = params.get("processo") ?? "";
  const pagina = Number(params.get("pagina") ?? "1") || 1;
  const [l, setL] = useState<Lista | null>(null);
  const [cats, setCats] = useState<Categoria[]>([]);
  const [novo, setNovo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => { api<{ categorias: Categoria[] }>("/financeiro").then((d) => setCats(d.categorias)).catch(() => undefined); }, []);
  useEffect(() => {
    const qs = new URLSearchParams({ pagina: String(pagina), por_pagina: "50" });
    if (tipo) qs.set("tipo", tipo);
    if (situacao) qs.set("situacao", situacao);
    if (q) qs.set("q", q);
    if (processo) qs.set("processo_id", processo);
    api<Lista>(`/financeiro/lancamentos?${qs}`).then(setL).catch((e) => setErro(e.message));
  }, [tipo, situacao, q, processo, pagina]);

  const ir = (novos: Record<string, string>) => {
    const qs = new URLSearchParams({ tipo, situacao, q, processo, ...novos });
    for (const [k, v] of [...qs.entries()]) if (!v && k !== "situacao") qs.delete(k);
    router.push(`${caminho}?${qs}`);
  };
  const exportar = new URLSearchParams({ ...(tipo && { tipo }), ...(situacao && { situacao }), ...(processo && { processo_id: processo }) });

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl font-semibold">Lançamentos</h1>
          <p className="text-sm text-suave">Receitas e despesas. Nada é apagado: cancelar e estornar pedem motivo e ficam na auditoria.</p>
        </div>
        {l?.pode.gerenciar && <Botao onClick={() => setNovo((v) => !v)} aria-expanded={novo}>{novo ? "Fechar" : "Novo lançamento"}</Botao>}
      </div>
      <Submenu atual="/painel/financeiro/lancamentos" />
      {erro && <Aviso>{erro}</Aviso>}
      {novo && <Cartao titulo="Novo lançamento"><NovoLancamento categorias={cats} aoCriar={(x) => router.push(`/painel/financeiro/lancamentos/${x.id}`)} /></Cartao>}
      <Cartao titulo="Lançamentos" acao={l?.pode.exportar && <a className="text-sm text-dourado hover:underline" href={`/api/v1/financeiro/exportar/lancamentos.csv?${exportar}`}>Exportar CSV</a>}>
        <div className="mb-3 grid gap-2 sm:grid-cols-3">
          <Selecao id="f-tipo" rotulo="Tipo" value={tipo} onChange={(e) => ir({ tipo: e.target.value, pagina: "" })}>
            <option value="">Receitas e despesas</option><option value="receita">Receitas</option><option value="despesa">Despesas</option></Selecao>
          <Selecao id="f-situacao" rotulo="Situação" value={situacao} onChange={(e) => ir({ situacao: e.target.value, pagina: "" })}>
            {SITUACOES.map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Selecao>
          <form onSubmit={(e) => { e.preventDefault(); ir({ q: String(new FormData(e.currentTarget).get("q") ?? ""), pagina: "" }); }}>
            <Campo id="f-q" name="q" rotulo="Descrição ou cliente" defaultValue={q} /></form>
        </div>
        {processo && <p className="mb-2 text-sm">Filtrando por um processo. <button className="text-dourado hover:underline" onClick={() => ir({ processo: "", pagina: "" })}>Ver todos</button></p>}
        {!l ? <p className="text-suave" aria-busy="true">Carregando…</p> : (<>
          <p className="mb-2 text-xs text-suave" aria-label="Somas do filtro">Receitas em aberto {reais(l.somas.receitas_abertas)} · recebidas {reais(l.somas.receitas_recebidas)} ·
            despesas a pagar {reais(l.somas.despesas_abertas)} · pagas {reais(l.somas.despesas_pagas)}</p>
          <ListaLancamentos itens={l.itens} rotulo="Lista de lançamentos" vazio="Nenhum lançamento com esses filtros." />
          <div className="mt-3"><Paginacao pagina={l.pagina} total={l.total} porPagina={l.por_pagina} aoMudar={(p) => ir({ pagina: String(p) })} /></div>
        </>)}
      </Cartao>
    </div>
  );
}
