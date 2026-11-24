"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Pagina, ProcessoResumo } from "@/lib/tipos";

/** Escolha de processo por número (com ou sem máscara, ou trecho), parte ou cliente. */
export function BuscaProcesso({ id, rotulo = "Processo", aoEscolher }: { id: string; rotulo?: string; aoEscolher: (p: ProcessoResumo | null) => void }) {
  const [q, setQ] = useState("");
  const [lista, setLista] = useState<ProcessoResumo[]>([]);
  const [escolhido, setEscolhido] = useState<ProcessoResumo | null>(null);

  useEffect(() => {
    if (escolhido || q.trim().length < 3) return;
    const t = setTimeout(() => {
      api<Pagina<ProcessoResumo>>(`/processos?por_pagina=8&q=${encodeURIComponent(q.trim())}`).then((r) => setLista(r.itens)).catch(() => setLista([]));
    }, 250);
    return () => clearTimeout(t);
  }, [q, escolhido]);

  if (escolhido) {
    return (
      <div className="flex flex-col gap-1">
        <span className="text-sm font-medium">{rotulo}</span>
        <div className="flex items-center justify-between gap-2 rounded-md border border-dourado/50 bg-dourado/5 px-3 py-2 text-sm">
          <span className="font-mono">{escolhido.numero} <span className="font-sans text-xs text-suave">{escolhido.classe ?? ""}</span></span>
          <button type="button" className="text-xs text-dourado hover:underline" onClick={() => { setEscolhido(null); setQ(""); aoEscolher(null); }}>Trocar</button>
        </div>
      </div>
    );
  }
  return (
    <div className="relative flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium">{rotulo}</label>
      <input id={id} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Número, parte ou cliente" autoComplete="off"
        className="rounded-md border border-borda bg-superficie px-3 py-2 text-sm" />
      {q.trim().length >= 3 && (
        <ul className="absolute left-0 right-0 top-full z-20 mt-1 max-h-60 overflow-auto rounded-md border border-borda bg-superficie shadow-lg" role="listbox" aria-label="Processos encontrados">
          {lista.length === 0 && <li className="px-3 py-2 text-sm text-suave">Nenhum processo encontrado.</li>}
          {lista.map((p) => (
            <li key={p.id} role="option" aria-selected={false}>
              <button type="button" className="flex w-full justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-superficie-2"
                onClick={() => { setEscolhido(p); setLista([]); aoEscolher(p); }}>
                <span className="font-mono">{p.numero}</span><span className="text-xs text-suave">{p.clientes.map((c) => c.nome).join(", ")}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
