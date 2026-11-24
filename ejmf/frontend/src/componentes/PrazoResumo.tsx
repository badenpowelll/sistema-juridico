"use client";
import Link from "next/link";
import { Selo } from "@/componentes/ui";
import { dataCurta, diasRestantes, SITUACAO_PRAZO } from "@/lib/rotulos";
import type { Calculo, Prazo } from "@/lib/tipos";

/** Linha de prazo: vencimento, situação e o aviso explícito quando não está confirmado. */
export function PrazoResumo({ pz, mostrarProcesso = true }: { pz: Prazo; mostrarProcesso?: boolean }) {
  const [rot, tom] = SITUACAO_PRAZO[pz.situacao] ?? [pz.situacao, "neutro"];
  const urgente = pz.dias_restantes != null && pz.dias_restantes <= 1 && !["concluido"].includes(pz.situacao);
  return (
    <div className="flex flex-wrap items-start justify-between gap-3" data-prazo={pz.id} data-situacao={pz.situacao}>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <Selo tom={tom}>{rot}</Selo>
          {pz.simulado && <Selo tom="alerta">Simulado</Selo>}
          {pz.regra && !pz.regra.homologada && <Selo tom="alerta">Regra não homologada</Selo>}
          {mostrarProcesso && pz.processo && <Link href={`/painel/processos/${pz.processo_id}`} className="font-mono text-xs text-dourado hover:underline">{pz.processo.numero}</Link>}
        </div>
        <Link href={`/painel/prazos/${pz.id}`} className="mt-1 block text-sm hover:underline">{pz.descricao}</Link>
        {pz.vencimento_alternativo && pz.situacao !== "concluido" && (
          <p className="mt-1 text-xs text-alerta">Se a suspensão de expediente for confirmada, vence em {dataCurta(pz.vencimento_alternativo)}.</p>
        )}
      </div>
      <div className="text-right">
        <div className={`font-mono text-lg font-semibold ${urgente ? "text-perigo" : ""}`}>{dataCurta(pz.vencimento)}</div>
        <div className="text-xs text-suave">{pz.situacao === "concluido" ? "concluído" : diasRestantes(pz.dias_restantes)}</div>
        {!pz.confirmado && pz.situacao !== "concluido" && pz.vencimento && <div className="text-xs font-medium text-alerta">não confirmado</div>}
      </div>
    </div>
  );
}

/** Memória de cálculo do motor determinístico, com fundamentos e avisos. */
export function MemoriaCalculo({ c }: { c: Calculo }) {
  return (
    <div className="flex flex-col gap-3 text-sm">
      {c.avisos?.map((a) => <p key={a} role="note" className="rounded-md border border-alerta/40 bg-alerta/10 px-3 py-2 text-xs text-alerta">{a}</p>)}
      {c.memoria?.length > 0 && (
        <ol className="flex flex-col gap-1" aria-label="Memória de cálculo">
          {c.memoria.map((m, i) => (
            <li key={i} className="flex gap-3"><span className="w-24 shrink-0 font-mono text-xs text-suave">{dataCurta(m.data)}</span><span>{m.evento}</span></li>
          ))}
        </ol>
      )}
      {c.regra && <p className="text-xs text-suave">Regra: {c.regra.nome} (v{c.regra.versao}) — {c.regra.fundamento}</p>}
      {(c.dias_desconsiderados?.length ?? 0) > 0 && (
        <details className="text-xs"><summary className="cursor-pointer text-suave">Dias desconsiderados ({c.dias_desconsiderados!.length} além de {c.fins_de_semana_desconsiderados ?? 0} dia(s) de fim de semana)</summary>
          <ul className="mt-1 flex flex-col gap-0.5">{c.dias_desconsiderados!.map((d) => <li key={d.data + d.motivo}><span className="font-mono">{dataCurta(d.data)}</span> — {d.motivo}</li>)}</ul>
        </details>
      )}
    </div>
  );
}
