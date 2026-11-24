"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { Aviso, Botao, Cartao, Paginacao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { SITUACAO_LINHA, STATUS_IMPORTACAO } from "@/lib/rotulos";
import type { Importacao, LinhaImportacao, Pagina } from "@/lib/tipos";

type Campo = { campo: string; rotulo: string; obrigatorio: boolean };
const NIVEL: Record<string, [string, string]> = {
  erro: ["erro", "perigo"], aviso: ["aviso", "alerta"], conferencia: ["dúvida", "alerta"], info: ["informação", "neutro"],
};
const POR_PAGINA = 50;

export default function DetalheImportacao() {
  const { id } = useParams<{ id: string }>();
  const { eu } = useEu();
  const [imp, setImp] = useState<Importacao | null>(null);
  const [campos, setCampos] = useState<Campo[]>([]);
  const [mapa, setMapa] = useState<Record<string, string>>({});
  const [filtro, setFiltro] = useState("");
  const [pagina, setPagina] = useState(1);
  const [linhas, setLinhas] = useState<Pagina<LinhaImportacao> | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const [progresso, setProgresso] = useState<number | null>(null);

  const aplicar = useCallback((d: Importacao) => {
    setImp(d);
    setMapa((m) => (Object.keys(m).length ? m : Object.fromEntries(Object.entries(d.mapeamento ?? {}).filter(([, v]) => v)) as Record<string, string>));
  }, []);
  const carregar = useCallback(() => api<Importacao>(`/importacoes/${id}`).then(aplicar), [id, aplicar]);
  useEffect(() => {
    api<Importacao>(`/importacoes/${id}`).then(aplicar).catch((e) => setErro(e.message));
    api<Campo[]>("/importacoes/campos").then(setCampos).catch(() => {});
  }, [id, aplicar]);
  useEffect(() => {
    const qs = new URLSearchParams({ pagina: String(pagina), por_pagina: String(POR_PAGINA) });
    if (filtro === "_mensagens") qs.set("so_com_mensagens", "true"); else if (filtro) qs.set("situacao", filtro);
    api<Pagina<LinhaImportacao>>(`/importacoes/${id}/linhas?${qs}`).then(setLinhas).catch(() => {});
  }, [id, filtro, pagina, imp?.status, imp?.totais.por_situacao]);

  async function validar() {
    setErro(null); setOcupado("Validando todas as linhas…");
    try { await enviar(`/importacoes/${id}/validar`, "POST", { mapeamento: mapa }); await carregar(); setFiltro("_mensagens"); setPagina(1); }
    catch (x) { setErro((x as Error).message); } finally { setOcupado(null); }
  }

  async function executar() {
    setErro(null); setOcupado("Gravando em lotes de 500…");
    const total = (imp?.totais.por_situacao?.valida ?? 0) + (imp?.totais.por_situacao?.conferencia ?? 0);
    try {
      for (;;) {  // cada chamada grava por até ~8 s e devolve o progresso; pode ser retomada a qualquer momento
        const r = await enviar<{ status: string; restantes: number }>(`/importacoes/${id}/executar?prazo_segundos=8`, "POST");
        setProgresso(total ? Math.round(((total - r.restantes) / total) * 100) : 100);
        if (r.status !== "processando") break;
      }
      await carregar(); setFiltro(""); setPagina(1);
    } catch (x) { setErro((x as Error).message); } finally { setOcupado(null); setProgresso(null); }
  }

  async function reverter() {
    if (!confirm("Reverter esta importação? Processos alterados depois da importação serão mantidos.")) return;
    setErro(null); setOcupado("Revertendo…");
    try { await enviar(`/importacoes/${id}/reverter`, "POST"); await carregar(); } catch (x) { setErro((x as Error).message); } finally { setOcupado(null); }
  }

  async function cancelar() {
    try { await enviar(`/importacoes/${id}/cancelar`, "POST"); await carregar(); } catch (x) { setErro((x as Error).message); }
  }

  if (erro && !imp) return <Aviso>{erro}</Aviso>;
  if (!imp) return <p className="text-suave" aria-busy="true">Carregando…</p>;
  const [rot, tom] = STATUS_IMPORTACAO[imp.status] ?? [imp.status, "neutro"];
  const sit = imp.totais.por_situacao ?? {};
  const editavel = imp.status === "analisado" || imp.status === "validado";

  return (
    <div className="flex flex-col gap-5">
      <div>
        <Link href="/painel/importacoes" className="text-sm text-dourado hover:underline">← Importações</Link>
        <div className="mt-1 flex flex-wrap items-center gap-3"><h1 className="font-serif text-3xl font-semibold">{imp.arquivo_nome}</h1><Selo tom={tom}>{rot}</Selo></div>
        <p className="text-sm text-suave">{imp.totais.linhas ?? 0} linha(s) · {imp.formato.toUpperCase()} · enviado em {dataHora(imp.criado_em)}</p>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {imp.totais.aviso && <Aviso tom="alerta">Atenção: {imp.totais.aviso}.</Aviso>}
      {ocupado && <Aviso tom="info"><span aria-live="polite">{ocupado}{progresso !== null && ` ${progresso}%`}</span></Aviso>}

      {editavel && (
        <Cartao titulo="1. Mapeamento das colunas" acao={<span className="text-xs text-suave">Sugerido automaticamente; confira.</span>}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {campos.map((c) => (
              <div key={c.campo} className="flex flex-col gap-1">
                <label htmlFor={`m-${c.campo}`} className="text-sm font-medium">{c.rotulo}{c.obrigatorio && <span className="text-perigo"> *</span>}</label>
                <select id={`m-${c.campo}`} value={mapa[c.campo] ?? ""} onChange={(e) => setMapa({ ...mapa, [c.campo]: e.target.value })}
                  className="rounded-md border border-borda bg-superficie px-3 py-2 text-sm">
                  <option value="">— não importar —</option>
                  {imp.colunas.map((col) => <option key={col} value={col}>{col}</option>)}
                </select>
              </div>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Botao onClick={validar} disabled={!!ocupado || !mapa.numero}>{imp.status === "validado" ? "Validar de novo" : "Validar linhas"}</Botao>
            <Botao variante="secundario" onClick={cancelar} disabled={!!ocupado}>Cancelar importação</Botao>
          </div>
          <p className="mt-2 text-xs text-suave">Clientes só são associados automaticamente por CPF/CNPJ válido. Nome sem documento que coincida com cliente existente vai para conferência.</p>
        </Cartao>
      )}

      {imp.status !== "analisado" && (
        <Cartao titulo={imp.status === "validado" ? "2. Resultado da validação" : "Resultado"}>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4" aria-label="Totais por situação">
            {Object.entries(sit).sort().map(([k, v]) => {
              const [r, t] = SITUACAO_LINHA[k] ?? [k, "neutro"];
              return (
                <button key={k} onClick={() => { setFiltro(k); setPagina(1); }} data-situacao={k}
                  className={`rounded-md border p-3 text-left ${filtro === k ? "border-dourado" : "border-borda"}`}>
                  <div className="font-serif text-2xl font-semibold">{v.toLocaleString("pt-BR")}</div><Selo tom={t}>{r}</Selo>
                </button>
              );
            })}
          </div>
          {imp.totais.reversao && (
            <p className="mt-3 text-sm">Reversão: {imp.totais.reversao.processos_removidos} processo(s) removido(s), {imp.totais.reversao.processos_mantidos} mantido(s) por terem alterações posteriores, {imp.totais.reversao.vinculos_removidos} vínculo(s) desfeito(s), {imp.totais.reversao.clientes_removidos} cliente(s) removido(s).</p>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            {imp.status === "validado" && <Botao onClick={executar} disabled={!!ocupado || !((sit.valida ?? 0) + (sit.conferencia ?? 0))}>
              Executar importação ({((sit.valida ?? 0) + (sit.conferencia ?? 0)).toLocaleString("pt-BR")} linha(s))</Botao>}
            {imp.status === "processando" && <Botao onClick={executar} disabled={!!ocupado}>Retomar execução</Botao>}
            <a href={`/api/v1/importacoes/${id}/relatorio.csv`} className="rounded-md border border-borda px-4 py-2 text-sm hover:bg-superficie-2">Baixar relatório de inconsistências</a>
            {imp.status === "concluido" && (sit.importada ?? 0) > 0 && <Link href={`/painel/processos?importacao_id=${id}`} className="rounded-md border border-borda px-4 py-2 text-sm hover:bg-superficie-2">Ver processos importados</Link>}
            {(imp.totais.conferencia_pendente ?? 0) > 0 && eu.permissoes.includes("importacoes:conferir") && imp.status !== "validado" && <Link href="/painel/importacoes/conferencia" className="rounded-md border border-alerta/60 px-4 py-2 text-sm text-alerta">Conferir {imp.totais.conferencia_pendente} linha(s)</Link>}
            {imp.status === "concluido" && eu.permissoes.includes("importacoes:reverter") && <Botao variante="perigo" onClick={reverter} disabled={!!ocupado}>Reverter importação</Botao>}
          </div>
          {imp.status === "validado" && (sit.conferencia ?? 0) > 0 && (
            <p className="mt-2 text-xs text-suave">Linhas em conferência também são gravadas, mas sem cliente associado até alguém confirmar a quem pertencem.</p>
          )}
        </Cartao>
      )}

      <Cartao titulo="Linhas" acao={
        <select aria-label="Filtrar linhas" value={filtro} onChange={(e) => { setFiltro(e.target.value); setPagina(1); }} className="rounded-md border border-borda bg-superficie px-2 py-1 text-sm">
          <option value="">Todas</option><option value="_mensagens">Com mensagens</option>
          {Object.entries(SITUACAO_LINHA).map(([k, [r]]) => <option key={k} value={k}>{r}</option>)}
        </select>}>
        {!linhas ? <p className="text-suave">Carregando…</p> : linhas.itens.length === 0 ? <Vazio>Nenhuma linha neste filtro.</Vazio> : (
          <div className="flex flex-col gap-4">
            <ul className="divide-y divide-borda" aria-label="Linhas do arquivo">
              {linhas.itens.map((l) => {
                const [r, t] = SITUACAO_LINHA[l.situacao] ?? [l.situacao, "neutro"];
                const numero = (l.normalizado?.numero_formatado as string) ?? l.original[imp.mapeamento?.numero ?? ""] ?? "(sem número)";
                return (
                  <li key={l.id} className="flex flex-col gap-1 py-2 text-sm" data-linha={l.linha}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="w-16 text-xs text-suave">linha {l.linha}</span><Selo tom={t}>{r}</Selo>
                      {l.processo_id ? <Link href={`/painel/processos/${l.processo_id}`} className="font-mono text-xs text-dourado hover:underline">{numero}</Link> : <span className="font-mono text-xs">{numero}</span>}
                      {typeof l.normalizado?.cliente_nome === "string" && <span className="text-xs text-suave">· {l.normalizado.cliente_nome as string}</span>}
                    </div>
                    {l.mensagens.length > 0 && (
                      <ul className="ml-16 flex flex-col gap-0.5">
                        {l.mensagens.map((m, i) => <li key={i} className="flex items-start gap-2 text-xs"><Selo tom={NIVEL[m.nivel]?.[1]}>{NIVEL[m.nivel]?.[0] ?? m.nivel}</Selo><span>{m.texto}</span></li>)}
                      </ul>
                    )}
                  </li>
                );
              })}
            </ul>
            <Paginacao pagina={pagina} total={linhas.total} porPagina={POR_PAGINA} aoMudar={setPagina} />
          </div>
        )}
      </Cartao>
    </div>
  );
}
