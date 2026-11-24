"use client";
import { dolares, reais } from "@/lib/financeiro";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Aviso, Cartao, Selo } from "@/componentes/ui";
import { api, dataHora } from "@/lib/api";
import { ROTULO_PRIORIDADE, TOM_ESTADO } from "@/lib/rotulos";

type Item = { id: string; titulo: string; prioridade: string; justificativa: string; acao: string | null; origem: string };
type Indicador = { codigo: string; rotulo: string; valor: number | null; disponivel: boolean; fase?: number; link?: string; formato?: "moeda" | "dolar"; texto?: string };
const formatar = (i: Indicador) => i.texto ? i.texto : i.formato === "moeda" ? reais(i.valor ?? 0) : i.formato === "dolar" ? dolares(i.valor ?? 0) : (i.valor ?? 0).toLocaleString("pt-BR");
type IntegracaoResumo = { codigo: string; nome: string; estado: string; estado_rotulo: string; simulado: boolean; critica: boolean; ultimo_sucesso_em: string | null; ultimo_erro: string | null };
type Painel = { gerado_em: string; saudacao: string; atencao_agora: Item[]; indicadores: Indicador[]; integracoes: IntegracaoResumo[] };

export default function CentralDeComando() {
  const [p, setP] = useState<Painel | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  useEffect(() => { api<Painel>("/painel").then(setP).catch((e) => setErro(e.message)); }, []);
  if (erro) return <Aviso>{erro}</Aviso>;
  if (!p) return <p className="text-suave" aria-busy="true">Carregando a central…</p>;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-sm text-suave">{p.saudacao} · atualizado em {dataHora(p.gerado_em)}</p>
        <h1 className="font-serif text-3xl font-semibold">Central de comando</h1>
      </div>

      <Cartao titulo={<span>O que exige minha atenção agora</span>} acao={<Selo tom="dourado">{p.atencao_agora.length} item(ns)</Selo>}>
        {p.atencao_agora.length === 0 ? (
          <p className="text-suave">Nenhuma pendência identificada pelas regras atuais.</p>
        ) : (
          <ol className="flex flex-col divide-y divide-borda" aria-label="Pendências por prioridade">
            {p.atencao_agora.map((i) => {
              const [rotulo, tom] = ROTULO_PRIORIDADE[i.prioridade] ?? [i.prioridade, "neutro"];
              return (
                <li key={i.id} className="flex flex-col gap-1 py-3 sm:flex-row sm:items-start sm:justify-between sm:gap-6" data-item={i.id}>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2"><Selo tom={tom}>{rotulo}</Selo><span className="font-medium">{i.titulo}</span></div>
                    <p className="mt-1 text-sm text-suave"><span className="font-medium text-texto">Por quê: </span>{i.justificativa}</p>
                  </div>
                  {i.acao && <Link href={i.acao} className="shrink-0 text-sm text-dourado underline-offset-4 hover:underline">Resolver</Link>}
                </li>
              );
            })}
          </ol>
        )}
      </Cartao>

      <section aria-label="Indicadores" className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {p.indicadores.map((i) => (
          <div key={i.codigo} className="rounded-xl border border-borda bg-superficie p-4" data-indicador={i.codigo}>
            <div className="text-xs text-suave">{i.rotulo}</div>
            {i.disponivel ? (
              i.link ? <Link href={i.link} className={`mt-1 block font-serif font-semibold tabular-nums hover:text-dourado ${i.texto ? "text-lg" : i.formato ? "text-2xl" : "text-3xl"}`}>{formatar(i)}</Link>
                : <div className={`mt-1 font-serif font-semibold tabular-nums ${i.formato ? "text-2xl" : "text-3xl"}`}>{formatar(i)}</div>
            ) : (
              <div className="mt-2 text-xs text-suave">Módulo previsto para a Fase {i.fase}</div>
            )}
          </div>
        ))}
      </section>

      <Cartao titulo="Fontes e integrações" acao={<Link href="/painel/integracoes" className="text-sm text-dourado hover:underline">Detalhes</Link>}>
        <ul className="grid gap-2 sm:grid-cols-2">
          {p.integracoes.map((i) => (
            <li key={i.codigo} className="flex items-center justify-between gap-3 rounded-md border border-borda px-3 py-2">
              <span className="text-sm">{i.nome}{i.simulado && <Selo tom="alerta">Simulado</Selo>}</span>
              <Selo tom={TOM_ESTADO[i.estado]}>{i.estado_rotulo}</Selo>
            </li>
          ))}
        </ul>
      </Cartao>
    </div>
  );
}
