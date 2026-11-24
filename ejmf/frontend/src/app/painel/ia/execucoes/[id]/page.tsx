"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Aviso, Botao, Cartao, Selo } from "@/componentes/ui";
import { api, dataHora, enviar } from "@/lib/api";
import { dolar, ORIGEM, TOM_ESTADO, type Execucao, type Passo } from "@/lib/ia";

type Detalhe = Execucao & { passos: Passo[]; pode_cancelar: boolean; aplicavel: boolean };
type Saida = Record<string, unknown> & {
  aviso?: string | null; link?: string; resumo_ia?: string; resumo_regras?: string; destaques?: string[]; resposta?: string | null;
  lacunas?: string; citacoes?: { id: string; titulo: string; trecho: string; uso: string; link?: string; selo?: string }[]; citacoes_descartadas?: string[];
  sugestao?: { departamento: string; departamento_nome: string; assuntos: string[]; justificativa: string; confianca: string };
  audiencias?: { data: string; hora: string | null; tipo: string; modalidade: string; local: string | null; trecho: string }[];
  descartadas?: { data: string; hora: string | null; trecho: string; motivo: string }[];
  sugestoes?: { tipo: string; titulo: string; texto: string; trecho: string }[]; problemas?: string[];
  aplicado?: Record<string, unknown> & { por?: string; em?: string }; decisao?: Record<string, unknown> & { decisao?: string; por?: string; link?: string };
};
const TIPO_PASSO: Record<string, string> = { modelo: "Modelo", ferramenta: "Ferramenta", validacao: "Validação", aprovacao: "Aprovação",
  regra: "Regra", bloqueio: "Bloqueio" };

