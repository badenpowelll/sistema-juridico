"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

type Resultado = { tipo: string; id: string; titulo: string; detalhe: string; origem: string; link: string };

/** Pesquisa em processos e clientes conforme as permissões. Atalho: tecla "/". */
export function PesquisaGlobal() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [res, setRes] = useState<Resultado[] | null>(null);
  const [ativo, setAtivo] = useState(0);
  const campo = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const atalho = (e: KeyboardEvent) => {
      const alvo = e.target as HTMLElement;
      if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(alvo.tagName)) { e.preventDefault(); campo.current?.focus(); }
    };
    window.addEventListener("keydown", atalho);
    return () => window.removeEventListener("keydown", atalho);
  }, []);

  useEffect(() => {
    if (q.trim().length < 2) return;
    const t = setTimeout(() => {
      api<{ resultados: Resultado[] }>(`/pesquisa?q=${encodeURIComponent(q.trim())}`).then((r) => { setRes(r.resultados); setAtivo(0); }).catch(() => setRes([]));
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  const visiveis = q.trim().length >= 2 ? res : null;
  function abrir(r: Resultado) { setQ(""); setRes(null); router.push(r.link); }

  return (
    <div className="relative w-full max-w-md" role="search">
      <label htmlFor="pesquisa-global" className="sr-only">Pesquisar processos e clientes</label>
      <input id="pesquisa-global" ref={campo} value={q} onChange={(e) => setQ(e.target.value)} autoComplete="off"
        placeholder="Pesquisar processo, cliente, CPF/CNPJ…  ( / )"
        role="combobox" aria-expanded={!!visiveis} aria-controls="pesquisa-resultados" aria-autocomplete="list"
        onKeyDown={(e) => {
          if (!visiveis?.length) { if (e.key === "Escape") setQ(""); return; }
          if (e.key === "ArrowDown") { e.preventDefault(); setAtivo((a) => Math.min(a + 1, visiveis.length - 1)); }
          if (e.key === "ArrowUp") { e.preventDefault(); setAtivo((a) => Math.max(a - 1, 0)); }
          if (e.key === "Enter") { e.preventDefault(); abrir(visiveis[ativo]); }
          if (e.key === "Escape") { setQ(""); setRes(null); }
        }}
        className="w-full rounded-md border border-borda bg-fundo px-3 py-1.5 text-sm placeholder:text-suave/70" />
      {visiveis && (
        <ul id="pesquisa-resultados" role="listbox" aria-label="Resultados da pesquisa"
          className="absolute left-0 right-0 top-full z-30 mt-1 max-h-96 overflow-auto rounded-md border border-borda bg-superficie shadow-lg">
          {visiveis.length === 0 && <li className="px-3 py-2 text-sm text-suave">Nada encontrado nas áreas que você pode consultar.</li>}
          {visiveis.map((r, i) => (
            <li key={`${r.tipo}-${r.id}`} role="option" aria-selected={i === ativo}>
              <Link href={r.link} onClick={() => { setQ(""); setRes(null); }}
                className={`flex items-start justify-between gap-3 px-3 py-2 text-sm ${i === ativo ? "bg-superficie-2" : ""}`}>
                <span className="min-w-0"><span className="block truncate font-medium">{r.titulo}</span>
                  <span className="block truncate text-xs text-suave">{r.detalhe}</span></span>
                <span className="shrink-0 text-xs text-dourado">{r.origem}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
