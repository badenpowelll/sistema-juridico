"use client";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { Aviso, Botao, Cartao, Paginacao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, enviar } from "@/lib/api";
import { dataCurta, STATUS_PROCESSO } from "@/lib/rotulos";
import type { Departamento, Pagina, ProcessoResumo, Tribunal } from "@/lib/tipos";

const POR_PAGINA = 25;

export default function Processos() {
  const { eu } = useEu();
  const router = useRouter();
  const caminho = usePathname();
  const params = useSearchParams();
  const pagina = Number(params.get("pagina") ?? "1") || 1;
  const filtros = {
    q: params.get("q") ?? "", status: params.get("status") ?? "", tribunal: params.get("tribunal") ?? "",
    departamento_id: params.get("departamento_id") ?? "", cliente_id: params.get("cliente_id") ?? "",
    importacao_id: params.get("importacao_id") ?? "",
  };
  const chave = params.toString();
  const [dados, setDados] = useState<Pagina<ProcessoResumo> | null>(null);
  const [tribunais, setTribunais] = useState<Tribunal[]>([]);
  const [deps, setDeps] = useState<Departamento[]>([]);
  const [selecionados, setSelecionados] = useState<Set<string>>(new Set());
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const podeGerenciar = eu.permissoes.includes("processos:gerenciar");
  const podeLote = podeGerenciar && eu.permissoes.includes("processos:lote");

  useEffect(() => {
    api<Tribunal[]>("/tribunais").then(setTribunais).catch(() => {});
    api<Departamento[]>("/departamentos").then(setDeps).catch(() => {});
  }, []);

  useEffect(() => {
    const qs = new URLSearchParams(chave);
    qs.set("pagina", String(pagina));
    qs.set("por_pagina", String(POR_PAGINA));
    api<Pagina<ProcessoResumo>>(`/processos?${qs}`).then((d) => { setDados(d); setSelecionados(new Set()); })
      .catch((e) => setErro(e.message));
  }, [chave, pagina]);

  function navegar(novos: Record<string, string>) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries({ ...filtros, ...novos })) if (v) qs.set(k, v);
    router.push(`${caminho}?${qs}`);
  }

  function filtrar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    navegar({ q: String(f.get("q") ?? ""), status: String(f.get("status") ?? ""), tribunal: String(f.get("tribunal") ?? ""),
      departamento_id: String(f.get("departamento_id") ?? ""), pagina: "" });
  }

  async function aplicarLote(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const [acao, valor] = String(f.get("operacao")).split(":");
    if (!acao) return;
    setErro(null);
    try {
      const r = await enviar<{ selecionados: number; alterados: number }>("/processos/lote", "POST",
        { ids: [...selecionados], acao, valor: valor || null });
      setAviso(`${r.alterados} de ${r.selecionados} processo(s) alterado(s). A operação ficou registrada na auditoria.`);
      api<Pagina<ProcessoResumo>>(`/processos?${new URLSearchParams({ ...Object.fromEntries(new URLSearchParams(chave)), pagina: String(pagina), por_pagina: String(POR_PAGINA) })}`)
        .then((d) => { setDados(d); setSelecionados(new Set()); });
    } catch (x) { setErro((x as Error).message); }
  }

  const todos = dados?.itens.length ? dados.itens.every((p) => selecionados.has(p.id)) : false;
  const filtroAtivo = Object.values(filtros).some(Boolean);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl font-semibold">Processos</h1>
          <p className="text-sm text-suave">Prontuário digital de cada processo, com partes, clientes e linha do tempo.</p>
        </div>
        <div className="flex gap-2">
          {eu.permissoes.includes("importacoes:executar") && <Link href="/painel/importacoes" className="rounded-md border border-borda px-4 py-2 text-sm hover:bg-superficie-2">Importar em massa</Link>}
          {podeGerenciar && <Link href="/painel/processos/novo" className="rounded-md border border-dourado/60 bg-marinho px-4 py-2 text-sm font-medium text-white hover:bg-marinho-profundo">Novo processo</Link>}
        </div>
      </div>

      <Cartao>
        <form onSubmit={filtrar} key={chave} className="grid gap-3 md:grid-cols-[2fr_1fr_1fr_1fr_auto] md:items-end">
          <div className="flex flex-col gap-1">
            <label htmlFor="f-q" className="text-sm font-medium">Buscar</label>
            <input id="f-q" name="q" defaultValue={filtros.q} placeholder="Número, parte, cliente, classe…" className="rounded-md border border-borda bg-superficie px-3 py-2 text-sm" />
          </div>
          <Selecao id="f-status" name="status" rotulo="Situação" defaultValue={filtros.status}>
            <option value="">Todas</option>
            {Object.entries(STATUS_PROCESSO).map(([v, [r]]) => <option key={v} value={v}>{r}</option>)}
          </Selecao>
          <Selecao id="f-tribunal" name="tribunal" rotulo="Tribunal" defaultValue={filtros.tribunal}>
            <option value="">Todos</option>
            {tribunais.map((t) => <option key={t.codigo} value={t.codigo}>{t.sigla}</option>)}
          </Selecao>
          <Selecao id="f-dep" name="departamento_id" rotulo="Departamento" defaultValue={filtros.departamento_id}>
            <option value="">Todos</option>
            {deps.map((d) => <option key={d.id} value={d.id}>{d.nome}</option>)}
          </Selecao>
          <div className="flex gap-2">
            <Botao type="submit">Filtrar</Botao>
            {filtroAtivo && <Botao type="button" variante="secundario" onClick={() => router.push(caminho)}>Limpar</Botao>}
          </div>
        </form>
        {(filtros.cliente_id || filtros.importacao_id) && (
          <p className="mt-3 text-xs text-suave">Filtrando por {filtros.cliente_id ? "cliente" : "importação"} específico(a).</p>
        )}
      </Cartao>

      {erro && <Aviso>{erro}</Aviso>}
      {aviso && <Aviso tom="ok">{aviso}</Aviso>}

      {podeLote && selecionados.size > 0 && (
        <form onSubmit={aplicarLote} className="flex flex-wrap items-end gap-3 rounded-xl border border-dourado/50 bg-dourado/5 p-4" aria-label="Operação em lote">
          <span className="text-sm font-medium">{selecionados.size} selecionado(s)</span>
          <Selecao id="lote-op" name="operacao" rotulo="Aplicar aos selecionados" required defaultValue="">
            <option value="" disabled>Escolha…</option>
            <optgroup label="Situação">
              {Object.entries(STATUS_PROCESSO).map(([v, [r]]) => <option key={v} value={`status:${v}`}>Marcar como {r.toLowerCase()}</option>)}
            </optgroup>
            <optgroup label="Departamento">
              {deps.map((d) => <option key={d.id} value={`departamento:${d.id}`}>Mover para {d.nome}</option>)}
            </optgroup>
          </Selecao>
          <Botao type="submit">Aplicar</Botao>
          <Botao type="button" variante="secundario" onClick={() => setSelecionados(new Set())}>Cancelar</Botao>
        </form>
      )}

      <Cartao>
        {!dados ? <p className="text-suave" aria-busy="true">Carregando…</p> : dados.itens.length === 0 ? (
          <Vazio>{filtroAtivo ? "Nenhum processo com esses filtros." : "Nenhum processo cadastrado ainda. Cadastre um ou importe a carteira existente."}</Vazio>
        ) : (
          <div className="flex flex-col gap-4">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="border-b border-borda text-xs uppercase tracking-wide text-suave">
                  <tr>
                    {podeLote && <th className="w-8 py-2"><input type="checkbox" aria-label="Selecionar todos da página" checked={todos}
                      onChange={() => setSelecionados(todos ? new Set() : new Set(dados.itens.map((p) => p.id)))} /></th>}
                    <th className="py-2 pr-3">Número</th><th className="py-2 pr-3">Tribunal</th><th className="py-2 pr-3">Classe</th>
                    <th className="py-2 pr-3">Cliente(s)</th><th className="py-2 pr-3">Situação</th><th className="py-2">Última mov.</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-borda">
                  {dados.itens.map((p) => {
                    const [rot, tom] = STATUS_PROCESSO[p.status] ?? [p.status, "neutro"];
                    return (
                      <tr key={p.id} data-processo={p.numero}>
                        {podeLote && <td className="py-2"><input type="checkbox" aria-label={`Selecionar ${p.numero}`} checked={selecionados.has(p.id)}
                          onChange={() => { const s = new Set(selecionados); if (s.has(p.id)) s.delete(p.id); else s.add(p.id); setSelecionados(s); }} /></td>}
                        <td className="py-2 pr-3 font-mono text-xs"><Link href={`/painel/processos/${p.id}`} className="text-dourado hover:underline">{p.numero}</Link></td>
                        <td className="py-2 pr-3">{p.tribunal?.sigla ?? "—"}</td>
                        <td className="py-2 pr-3">{p.classe ?? "—"}</td>
                        <td className="py-2 pr-3">{p.clientes.map((c) => c.nome).join(", ") || <span className="text-suave">sem cliente</span>}</td>
                        <td className="py-2 pr-3"><Selo tom={tom}>{rot}</Selo></td>
                        <td className="py-2">{dataCurta(p.ultima_movimentacao_em)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <Paginacao pagina={pagina} total={dados.total} porPagina={POR_PAGINA} aoMudar={(n) => navegar({ pagina: String(n) })} />
          </div>
        )}
      </Cartao>
    </div>
  );
}
