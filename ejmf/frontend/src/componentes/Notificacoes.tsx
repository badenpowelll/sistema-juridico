"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api, dataHora, enviar } from "@/lib/api";
import type { Notificacao } from "@/lib/tipos";

export function Notificacoes() {
  const [dados, setDados] = useState<{ nao_lidas: number; itens: Notificacao[] } | null>(null);
  const [aberto, setAberto] = useState(false);
  const [versao, setVersao] = useState(0);
  useEffect(() => {
    const ler = () => api<{ nao_lidas: number; itens: Notificacao[] }>("/notificacoes").then(setDados).catch(() => {});
    ler();
    const t = setInterval(ler, 60_000);
    return () => clearInterval(t);
  }, [versao]);
  const lida = (n: Notificacao) => { if (!n.lida_em) enviar(`/notificacoes/${n.id}/lida`, "POST").then(() => setVersao((v) => v + 1)).catch(() => {}); setAberto(false); };
  const n = dados?.nao_lidas ?? 0;
  return (
    <div className="relative">
      <button aria-expanded={aberto} aria-controls="notificacoes" onClick={() => setAberto(!aberto)} data-notificacoes={n}
        className="relative rounded-md border border-borda px-3 py-1 text-sm hover:bg-superficie-2" aria-label={`Notificações${n ? `, ${n} não lida(s)` : ""}`}>
        Avisos{n > 0 && <span className="ml-1 rounded-full bg-perigo px-1.5 text-xs font-semibold text-white">{n > 99 ? "99+" : n}</span>}
      </button>
      {aberto && (
        <div id="notificacoes" className="absolute right-0 z-20 mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-xl border border-borda bg-superficie p-2 shadow-lg">
          <div className="flex items-center justify-between px-2 py-1">
            <span className="text-sm font-medium">Notificações</span>
            {n > 0 && <button className="text-xs text-dourado hover:underline" onClick={() => enviar("/notificacoes/lidas", "POST").then(() => setVersao((v) => v + 1))}>Marcar todas como lidas</button>}
          </div>
          {!dados?.itens.length ? <p className="px-2 py-3 text-sm text-suave">Nenhuma notificação.</p> : (
            <ul className="max-h-96 overflow-auto">
              {dados.itens.map((x) => (
                <li key={x.id} className={`rounded-md px-2 py-2 text-sm ${x.lida_em ? "text-suave" : ""}`}>
                  {x.link ? <Link href={x.link} onClick={() => lida(x)} className="font-medium hover:underline">{x.titulo}</Link>
                    : <button onClick={() => lida(x)} className="text-left font-medium">{x.titulo}</button>}
                  {x.texto && <p className="line-clamp-2 text-xs text-suave">{x.texto}</p>}
                  <p className="text-xs text-suave">{dataHora(x.criado_em)}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
