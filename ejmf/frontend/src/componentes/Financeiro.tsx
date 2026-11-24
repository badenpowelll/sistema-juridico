"use client";
import Link from "next/link";
import { Selo, Vazio } from "@/componentes/ui";
import { dia, reais, tomSituacao, type Lancamento } from "@/lib/financeiro";

export const SUBMENU: [string, string][] = [["/painel/financeiro", "Visão geral"], ["/painel/financeiro/lancamentos", "Lançamentos"],
  ["/painel/financeiro/contratos", "Contratos de honorários"], ["/painel/financeiro/conciliacao", "Conciliação"],
  ["/painel/financeiro/relatorios", "Fluxo de caixa e rentabilidade"]];

export function Submenu({ atual }: { atual: string }) {
  return (
    <nav aria-label="Seções do financeiro" className="flex flex-wrap gap-1 text-sm">
      {SUBMENU.map(([h, r]) => <Link key={h} href={h} aria-current={h === atual ? "page" : undefined}
        className={`rounded-full border px-3 py-1 ${h === atual ? "border-dourado bg-dourado/10 font-medium" : "border-borda hover:bg-superficie-2"}`}>{r}</Link>)}
    </nav>
  );
}

export function ListaLancamentos({ itens, rotulo, vazio = "Nada por aqui." }: { itens: Lancamento[]; rotulo: string; vazio?: string }) {
  if (!itens.length) return <Vazio>{vazio}</Vazio>;
  return (
    <ul className="divide-y divide-borda" aria-label={rotulo}>
      {itens.map((l) => (
        <li key={l.id} className="flex flex-col gap-1 py-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <Link href={`/painel/financeiro/lancamentos/${l.id}`} className="font-medium hover:underline">{l.descricao}</Link>
            <p className="text-xs text-suave">{l.categoria}{l.cliente ? ` · ${l.cliente}` : ""}{l.processo ? ` · ${l.processo}` : ""} · vence {dia(l.vencimento)}
              {l.liquidado_em ? ` · ${l.tipo === "receita" ? "recebido" : "pago"} em ${dia(l.liquidado_em)}` : ""}</p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`font-medium tabular-nums ${l.tipo === "despesa" ? "text-perigo" : ""}`}>{l.tipo === "despesa" ? "− " : ""}{reais(l.valor)}</span>
            <Selo tom={tomSituacao(l)}>{l.vencido ? `Vencido há ${l.dias_atraso} dia(s)` : l.situacao_rotulo}</Selo>
          </div>
        </li>
      ))}
    </ul>
  );
}

