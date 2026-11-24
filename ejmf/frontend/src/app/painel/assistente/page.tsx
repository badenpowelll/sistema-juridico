"use client";
import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Aviso, Botao, Cartao, Selo } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import type { Comando } from "@/lib/ia";

type Historico = { itens: Comando[]; exemplos: string[] };

function Itens({ itens }: { itens: Record<string, unknown>[] }) {
  return (
    <ul className="mt-2 flex flex-col gap-1 text-sm">
      {itens.slice(0, 10).map((x, i) => {
        const titulo = String(x.titulo ?? x.descricao ?? x.processo ?? x.nome ?? x.documento ?? x.resumo ?? x.tipo ?? "Item");
        const extra = [x.quando, x.vencimento, x.disponibilizada_em, x.tribunal, x.situacao, x.cliente].filter(Boolean).map(String).join(" · ");
        return (
          <li key={i}>{x.link ? <Link href={String(x.link)} className="hover:underline">{titulo}</Link> : titulo}
            {extra && <span className="text-xs text-suave"> · {extra}</span>}{x.simulada || x.simulado ? <> <Selo tom="alerta">Simulado</Selo></> : null}</li>
        );
      })}
    </ul>
  );
}

export default function Assistente() {
  const [h, setH] = useState<Historico | null>(null);
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);
  const fim = useRef<HTMLDivElement>(null);

  useEffect(() => { api<Historico>("/assistente").then(setH).catch((e) => setErro(e.message)); }, [versao]);
  useEffect(() => { fim.current?.scrollIntoView({ block: "end" }); }, [h]);

  async function mandar(t: string) {
    if (t.trim().length < 2) return;
    setErro(null); setEnviando(true);
    try { await enviar("/assistente", "POST", { texto: t }); setTexto(""); setVersao((v) => v + 1); }
    catch (x) { setErro((x as Error).message); } finally { setEnviando(false); }
  }

  async function decidir(id: string, acao: "confirmar" | "cancelar") {
    setErro(null);
    try { await enviar(`/assistente/${id}/${acao}`, "POST"); setVersao((v) => v + 1); } catch (x) { setErro((x as Error).message); }
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-serif text-3xl font-semibold">Assistente</h1>
        <p className="text-sm text-suave">Consultas com as suas permissões. O assistente não cancela, não envia, não assina, não paga e não agenda:
          ele mostra o que existe e aponta a tela certa. Criar uma pendência só acontece depois que você confirma.</p>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      <Cartao titulo="Conversa">
        <div className="flex max-h-[60vh] flex-col gap-3 overflow-y-auto" aria-live="polite" aria-label="Histórico do assistente">
          {!h ? <p className="text-suave" aria-busy="true">Carregando…</p> : h.itens.length === 0 ? (
            <p className="text-sm text-suave">Experimente um dos exemplos abaixo.</p>
          ) : h.itens.map((c) => (
            <div key={c.id} className="flex flex-col gap-1">
              <p className="self-end rounded-lg bg-marinho px-3 py-2 text-sm text-white">{c.texto}</p>
              <div className={`self-start rounded-lg border px-3 py-2 text-sm ${c.tipo === "recusado" ? "border-alerta/40 bg-alerta/5" : "border-borda bg-superficie-2"}`}>
                <p className="whitespace-pre-wrap">{c.resposta?.texto}</p>
                {c.resposta?.aviso && <p className="mt-1 text-xs text-suave">{c.resposta.aviso}</p>}
                {c.resposta?.itens && c.resposta.itens.length > 0 && <Itens itens={c.resposta.itens} />}
                {c.resposta?.fontes && c.resposta.fontes.length > 0 && <p className="mt-1 text-xs text-suave">Consultou: {c.resposta.fontes.map((f) => f.ferramenta).join(", ")}</p>}
                <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-suave">
                  {c.resposta?.origem && <span>Fonte: {c.resposta.origem}</span>}
                  {c.resposta?.ia && <Selo tom="dourado">Resposta de IA: confira</Selo>}
                  {c.resposta?.simulado && <Selo tom="alerta">Simulado</Selo>}
                  {c.resposta?.link && <Link className="text-dourado hover:underline" href={c.resposta.link}>Abrir tela</Link>}
                  {c.execucao_id && <Link className="hover:underline" href={`/painel/ia/execucoes/${c.execucao_id}`}>ver execução</Link>}
                  <span>{dataHora(c.criado_em)}</span>
                </div>
                {c.situacao === "aguardando_confirmacao" && (
                  <div className="mt-2 flex gap-2">
                    <Botao onClick={() => decidir(c.id, "confirmar")}>Confirmar</Botao>
                    <Botao variante="secundario" onClick={() => decidir(c.id, "cancelar")}>Cancelar</Botao>
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={fim} />
        </div>
        <form className="mt-4 flex gap-2" aria-label="Comando ao assistente" onSubmit={(e: FormEvent) => { e.preventDefault(); mandar(texto); }}>
          <input aria-label="Seu comando" value={texto} onChange={(e) => setTexto(e.target.value)} maxLength={2000} placeholder="Ex.: prazos dos próximos 7 dias"
            className="flex-1 rounded-md border border-borda bg-superficie px-3 py-2 text-sm" />
          <Botao type="submit" disabled={enviando || texto.trim().length < 2}>{enviando ? "…" : "Enviar"}</Botao>
        </form>
        {h && <div className="mt-3 flex flex-wrap gap-1" aria-label="Exemplos">{h.exemplos.map((x) => (
          <button key={x} type="button" onClick={() => mandar(x)} className="rounded-full border border-borda px-3 py-1 text-xs hover:bg-superficie-2">{x}</button>))}</div>}
      </Cartao>
    </div>
  );
}
