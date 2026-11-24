"use client";
import { useSyncExternalStore } from "react";

type Tema = "sistema" | "claro" | "escuro";
const ouvintes = new Set<() => void>();

function lerTema(): Tema {
  const t = document.documentElement.dataset.tema;
  return t === "claro" || t === "escuro" ? t : "sistema";
}

function assinar(cb: () => void) {
  ouvintes.add(cb);
  return () => ouvintes.delete(cb);
}

export function SeletorTema({ claro = false }: { claro?: boolean }) {
  const tema = useSyncExternalStore(assinar, lerTema, () => "sistema" as Tema);
  function escolher(t: Tema) {
    try {
      if (t === "sistema") { localStorage.removeItem("ejmf-tema"); delete document.documentElement.dataset.tema; }
      else { localStorage.setItem("ejmf-tema", t); document.documentElement.dataset.tema = t; }
    } catch {
      if (t !== "sistema") document.documentElement.dataset.tema = t;
    }
    ouvintes.forEach((cb) => cb());
  }
  return (
    <label className={`text-xs flex items-center gap-2 ${claro ? "text-white/80" : "text-suave"}`}>
      Tema
      <select value={tema} onChange={(e) => escolher(e.target.value as Tema)}
        className="rounded-md border border-borda bg-superficie text-texto px-2 py-1 text-xs" aria-label="Tema de cores">
        <option value="sistema">Do sistema</option>
        <option value="claro">Claro</option>
        <option value="escuro">Escuro</option>
      </select>
    </label>
  );
}
