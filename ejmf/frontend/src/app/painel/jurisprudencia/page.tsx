"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { AreaTexto, Aviso, Botao, Campo, Cartao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { TOM_VERIFICACAO, type Colecao, type Julgado } from "@/lib/conhecimento";

type Lista = {
  itens: Julgado[]; verificacoes: Record<string, string>; colecoes: Colecao[]; fontes: { nome: string; dominios: string[] }[];
  pode_gerenciar: boolean; pode_homologar: boolean;
};

const data = (d: string | null) => (d ? new Date(d + "T12:00").toLocaleDateString("pt-BR") : "—");

export default function Jurisprudencia() {
  const params = useSearchParams();
  const [l, setL] = useState<Lista | null>(null);
  const [filtro, setFiltro] = useState({ q: "", verificacao: "", homologadas: false });
  const [aberto, setAberto] = useState<string | null>(params.get("id"));
  const [novo, setNovo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);
  const [ocupado, setOcupado] = useState<string | null>(null);

  useEffect(() => {
    const qs = new URLSearchParams();
    if (filtro.q) qs.set("q", filtro.q);
    if (filtro.verificacao) qs.set("verificacao", filtro.verificacao);
    if (filtro.homologadas) qs.set("homologadas", "true");
    const t = setTimeout(() => api<Lista>(`/jurisprudencia?${qs}`).then(setL).catch((e) => setErro(e.message)), 200);
    return () => clearTimeout(t);
  }, [filtro, versao]);

  async function cadastrar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const t = (k: string) => String(f.get(k) ?? "").trim() || null;
    setErro(null); setOk(null);
    try {
      const j = await enviar<Julgado>("/jurisprudencia", "POST", {
        tribunal: t("tribunal"), numero: t("numero"), classe: t("classe"), orgao_julgador: t("orgao"), relator: t("relator"),
        data_julgamento: t("julgamento"), data_publicacao: t("publicacao"), ementa: t("ementa"), url_original: t("url"),
      });
      setOk("Julgado cadastrado como pendente. Peça a verificação no original.");
      setNovo(false); setAberto(j.id); setVersao((v) => v + 1);
    } catch (x) { setErro((x as Error).message); }
  }

  async function acao(j: Julgado, caminho: string, msg: (r: Julgado) => string, corpo?: unknown) {
    setErro(null); setOk(null); setOcupado(j.id);
    try {
      const r = await enviar<Julgado>(`/jurisprudencia/${j.id}/${caminho}`, "POST", corpo);
      setOk(msg(r)); setVersao((v) => v + 1);
    } catch (x) { setErro((x as Error).message); }
    setOcupado(null);
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link href="/painel/conhecimento" className="text-sm text-dourado hover:underline">← Pesquisa</Link>
          <h1 className="font-serif text-3xl font-semibold">Jurisprudência</h1>
          <p className="text-sm text-suave">Só julgado conferido no site oficial do tribunal e homologado pelo advogado pode ser citado em documento.</p>
        </div>
        {l?.pode_gerenciar && <Botao onClick={() => setNovo((v) => !v)} aria-expanded={novo}>{novo ? "Fechar" : "Novo julgado"}</Botao>}
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}

      {novo && l && (
        <Cartao titulo="Novo julgado">
          <form onSubmit={cadastrar} className="grid gap-3 sm:grid-cols-3" aria-label="Novo julgado">
            <Campo id="nj-tribunal" name="tribunal" rotulo="Tribunal (sigla)" required placeholder="TST" pattern="[A-Za-z0-9]+" maxLength={20} />
            <Campo id="nj-numero" name="numero" rotulo="Número do processo" required minLength={3} maxLength={120} />
            <Campo id="nj-classe" name="classe" rotulo="Classe (ex.: RR, REsp)" maxLength={120} />
            <Campo id="nj-orgao" name="orgao" rotulo="Órgão julgador" maxLength={200} />
            <Campo id="nj-relator" name="relator" rotulo="Relator(a)" maxLength={200} />
            <div className="grid grid-cols-2 gap-2">
              <Campo id="nj-julg" name="julgamento" type="date" rotulo="Julgamento" />
              <Campo id="nj-pub" name="publicacao" type="date" rotulo="Publicação" />
            </div>
            <div className="sm:col-span-3"><AreaTexto id="nj-ementa" name="ementa" rotulo="Ementa (completa, como está no original)" required minLength={20} rows={5} /></div>
            <div className="sm:col-span-3">
              <Campo id="nj-url" name="url" type="url" rotulo="Endereço do original no site oficial do tribunal" maxLength={1000}
                ajuda={`Domínios aceitos: ${l.fontes.flatMap((f) => f.dominios).join(", ")}`} />
            </div>
            <div className="sm:col-span-3"><Botao type="submit">Cadastrar</Botao></div>
          </form>
        </Cartao>
      )}

      <Cartao titulo="Julgados">
        <div className="mb-3 grid gap-2 sm:grid-cols-3">
          <input aria-label="Filtrar julgados" type="search" placeholder="Número, relator ou palavra da ementa" value={filtro.q}
            onChange={(e) => setFiltro((f) => ({ ...f, q: e.target.value }))} className="rounded-md border border-borda bg-superficie px-3 py-2 text-sm" />
          <select aria-label="Verificação" value={filtro.verificacao} onChange={(e) => setFiltro((f) => ({ ...f, verificacao: e.target.value }))} className="rounded-md border border-borda bg-superficie px-2 py-2 text-sm">
            <option value="">Qualquer verificação</option>
            {l && Object.entries(l.verificacoes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={filtro.homologadas} onChange={(e) => setFiltro((f) => ({ ...f, homologadas: e.target.checked }))} /> Só homologados</label>
        </div>
        {!l ? <p className="text-suave" aria-busy="true">Carregando…</p> : l.itens.length === 0 ? <Vazio>Nenhum julgado.</Vazio> : (
          <ul className="divide-y divide-borda" aria-label="Lista de julgados">
            {l.itens.map((j) => {
              const det = j.verificacao_detalhe;
              return (
                <li key={j.id} className="py-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <button className="text-left font-medium text-dourado hover:underline" aria-expanded={aberto === j.id} onClick={() => setAberto((a) => (a === j.id ? null : j.id))}>
                      {j.favorito ? "★ " : ""}{j.rotulo}
                    </button>
                    <div className="flex flex-wrap gap-1">
                      <Selo tom={TOM_VERIFICACAO[j.verificacao] ?? "neutro"}>{j.verificacao_rotulo}</Selo>
                      {j.homologada_em ? <Selo tom="ok">Homologado</Selo> : <Selo>Não homologado</Selo>}
                      {j.origem === "sugestao_ia" && <Selo tom="info">Sugerido por IA</Selo>}
                    </div>
                  </div>
                  <p className="line-clamp-2 text-sm text-suave">{j.ementa}</p>
                  {aberto === j.id && (
                    <div className="mt-2 flex flex-col gap-2 rounded-md border border-borda p-3 text-sm">
                      <p className="whitespace-pre-wrap font-serif">{j.ementa}</p>
                      <dl className="grid gap-1 sm:grid-cols-2">
                        <div><dt className="inline text-suave">Órgão julgador: </dt><dd className="inline">{j.orgao_julgador ?? "—"}</dd></div>
                        <div><dt className="inline text-suave">Julgamento / publicação: </dt><dd className="inline">{data(j.data_julgamento)} / {data(j.data_publicacao)}</dd></div>
                        <div className="sm:col-span-2 break-all"><dt className="inline text-suave">Original: </dt><dd className="inline">{j.url_original ? <a className="text-dourado underline" href={j.url_original} target="_blank" rel="noopener noreferrer">{j.url_original}</a> : "não informado"}</dd></div>
                        <div><dt className="inline text-suave">Consultado em: </dt><dd className="inline">{dataHora(j.consultado_em)}</dd></div>
                        <div><dt className="inline text-suave">Homologado: </dt><dd className="inline">{j.homologada_em ? `${j.homologada_por ?? "—"} em ${dataHora(j.homologada_em)}` : "não"}</dd></div>
                      </dl>
                      <p role="status" className="rounded-md bg-superficie-2 px-2 py-1 text-xs">
                        Verificação: {det.motivo ?? j.verificacao_rotulo}
                        {det.cobertura_ementa !== undefined && ` · ementa encontrada: ${Math.round(det.cobertura_ementa * 100)}%`}
                        {det.numero !== undefined && ` · número ${det.numero ? "confere" : "não encontrado"}`}
                        {det.relator !== undefined && ` · relator ${det.relator ? "confere" : "não confere"}`}
                        {det.data_julgamento !== undefined && ` · data ${det.data_julgamento ? "confere" : "não confere"}`}
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {l.pode_gerenciar && <Botao variante="secundario" disabled={ocupado === j.id} onClick={() => acao(j, "verificar", (r) => `Resultado: ${r.verificacao_rotulo}`)}>Verificar no original</Botao>}
                        {l.pode_homologar && j.verificacao === "verificada" && !j.homologada_em &&
                          <Botao disabled={ocupado === j.id} onClick={() => acao(j, "homologar", () => "Julgado homologado")}>Homologar</Botao>}
                        <Botao variante="secundario" onClick={() => enviar("/conhecimento/favoritos", "POST", { tipo: "jurisprudencia", ref_id: j.id, favorito: !j.favorito }).then(() => setVersao((v) => v + 1))}>
                          {j.favorito ? "Tirar dos favoritos" : "Favoritar"}
                        </Botao>
                        {l.pode_gerenciar && <Botao variante="perigo" onClick={() => { const m = window.prompt("Motivo do descarte"); if (m) acao(j, "descartar", () => "Julgado descartado", { motivo: m }); }}>Descartar</Botao>}
                      </div>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </Cartao>
    </div>
  );
}
