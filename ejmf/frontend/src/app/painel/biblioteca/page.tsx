"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { AreaTexto, Aviso, Botao, Campo, Cartao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { TOM_VIGENCIA, type Colecao, type ItemBiblioteca } from "@/lib/conhecimento";

type Lista = {
  itens: ItemBiblioteca[]; tipos: Record<string, string>; licencas: Record<string, string>; vigencias: Record<string, string>;
  colecoes: Colecao[]; pode_gerenciar: boolean; pode_conferir: boolean;
};
type RegistroLexml = { urn: string; titulo: string; data: string | null; tipo_documento: string | null; autoridade: string | null; ementa: string | null; assunto: string | null; url: string };

export default function Biblioteca() {
  const router = useRouter();
  const [l, setL] = useState<Lista | null>(null);
  const [filtro, setFiltro] = useState({ q: "", tipo: "", colecao_id: "", alerta: false, favoritos: false });
  const [painel, setPainel] = useState<"" | "novo" | "lexml" | "colecao">("");
  const [lexml, setLexml] = useState<{ disponivel: boolean; erro?: string; total: number; itens: RegistroLexml[] } | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);

  useEffect(() => {
    const qs = new URLSearchParams();
    if (filtro.q) qs.set("q", filtro.q);
    if (filtro.tipo) qs.set("tipo", filtro.tipo);
    if (filtro.colecao_id) qs.set("colecao_id", filtro.colecao_id);
    if (filtro.alerta) qs.set("alerta", "true");
    if (filtro.favoritos) qs.set("favoritos", "true");
    const t = setTimeout(() => api<Lista>(`/biblioteca?${qs}`).then(setL).catch((e) => setErro(e.message)), 200);
    return () => clearTimeout(t);
  }, [filtro, versao]);

  async function criar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const txt = (k: string) => String(f.get(k) ?? "").trim() || null;
    setErro(null);
    try {
      const i = await enviar<ItemBiblioteca>("/biblioteca", "POST", {
        tipo: f.get("tipo"), titulo: txt("titulo"), identificador: txt("identificador"), url_origem: txt("url_origem"),
        licenca: f.get("licenca") || null, monitorar: f.get("monitorar") === "on", ementa: txt("ementa"), texto: txt("texto"),
      });
      router.push(`/painel/biblioteca/${i.id}`);
    } catch (x) { setErro((x as Error).message); }
  }

  async function buscarLexml(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const q = String(new FormData(e.currentTarget).get("q") ?? "").trim();
    setErro(null);
    try { setLexml(await api(`/biblioteca/lexml?q=${encodeURIComponent(q)}`)); } catch (x) { setErro((x as Error).message); }
  }

  async function importar(r: RegistroLexml) {
    setErro(null);
    try {
      const i = await enviar<ItemBiblioteca>("/biblioteca/lexml", "POST", r);
      router.push(`/painel/biblioteca/${i.id}`);
    } catch (x) { setErro((x as Error).message); }
  }

  async function criarColecao(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setErro(null);
    try {
      await enviar("/conhecimento/colecoes", "POST", { nome: f.get("nome"), descricao: String(f.get("descricao") ?? "").trim() || null });
      setOk("Coleção criada");
      setPainel("");
      setVersao((v) => v + 1);
    } catch (x) { setErro((x as Error).message); }
  }

  const alternar = (p: typeof painel) => setPainel((x) => (x === p ? "" : p));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link href="/painel/conhecimento" className="text-sm text-dourado hover:underline">← Pesquisa</Link>
          <h1 className="font-serif text-3xl font-semibold">Biblioteca</h1>
          <p className="text-sm text-suave">Normas, súmulas, temas, doutrina licenciada e materiais internos, com versões, vigência conferida e origem de cada texto.</p>
        </div>
        {l?.pode_gerenciar && (
          <div className="flex flex-wrap gap-2">
            <Botao onClick={() => alternar("novo")} aria-expanded={painel === "novo"}>Novo item</Botao>
            <Botao variante="secundario" onClick={() => alternar("lexml")} aria-expanded={painel === "lexml"}>Buscar no LexML</Botao>
            <Botao variante="secundario" onClick={() => alternar("colecao")} aria-expanded={painel === "colecao"}>Nova coleção</Botao>
          </div>
        )}
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}

      {painel === "novo" && l && (
        <Cartao titulo="Novo item">
          <form onSubmit={criar} className="grid gap-3 sm:grid-cols-2" aria-label="Novo item da biblioteca">
            <Selecao id="nb-tipo" name="tipo" rotulo="Tipo" defaultValue="lei">
              {Object.entries(l.tipos).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Selecao>
            <Selecao id="nb-licenca" name="licenca" rotulo="Licença do texto" defaultValue="">
              <option value="">Automática (pública ou interna)</option>
              {Object.entries(l.licencas).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Selecao>
            <div className="sm:col-span-2"><Campo id="nb-titulo" name="titulo" rotulo="Título" required minLength={3} maxLength={400} /></div>
            <Campo id="nb-ident" name="identificador" rotulo="Identificação (ex.: Lei 13.467/2017)" maxLength={200} />
            <Campo id="nb-url" name="url_origem" rotulo="Endereço oficial (HTTPS)" type="url" maxLength={1000} placeholder="https://www.planalto.gov.br/…" />
            <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" name="monitorar" /> Monitorar a fonte oficial todos os dias</label>
            <div className="sm:col-span-2"><AreaTexto id="nb-ementa" name="ementa" rotulo="Ementa ou descrição (opcional)" maxLength={5000} /></div>
            <div className="sm:col-span-2"><AreaTexto id="nb-texto" name="texto" rotulo="Texto (opcional; nunca cole obra protegida sem licença)" rows={6} /></div>
            <div className="sm:col-span-2"><Botao type="submit">Cadastrar</Botao></div>
          </form>
        </Cartao>
      )}

      {painel === "lexml" && (
        <Cartao titulo="Buscar norma no LexML">
          <form onSubmit={buscarLexml} className="flex flex-wrap items-end gap-2" aria-label="Buscar no LexML">
            <div className="min-w-64 flex-1"><Campo id="lx-q" name="q" rotulo="Palavras do título ou número" required minLength={2} /></div>
            <Botao type="submit">Buscar</Botao>
          </form>
          {lexml && !lexml.disponivel && <div className="mt-3"><Aviso tom="alerta">LexML indisponível agora: {lexml.erro}</Aviso></div>}
          {lexml?.disponivel && (
            lexml.itens.length === 0 ? <div className="mt-3"><Vazio>Nada encontrado.</Vazio></div> : (
              <ul className="mt-3 divide-y divide-borda" aria-label="Resultados do LexML">
                {lexml.itens.map((r) => (
                  <li key={r.urn} className="flex flex-wrap items-center justify-between gap-2 py-2">
                    <div>
                      <p className="font-medium">{r.titulo}</p>
                      <p className="text-xs text-suave">{r.tipo_documento} · {r.data} · {r.urn}</p>
                      {r.ementa && <p className="text-sm text-suave">{r.ementa}</p>}
                    </div>
                    <Botao variante="secundario" onClick={() => importar(r)}>Importar</Botao>
                  </li>
                ))}
              </ul>
            ))}
        </Cartao>
      )}

      {painel === "colecao" && (
        <Cartao titulo="Nova coleção">
          <form onSubmit={criarColecao} className="grid gap-3 sm:grid-cols-2" aria-label="Nova coleção">
            <Campo id="nc-nome" name="nome" rotulo="Nome da coleção" required minLength={3} maxLength={200} />
            <Campo id="nc-desc" name="descricao" rotulo="Descrição (opcional)" maxLength={2000} />
            <div><Botao type="submit">Criar coleção</Botao></div>
          </form>
        </Cartao>
      )}

      <Cartao titulo="Acervo" acao={l && <span className="text-xs text-suave">{l.itens.length} item(ns)</span>}>
        <div className="mb-3 grid gap-2 sm:grid-cols-4">
          <input aria-label="Filtrar por título" type="search" placeholder="Filtrar por título ou número" value={filtro.q}
            onChange={(e) => setFiltro((f) => ({ ...f, q: e.target.value }))} className="rounded-md border border-borda bg-superficie px-3 py-2 text-sm" />
          <select aria-label="Filtrar por tipo" value={filtro.tipo} onChange={(e) => setFiltro((f) => ({ ...f, tipo: e.target.value }))} className="rounded-md border border-borda bg-superficie px-2 py-2 text-sm">
            <option value="">Todos os tipos</option>
            {l && Object.entries(l.tipos).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select aria-label="Filtrar por coleção" value={filtro.colecao_id} onChange={(e) => setFiltro((f) => ({ ...f, colecao_id: e.target.value }))} className="rounded-md border border-borda bg-superficie px-2 py-2 text-sm">
            <option value="">Todas as coleções</option>
            {l?.colecoes.map((c) => <option key={c.id} value={c.id}>{c.nome} ({c.itens})</option>)}
          </select>
          <div className="flex items-center gap-3 text-sm">
            <label className="flex items-center gap-1"><input type="checkbox" checked={filtro.alerta} onChange={(e) => setFiltro((f) => ({ ...f, alerta: e.target.checked }))} /> Com alerta</label>
            <label className="flex items-center gap-1"><input type="checkbox" checked={filtro.favoritos} onChange={(e) => setFiltro((f) => ({ ...f, favoritos: e.target.checked }))} /> Favoritos</label>
          </div>
        </div>
        {!l ? <p className="text-suave" aria-busy="true">Carregando…</p> : l.itens.length === 0 ? <Vazio>Nenhum item.</Vazio> : (
          <ul className="divide-y divide-borda" aria-label="Itens da biblioteca">
            {l.itens.map((i) => (
              <li key={i.id} className="flex flex-wrap items-start justify-between gap-2 py-3">
                <div className="min-w-0 flex-1">
                  <Link href={`/painel/biblioteca/${i.id}`} className="font-medium text-dourado hover:underline">{i.favorito ? "★ " : ""}{i.titulo}</Link>
                  <p className="text-xs text-suave">{i.tipo_rotulo}{i.identificador ? ` · ${i.identificador}` : ""} · {i.versao_atual ? `versão ${i.versao_atual}, coletada em ${dataHora(i.coletado_em)}` : "sem texto"}{i.monitorar ? " · monitorado" : ""}</p>
                  {i.alertas.length > 0 && <p className="text-xs text-alerta">{i.alertas.join(" · ")}</p>}
                </div>
                <div className="flex gap-1">
                  <Selo tom={TOM_VIGENCIA[i.vigencia] ?? "neutro"}>{i.vigencia_rotulo}</Selo>
                  {i.situacao === "alteracao_a_conferir" && <Selo tom="alerta">Versão nova a conferir</Selo>}
                  {i.licenca === "referencia" && <Selo>Só referência</Selo>}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Cartao>
    </div>
  );
}
