"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Cliente, Pagina } from "@/lib/tipos";

/** Escolha de cliente por nome ou CPF/CNPJ (o documento é comparado no servidor sem ser exibido). */
export function BuscaCliente({ id, rotulo = "Cliente", aoEscolher }: { id: string; rotulo?: string; aoEscolher: (c: Cliente | null) => void }) {
  const [q, setQ] = useState("");
  const [lista, setLista] = useState<Cliente[]>([]);
  const [escolhido, setEscolhido] = useState<Cliente | null>(null);

  useEffect(() => {
    if (escolhido || q.trim().length < 2) return;
    const t = setTimeout(() => {
      api<Pagina<Cliente>>(`/clientes?por_pagina=8&q=${encodeURIComponent(q.trim())}`).then((r) => setLista(r.itens)).catch(() => setLista([]));
    }, 250);
    return () => clearTimeout(t);
  }, [q, escolhido]);

  if (escolhido) {
    return (
      <div className="flex flex-col gap-1">
        <span className="text-sm font-medium">{rotulo}</span>
        <div className="flex items-center justify-between gap-2 rounded-md border border-dourado/50 bg-dourado/5 px-3 py-2 text-sm">
          <span>{escolhido.nome} <span className="text-xs text-suave">{escolhido.documento ?? "sem documento"}</span></span>
          <button type="button" className="text-xs text-dourado hover:underline" onClick={() => { setEscolhido(null); setQ(""); aoEscolher(null); }}>Trocar</button>
        </div>
      </div>
    );
  }
  const mostrar = q.trim().length >= 2;
  return (
    <div className="relative flex flex-col gap-1">
      <label htmlFor={id} className="text-sm font-medium">{rotulo}</label>
      <input id={id} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nome ou CPF/CNPJ" autoComplete="off"
        className="rounded-md border border-borda bg-superficie px-3 py-2 text-sm" />
      {mostrar && (
        <ul className="absolute left-0 right-0 top-full z-20 mt-1 max-h-60 overflow-auto rounded-md border border-borda bg-superficie shadow-lg" role="listbox" aria-label="Clientes encontrados">
          {lista.length === 0 && <li className="px-3 py-2 text-sm text-suave">Nenhum cliente encontrado.</li>}
          {lista.map((c) => (
            <li key={c.id} role="option" aria-selected={false}>
              <button type="button" className="flex w-full justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-superficie-2"
                onClick={() => { setEscolhido(c); setLista([]); aoEscolher(c); }}>
                <span>{c.nome}</span><span className="text-xs text-suave">{c.documento ?? c.tipo}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
