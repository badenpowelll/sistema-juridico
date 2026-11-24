"use client";
import Link from "next/link";
import { reais } from "@/lib/financeiro";
import { useParams } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { Aviso, Cartao, Selo } from "@/componentes/ui";
import { api, dataHora } from "@/lib/api";
import { dataCurta, horaLocal } from "@/lib/rotulos";
import type { Relatorio } from "@/lib/tipos";

type PzR = { id: string; descricao: string; processo: string; vencimento: string | null; confirmado: boolean; link: string; conclusao?: string | null };
type CpR = { id: string; tipo_rotulo: string; titulo: string; inicio: string; dia_inteiro: boolean; local: string | null; processo?: string | null; resultado?: string | null };
const ESTADO: Record<string, string> = { entregue: "entregue", aguardando_credenciais: "aguardando credenciais", nao_implementada: "não implementada",
  aguardando_autorizacao: "aguardando autorização", ambiente_testes: "em testes (sem envio)", implementada_validada: "validada", indisponivel: "indisponível" };

function Prazos({ itens, vazio }: { itens: PzR[]; vazio: string }) {
  if (!itens?.length) return <p className="text-sm text-suave">{vazio}</p>;
  return <ul className="flex flex-col gap-1 text-sm">{itens.map((p) => (
    <li key={p.id}><Link href={p.link} className="hover:underline">{p.descricao}</Link> <span className="font-mono text-xs text-suave">{p.processo} · {dataCurta(p.vencimento)}</span>
      {" "}{p.confirmado ? <Selo tom="ok">homologado</Selo> : <Selo tom="alerta">não confirmado</Selo>}{p.conclusao && <span className="text-xs text-suave"> — {p.conclusao}</span>}</li>))}</ul>;
}
function Comps({ itens, vazio }: { itens: CpR[]; vazio: string }) {
  if (!itens?.length) return <p className="text-sm text-suave">{vazio}</p>;
  return <ul className="flex flex-col gap-1 text-sm">{itens.map((c) => (
    <li key={c.id}><span className="font-mono text-xs">{c.dia_inteiro ? "dia todo" : horaLocal(c.inicio)}</span> <Link href={`/painel/agenda?compromisso=${c.id}`} className="hover:underline">{c.titulo}</Link>
      <span className="text-xs text-suave"> · {c.tipo_rotulo}{c.local && ` · ${c.local}`}{c.resultado && ` · ${c.resultado}`}</span></li>))}</ul>;
}
const Bloco = ({ titulo, children }: { titulo: string; children: ReactNode }) => <Cartao titulo={titulo}>{children}</Cartao>;

