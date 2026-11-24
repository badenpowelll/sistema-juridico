"use client";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { AreaTexto, Aviso, Botao, Campo, Cartao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { AUTOR_MENSAGEM, ESTADO_CONVERSA, type Conversa, type MensagemConversa } from "@/lib/atendimento";

type Lista = { itens: Conversa[]; simulador: boolean; whatsapp_configurado: boolean; aguardando_equipe: number };
type Fio = Conversa & { mensagens: MensagemConversa[] };
const SITUACAO_MSG: Record<string, string> = { pendente: "na fila", enviada: "enviada", entregue: "entregue", lida: "lida", falha: "falhou", simulada: "simulada", recebida: "" };

export default function Conversas() {
  const { eu } = useEu();
  const router = useRouter();
  const caminho = usePathname();
  const params = useSearchParams();
  const selecionada = params.get("c");
  const filtro = params.get("estado") ?? "";
  const pode = eu.permissoes.includes("conversas:responder");
  const [lista, setLista] = useState<Lista | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);

  useEffect(() => {
    const buscar = () => api<Lista>(`/conversas${filtro ? `?estado=${filtro}` : ""}`).then(setLista).catch((e) => setErro(e.message));
    buscar();
    const t = setInterval(buscar, 15_000);
    return () => clearInterval(t);
  }, [filtro, versao]);

  const ir = (mud: Record<string, string | null>) => {
    const p = new URLSearchParams(params.toString());
    for (const [k, v] of Object.entries(mud)) { if (v) p.set(k, v); else p.delete(k); }
    router.replace(`${caminho}?${p}`);
  };

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-serif text-3xl font-semibold">Conversas</h1>
        <p className="text-sm text-suave">WhatsApp do escritório. A recepcionista virtual responde o básico, envia o link seguro e passa para a equipe quando precisa. Ela nunca informa dados de processo pelo chat.</p>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {lista && !lista.whatsapp_configurado && (
        <Aviso tom="alerta">WhatsApp Business aguardando credenciais: nenhuma mensagem real é enviada ou recebida. {lista.simulador ? "Use o simulador abaixo para testar com dados fictícios." : "Veja a página de Integrações."}</Aviso>
      )}
      {lista?.simulador && pode && <Simulador aoEnviar={(cid) => { setVersao((v) => v + 1); ir({ c: cid }); }} />}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <Cartao titulo={lista ? `Conversas${lista.aguardando_equipe ? ` (${lista.aguardando_equipe} não lidas com a equipe)` : ""}` : "Conversas"}>
          <nav aria-label="Filtrar conversas" className="mb-3 flex flex-wrap gap-2 text-xs">
            {[["", "Todas"], ["humano", "Com a equipe"], ["recepcionista", "Com a recepcionista"], ["encerrada", "Encerradas"]].map(([v, r]) => (
              <button key={v} aria-pressed={filtro === v} onClick={() => ir({ estado: v || null })}
                className={`rounded-full border px-3 py-1 ${filtro === v ? "border-dourado bg-dourado/10 text-dourado" : "border-borda text-suave"}`}>{r}</button>
            ))}
          </nav>
          {!lista ? <p className="text-suave" aria-busy="true">Carregando…</p> : lista.itens.length === 0 ? <Vazio>Nenhuma conversa.</Vazio> : (
            <ul className="flex flex-col divide-y divide-borda">
              {lista.itens.map((c) => { const [r, t] = ESTADO_CONVERSA[c.estado]; return (
                <li key={c.id}>
                  <button onClick={() => ir({ c: c.id })} aria-current={selecionada === c.id ? "true" : undefined} data-conversa={c.contato_id}
                    className={`w-full py-2 text-left ${selecionada === c.id ? "text-dourado" : ""}`}>
                    <div className="flex flex-wrap items-center gap-2"><span className="font-medium">{c.contato_nome ?? c.contato_id}</span>
                      {c.nao_lidas > 0 && <Selo tom="perigo">{c.nao_lidas}</Selo>}</div>
                    <div className="mt-1 flex flex-wrap gap-1"><Selo tom={t}>{r}</Selo>{c.simulado && <Selo tom="alerta">Simulado</Selo>}</div>
                    {c.ultima && <p className="mt-1 line-clamp-1 text-xs text-suave">{c.ultima.texto}</p>}
                  </button>
                </li>); })}
            </ul>
          )}
        </Cartao>
        {selecionada ? <FioConversa key={`${selecionada}-${versao}`} id={selecionada} pode={pode} aoMudar={() => setVersao((v) => v + 1)} />
          : <Cartao titulo="Conversa"><Vazio>Escolha uma conversa.</Vazio></Cartao>}
      </div>
    </div>
  );
}

