"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { Editor } from "@/componentes/Editor";
import { Aviso, Botao, Campo, Cartao, Selo } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { SITUACAO_MODELO, type Modelo } from "@/lib/documentos";

type Detalhe = Modelo & { homologado_por: string | null; versoes: Modelo[]; pode_editar: boolean; pode_homologar: boolean };

export default function EditorModelo() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [m, setM] = useState<Detalhe | null>(null);
  const [campos, setCampos] = useState<{ campo: string; rotulo: string }[]>([]);
  const [ajudaManual, setAjudaManual] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [sujo, setSujo] = useState(false);
  const html = useRef<string>("");

  const carregar = useCallback(() => api<Detalhe>(`/modelos/${id}`).then((r) => { html.current = r.conteudo ?? ""; setM(r); setSujo(false); }).catch((e) => setErro(e.message)), [id]);
  useEffect(() => { carregar(); }, [carregar]);
  useEffect(() => { api<{ campos: { campo: string; rotulo: string }[]; manual: string }>("/modelos/campos").then((r) => { setCampos(r.campos); setAjudaManual(r.manual); }).catch(() => {}); }, []);

  async function salvar(form: HTMLFormElement | null) {
    setErro(null); setOk(null);
    const f = form ? new FormData(form) : null;
    try {
      const r = await enviar<Modelo>(`/modelos/${id}`, "PATCH", {
        conteudo: html.current, ...(f ? { titulo: String(f.get("titulo")).trim(), cabecalho: String(f.get("cabecalho") ?? "") || null, rodape: String(f.get("rodape") ?? "") || null } : {}),
      });
      if (r.id !== id) { setOk(`Criada a versão ${r.versao} em rascunho. A versão homologada continua em uso até a nova ser homologada.`); router.push(`/painel/modelos/${r.id}`); return; }
      setOk("Modelo salvo."); await carregar();
    } catch (x) { setErro((x as Error).message); }
  }

  async function agir(fn: () => Promise<unknown>, msg: string) {
    setErro(null); setOk(null);
    try { await fn(); setOk(msg); await carregar(); } catch (x) { setErro((x as Error).message); }
  }

  if (erro && !m) return <Aviso>{erro}</Aviso>;
  if (!m) return <p className="text-suave" aria-busy="true">Carregando…</p>;
  const [rs, ts] = SITUACAO_MODELO[m.situacao] ?? [m.situacao, "neutro"];
  const editavel = m.pode_editar && (m.situacao === "rascunho" || m.situacao === "homologado");
  return (
    <div className="flex flex-col gap-4">
      <div>
        <Link href="/painel/modelos" className="text-sm text-dourado hover:underline">← Modelos</Link>
        <h1 className="font-serif text-3xl font-semibold">{m.titulo}</h1>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-suave">
          <Selo tom={ts}>{rs}</Selo><span>versão {m.versao} · {m.categoria_rotulo}</span>
          {m.homologado_em && <span>homologado por {m.homologado_por} em {dataHora(m.homologado_em)}</span>}
        </div>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}
      {m.sugerido_pelo_sistema && m.situacao === "rascunho" && <Aviso tom="alerta">Modelo inicial sugerido pelo sistema. Confira o texto jurídico e homologue antes de usar.</Aviso>}
      {m.situacao === "homologado" && editavel && <Aviso tom="info">Este modelo está homologado. Ao salvar uma alteração, o sistema cria uma nova versão em rascunho; a atual continua valendo.</Aviso>}

      <div className="grid gap-4 xl:grid-cols-[1fr_18rem]">
        <form id="f-modelo" className="flex flex-col gap-3" onSubmit={(e) => { e.preventDefault(); salvar(e.currentTarget); }} aria-label="Modelo">
          <div className="grid gap-3 sm:grid-cols-3">
            <Campo id="m-titulo" name="titulo" rotulo="Título" defaultValue={m.titulo} required minLength={3} disabled={!editavel} />
            <Campo id="m-cab" name="cabecalho" rotulo="Cabeçalho" defaultValue={m.cabecalho ?? ""} disabled={!editavel} maxLength={500} />
            <Campo id="m-rod" name="rodape" rotulo="Rodapé" defaultValue={m.rodape ?? ""} disabled={!editavel} maxLength={500} ajuda="{{pagina}} vira o número da página" />
          </div>
          <Editor key={`${m.id}-${m.atualizado_em}`} inicial={m.conteudo ?? ""} rotulo="Texto do modelo" somenteLeitura={!editavel}
            campos={[...campos, { campo: "manual.nome_do_campo", rotulo: "Campo manual (renomeie)" }]}
            aoMudar={(h) => { html.current = h; setSujo(true); }} />
          {editavel && (
            <div className="flex flex-wrap gap-2">
              <Botao type="submit">{sujo ? "Salvar alterações" : "Salvar"}</Botao>
              {m.pode_homologar && m.situacao === "rascunho" && (
                <Botao type="button" variante="secundario" disabled={sujo} title={sujo ? "Salve antes de homologar" : undefined}
                  onClick={() => { if (window.confirm("Homologar este modelo? Ele passa a gerar documentos.")) agir(() => enviar(`/modelos/${id}/homologar`, "POST"), "Modelo homologado: já pode gerar minutas."); }}>
                  Homologar
                </Botao>
              )}
              <Botao type="button" variante="perigo" onClick={() => { if (window.confirm("Arquivar todas as versões deste modelo?")) agir(() => enviar(`/modelos/${id}/arquivar`, "POST"), "Modelo arquivado."); }}>Arquivar</Botao>
            </div>
          )}
        </form>
        <div className="flex flex-col gap-4">
          <Cartao titulo="Campos usados">
            {(m.campos ?? []).length === 0 ? <p className="text-sm text-suave">Nenhum campo.</p> : (
              <ul className="flex flex-col gap-1 text-sm">
                {m.campos!.map((c) => <li key={c.campo}><code className="text-xs">{`{{${c.campo}}}`}</code> <span className="text-suave">— {c.rotulo}</span></li>)}
              </ul>
            )}
            <p className="mt-3 text-xs text-suave">{ajudaManual}</p>
          </Cartao>
          <Cartao titulo="Versões">
            <ul className="flex flex-col gap-1 text-sm">
              {m.versoes.map((v) => (
                <li key={v.id} className="flex items-center justify-between gap-2">
                  {v.id === m.id ? <span className="font-medium">v{v.versao}</span> : <Link href={`/painel/modelos/${v.id}`} className="text-dourado hover:underline">v{v.versao}</Link>}
                  <Selo tom={(SITUACAO_MODELO[v.situacao] ?? ["", "neutro"])[1]}>{(SITUACAO_MODELO[v.situacao] ?? [v.situacao])[0]}</Selo>
                </li>
              ))}
            </ul>
          </Cartao>
        </div>
      </div>
    </div>
  );
}