export default function DetalheRelatorio() {
  const { id } = useParams<{ id: string }>();
  const [r, setR] = useState<Relatorio | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  useEffect(() => { api<Relatorio>(`/relatorios/${id}`).then(setR).catch((e) => setErro(e.message)); }, [id]);
  if (erro) return <Aviso>{erro}</Aviso>;
  if (!r?.conteudo) return <p className="text-suave" aria-busy="true">Carregando…</p>;
  const s = r.conteudo.secoes as Record<string, never>;
  const falhas = (s.falhas_integracao ?? []) as { codigo: string; nome: string; motivos: string[] }[];

  return (
    <div className="flex flex-col gap-5" data-relatorio-detalhe={r.tipo}>
      <div>
        <Link href="/painel/relatorios" className="text-sm text-dourado hover:underline">← Relatórios</Link>
        <h1 className="mt-1 font-serif text-2xl font-semibold sm:text-3xl">{r.titulo}</h1>
        <p className="text-sm text-suave">Gerado em {dataHora(r.gerado_em)} (previsto para {String(r.conteudo.horario_previsto ?? "—")}){r.conteudo.atrasado && " — gerado com atraso"}</p>
      </div>
      <Aviso tom={r.alerta ? "alerta" : "info"}>{r.resumo}</Aviso>
      {r.conteudo.avisos.map((a) => <Aviso key={a}>{a}</Aviso>)}
      {falhas.length > 0 && <Bloco titulo="Fontes comprometidas"><ul className="text-sm">{falhas.map((f) => <li key={f.codigo}><span className="font-medium">{f.nome}</span>: {f.motivos.join("; ")}</li>)}</ul></Bloco>}

      {r.tipo === "diario" ? (
        <div className="grid gap-5 lg:grid-cols-2">
          <Bloco titulo="Prazos que vencem hoje"><Prazos itens={s.prazos_hoje} vazio="Nenhum prazo vence hoje." /></Bloco>
          <Bloco titulo="Próximos 3 dias úteis"><Prazos itens={s.prazos_proximos} vazio="Nenhum prazo nos próximos dias úteis." /></Bloco>
          <Bloco titulo="Audiências do dia"><Comps itens={s.audiencias} vazio="Nenhuma audiência hoje." /></Bloco>
          <Bloco titulo="Reuniões e atendimentos"><Comps itens={s.reunioes} vazio="Nenhuma reunião hoje." /></Bloco>
          <Bloco titulo="Outros compromissos"><Comps itens={s.compromissos} vazio="Nada mais na agenda." /></Bloco>
          <Bloco titulo="Publicações">{(() => { const p = s.publicacoes as unknown as { novas_24h: number; pendentes: number }; return <p className="text-sm">{p.novas_24h} nova(s) nas últimas 24 h; {p.pendentes} por conferir. <Link href="/painel/publicacoes" className="text-dourado hover:underline">Abrir</Link></p>; })()}</Bloco>
          <Bloco titulo="Madrugada">{(() => { const m = s.madrugada as unknown as { sincronizacoes: number; falhas: number; itens_novos: number }; return <p className="text-sm">{m.sincronizacoes} sincronização(ões), {m.falhas} falha(s), {m.itens_novos} item(ns) novo(s).</p>; })()}</Bloco>
          <Bloco titulo="Conflitos de agenda">{(s.conflitos as unknown as { a: string; b: string; inicio: string }[]).length ? <ul className="text-sm">{(s.conflitos as unknown as { a: string; b: string; inicio: string }[]).map((c, i) => <li key={i}>{horaLocal(c.inicio)}: {c.a} × {c.b}</li>)}</ul> : <p className="text-sm text-suave">Sem conflitos.</p>}</Bloco>
          <Bloco titulo="Prioridades do dia">{(s.prioridades as unknown as { titulo: string; classe_rotulo: string; justificativa: string[]; link: string | null }[]).length ? <ul className="flex flex-col gap-1 text-sm">{(s.prioridades as unknown as { titulo: string; classe_rotulo: string; justificativa: string[]; link: string | null }[]).map((p, i) => <li key={i}><Selo tom="alerta">{p.classe_rotulo}</Selo> {p.link ? <Link href={p.link} className="hover:underline">{p.titulo}</Link> : p.titulo}<span className="text-xs text-suave"> — {p.justificativa.join("; ")}</span></li>)}</ul> : <p className="text-sm text-suave">Nada em atenção imediata ou alta.</p>}</Bloco>
          <Bloco titulo="Minutas em revisão"><p className="text-sm">{Number(s.minutas_em_revisao ?? 0)} aguardando o advogado. <Link href="/painel/minutas" className="text-dourado hover:underline">Abrir</Link></p></Bloco>
          {s.financeiro && <Bloco titulo="Financeiro">{(() => { const f = s.financeiro as unknown as Record<"receitas_vencidas" | "receitas_hoje" | "despesas_hoje_ou_vencidas", { quantidade: number; valor: string }>; return <ul className="text-sm"><li>Receitas vencidas: {f.receitas_vencidas.quantidade} ({reais(f.receitas_vencidas.valor)})</li><li>Receitas que vencem hoje: {f.receitas_hoje.quantidade} ({reais(f.receitas_hoje.valor)})</li><li>Despesas de hoje ou atrasadas: {f.despesas_hoje_ou_vencidas.quantidade} ({reais(f.despesas_hoje_ou_vencidas.valor)})</li><li><Link href="/painel/financeiro" className="text-dourado hover:underline">Abrir o financeiro</Link></li></ul>; })()}</Bloco>}
          {s.clientes_aguardando_retorno !== undefined && <Bloco titulo="Clientes aguardando retorno"><p className="text-sm">{Number(s.clientes_aguardando_retorno)} pedido(s) do portal sem resposta. <Link href="/painel/atendimentos" className="text-dourado hover:underline">Abrir</Link></p></Bloco>}
          {((s.modulos_futuros ?? []) as unknown as { rotulo: string; fase: number }[]).length > 0 && <Bloco titulo="Ainda não disponível"><ul className="text-sm text-suave">{(s.modulos_futuros as unknown as { rotulo: string; fase: number }[]).map((m) => <li key={m.rotulo}>{m.rotulo} (Fase {m.fase})</li>)}</ul></Bloco>}
        </div>
      ) : (
        <div className="grid gap-5 lg:grid-cols-2">
          <Bloco titulo="Prazos de hoje sem cumprimento registrado"><Prazos itens={s.prazos_hoje_sem_cumprimento} vazio="Todos os prazos de hoje têm cumprimento registrado." /></Bloco>
          <Bloco titulo="Prazos cumpridos hoje"><Prazos itens={s.prazos_cumpridos} vazio="Nenhum prazo cumprido hoje." /></Bloco>
          <Bloco titulo="Audiências sem resultado registrado"><Comps itens={s.audiencias_sem_resultado} vazio="Nenhuma." /></Bloco>
          <Bloco titulo="Realizados"><Comps itens={s.realizados} vazio="Nenhum compromisso marcado como realizado." /></Bloco>
          <Bloco titulo="Movimento do dia"><p className="text-sm">{String(s.publicacoes_conferidas)} publicação(ões) conferida(s); {String(s.atencao_imediata_em_aberto)} item(ns) em atenção imediata ainda abertos.</p></Bloco>
          {(() => { const a = s.amanha as unknown as { data: string; prazos: PzR[]; agenda: CpR[] }; return (
            <Bloco titulo={`Próximo dia útil (${dataCurta(a.data)})`}><Prazos itens={a.prazos} vazio="Nenhum prazo." /><div className="mt-2"><Comps itens={a.agenda} vazio="Agenda livre." /></div></Bloco>); })()}
        </div>
      )}
      <Cartao titulo="Entrega">
        <ul className="text-sm">{r.entregas.map((e) => <li key={e.canal}><span className="font-medium capitalize">{e.canal}</span>: {ESTADO[e.situacao] ?? e.situacao}{e.destinatarios != null && ` (${e.destinatarios} pessoa(s))`}{e.observacao && <span className="text-xs text-suave"> — {e.observacao}</span>}</li>)}</ul>
      </Cartao>
    </div>
  );
}
