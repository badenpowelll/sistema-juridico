"use client";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { AreaTexto, Aviso, Botao, Campo, Cartao, Paginacao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar, enviarArquivo } from "@/lib/api";
import { dataCurta, FONTE, SITUACAO_PUBLICACAO } from "@/lib/rotulos";
import type { Pagina, Publicacao } from "@/lib/tipos";

const ABAS: [string, string][] = [["nao_conferida", "Não conferidas"], ["conferida", "Conferidas"], ["duplicada", "Duplicadas"],
  ["descartada", "Descartadas"], ["", "Todas"]];
const POR_PAGINA = 25;

export default function Publicacoes() {
  const { eu } = useEu();
  const router = useRouter();
  const caminho = usePathname();
  const params = useSearchParams();
  const situacao = params.get("situacao") ?? "nao_conferida";
  const pagina = Number(params.get("pagina") ?? "1") || 1;
  const q = params.get("q") ?? "";
  const [dados, setDados] = useState<(Pagina<Publicacao> & { contagem: Record<string, number> }) | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const [painel, setPainel] = useState<"" | "cadastrar" | "importar">("");
  const [versao, setVersao] = useState(0);
  const podeCadastrar = eu.permissoes.includes("publicacoes:cadastrar");

  useEffect(() => {
    const qs = new URLSearchParams({ pagina: String(pagina), por_pagina: String(POR_PAGINA) });
    if (situacao) qs.set("situacao", situacao);
    if (q) qs.set("q", q);
    api<Pagina<Publicacao> & { contagem: Record<string, number> }>(`/publicacoes?${qs}`).then(setDados).catch((e) => setErro(e.message));
  }, [situacao, pagina, q, versao]);

  const ir = (novos: Record<string, string>) => {
    const qs = new URLSearchParams({ situacao, q, ...novos });
    for (const [k, v] of [...qs.entries()]) if (!v && k !== "situacao") qs.delete(k);
    router.push(`${caminho}?${qs}`);
  };

  async function cadastrar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setErro(null);
    try {
      const r = await enviar<Publicacao & { contagem: { prazos_sugeridos: number } }>("/publicacoes", "POST", {
        numero_processo: f.get("numero") || null, texto: f.get("texto"), disponibilizado_em: f.get("data"),
        tipo: f.get("tipo") || null, tribunal: f.get("tribunal") || null, orgao: f.get("orgao") || null });
      setAviso(`Publicação cadastrada${r.situacao === "duplicada" ? " (identificada como duplicada de outra já existente)" : ""}.`
        + (r.contagem.prazos_sugeridos ? " Um prazo foi sugerido e aguarda conferência." : ""));
      setPainel(""); setVersao((v) => v + 1);
    } catch (x) { setErro((x as Error).message); }
  }

  async function importar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const arq = (new FormData(e.currentTarget).get("arquivo") as File | null);
    if (!arq || !arq.size) return;
    setErro(null);
    try {
      const r = await enviarArquivo<{ recebidos: number; novos: number; ja_capturados: number; duplicados: number; vinculados: number; prazos_sugeridos: number }>("/publicacoes/importar", arq);
      setAviso(`${r.recebidos} comunicação(ões) no arquivo: ${r.novos} nova(s), ${r.ja_capturados} já capturada(s), ${r.duplicados} duplicada(s), ${r.vinculados} vinculada(s) a processo, ${r.prazos_sugeridos} prazo(s) sugerido(s).`);
      setPainel(""); setVersao((v) => v + 1);
    } catch (x) { setErro((x as Error).message); }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl font-semibold">Publicações e intimações</h1>
          <p className="text-sm text-suave">Tudo o que chega das fontes oficiais, com o original preservado. Cada item precisa ser lido, vinculado ao processo e conferido. Movimentação não é intimação.</p>
        </div>
        {podeCadastrar && (
          <div className="flex gap-2">
            <Botao variante="secundario" onClick={() => setPainel(painel === "importar" ? "" : "importar")}>Importar arquivo do DJEN</Botao>
            <Botao onClick={() => setPainel(painel === "cadastrar" ? "" : "cadastrar")}>Cadastrar publicação</Botao>
          </div>
        )}
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {aviso && <Aviso tom="ok">{aviso}</Aviso>}

      {painel === "cadastrar" && (
        <Cartao titulo="Cadastrar publicação manualmente">
          <form onSubmit={cadastrar} className="grid gap-3 md:grid-cols-2">
            <Campo id="pub-numero" name="numero" rotulo="Número do processo" placeholder="0000000-00.0000.0.00.0000" ajuda="Deixe vazio se não constar." />
            <Campo id="pub-data" name="data" type="date" rotulo="Data de disponibilização" required ajuda="A publicação é o 1º dia útil seguinte (calculada)." />
            <Campo id="pub-tipo" name="tipo" rotulo="Tipo" defaultValue="Intimação" />
            <Campo id="pub-tribunal" name="tribunal" rotulo="Tribunal (sigla)" placeholder="TJRN" />
            <div className="md:col-span-2"><Campo id="pub-orgao" name="orgao" rotulo="Órgão" /></div>
            <div className="md:col-span-2"><AreaTexto id="pub-texto" name="texto" rotulo="Texto integral" required minLength={10} rows={6} /></div>
            <div><Botao type="submit">Salvar publicação</Botao></div>
          </form>
        </Cartao>
      )}
      {painel === "importar" && (
        <Cartao titulo="Importar arquivo do DJEN">
          <form onSubmit={importar} className="flex flex-col gap-3 text-sm">
            <p className="text-suave">Use o arquivo .json devolvido pela consulta pública do DJEN (o endereço pronto está na Central de contingência). Comunicações já capturadas não são duplicadas.</p>
            <input type="file" name="arquivo" accept=".json,application/json" aria-label="Arquivo JSON do DJEN" required className="text-sm" />
            <div><Botao type="submit">Importar</Botao></div>
          </form>
        </Cartao>
      )}

      <div className="flex flex-wrap items-center gap-2" role="tablist" aria-label="Situação">
        {ABAS.map(([v, r]) => (
          <button key={v || "todas"} role="tab" aria-selected={situacao === v} onClick={() => ir({ situacao: v, pagina: "" })}
            className={`rounded-full border px-3 py-1 text-sm ${situacao === v ? "border-dourado bg-dourado/10 font-medium" : "border-borda hover:bg-superficie-2"}`}>
            {r}{v && dados?.contagem[v] != null ? ` (${dados.contagem[v]})` : ""}
          </button>
        ))}
        <form className="ml-auto flex gap-2" onSubmit={(e) => { e.preventDefault(); ir({ q: String(new FormData(e.currentTarget).get("q") ?? ""), pagina: "" }); }}>
          <input name="q" defaultValue={q} key={q} placeholder="Texto, órgão ou número…" aria-label="Buscar publicações"
            className="rounded-md border border-borda bg-superficie px-3 py-1.5 text-sm" />
          <Botao type="submit" variante="secundario">Buscar</Botao>
        </form>
      </div>

      {!dados ? <p className="text-suave" aria-busy="true">Carregando…</p> : dados.itens.length === 0 ? (
        <Cartao><Vazio>{situacao === "nao_conferida" ? "Nenhuma publicação aguardando conferência. Isso só significa que nada foi capturado: confira a Central de contingência para saber se as fontes estão operando." : "Nada nesta situação."}</Vazio></Cartao>
      ) : (
        <div className="flex flex-col gap-3">
          {dados.itens.map((p) => <ItemPublicacao key={p.id} p={p} />)}
          <Paginacao pagina={pagina} total={dados.total} porPagina={POR_PAGINA} aoMudar={(n) => ir({ pagina: String(n) })} />
        </div>
      )}
    </div>
  );
}

