"use client";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { useEu } from "@/componentes/CascoPainel";
import { AreaTexto, Aviso, Botao, Campo, Cartao, Selecao, Selo, Vazio } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { ROTULO_PRIORIDADE } from "@/lib/rotulos";
import type { Pendencia } from "@/lib/tipos";

type Resposta = { contagem: Record<string, number>; classes: Record<string, string>; adiadas: number; criterios: Record<string, unknown>; itens: Pendencia[] };
type Pessoa = { id: string; nome: string };

const ORDEM = ["atencao_imediata", "com_falha", "alta", "aguardando_aprovacao", "normal", "aguardando_informacoes",
  "aguardando_cliente", "aguardando_terceiros", "automatizada", "concluida"];

const ACOES: [string, string, "texto" | "quando" | "pessoa" | null][] = [
  ["reagendar", "Adiar / reagendar", "quando"], ["delegar", "Delegar a uma pessoa", "pessoa"],
  ["solicitar_informacoes", "Solicitar informações", "texto"], ["aguardar_cliente", "Aguardando cliente", "texto"],
  ["aguardar_terceiros", "Aguardando terceiros", "texto"], ["devolver", "Devolver", "texto"],
  ["delegar_funcao_virtual", "Delegar a função virtual", null], ["concluir", "Concluir", "texto"],
];

export default function Prioridades() {
  const { eu } = useEu();
  const pode = eu.permissoes.includes("prioridades:gerenciar");
  const router = useRouter();
  const caminho = usePathname();
  const params = useSearchParams();
  const classe = params.get("classe") ?? "";
  const meus = params.get("meus") === "1";
  const [dados, setDados] = useState<Resposta | null>(null);
  const [pessoas, setPessoas] = useState<Pessoa[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);
  const [aberto, setAberto] = useState<string | null>(null);
  const [novo, setNovo] = useState(false);

  useEffect(() => {
    const qs = new URLSearchParams();
    if (classe) qs.set("classe", classe);
    if (meus) qs.set("meus", "true");
    api<Resposta>(`/prioridades?${qs}`).then(setDados).catch((e) => setErro(e.message));
  }, [classe, meus, versao]);
  useEffect(() => { if (pode) api<Pessoa[]>("/agenda/pessoas").then(setPessoas).catch(() => {}); }, [pode]);

  const ir = (k: string, v: string | null) => {
    const qs = new URLSearchParams(params.toString());
    if (v) qs.set(k, v); else qs.delete(k);
    router.push(`${caminho}?${qs}`);
  };
  async function agir(p: Pendencia, corpo: Record<string, unknown>, msg: string) {
    setErro(null); setOk(null);
    try { await enviar(`/prioridades/${p.id}/acao`, "POST", corpo); setOk(msg); setAberto(null); setVersao((v) => v + 1); }
    catch (x) { setErro((x as Error).message); }
  }
  async function criar(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const prazo = f.get("prazo") as string;
    setErro(null); setOk(null);
    try {
      await enviar("/prioridades", "POST", { titulo: f.get("titulo"), descricao: f.get("descricao") || null,
        prazo_em: prazo ? `${prazo}:00-03:00` : null, responsavel_id: f.get("responsavel") || null });
      setOk("Pendência criada."); setNovo(false); setVersao((v) => v + 1);
    } catch (x) { setErro((x as Error).message); }
  }
  const total = dados ? Object.entries(dados.contagem).filter(([k]) => k !== "concluida").reduce((s, [, n]) => s + n, 0) : 0;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-3xl font-semibold">Central de prioridades</h1>
          <p className="text-sm text-suave">Itens gerados a partir de prazos, publicações, audiências, conflitos, falhas e aprovações, mais as pendências criadas pela equipe. Cada item mostra por que está nessa posição. Item crítico não pode ser adiado.</p>
        </div>
        {pode && <Botao onClick={() => setNovo(!novo)}>{novo ? "Fechar" : "Nova pendência"}</Botao>}
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}
      {novo && (
        <Cartao titulo="Nova pendência">
          <form aria-label="Nova pendência" onSubmit={criar} className="grid gap-3 sm:grid-cols-2">
            <div className="sm:col-span-2"><Campo id="pd-titulo" name="titulo" rotulo="Título" required minLength={3} /></div>
            <div className="sm:col-span-2"><AreaTexto id="pd-desc" name="descricao" rotulo="Descrição (opcional)" rows={2} /></div>
            <Campo id="pd-prazo" name="prazo" type="datetime-local" rotulo="Fazer até (opcional)" />
            <Selecao id="pd-resp" name="responsavel" rotulo="Responsável" defaultValue={eu.id}>
              <option value="">Sem responsável</option>
              {pessoas.map((p) => <option key={p.id} value={p.id}>{p.nome}</option>)}
            </Selecao>
            <div><Botao type="submit">Criar pendência</Botao></div>
          </form>
        </Cartao>
      )}

      <div className="flex flex-wrap items-center gap-2" role="tablist" aria-label="Classe de prioridade">
        <button role="tab" aria-selected={!classe} onClick={() => ir("classe", null)}
          className={`rounded-full border px-3 py-1 text-sm ${!classe ? "border-dourado bg-dourado/10 font-medium" : "border-borda hover:bg-superficie-2"}`}>
          Em aberto{total ? ` (${total})` : ""}
        </button>
        {ORDEM.map((c) => {
          const n = dados?.contagem[c];
          if (!n && classe !== c) return null;
          return (
            <button key={c} role="tab" aria-selected={classe === c} onClick={() => ir("classe", c)} data-classe={c}
              className={`rounded-full border px-3 py-1 text-sm ${classe === c ? "border-dourado bg-dourado/10 font-medium" : "border-borda hover:bg-superficie-2"}`}>
              {ROTULO_PRIORIDADE[c]?.[0] ?? c}{n ? ` (${n})` : ""}
            </button>
          );
        })}
        <label className="ml-auto flex items-center gap-2 text-sm"><input type="checkbox" checked={meus} onChange={(e) => ir("meus", e.target.checked ? "1" : null)} />Só os meus</label>
      </div>
      {dados && dados.adiadas > 0 && <p className="text-xs text-suave">{dados.adiadas} item(ns) adiado(s) não aparecem até a nova data.</p>}

      <Cartao>
        {!dados ? <p className="text-suave" aria-busy="true">Carregando…</p> : dados.itens.length === 0 ? <Vazio>Nada nesta classe.</Vazio> : (
          <ul className="flex flex-col divide-y divide-borda">
            {dados.itens.map((p) => {
              const [rot, tom] = ROTULO_PRIORIDADE[p.classe] ?? [p.classe_rotulo, "neutro"];
              return (
                <li key={p.id} className="py-3" data-pendencia={p.tipo}>
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <Selo tom={tom}>{rot}</Selo>
                        {p.critica && <Selo tom="perigo">crítico</Selo>}
                        {p.origem === "manual" && <Selo>manual</Selo>}
                        {p.link ? <Link href={p.link} className="font-medium hover:underline">{p.titulo}</Link> : <span className="font-medium">{p.titulo}</span>}
                      </div>
                      {p.descricao && <p className="mt-1 text-sm text-suave">{p.descricao}</p>}
                      <p className="mt-1 text-xs text-suave" data-justificativa>Por quê: {p.justificativa.join("; ") || "—"}</p>
                      <p className="mt-1 text-xs text-suave">
                        {p.responsavel ? `Responsável: ${p.responsavel}` : "Sem responsável"}
                        {p.prazo_em && ` · até ${dataHora(p.prazo_em)}`}
                        {p.observacao && ` · ${p.observacao}`}
                        {p.resolucao && ` · ${p.resolucao}`}
                      </p>
                    </div>
                    {pode && (p.situacao === "concluida"
                      ? <Botao variante="secundario" onClick={() => agir(p, { acao: "reabrir" }, "Item reaberto.")}>Reabrir</Botao>
                      : <Botao variante="secundario" aria-expanded={aberto === p.id} onClick={() => setAberto(aberto === p.id ? null : p.id)}>Agir</Botao>)}
                  </div>
                  {aberto === p.id && <Acoes p={p} pessoas={pessoas} agir={agir} />}
                </li>
              );
            })}
          </ul>
        )}
      </Cartao>
    </div>
  );
}

