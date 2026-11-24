"use client";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { BuscaCliente } from "@/componentes/BuscaCliente";
import { useEu } from "@/componentes/CascoPainel";
import { Aviso, Botao, Campo, Cartao, Paginacao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora } from "@/lib/api";
import { enviarArquivoCom } from "@/lib/atendimento";
import { ORIGEM, SITUACAO_DOC, type Documento } from "@/lib/documentos";
import type { Cliente } from "@/lib/tipos";

type Lista = { total: number; pagina: number; por_pagina: number; itens: Documento[]; categorias: Record<string, string> };

/** Destaca os trechos marcados pelo servidor com « » sem interpretar HTML. */
function Trecho({ texto }: { texto: string }) {
  const partes = texto.split(/(«[^»]*»)/g);
  return (
    <p className="text-xs text-suave">
      {partes.map((p, i) => p.startsWith("«") ? <mark key={i} className="bg-dourado/20 text-texto">{p.slice(1, -1)}</mark> : <span key={i}>{p}</span>)}
    </p>
  );
}

export default function Acervo() {
  const { eu } = useEu();
  const router = useRouter();
  const caminho = usePathname();
  const params = useSearchParams();
  const chave = params.toString();
  const pode = eu.permissoes.includes("documentos:gerenciar");
  const podeSigilo = eu.permissoes.includes("documentos:sigilosos");
  const [l, setL] = useState<Lista | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [envio, setEnvio] = useState(false);
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [versao, setVersao] = useState(0);

  useEffect(() => {
    const p = new URLSearchParams(chave);
    api<Lista>(`/documentos?${p}`).then(setL).catch((e) => setErro(e.message));
  }, [chave, versao]);

  function filtrar(mud: Record<string, string | null>) {
    const p = new URLSearchParams(chave);
    for (const [k, v] of Object.entries(mud)) { if (v) p.set(k, v); else p.delete(k); }
    if (!("pagina" in mud)) p.delete("pagina");
    router.replace(`${caminho}?${p}`);
  }

  async function enviarDoc(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const arquivo = f.get("arquivo") as File | null;
    if (!arquivo || !arquivo.size) { setErro("Escolha um arquivo"); return; }
    setErro(null); setOk(null); setEnviando(true);
    try {
      const d = await enviarArquivoCom<Documento>("/documentos", arquivo, {
        titulo: String(f.get("titulo") ?? "").trim() || null, categoria: String(f.get("categoria") ?? "") || null,
        cliente_id: cliente?.id ?? null, sigiloso: f.get("sigiloso") ? "true" : null,
      });
      if (d.duplicado) setOk(`Este arquivo já estava no acervo como “${d.titulo}”. Nada foi duplicado.`);
      else if (d.situacao === "quarentena") setOk(`Arquivo guardado em quarentena: ${d.motivo_situacao}. Ele não será aberto até alguém autorizado liberar.`);
      else setOk("Documento enviado. O texto (e o OCR, se for digitalização) é extraído em segundo plano.");
      (e.target as HTMLFormElement).reset(); setCliente(null); setVersao((v) => v + 1);
    } catch (x) { setErro((x as Error).message); } finally { setEnviando(false); }
  }

  const cats = l ? Object.entries(l.categorias) : [];
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl font-semibold">Documentos</h1>
          <p className="text-sm text-suave">Acervo do escritório. O original nunca é alterado: texto extraído e novas versões ficam ao lado.</p>
        </div>
        <div className="flex gap-2">
          <Link href="/painel/minutas" className="rounded-md border border-borda px-4 py-2 text-sm hover:bg-superficie-2">Minutas</Link>
          <Link href="/painel/modelos" className="rounded-md border border-borda px-4 py-2 text-sm hover:bg-superficie-2">Modelos</Link>
          {pode && <Botao onClick={() => setEnvio((v) => !v)} aria-expanded={envio}>{envio ? "Fechar" : "Enviar documento"}</Botao>}
        </div>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}

      {envio && pode && (
        <Cartao titulo="Enviar documento">
          <form onSubmit={enviarDoc} className="grid gap-3 sm:grid-cols-2" aria-label="Enviar documento">
            <div className="flex flex-col gap-1 sm:col-span-2">
              <label htmlFor="d-arquivo" className="text-sm font-medium">Arquivo</label>
              <input id="d-arquivo" name="arquivo" type="file" required className="text-sm"
                accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.webp,.heic,.docx,.xlsx,.csv,.txt,.mp3,.ogg,.m4a,.wav" />
              <p className="text-xs text-suave">PDF, imagem, Word, Excel, CSV, texto ou áudio. Executáveis e arquivos com macros não entram.</p>
            </div>
            <Campo id="d-titulo" name="titulo" rotulo="Título (opcional)" maxLength={300} />
            <Selecao id="d-categoria" name="categoria" rotulo="Categoria" defaultValue="">
              <option value="">Classificar automaticamente</option>
              {cats.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Selecao>
            <BuscaCliente id="d-cliente" rotulo="Cliente (opcional)" aoEscolher={setCliente} />
            {podeSigilo && (
              <label className="flex items-center gap-2 self-end text-sm"><input type="checkbox" name="sigiloso" /> Sigiloso (só quem tem acesso a sigilosos vê)</label>
            )}
            <div className="sm:col-span-2"><Botao type="submit" disabled={enviando}>{enviando ? "Enviando…" : "Enviar"}</Botao></div>
          </form>
        </Cartao>
      )}

      <Cartao>
        <form className="grid gap-3 sm:grid-cols-4" role="search" aria-label="Pesquisar documentos"
          onSubmit={(e) => { e.preventDefault(); filtrar({ q: String(new FormData(e.currentTarget).get("q") ?? "").trim() || null }); }}>
          <div className="sm:col-span-2"><Campo id="d-q" name="q" rotulo="Pesquisar no título e no conteúdo" defaultValue={params.get("q") ?? ""} placeholder="Ex.: rescisão, CTPS, nome do cliente" /></div>
          <Selecao id="d-fcat" rotulo="Categoria" value={params.get("categoria") ?? ""} onChange={(e) => filtrar({ categoria: e.target.value || null })}>
            <option value="">Todas</option>
            {cats.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Selecao>
          <Selecao id="d-fsit" rotulo="Situação" value={params.get("situacao") ?? "ativo"} onChange={(e) => filtrar({ situacao: e.target.value === "ativo" ? null : e.target.value })}>
            <option value="ativo">Ativos</option><option value="arquivado">Arquivados</option>
            <option value="quarentena">Em quarentena</option><option value="todos">Todos</option>
          </Selecao>
          <div className="sm:col-span-4"><Botao type="submit" variante="secundario">Pesquisar</Botao></div>
        </form>
      </Cartao>

      <Cartao titulo={l ? `Resultados (${l.total.toLocaleString("pt-BR")})` : "Resultados"}>
        {!l ? <p className="text-suave" aria-busy="true">Carregando…</p> : l.itens.length === 0 ? <Vazio>Nenhum documento encontrado.</Vazio> : (
          <div className="flex flex-col gap-3">
            <ul className="divide-y divide-borda" aria-label="Documentos">
              {l.itens.map((d) => {
                const [rs, ts] = SITUACAO_DOC[d.situacao] ?? [d.situacao, "neutro"];
                return (
                  <li key={d.id} className="flex flex-col gap-1 py-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Link href={`/painel/documentos/${d.id}`} className="font-medium text-dourado hover:underline">{d.titulo}</Link>
                      <div className="flex flex-wrap gap-1">
                        <Selo tom="info">{d.categoria_rotulo ?? d.categoria}</Selo>
                        {d.situacao !== "ativo" && <Selo tom={ts}>{rs}</Selo>}
                        {d.sigiloso && <Selo tom="perigo">Sigiloso</Selo>}
                      </div>
                    </div>
                    <p className="text-xs text-suave">{ORIGEM[d.origem] ?? d.origem} · {dataHora(d.criado_em)}{d.versao_atual > 1 && ` · versão ${d.versao_atual}`}</p>
                    {d.trecho && <Trecho texto={d.trecho} />}
                  </li>
                );
              })}
            </ul>
            <Paginacao pagina={l.pagina} total={l.total} porPagina={l.por_pagina} aoMudar={(p) => filtrar({ pagina: String(p) })} />
          </div>
        )}
      </Cartao>
    </div>
  );
}
