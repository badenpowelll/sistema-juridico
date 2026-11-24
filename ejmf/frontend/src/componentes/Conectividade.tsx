"use client";
import { useEffect, useSyncExternalStore } from "react";
import { registrarSW } from "@/lib/pwa";

const assinar = (cb: () => void) => { window.addEventListener("online", cb); window.addEventListener("offline", cb); return () => { window.removeEventListener("online", cb); window.removeEventListener("offline", cb); }; };

/** Registra o service worker (só no build de produção) e avisa quando a conexão cai. */
export function Conectividade() {
  const online = useSyncExternalStore(assinar, () => navigator.onLine, () => true);
  useEffect(() => { if (process.env.NODE_ENV === "production") registrarSW(); }, []);
  if (online) return null;
  return (
    <div role="status" className="border-b border-alerta/40 bg-alerta/10 px-4 py-2 text-center text-sm font-medium text-texto">
      Sem conexão. Nada é guardado neste aparelho: o que você estava vendo volta quando a internet voltar.
    </div>
  );
}
