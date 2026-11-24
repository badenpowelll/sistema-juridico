"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { Aviso, Botao, Campo, Cartao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { SITUACAO_MODELO, type Modelo } from "@/lib/documentos";

type Lista = { itens: Modelo[]; categorias: Record<string, string>; aviso_inicial: string };

function codigoDe(titulo: string) {
  return titulo.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "").replace(/^(\d)/, "m_$1").slice(0, 50);
}

export default function Modelos() {
  const { eu } = useEu();
  const router = useRouter();
  const pode = eu.permissoes.includes("modelos:gerenciar");
  const [l, setL] = useState<Lista | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [novo, setNovo] = useState(false);
  const [arquivados, setArquivados] = useState(false);
  const [versao, setVersao] = useState(0);

  useEffect(() => { api<Lista>(`/modelos${arquivados ? "?incluir_arquivados=true" : ""}`).then(setL).catch((e) => setErro(e.message)); }, [arquivados, versao]);

  async function criar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const titulo = String(f.get("titulo") ?? "").trim();
    setErro(null);
    try {
      const m = await enviar<Modelo>("/modelos", "POST", {
        codigo: `${codigoDe(titulo).slice(0, 44) || "modelo"}_${Date.now().toString(36).slice(-5)}`, titulo, categoria: f.get("categoria"),
        conteudo: `<h2 style="text-align: center">${titulo.toUpperCase().replace(/[<>&]/g, "")}</h2><p>Escreva o texto do modelo aqui.</p>`,
        rodape: "Página {{pagina}}",
      });
      router.push(`/painel/modelos/${m.id}`);
    } catch (x) { setErro((x as Error).message); }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Link href="/painel/documentos" className="text-sm text-dourado hover:underline">← Documentos</Link>
          <h1 className="font-serif text-3xl font-semibold">Modelos</h1>
          <p className="text-sm text-suave">Só modelos homologados pelo advogado geram documentos. Os campos são preenchidos apenas com dados confirmados.</p>
        </div>
        {pode && <Botao onClick={() => setNovo((v) => !v)} aria-expanded={novo}>{novo ? "Fechar" : "Novo modelo"}</Botao>}
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {novo && pode && l && (
        <Cartao titulo="Novo modelo">
          <form onSubmit={criar} className="grid gap-3 sm:grid-cols-3" aria-label="Novo modelo">
            <div className="sm:col-span-2"><Campo id="nm-titulo" name="titulo" rotulo="Título" required minLength={3} maxLength={200} /></div>
            <Selecao id="nm-cat" name="categoria" rotulo="Categoria" defaultValue="outro">
              {Object.entries(l.categorias).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </Selecao>
            <div className="sm:col-span-3"><Botao type="submit">Criar e abrir o editor</Botao></div>
          </form>
        </Cartao>
      )}
      <Cartao titulo="Biblioteca" acao={<label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={arquivados} onChange={(e) => setArquivados(e.target.checked)} /> Mostrar arquivados</label>}>
        {!l ? <p className="text-suave" aria-busy="true">Carregando…</p> : l.itens.length === 0 ? <Vazio>Nenhum modelo.</Vazio> : (
          <ul className="divide-y divide-borda" aria-label="Modelos">
            {l.itens.map((m) => {
              const [rs, ts] = SITUACAO_MODELO[m.situacao] ?? [m.situacao, "neutro"];
              return (
                <li key={m.codigo} className="flex flex-wrap items-center justify-between gap-2 py-3">
                  <div className="flex items-start gap-2">
                    <button aria-label={m.favorito ? `Tirar ${m.titulo} dos favoritos` : `Favoritar ${m.titulo}`} title="Favorito"
                      className={m.favorito ? "text-dourado" : "text-suave"}
                      onClick={() => enviar(`/modelos/${m.id}/favorito`, "POST", { favorito: !m.favorito }).then(() => setVersao((v) => v + 1)).catch((e) => setErro(e.message))}>
                      {m.favorito ? "★" : "☆"}
                    </button>
                    <div>
                      <Link href={`/painel/modelos/${m.id}`} className="font-medium text-dourado hover:underline">{m.titulo}</Link>
                      <p className="text-xs text-suave">{m.categoria_rotulo} · versão {m.versao}{m.versao_homologada && m.versao_homologada !== m.versao ? ` (em uso: v${m.versao_homologada})` : ""} · {dataHora(m.atualizado_em)}</p>
                      {m.sugerido_pelo_sistema && m.situacao === "rascunho" && <p className="text-xs text-alerta">{l.aviso_inicial}</p>}
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <Selo tom={ts}>{rs}</Selo>
                    {m.versao_homologada && m.situacao !== "homologado" && <Selo tom="ok">v{m.versao_homologada} homologada</Selo>}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </Cartao>
    </div>
  );
}