function FioConversa({ id, pode, aoMudar }: { id: string; pode: boolean; aoMudar: () => void }) {
  const [f, setF] = useState<Fio | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const fim = useRef<HTMLDivElement>(null);
  const carregar = () => api<Fio>(`/conversas/${id}`).then(setF).catch((e) => setErro(e.message));
  useEffect(() => { carregar(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { fim.current?.scrollIntoView({ block: "nearest" }); }, [f?.mensagens.length]);

  async function acao(a: "assumir" | "devolver" | "encerrar") {
    setErro(null);
    try { await enviar(`/conversas/${id}/${a}`, "POST"); await carregar(); aoMudar(); } catch (x) { setErro((x as Error).message); }
  }
  async function responder(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    setErro(null);
    try { await enviar(`/conversas/${id}/mensagens`, "POST", { texto: String(new FormData(form).get("texto") ?? "") }); form.reset(); await carregar(); }
    catch (x) { setErro((x as Error).message); }
  }

  if (!f) return <Cartao titulo="Conversa">{erro ? <Aviso>{erro}</Aviso> : <p className="text-suave" aria-busy="true">Carregando…</p>}</Cartao>;
  const [r, t] = ESTADO_CONVERSA[f.estado];
  return (
    <Cartao titulo={f.contato_nome ?? f.contato_id} acao={<div className="flex flex-wrap gap-1"><Selo tom={t}>{r}</Selo>{f.simulado && <Selo tom="alerta">Simulado</Selo>}</div>}>
      <div className="mb-3 flex flex-wrap items-center gap-3 text-xs text-suave">
        <span className="font-mono">{f.contato_id}</span>
        {f.cliente_id && <Link href={`/painel/clientes/${f.cliente_id}`} className="text-dourado hover:underline">Ficha do cliente</Link>}
        {f.atendimento_id && <Link href={`/painel/atendimentos/${f.atendimento_id}`} className="text-dourado hover:underline">Atendimento</Link>}
        {f.motivo_transferencia && <span>Transferida: {f.motivo_transferencia}</span>}
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      <ol className="flex max-h-[28rem] flex-col gap-2 overflow-y-auto rounded-md bg-superficie-2 p-3" aria-label="Mensagens" data-fio>
        {f.mensagens.map((m) => (
          <li key={m.id} className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${m.direcao === "entrada" ? "self-start bg-superficie" : "self-end bg-marinho text-white"}`} data-autor={m.autor}>
            <p className="whitespace-pre-wrap">{m.texto || <em>({m.tipo})</em>}</p>
            <p className={`mt-1 text-[11px] ${m.direcao === "entrada" ? "text-suave" : "text-white/70"}`}>
              {m.autor === "equipe" ? m.usuario ?? "Equipe" : AUTOR_MENSAGEM[m.autor]} · {dataHora(m.criado_em)}{SITUACAO_MSG[m.situacao] && ` · ${SITUACAO_MSG[m.situacao]}`}
              {m.erro && ` · ${m.erro}`}
            </p>
          </li>
        ))}
        <div ref={fim} />
      </ol>
      {pode && (
        <>
          <div className="mt-3 flex flex-wrap gap-2">
            {f.estado !== "humano" && <Botao variante="secundario" onClick={() => acao("assumir")}>Assumir conversa</Botao>}
            {f.estado === "humano" && <Botao variante="secundario" onClick={() => acao("devolver")}>Devolver à recepcionista</Botao>}
            {f.estado !== "encerrada" && <Botao variante="perigo" onClick={() => acao("encerrar")}>Encerrar</Botao>}
          </div>
          {f.janela_aberta ? (
            <form onSubmit={responder} className="mt-3 flex flex-col gap-2" aria-label="Responder">
              <AreaTexto id="cv-texto" name="texto" rotulo="Sua resposta" required maxLength={4000} />
              <p className="text-xs text-suave">Responder assume a conversa: a recepcionista para de responder até você devolver.</p>
              <div><Botao type="submit">Enviar</Botao></div>
            </form>
          ) : <Aviso tom="alerta">Passaram mais de 24 horas desde a última mensagem do contato. O WhatsApp só permite modelos aprovados pela Meta, ainda não configurados.</Aviso>}
        </>
      )}
    </Cartao>
  );
}

function Simulador({ aoEnviar }: { aoEnviar: (conversaId: string) => void }) {
  const [erro, setErro] = useState<string | null>(null);
  async function simular(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const d = new FormData(form);
    setErro(null);
    try {
      const r = await enviar<{ conversa: Conversa }>("/simulador/whatsapp", "POST", {
        contato: String(d.get("contato") ?? "").replace(/\D/g, ""), nome: String(d.get("nome") ?? "").trim() || null, texto: String(d.get("texto") ?? ""),
      });
      (form.elements.namedItem("texto") as HTMLTextAreaElement).value = "";
      aoEnviar(r.conversa.id);
    } catch (x) { setErro((x as Error).message); }
  }
  return (
    <Cartao titulo={<span className="flex items-center gap-2">Simulador de WhatsApp <Selo tom="alerta">Simulado</Selo></span>}>
      <p className="mb-3 text-sm text-suave">Faz de conta que um contato escreveu. Use só dados fictícios. Nada sai do sistema.</p>
      {erro && <Aviso>{erro}</Aviso>}
      <form onSubmit={simular} className="grid gap-3 sm:grid-cols-[1fr_1fr_2fr_auto] sm:items-end" aria-label="Simular mensagem">
        <Campo id="sim-contato" name="contato" rotulo="Número fictício" inputMode="numeric" defaultValue="5584900000001" required minLength={8} maxLength={20} />
        <Campo id="sim-nome" name="nome" rotulo="Nome fictício" defaultValue="Contato de Teste" />
        <AreaTexto id="sim-texto" name="texto" rotulo="Mensagem do contato" required rows={1} />
        <Botao type="submit">Simular</Botao>
      </form>
    </Cartao>
  );
}