function Acoes({ p, pessoas, agir }: { p: Pendencia; pessoas: Pessoa[]; agir: (p: Pendencia, c: Record<string, unknown>, m: string) => void }) {
  const disponiveis = ACOES.filter(([a]) => !(a === "concluir" && p.origem === "sistema") && !(a === "reagendar" && p.critica));
  const [acao, setAcao] = useState(disponiveis[0][0]);
  const campo = ACOES.find(([a]) => a === acao)?.[2];
  return (
    <form className="mt-3 grid gap-2 rounded-lg border border-borda bg-superficie-2 p-3 sm:grid-cols-3" aria-label="Ação na pendência"
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        const q = f.get("quando") as string | null;
        agir(p, { acao, texto: f.get("texto") || null, quando: q ? `${q}:00-03:00` : null, responsavel_id: f.get("pessoa") || null }, "Ação registrada.");
      }}>
      <Selecao id={`ac-${p.id}`} rotulo="Ação" value={acao} onChange={(e) => setAcao(e.target.value)}>
        {disponiveis.map(([a, r]) => <option key={a} value={a}>{r}</option>)}
      </Selecao>
      {campo === "quando" && <Campo id={`ac-q-${p.id}`} name="quando" type="datetime-local" rotulo="Nova data" required />}
      {campo === "pessoa" && <Selecao id={`ac-p-${p.id}`} name="pessoa" rotulo="Pessoa" required defaultValue="">
        <option value="" disabled>Escolha</option>{pessoas.map((x) => <option key={x.id} value={x.id}>{x.nome}</option>)}</Selecao>}
      {campo === "texto" && <Campo id={`ac-t-${p.id}`} name="texto" rotulo={acao === "concluir" ? "Como foi resolvido (opcional)" : "Explique"} required={acao !== "concluir"} />}
      {campo === null && <p className="text-xs text-suave sm:col-span-1">Funções virtuais (agentes) chegam na Fase 8.</p>}
      {p.origem === "sistema" && <p className="text-xs text-suave sm:col-span-3">Item automático: ele sai da lista sozinho quando a origem é resolvida.</p>}
      <div className="flex items-end"><Botao type="submit">Registrar</Botao></div>
    </form>
  );
}