export default function DetalheExecucao() {
  const { id } = useParams<{ id: string }>();
  const [e, setE] = useState<Detalhe | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [versao, setVersao] = useState(0);
  const [escolhidas, setEscolhidas] = useState<number[]>([]);

  useEffect(() => { api<Detalhe>(`/ia/execucoes/${id}`).then(setE).catch((x) => setErro(x.message)); }, [id, versao]);

  async function fazer(fn: () => Promise<unknown>, msg: string) {
    setErro(null); setOk(null);
    try { await fn(); setOk(msg); setVersao((v) => v + 1); } catch (x) { setErro((x as Error).message); }
  }

  if (!e) return erro ? <Aviso>{erro}</Aviso> : <p className="text-suave" aria-busy="true">Carregando…</p>;
  const s = (e.saida ?? {}) as Saida;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Link href="/painel/ia/execucoes" className="text-sm text-dourado hover:underline">← Execuções</Link>
        <h1 className="font-serif text-3xl font-semibold">{e.numero}. {e.funcao_nome}</h1>
        <div className="mt-1 flex flex-wrap gap-1">
          <Selo tom={TOM_ESTADO[e.estado]}>{e.estado_rotulo}</Selo>{e.simulado && <Selo tom="alerta">Simulado: nenhum modelo real</Selo>}
          <Selo>{ORIGEM[e.origem] ?? e.origem}</Selo>
        </div>
      </div>
      {erro && <Aviso>{erro}</Aviso>}
      {ok && <Aviso tom="ok">{ok}</Aviso>}
      {e.erro && <Aviso tom={e.estado === "bloqueada" ? "alerta" : "perigo"}>{e.erro}</Aviso>}
      {s.aviso && <Aviso tom="info">{s.aviso}</Aviso>}

      <Cartao titulo="Resumo">
        <dl className="grid gap-2 text-sm sm:grid-cols-3">
          <div><dt className="text-suave">Pedida por</dt><dd>{e.solicitada_por ?? "—"} em {dataHora(e.criado_em)}</dd></div>
          <div><dt className="text-suave">Concluída</dt><dd>{dataHora(e.concluida_em)}</dd></div>
          <div><dt className="text-suave">Modelo</dt><dd>{e.modelo ?? "sem modelo"}{e.prompt_versao ? ` · instrução v${e.prompt_versao}` : ""}</dd></div>
          <div><dt className="text-suave">Tokens</dt><dd>{e.tokens_entrada} entrada · {e.tokens_saida} saída · {e.iteracoes} chamada(s)</dd></div>
          <div><dt className="text-suave">Custo</dt><dd>{dolar(e.custo, 6)}</dd></div>
          <div><dt className="text-suave">Tentativas</dt><dd>{e.tentativas}</dd></div>
        </dl>
        <div className="mt-3 flex flex-wrap gap-2">
          {s.link && <Link href={s.link} className="rounded-md border border-borda px-3 py-1.5 text-sm hover:bg-superficie-2">Abrir item</Link>}
          {e.aprovacao_id && <Link href="/painel/aprovacoes" className="rounded-md border border-borda px-3 py-1.5 text-sm hover:bg-superficie-2">Central de aprovações</Link>}
          {e.pode_cancelar && <Botao variante="perigo" onClick={() => { const m = window.prompt("Motivo do cancelamento"); if (m) fazer(() => enviar(`/ia/execucoes/${id}/cancelar`, "POST", { motivo: m }), "Execução cancelada"); }}>Cancelar</Botao>}
        </div>
      </Cartao>

      {(s.resumo_ia || s.resumo_regras) && (
        <Cartao titulo="Resultado">
          {s.resumo_ia && <><p className="text-xs font-semibold text-dourado">Redigido por IA (confira no relatório)</p><p className="whitespace-pre-wrap">{s.resumo_ia}</p>
            {!!s.destaques?.length && <ul className="mt-2 list-disc pl-5 text-sm">{s.destaques.map((d) => <li key={d}>{d}</li>)}</ul>}</>}
          {s.resumo_regras && <p className="mt-2 text-sm text-suave">Pelas regras: {s.resumo_regras}</p>}
        </Cartao>
      )}
      {s.sugestao && (
        <Cartao titulo="Sugestão de classificação">
          <p><strong>{s.sugestao.departamento_nome}</strong> <Selo>confiança {s.sugestao.confianca}</Selo></p>
          {!!s.sugestao.assuntos?.length && <p className="text-sm">Assuntos: {s.sugestao.assuntos.join(", ")}</p>}
          <p className="text-sm text-suave">{s.sugestao.justificativa}</p>
          {e.aplicavel && <div className="mt-2"><Botao onClick={() => fazer(() => enviar(`/ia/execucoes/${id}/aplicar`, "POST", {}), "Classificação aplicada")}>Aplicar ao processo</Botao></div>}
        </Cartao>
      )}
      {s.audiencias && (
        <Cartao titulo="Audiências encontradas">
          {s.audiencias.length === 0 ? <p className="text-sm text-suave">Nenhuma sustentada pelo texto.</p> : (
            <ul className="flex flex-col gap-2">{s.audiencias.map((a, i) => (
              <li key={i} className="text-sm"><strong>{a.data.split("-").reverse().join("/")}{a.hora ? ` às ${a.hora}` : ""}</strong> · {a.tipo} · {a.modalidade.replace("_", " ")}
                <blockquote className="mt-1 border-l-2 border-dourado pl-2 text-suave">“{a.trecho}”</blockquote></li>))}</ul>
          )}
          {!!s.descartadas?.length && <details className="mt-2 text-sm"><summary className="cursor-pointer text-suave">{s.descartadas.length} descartada(s) pela validação</summary>
            <ul className="mt-1 list-disc pl-5">{s.descartadas.map((d, i) => <li key={i}>{d.data} — {d.motivo}</li>)}</ul></details>}
        </Cartao>
      )}
      {s.resposta !== undefined && (
        <Cartao titulo="Resposta (rascunho)">
          {s.resposta ? <p className="whitespace-pre-wrap">{s.resposta}</p> : <p className="text-suave">Sem resposta.</p>}
          {s.lacunas && <p className="mt-2 text-sm text-suave">Lacunas: {s.lacunas}</p>}
          {!!s.citacoes?.length && <ul className="mt-3 flex flex-col gap-2" aria-label="Fontes citadas">{s.citacoes.map((c) => (
            <li key={c.id} className="text-sm">{c.link ? <Link href={c.link} className="font-medium hover:underline">{c.titulo}</Link> : <strong>{c.titulo}</strong>} {c.selo && <Selo>{c.selo}</Selo>}
              <p className="text-suave">“{c.trecho}”</p><p className="text-xs">Uso: {c.uso}</p></li>))}</ul>}
          {!!s.citacoes_descartadas?.length && <Aviso tom="alerta">{s.citacoes_descartadas.length} citação(ões) sem trecho correspondente foram descartadas.</Aviso>}
        </Cartao>
      )}
      {s.sugestoes && (
        <Cartao titulo="Sugestões de memória do cliente">
          {s.sugestoes.length === 0 ? <p className="text-sm text-suave">Nenhuma.</p> : (
            <ul className="flex flex-col gap-2">{s.sugestoes.map((m, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                {e.aplicavel && <input type="checkbox" aria-label={`Escolher ${m.titulo}`} checked={escolhidas.includes(i)}
                  onChange={(x) => setEscolhidas((v) => (x.target.checked ? [...v, i] : v.filter((y) => y !== i)))} />}
                <span><strong>{m.titulo}</strong> ({m.tipo}) — {m.texto}<br /><span className="text-suave">Trecho: “{m.trecho}”</span></span>
              </li>))}</ul>
          )}
          {e.aplicavel && <div className="mt-2"><Botao disabled={!escolhidas.length} onClick={() => fazer(() => enviar(`/ia/execucoes/${id}/aplicar`, "POST", { indices: escolhidas }), "Enviadas para a memória (a confirmar)")}>Enviar para a memória</Botao></div>}
        </Cartao>
      )}
      {s.problemas && (
        <Cartao titulo="Revisão estrutural">
          {s.problemas.length === 0 ? <p className="text-ok">Nenhum problema estrutural encontrado.</p> : <ul className="list-disc pl-5 text-sm">{s.problemas.map((p) => <li key={p}>{p}</li>)}</ul>}
        </Cartao>
      )}
      {s.aplicado && <Aviso tom="ok">Aplicado por {s.aplicado.por} em {dataHora(s.aplicado.em)}.</Aviso>}
      {s.decisao && <Aviso tom="info">Proposta {s.decisao.decisao} por {s.decisao.por}.{s.decisao.link && <> <Link className="underline" href={String(s.decisao.link)}>Abrir</Link></>}</Aviso>}

      <Cartao titulo="Passos">
        <ol className="flex flex-col gap-2" aria-label="Passos da execução">
          {e.passos.map((p) => (
            <li key={p.ordem} className="rounded-md border border-borda p-2 text-sm">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span><Selo tom={p.sucesso ? "neutro" : "perigo"}>{TIPO_PASSO[p.tipo] ?? p.tipo}</Selo> <span className="font-mono text-xs">{p.nome}</span></span>
                <span className="text-xs text-suave">{p.duracao_ms} ms{p.tokens_entrada ? ` · ${p.tokens_entrada}/${p.tokens_saida} tokens · ${dolar(p.custo, 6)}` : ""}</span>
              </div>
              <details className="mt-1"><summary className="cursor-pointer text-xs text-suave">Detalhes</summary>
                <pre className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-superficie-2 p-2 text-xs">{JSON.stringify({ parametros: p.parametros, resultado: p.resultado }, null, 2)}</pre></details>
            </li>
          ))}
        </ol>
      </Cartao>
    </div>
  );
}