function ItemPublicacao({ p }: { p: Publicacao }) {
  const [rot, tom] = SITUACAO_PUBLICACAO[p.situacao] ?? [p.situacao, "neutro"];
  return (
    <Link href={`/painel/publicacoes/${p.id}`} data-publicacao={p.id}
      className="block rounded-xl border border-borda bg-superficie p-4 transition hover:border-dourado/60">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Selo tom={p.tipo === "intimacao" || p.tipo === "citacao" ? "dourado" : "info"}>{p.tipo_rotulo}</Selo>
        <Selo tom={tom}>{rot}</Selo>
        {p.simulado && <Selo tom="alerta">Simulado</Selo>}
        <span className="text-suave">{FONTE[p.fonte] ?? p.fonte}{p.tribunal && ` · ${p.tribunal}`}{p.orgao && ` · ${p.orgao}`}</span>
      </div>
      <div className="mt-2 font-mono text-sm">{p.processo?.numero ?? p.numero_processo ?? "Sem número de processo"}
        {!p.processo_id && <span className="ml-2 font-sans text-xs text-perigo">processo não vinculado</span>}</div>
      <p className="mt-1 line-clamp-2 text-sm">{p.resumo}</p>
      <dl className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-suave">
        <div><dt className="inline">Disponibilizada: </dt><dd className="inline">{dataCurta(p.disponibilizado_em)}</dd></div>
        <div><dt className="inline">Publicada: </dt><dd className="inline">{dataCurta(p.publicado_em)}</dd></div>
        <div><dt className="inline">Capturada: </dt><dd className="inline">{dataHora(p.capturado_em)}</dd></div>
        <div><dt className="inline">Ciência: </dt><dd className="inline">{p.ciencia_em ? dataHora(p.ciencia_em) : "não registrada"}</dd></div>
        {p.prazo_dias_no_texto && <div><dt className="inline">Prazo no texto: </dt><dd className="inline">{p.prazo_dias_no_texto} dia(s)</dd></div>}
      </dl>
      {p.pendencias.length > 0 && p.situacao === "nao_conferida" && (
        <ul className="mt-2 flex flex-col gap-1 text-xs">{p.pendencias.map((x) => <li key={x} className="text-alerta">• {x}</li>)}</ul>
      )}
    </Link>
  );
}
